export type TaskQuestion = {
    type: 'choice';
    instructions: string;
    criteria: Record<string, string>;
    abstain_choice?: string;
};
export type DecisionTask = {
    task_version: 'bounded-task/1';
    task_id: string;
    rules_version: string;
    state: unknown;
    questions: Record<string, TaskQuestion>;
};
export type Selection = {
    provider: string;
    model: string;
    returned_model_policy?: 'exact' | 'any_nonempty';
};
export type DecisionRecord = {
    contract_version: 'bounded-decisions/1';
    provider: string;
    requested_model: string;
    returned_model: string | null;
    status: 'ok' | 'error' | 'pending';
    answers: Record<string, unknown>;
    usage: {
        input_tokens?: number;
        output_tokens?: number;
    } | null;
    billing: {
        amount: number;
        currency: string;
        source: string | null;
    } | null;
    billing_state: 'observed' | 'unknown' | 'invalid';
    estimate: {
        amount: number;
        currency: string;
        source: string | null;
    } | null;
    receipt: {
        id: string | null;
        reused: boolean;
    };
    uncertain: boolean;
    error: {
        code: 'route' | 'input_limit' | 'body_limit' | 'http' | 'invalid_response' | 'timeout' | 'transport';
        http_status: number | null;
    } | null;
};
export type DecisionAdapter = {
    validateSelection?(selection: Selection): void;
    decide(task: DecisionTask, selection: Selection, context: {
        receiptId?: string;
        reused?: boolean;
    }): Promise<DecisionRecord> | DecisionRecord;
};
export type Policy = {
    require_confidence?: boolean;
    require_probabilities?: boolean;
    require_usage?: boolean;
    minimum_confidence?: number;
    bypass_confidence_choices?: Record<string, string[]>;
    expected_choices?: Record<string, string>;
};
export type Evaluation = {
    task_version: 'bounded-task/1';
    task_id: string;
    rules_version: string;
    record: DecisionRecord;
    evaluation: {
        status: 'accepted' | 'review' | 'rejected';
        issues: string[];
        quality: null | {
            matched: boolean;
            questions: Record<string, boolean>;
        };
    };
};
const obj = (v: unknown): v is Record<string, any> => v !== null && typeof v === 'object' && !Array.isArray(v);
const nonempty = (v: unknown): v is string => typeof v === 'string' && !!v.trim();
function jsonSafe(v: unknown, seen = new Set<object>()): boolean { if (v === null || typeof v === 'string' || typeof v === 'boolean')
    return true; if (typeof v === 'number')
    return Number.isFinite(v) && (!Number.isInteger(v) || Number.isSafeInteger(v)); if (typeof v !== 'object')
    return false; if (seen.has(v))
    return false; seen.add(v); const ok = Array.isArray(v) ? Object.keys(v).length === v.length && Array.from({ length: v.length }, (_, i) => Object.hasOwn(v, i) && jsonSafe(v[i], seen)).every(Boolean) : ((Object.getPrototypeOf(v) === Object.prototype || Object.getPrototypeOf(v) === null) && Reflect.ownKeys(v).every(k => typeof k === 'string') && Object.entries(v).every(([, x]) => jsonSafe(x, seen))); seen.delete(v); return ok; }
