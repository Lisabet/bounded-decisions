param([string]$RepoRoot = (Split-Path $PSScriptRoot -Parent))
$ErrorActionPreference = 'Stop'
$contractRoot = Join-Path $RepoRoot 'packages/decision-contract'
$matrix = Get-Content (Join-Path $contractRoot 'fixtures.json') -Raw -Encoding utf8 | ConvertFrom-Json -AsHashtable
function Test-Record($Value) {
    Test-Json -Json ($Value | ConvertTo-Json -Depth 40 -Compress) -SchemaFile (Join-Path $contractRoot 'record.schema.json') -ErrorAction SilentlyContinue
}
foreach ($case in $matrix.cases) {
    if (-not (Test-Record $case.expected)) { throw "Invalid expected record: $($case.id)" }
    if (-not (Test-Json -Json ($case.request | ConvertTo-Json -Depth 40 -Compress) -SchemaFile (Join-Path $contractRoot 'request.schema.json') -ErrorAction SilentlyContinue)) { throw "Invalid shared request: $($case.id)" }
}
$negativeCount = 0
foreach ($kind in @('observed-null','unknown-charge','ok-error','pending-certain','error-answers','reused-without-id')) {
    $copy = $matrix.cases[0].expected | ConvertTo-Json -Depth 40 | ConvertFrom-Json -AsHashtable
    switch ($kind) {
        'observed-null' {$copy.billing = $null}
        'unknown-charge' {$copy.billing_state = 'unknown'}
        'ok-error' {$copy.error = @{code='http';http_status=503}}
        'pending-certain' {$copy.status = 'pending'; $copy.answers = @{}; $copy.usage = $null; $copy.returned_model = $null; $copy.error = @{code='transport';http_status=$null}}
        'error-answers' {$copy.status = 'error';$copy.error = @{code='http';http_status=503}}
        'reused-without-id' {$copy.receipt.reused = $true; $copy.receipt.id = $null}
    }
    if (Test-Record $copy) { throw "Contradiction passed schema: $kind" }
    $negativeCount++
}
$neutral = Get-Content (Join-Path $contractRoot 'universal-fixtures.json') -Raw -Encoding utf8 | ConvertFrom-Json -AsHashtable
foreach ($case in $neutral.cases) {
    foreach ($pair in @(@('task','task.schema.json'),@('selection','selection.schema.json'),@('policy','policy.schema.json'),@('record','record.schema.json'))) {
        if (-not (Test-Json -Json ($case[$pair[0]] | ConvertTo-Json -Depth 50 -Compress) -SchemaFile (Join-Path $contractRoot $pair[1]) -ErrorAction SilentlyContinue)) { throw "Invalid neutral fixture $($case.id): $($pair[0])" }
    }
    $outcome = @{task_version=$case.task.task_version;task_id=$case.task.task_id;rules_version=$case.task.rules_version;record=$case.record;evaluation=$case.expected_evaluation}
    if (-not (Test-Json -Json ($outcome | ConvertTo-Json -Depth 60 -Compress) -SchemaFile (Join-Path $contractRoot 'outcome.schema.json') -ErrorAction SilentlyContinue)) { throw "Invalid neutral outcome $($case.id)" }
}
foreach ($bundle in @('packages/decision-kit/decision_kit/contract_data','packages/jev-decision-core/contract','packages/bounded-decision-core/contract')) {
    foreach ($name in @('request.schema.json','record.schema.json','task.schema.json','selection.schema.json','policy.schema.json','outcome.schema.json','fixtures.json','universal-fixtures.json','README.md')) {
        $masterHash = (Get-FileHash -LiteralPath (Join-Path $contractRoot $name) -Algorithm SHA256).Hash
        $bundleHash = (Get-FileHash -LiteralPath (Join-Path (Join-Path $RepoRoot $bundle) $name) -Algorithm SHA256).Hash
        if ($masterHash -ne $bundleHash) { throw "Contract bundle drift: $bundle/$name" }
    }
}
@{status='pass'; shared_cases=$matrix.cases.Count; schema_contradictions_rejected=$negativeCount; neutral_cases=$neutral.cases.Count; bundled_copies=27} | ConvertTo-Json -Compress
