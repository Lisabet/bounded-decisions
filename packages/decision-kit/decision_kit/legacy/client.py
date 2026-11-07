"""Small, standard-library-only PlusVibe decisions client.

The client deliberately makes one request per call. It never retries and only
uses a local cache when the caller explicitly supplies a cache path.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import tempfile
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any, Callable, Mapping


ENDPOINT = "https://plusvibeapi.ru/v1/decisions"
MODEL = "typesafe/jev-1.13"
DEFAULT_PRICE_RUB_PER_MILLION = 7.4
_TOLERANCE = 0.02


@dataclass(frozen=True)
class DecisionResult:
    answer: dict[str, str]
    answers: dict[str, dict[str, Any]]
    requested_model: str
    returned_model: str
    model_version: str | None
    elapsed_seconds: float
    usage: dict[str, int]
    billed_cost_rub: float | None
    estimated_cost_rub: float
    request_sha256: str
    cache_hit: bool = False
    new_call_cost_rub: float | None = None
    new_call_elapsed_seconds: float | None = None
    billing_header_invalid: bool = False


class DecisionClientError(Exception):
    """Safe structured API or validation error; never contains response text."""

    def __init__(self, error_class: str, *, status: int | None = None,
                 billed_cost_rub: float | None = None, billing_header_invalid: bool = False):
        self.error_class = error_class
        self.status = status
        self.billed_cost_rub = billed_cost_rub
        self.billing_header_invalid = billing_header_invalid
        label = f"{error_class}" + (f" (HTTP {status})" if status is not None else "")
        super().__init__(label)


Transport = Callable[[str, Mapping[str, str], bytes, float], tuple[int, Mapping[str, str], bytes]]


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req: Any, fp: Any, code: int, msg: str,
                         headers: Any, newurl: str) -> None:
        return None


def _stdlib_transport(url: str, headers: Mapping[str, str], body: bytes,
                      timeout: float) -> tuple[int, Mapping[str, str], bytes]:
    opener = urllib.request.build_opener(_NoRedirect)
    request = urllib.request.Request(url, data=body, headers=dict(headers), method="POST")
    try:
        with opener.open(request, timeout=timeout) as response:
            try:
                return response.status, response.headers, response.read()
            except Exception as exc:
                kind = "timeout" if isinstance(exc, TimeoutError) else "transport_error"
                raise DecisionClientError(kind, status=response.status,
                    billed_cost_rub=_cost_header(response.headers),
                    billing_header_invalid=_invalid_cost_header(response.headers)) from None
    except urllib.error.HTTPError as exc:
        # A 3xx response is returned as a status for safe structured handling;
        # the Authorization header is never forwarded to another host.
        return exc.code, exc.headers, b""


def _finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _cost_header(headers: Mapping[str, str]) -> float | None:
    raw = next((v for k, v in headers.items() if k.lower() == "x-pv-cost-rub"), None)
    if raw is None:
        return None
    if not isinstance(raw, str) or not re.fullmatch(r"[+-]?(?:[0-9]+\.?[0-9]*|\.[0-9]+)(?:[eE][+-]?[0-9]+)?", raw.strip()):
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) and value >= 0 else None


def _invalid_cost_header(headers: Mapping[str, str]) -> bool:
    present = any(k.lower() == "x-pv-cost-rub" for k in headers)
    return present and _cost_header(headers) is None


def _canonical(value: Any) -> bytes:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                          allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, UnicodeError) as exc:
        raise DecisionClientError("invalid_request_json") from exc


def _validate_payload(state: Any, questions: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    if not ((isinstance(state, str) and state.strip())
            or (isinstance(state, (Mapping, list)) and len(state) > 0)):
        raise DecisionClientError("invalid_state")
    if not isinstance(questions, Mapping) or not 1 <= len(questions) <= 20:
        raise DecisionClientError("invalid_question_count")
    qcopy: dict[str, Any] = {}
    for qid, item in questions.items():
        if not isinstance(qid, str) or not qid.strip() or not isinstance(item, Mapping):
            raise DecisionClientError("invalid_question")
        if set(item) not in ({"instructions", "criteria"}, {"type", "instructions", "criteria"}):
            raise DecisionClientError("invalid_question_fields")
        if "type" in item and item["type"] != "choice":
            raise DecisionClientError("invalid_question_type")
        instructions, criteria = item["instructions"], item["criteria"]
        if not isinstance(instructions, str) or not instructions.strip():
            raise DecisionClientError("invalid_instructions")
        if not isinstance(criteria, Mapping) or len(criteria) < 2:
            raise DecisionClientError("invalid_criteria")
        if any(not isinstance(k, str) or not k.strip() or not isinstance(v, str) or not v.strip()
               for k, v in criteria.items()):
            raise DecisionClientError("invalid_criteria")
        qcopy[qid] = {"type": "choice", "instructions": instructions,
                      "criteria": dict(criteria)}
    payload = {"state": state, "questions": qcopy}
    _canonical(payload)
    return payload


def _validate_response(raw: bytes, model: str, questions: Mapping[str, Any],
                       cost: float | None, elapsed: float, request_hash: str,
                       price: float) -> DecisionResult:
    try:
        data = json.loads(raw.decode("utf-8"), parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except (UnicodeError, ValueError, json.JSONDecodeError) as exc:
        raise DecisionClientError("malformed_json", billed_cost_rub=cost) from exc
    if not isinstance(data, dict) or data.get("model") != model:
        raise DecisionClientError("model_mismatch", billed_cost_rub=cost)
    answers = data.get("answers")
    if not isinstance(answers, dict) or set(answers) != set(questions):
        raise DecisionClientError("answer_keys_mismatch", billed_cost_rub=cost)
    clean: dict[str, str] = {}
    clean_answers: dict[str, dict[str, Any]] = {}
    for qid, response in answers.items():
        if not isinstance(response, dict):
            raise DecisionClientError("invalid_answer", billed_cost_rub=cost)
        if "type" in response and response["type"] != "choice":
            raise DecisionClientError("invalid_answer_type", billed_cost_rub=cost)
        if "type" in response and response["type"] != "choice":
            raise DecisionClientError("invalid_answer_type", billed_cost_rub=cost)
        criteria = questions[qid]["criteria"]
        option = response.get("choice")
        if not isinstance(option, str) or option not in criteria:
            raise DecisionClientError("invalid_choice", billed_cost_rub=cost)
        probabilities = response.get("probabilities")
        if "probabilities" in response:
            if not isinstance(probabilities, dict) or set(probabilities) != set(criteria):
                raise DecisionClientError("invalid_probabilities", billed_cost_rub=cost)
            vals = list(probabilities.values())
            if (any(not _finite_number(v) or v < 0 or v > 1 for v in vals)
                    or abs(sum(vals) - 1.0) > _TOLERANCE):
                raise DecisionClientError("invalid_probabilities", billed_cost_rub=cost)
        confidence = response.get("confidence")
        if "confidence" in response and (not _finite_number(confidence) or not 0 <= confidence <= 1):
            raise DecisionClientError("invalid_confidence", billed_cost_rub=cost)
        clean[qid] = option
        clean_answers[qid] = {"type": "choice", "choice": option}
        if probabilities is not None:
            clean_answers[qid]["probabilities"] = dict(probabilities)
        if confidence is not None:
            clean_answers[qid]["confidence"] = confidence
    usage = data.get("usage")
    if not isinstance(usage, dict):
        raise DecisionClientError("invalid_usage", billed_cost_rub=cost)
    input_tokens, output_tokens = usage.get("input_tokens"), usage.get("output_tokens")
    if any(not isinstance(v, int) or isinstance(v, bool) or v < 0 or v > 9007199254740991
           for v in (input_tokens, output_tokens)):
        raise DecisionClientError("invalid_usage", billed_cost_rub=cost)
    version = data.get("model_version")
    if version is not None and not isinstance(version, str):
        raise DecisionClientError("invalid_model_version", billed_cost_rub=cost)
    estimated = input_tokens * price / 1_000_000
    return DecisionResult(clean, clean_answers, model, data["model"], version, elapsed,
                          {"input_tokens": input_tokens, "output_tokens": output_tokens},
                          cost, estimated, request_hash, False, cost, elapsed)


class DecisionClient:
    def __init__(self, *, api_key: str | None = None, endpoint: str = ENDPOINT,
                 model: str = MODEL, timeout: float = 60.0,
                 price_rub_per_million: float = DEFAULT_PRICE_RUB_PER_MILLION,
                 transport: Transport | None = None,
                 cache_path: str | os.PathLike[str] | None = None):
        key = api_key if api_key is not None else os.environ.get("PLUSVIBE_API_KEY")
        if not isinstance(key, str) or not key.strip():
            raise DecisionClientError("missing_api_key")
        if not isinstance(endpoint, str) or not endpoint.startswith("https://"):
            raise DecisionClientError("https_required")
        if not isinstance(model, str) or not model:
            raise DecisionClientError("invalid_model")
        if not _finite_number(timeout) or timeout <= 0:
            raise DecisionClientError("invalid_timeout")
        if not _finite_number(price_rub_per_million) or price_rub_per_million < 0:
            raise DecisionClientError("invalid_price")
        self._key = key
        self.endpoint, self.model = endpoint, model
        self.timeout, self.price = float(timeout), float(price_rub_per_million)
        self.transport = transport or _stdlib_transport
        self.cache_path = Path(cache_path) if cache_path is not None else None

    def decide(self, state: Any, questions: Mapping[str, Mapping[str, Any]]) -> DecisionResult:
        payload = _validate_payload(state, questions)
        payload["model"] = self.model
        body = _canonical(payload)
        request_hash = hashlib.sha256(body).hexdigest()
        cache_key = hashlib.sha256(_canonical({"endpoint": self.endpoint, "model": self.model,
                                                "payload": payload})).hexdigest()
        if self.cache_path is not None:
            cached = self._read_cache(cache_key, payload, request_hash)
            if cached is not None:
                return DecisionResult(**{**asdict(cached), "cache_hit": True,
                                         "new_call_cost_rub": 0.0,
                                         "new_call_elapsed_seconds": 0.0})
        headers = {"Authorization": f"Bearer {self._key}", "Content-Type": "application/json",
                   "Accept": "application/json"}
        started = time.perf_counter()
        try:
            status, response_headers, response_body = self.transport(
                self.endpoint, headers, body, self.timeout)
        except DecisionClientError:
            raise
        except (TimeoutError, urllib.error.URLError) as exc:
            reason = getattr(exc, "reason", None)
            kind = "timeout" if isinstance(exc, TimeoutError) or isinstance(reason, TimeoutError) else "transport_error"
            raise DecisionClientError(kind) from None
        except Exception as exc:
            # Keep injected/custom transport exception content out of the public error.
            raise DecisionClientError("transport_error") from None
        elapsed = time.perf_counter() - started
        cost = _cost_header(response_headers)
        invalid_header = _invalid_cost_header(response_headers)
        if status < 200 or status >= 300:
            raise DecisionClientError("http_error", status=status, billed_cost_rub=cost,
                                      billing_header_invalid=invalid_header)
        try:
            result = _validate_response(response_body, self.model, payload["questions"], cost,
                                        elapsed, request_hash, self.price)
        except DecisionClientError as exc:
            raise DecisionClientError(exc.error_class, status=status, billed_cost_rub=cost,
                                      billing_header_invalid=invalid_header) from None
        result = replace(result, billing_header_invalid=invalid_header)
        if self.cache_path is not None:
            self._write_cache(cache_key, result)
        return result

    def _read_cache(self, cache_key: str, payload: Mapping[str, Any],
                    request_hash: str) -> DecisionResult | None:
        try:
            root = json.loads(self.cache_path.read_text(encoding="utf-8"))
            entry = root.get(cache_key) if isinstance(root, dict) else None
            if not isinstance(entry, dict) or entry.get("request_sha256") != request_hash:
                return None
            expected = payload["questions"]
            answers = entry.get("answer")
            usage = entry.get("usage")
            if (not isinstance(answers, dict) or set(answers) != set(expected)
                    or any(v not in expected[k]["criteria"] for k, v in answers.items())
                    or not isinstance(usage, dict)
                    or any(not isinstance(usage.get(k), int) or isinstance(usage.get(k), bool)
                           or usage[k] < 0 for k in ("input_tokens", "output_tokens"))
                    or entry.get("requested_model") != self.model
                    or entry.get("returned_model") != self.model
                    or not isinstance(entry.get("answers"), dict)
                    or set(entry["answers"]) != set(expected)
                    or not _finite_number(entry.get("elapsed_seconds"))
                    or not _finite_number(entry.get("estimated_cost_rub"))
                    or (entry.get("billed_cost_rub") is not None and not _finite_number(entry["billed_cost_rub"]))):
                return None
            packed_answers: dict[str, Any] = {}
            for qid, answer in entry["answers"].items():
                if not isinstance(answer, dict) or answer.get("type") != "choice":
                    return None
                packed_answers[qid] = {k: v for k, v in answer.items() if k != "type"}
            raw = _canonical({"model": entry["returned_model"],
                              "model_version": entry.get("model_version"),
                              "answers": packed_answers, "usage": usage})
            validated = _validate_response(raw, self.model, expected,
                                           entry.get("billed_cost_rub"),
                                           entry["elapsed_seconds"], request_hash, self.price)
            if validated.answer != answers:
                return None
            return replace(validated, estimated_cost_rub=entry["estimated_cost_rub"])
        except (OSError, ValueError, TypeError, KeyError):
            return None

    def _write_cache(self, cache_key: str, result: DecisionResult) -> None:
        path = self.cache_path
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            root = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
            if not isinstance(root, dict):
                root = {}
        except (OSError, ValueError):
            root = {}
        root[cache_key] = asdict(result)
        content = _canonical(root)
        fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp_name, path)
        finally:
            try:
                os.unlink(temp_name)
            except FileNotFoundError:
                pass