function exactKeys(v: Record<string, unknown>, keys: string[]) { return Object.keys(v).every(k => keys.includes(k)); }
export function validateTask(task: unknown): asserts task is DecisionTask { if (!obj(task) || !jsonSafe(task) || !exactKeys(task, ['task_version', 'task_id', 'rules_version', 'state', 'questions']) || task.task_version !== 'bounded-task/1' || !nonempty(task.task_id) || !nonempty(task.rules_version) || !jsonSafe(task.state) || !(nonempty(task.state) || Array.isArray(task.state) && task.state.length > 0 || obj(task.state) && Object.keys(task.state).length > 0) || !obj(task.questions))
    throw new TypeError('invalid_task'); const qs = Object.entries(task.questions); if (qs.length < 1 || qs.length > 20)
    throw new TypeError('invalid_task'); for (const [id, q] of qs) {
    if (!nonempty(id) || !obj(q) || !exactKeys(q, ['type', 'instructions', 'criteria', ...(Object.hasOwn(q, 'abstain_choice') ? ['abstain_choice'] : [])]) || q.type !== 'choice' || !nonempty(q.instructions) || !obj(q.criteria))
        throw new TypeError('invalid_task');
    const cs = Object.entries(q.criteria);
    if (cs.length < 2 || cs.some(([k, v]) => !nonempty(k) || !nonempty(v)))
        throw new TypeError('invalid_task');
    if (q.abstain_choice !== undefined && (!nonempty(q.abstain_choice) || !Object.hasOwn(q.criteria, q.abstain_choice)))
        throw new TypeError('invalid_task');
} }
function validatePolicy(task: DecisionTask, selection: Selection, policy: Policy, context: unknown) { if (!obj(selection) || !exactKeys(selection, ['provider', 'model', ...(Object.hasOwn(selection, 'returned_model_policy') ? ['returned_model_policy'] : [])]) || !nonempty(selection.provider) || !nonempty(selection.model) || selection.returned_model_policy !== undefined && !['exact', 'any_nonempty'].includes(selection.returned_model_policy))
    throw new TypeError('invalid_selection'); const p = policy as Record<string, unknown>; if (!obj(policy) || !exactKeys(policy, ['require_confidence', 'require_probabilities', 'require_usage', 'minimum_confidence', 'bypass_confidence_choices', 'expected_choices']) || ['require_confidence', 'require_probabilities', 'require_usage'].some(k => p[k] !== undefined && typeof p[k] !== 'boolean') || policy.minimum_confidence !== undefined && (!Number.isFinite(policy.minimum_confidence) || policy.minimum_confidence < 0 || policy.minimum_confidence > 1))
    throw new TypeError('invalid_policy'); for (const key of ['expected_choices', 'bypass_confidence_choices'] as const) {
    const map = policy[key];
    if (map !== undefined) {
        if (!obj(map))
            throw new TypeError('invalid_policy');
        for (const [qid, c] of Object.entries(map)) {
            if (!Object.hasOwn(task.questions, qid))
                throw new TypeError('invalid_policy');
            const q = task.questions[qid];
            if (key === 'expected_choices' ? (!nonempty(c) || !Object.hasOwn(q.criteria, c as string)) : (!Array.isArray(c) || new Set(c).size !== c.length || (c as unknown[]).some(id => !nonempty(id) || !Object.hasOwn(q.criteria, id as string))))
                throw new TypeError('invalid_policy');
        }
    }
} if (context !== undefined && (!obj(context) || !exactKeys(context, ['receiptId', 'reused']) || context.receiptId !== undefined && !nonempty(context.receiptId) || context.reused !== undefined && typeof context.reused !== 'boolean' || context.reused === true && !nonempty(context.receiptId)))
    throw new TypeError('invalid_context'); }
function validMoney(v: any) { return v === null || obj(v) && exactKeys(v, ['amount', 'currency', 'source']) && Number.isFinite(v.amount) && v.amount >= 0 && nonempty(v.currency) && (v.source === null || nonempty(v.source)); }
export function evaluateRecord(task: DecisionTask, selection: Selection, record: unknown, policy: Policy = {}): Evaluation {
    validateTask(task);
    validatePolicy(task, selection, policy, {});
    if (!obj(record) || !exactKeys(record, ['contract_version', 'provider', 'requested_model', 'returned_model', 'status', 'answers', 'usage', 'billing', 'billing_state', 'estimate', 'receipt', 'uncertain', 'error']) || record.contract_version !== 'bounded-decisions/1' || record.provider !== selection.provider || record.requested_model !== selection.model || !['ok', 'error', 'pending'].includes(record.status) || !obj(record.answers) || !['observed', 'unknown', 'invalid'].includes(record.billing_state) || !validMoney(record.billing) || !validMoney(record.estimate) || !obj(record.receipt) || !exactKeys(record.receipt, ['id', 'reused']) || typeof record.receipt.reused !== 'boolean' || record.receipt.id !== null && !nonempty(record.receipt.id) || record.receipt.reused && !record.receipt.id || typeof record.uncertain !== 'boolean')
        throw new TypeError('invalid_record');
    const err = record.error;
    if (record.status === 'ok') {
        if (record.uncertain || err !== null || !nonempty(record.returned_model) || Object.keys(record.answers).length === 0)
            throw new TypeError('invalid_record');
    } else {
        if (record.returned_model !== null || Object.keys(record.answers).length !== 0 || record.usage !== null
            || !obj(err) || !exactKeys(err, ['code', 'http_status'])
            || !['route', 'input_limit', 'body_limit', 'http', 'invalid_response', 'timeout', 'transport'].includes(err.code)
            || (err.http_status !== null && (!Number.isInteger(err.http_status) || err.http_status < 100 || err.http_status > 599))
            || record.uncertain !== (record.status === 'pending'))
            throw new TypeError('invalid_record');
    }
    if (record.status === 'ok' && (selection.returned_model_policy === 'any_nonempty' ? !nonempty(record.returned_model) : record.returned_model !== selection.model))
        throw new TypeError('invalid_record');
    if (record.billing_state === 'observed' && (record.billing === null || !validMoney(record.billing)) || record.billing_state !== 'observed' && record.billing !== null)
        throw new TypeError('invalid_record');
    if (record.usage !== null && (!obj(record.usage) || !exactKeys(record.usage, ['input_tokens', 'output_tokens']) || Object.values(record.usage).some(n => !Number.isSafeInteger(n) || Number(n) < 0)))
        throw new TypeError('invalid_record');
    const issues: string[] = [];
    if (record.status === 'error')
        issues.push('operation_error');
    if (record.status === 'pending')
        issues.push('operation_pending');
    if (record.billing_state === 'unknown')
        issues.push('billing_unknown');
    if (record.billing_state === 'invalid')
        issues.push('billing_invalid');
    const qualityQuestions: Record<string, boolean> = {};
    if (record.status === 'ok' && !exactKeys(record.answers, Object.keys(task.questions)))
        throw new TypeError('invalid_record');
    for (const [qid, q] of Object.entries(task.questions)) {
        const a = record.answers[qid] as any;
        if (record.status === 'ok') {
            if (!obj(a) || !exactKeys(a, ['type', 'choice', ...(Object.hasOwn(a, 'confidence') ? ['confidence'] : []), ...(Object.hasOwn(a, 'probabilities') ? ['probabilities'] : [])]) || a.type !== 'choice' || !nonempty(a.choice) || !Object.hasOwn(q.criteria, a.choice) || a.confidence !== undefined && (!Number.isFinite(a.confidence) || a.confidence < 0 || a.confidence > 1) || a.probabilities !== undefined && (!obj(a.probabilities) || !exactKeys(a.probabilities, Object.keys(q.criteria)) || Object.keys(q.criteria).some(k => !Number.isFinite(a.probabilities[k]) || a.probabilities[k] < 0 || a.probabilities[k] > 1) || Math.abs(Object.values(a.probabilities).reduce((s: number, n: any) => s + n, 0) - 1) > 0.02))
                throw new TypeError('invalid_record');
            if ((policy.require_confidence || policy.minimum_confidence !== undefined) && !Object.hasOwn(a, 'confidence'))
                issues.push(`confidence_required:${qid}`);
            if (policy.require_probabilities && !Object.hasOwn(a, 'probabilities'))
                issues.push(`probabilities_required:${qid}`);
            if (policy.minimum_confidence !== undefined && a.confidence !== undefined && a.confidence < policy.minimum_confidence && !(policy.bypass_confidence_choices?.[qid] || []).includes(a.choice))
                issues.push(`confidence_below_minimum:${qid}`);
            if (q.abstain_choice === a.choice)
                issues.push(`abstained:${qid}`);
            if (policy.expected_choices && Object.hasOwn(policy.expected_choices, qid))
                Object.defineProperty(qualityQuestions, qid, { value: a.choice === policy.expected_choices[qid], enumerable: true, configurable: true, writable: true });
        }
    }
    if (record.status === 'ok' && policy.require_usage && (!record.usage || !Number.isSafeInteger(record.usage.input_tokens) || !Number.isSafeInteger(record.usage.output_tokens)))
        issues.push('usage_required');
    const quality = record.status === 'ok' && policy.expected_choices && Object.keys(policy.expected_choices).length ? { matched: Object.values(qualityQuestions).every(Boolean) && Object.keys(qualityQuestions).length === Object.keys(policy.expected_choices).length, questions: qualityQuestions } : null;
    return { task_version: task.task_version, task_id: task.task_id, rules_version: task.rules_version, record: record as DecisionRecord, evaluation: { status: record.status === 'error' ? 'rejected' : record.status === 'pending' || issues.length ? 'review' : 'accepted', issues, quality } };
}
function invalidRecord(selection: Selection, raw: unknown, context: {
    receiptId?: string;
    reused?: boolean;
}): DecisionRecord { const r = obj(raw) ? raw : {}; const billingValid = validMoney(r.billing) && r.billing !== null; const pending = r.status === 'pending'; return { contract_version: 'bounded-decisions/1', provider: selection.provider, requested_model: selection.model, returned_model: null, status: pending ? 'pending' : 'error', answers: {}, usage: null, billing: billingValid ? r.billing : null, billing_state: billingValid ? 'observed' : r.billing !== null ? 'invalid' : 'unknown', estimate: validMoney(r.estimate) ? r.estimate : null, receipt: { id: context.receiptId !== undefined ? context.receiptId : nonempty(r.receipt?.id) ? r.receipt.id : null, reused: context.reused !== undefined ? context.reused : r.receipt?.reused === true }, uncertain: pending, error: { code: 'invalid_response', http_status: Number.isInteger(r.error?.http_status) && r.error.http_status >= 100 && r.error.http_status <= 599 ? r.error.http_status : null } }; }
export async function executeTask(task: DecisionTask, selection: Selection, registry: Map<string, DecisionAdapter>, policy: Policy = {}, context: {
    receiptId?: string;
    reused?: boolean;
} = {}): Promise<Evaluation> { validateTask(task); validatePolicy(task, selection, policy, context); if (!(registry instanceof Map) || !registry.has(selection.provider))
    throw new TypeError('unknown_provider'); const adapter = registry.get(selection.provider)!; if (!adapter || typeof adapter.decide !== 'function')
    throw new TypeError('invalid_adapter'); const frozenTask = structuredClone(task), frozenSelection = structuredClone(selection), frozenPolicy = structuredClone(policy), frozenContext = structuredClone(context);
    if (adapter.validateSelection !== undefined) {
        if (typeof adapter.validateSelection !== 'function') throw new TypeError('invalid_adapter_preflight');
        adapter.validateSelection(structuredClone(frozenSelection));
    }
    let raw: unknown; try {
    raw = await adapter.decide(structuredClone(frozenTask), structuredClone(frozenSelection), structuredClone(frozenContext));
}
catch {
    return evaluateRecord(frozenTask, frozenSelection, { contract_version: 'bounded-decisions/1', provider: frozenSelection.provider, requested_model: frozenSelection.model, returned_model: null, status: 'pending', answers: {}, usage: null, billing: null, billing_state: 'unknown', estimate: null, receipt: { id: frozenContext.receiptId ?? null, reused: frozenContext.reused ?? false }, uncertain: true, error: { code: 'transport', http_status: null } }, frozenPolicy);
} try {
    const result = evaluateRecord(frozenTask, frozenSelection, raw, frozenPolicy);
    const r = result.record;
    if (frozenContext.receiptId !== undefined && r.receipt.id !== frozenContext.receiptId || r.receipt.reused !== (frozenContext.reused ?? false))
        return evaluateRecord(frozenTask, frozenSelection, invalidRecord(frozenSelection, raw, frozenContext), frozenPolicy);
    return result;
}
catch (error) {
    if (error instanceof TypeError && error.message === 'invalid_record')
        return evaluateRecord(frozenTask, frozenSelection, invalidRecord(frozenSelection, raw, frozenContext), frozenPolicy);
    throw error;
} }
