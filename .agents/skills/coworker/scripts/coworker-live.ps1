[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('preflight', 'start', 'resume', 'status', 'collect', 'cancel', 'worker')]
    [string]$Action,
    [Parameter(Mandatory = $true)]
    [string]$Repo,
    [Parameter(Mandatory = $true)]
    [AllowEmptyString()]
    [string]$TaskId,
    [string]$PromptFile,
    [string]$Plan,
    [string]$Handoff,
    [string]$Report,
    [string]$Review,
    [string]$ClaudeCommand,
    [ValidateRange(1, 99)]
    [int]$Round = 1,
    [ValidateSet('start', 'resume')]
    [string]$Mode = 'start'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Assert-TaskId {
    param([AllowEmptyString()][string]$Value)

    if ([string]::IsNullOrWhiteSpace($Value) -or $Value -notmatch '^[a-zA-Z0-9][a-zA-Z0-9._-]{0,79}$') {
        throw 'TaskId must match ^[a-zA-Z0-9][a-zA-Z0-9._-]{0,79}$'
    }
}

function Invoke-Git {
    param(
        [string]$RepoRoot,
        [string[]]$Arguments
    )

    $output = @(& git -C $RepoRoot @Arguments 2>$null)
    if ($LASTEXITCODE -ne 0) {
        throw "Git command failed: git -C $RepoRoot $($Arguments -join ' ')"
    }
    return $output
}

function Resolve-RepoPath {
    param([string]$Path)

    $resolved = (Resolve-Path -LiteralPath $Path -ErrorAction Stop).Path
    $topLevel = @(Invoke-Git -RepoRoot $resolved -Arguments @('rev-parse', '--show-toplevel'))
    if ($topLevel.Count -ne 1 -or [string]::IsNullOrWhiteSpace($topLevel[0])) {
        throw "$resolved is not a Git worktree"
    }
    return [System.IO.Path]::GetFullPath($topLevel[0])
}

function Resolve-RepoChild {
    param(
        [string]$RepoRoot,
        [string]$Path,
        [switch]$MustExist
    )

    if ([string]::IsNullOrWhiteSpace($Path)) {
        throw 'A required repository path was not provided'
    }
    $candidate = if ([System.IO.Path]::IsPathRooted($Path)) {
        [System.IO.Path]::GetFullPath($Path)
    }
    else {
        [System.IO.Path]::GetFullPath((Join-Path $RepoRoot $Path))
    }
    $rootPrefix = $RepoRoot.TrimEnd('\') + '\'
    if (-not $candidate.StartsWith($rootPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Path escapes the repository: $Path"
    }
    if ($MustExist -and -not (Test-Path -LiteralPath $candidate -PathType Leaf)) {
        throw "Required file does not exist: $candidate"
    }
    return $candidate
}

function Get-RuntimePaths {
    param(
        [string]$RepoRoot,
        [string]$Id
    )

    Assert-TaskId -Value $Id
    $taskRoot = [System.IO.Path]::GetFullPath((Join-Path $RepoRoot "coworker\runtime\$Id"))
    $runtimeRoot = [System.IO.Path]::GetFullPath((Join-Path $RepoRoot 'coworker\runtime'))
    $runtimePrefix = $runtimeRoot.TrimEnd('\') + '\'
    if (-not $taskRoot.StartsWith($runtimePrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw 'Resolved runtime directory escaped coworker/runtime'
    }
    return [ordered]@{
        root = $taskRoot
        state = Join-Path $taskRoot 'state.json'
        prompt = Join-Path $taskRoot 'prompt.txt'
        stdout = Join-Path $taskRoot 'stdout.json'
        stderr = Join-Path $taskRoot 'stderr.log'
        result = Join-Path $taskRoot 'result.json'
        heartbeat = Join-Path $taskRoot 'heartbeat.txt'
        lock = Join-Path $taskRoot 'controller.lock'
    }
}

function Write-Utf8File {
    param(
        [string]$Path,
        [AllowEmptyString()][string]$Content
    )

    $encoding = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($Path, $Content, $encoding)
}

function Write-StateAtomic {
    param(
        [string]$Path,
        [object]$State
    )

    $temporary = "$Path.$([Guid]::NewGuid().ToString('N')).tmp"
    try {
        Write-Utf8File -Path $temporary -Content ($State | ConvertTo-Json -Depth 10)
        Move-Item -LiteralPath $temporary -Destination $Path -Force
    }
    finally {
        if (Test-Path -LiteralPath $temporary) {
            Remove-Item -LiteralPath $temporary -Force
        }
    }
}

function Read-State {
    param([string]$Path)

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw 'No recorded live-loop state exists for this task'
    }
    try {
        return (Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json)
    }
    catch {
        throw "Recorded live-loop state is invalid: $Path"
    }
}

function Test-ProcessAlive {
    param([object]$PidValue)

    if ($null -eq $PidValue) { return $false }
    $parsed = 0
    if (-not [int]::TryParse([string]$PidValue, [ref]$parsed) -or $parsed -le 0) {
        return $false
    }
    return $null -ne (Get-Process -Id $parsed -ErrorAction SilentlyContinue)
}

function Enter-TaskLock {
    param([string]$Path)

    for ($attempt = 0; $attempt -lt 2; $attempt++) {
        try {
            $stream = [System.IO.File]::Open(
                $Path,
                [System.IO.FileMode]::CreateNew,
                [System.IO.FileAccess]::Write,
                [System.IO.FileShare]::None
            )
            try {
                $payload = [ordered]@{
                    pid = $PID
                    created_at = [DateTime]::UtcNow.ToString('o')
                } | ConvertTo-Json -Compress
                $bytes = (New-Object System.Text.UTF8Encoding($false)).GetBytes($payload)
                $stream.Write($bytes, 0, $bytes.Length)
            }
            finally {
                $stream.Dispose()
            }
            return
        }
        catch [System.IO.IOException] {
            $ownerPid = $null
            try {
                $lockState = Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json
                $ownerPid = $lockState.pid
            }
            catch {
                $ownerPid = $null
            }
            if (Test-ProcessAlive -PidValue $ownerPid) {
                throw "Controller lock is held by live PID $ownerPid"
            }
            Remove-Item -LiteralPath $Path -Force -ErrorAction Stop
        }
    }
    throw "Could not acquire controller lock: $Path"
}

function Exit-TaskLock {
    param([string]$Path)

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return }
    try {
        $lockState = Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json
        if ([int]$lockState.pid -eq $PID) {
            Remove-Item -LiteralPath $Path -Force
        }
    }
    catch {
        # Never remove a lock that cannot be proven to belong to this process.
    }
}

function Get-ClaudeExecutable {
    param([string]$Requested)

    if (-not [string]::IsNullOrWhiteSpace($Requested)) {
        $resolved = Resolve-Path -LiteralPath $Requested -ErrorAction Stop
        return $resolved.Path
    }
    $command = Get-Command claude -ErrorAction Stop
    return $command.Source
}

function Convert-StateToOutput {
    param(
        [object]$State,
        [bool]$WorkerAlive,
        [Nullable[double]]$HeartbeatAgeSeconds
    )

    $output = [ordered]@{}
    foreach ($property in $State.PSObject.Properties) {
        $output[$property.Name] = $property.Value
    }
    $output.worker_alive = $WorkerAlive
    $output.heartbeat_age_seconds = $HeartbeatAgeSeconds
    return ($output | ConvertTo-Json -Depth 10 -Compress)
}

function Start-WorkerHost {
    param(
        [string]$RepoRoot,
        [string]$Id,
        [object]$State,
        [System.Collections.IDictionary]$Paths
    )

    $hostExecutable = (Get-Command powershell.exe -ErrorAction Stop).Source
    $arguments = @(
        '-NoProfile',
        '-ExecutionPolicy', 'Bypass',
        '-File', ('"' + $PSCommandPath + '"'),
        '-Action', 'worker',
        '-Repo', ('"' + $RepoRoot + '"'),
        '-TaskId', ('"' + $Id + '"'),
        '-Mode', ([string]$State.mode)
    )
    $process = Start-Process -FilePath $hostExecutable -ArgumentList $arguments -WindowStyle Hidden -PassThru
    $State.worker_pid = $process.Id
    $State.updated_at = [DateTime]::UtcNow.ToString('o')
    Write-StateAtomic -Path $Paths.state -State $State
    return $process
}

function New-ExecutorPrompt {
    param([string]$Body)

    return @"
Role: executor

You are the Claude Code worker. Execute only the bounded assignment below.
Do not start or resume another coworker live loop. Do not issue APPROVE, REVISE,
or BLOCK. Preserve unrelated local changes, write the required report, and stop
for Codex Controller review.

$Body
"@
}

function Invoke-Start {
    param(
        [string]$RepoPath,
        [string]$Id
    )

    Assert-TaskId -Value $Id
    $repoRoot = Resolve-RepoPath -Path $RepoPath
    $paths = Get-RuntimePaths -RepoRoot $repoRoot -Id $Id
    New-Item -ItemType Directory -Path $paths.root -Force | Out-Null
    Enter-TaskLock -Path $paths.lock
    try {
        if (Test-Path -LiteralPath $paths.state) {
            $existing = Read-State -Path $paths.state
            if ($existing.state -in @('WORKER_STARTING', 'WORKER_RUNNING')) {
                throw "Task '$Id' already has a worker in state $($existing.state)"
            }
            throw "Task '$Id' already has recorded state; use resume or choose another TaskId"
        }

        $promptPath = Resolve-RepoChild -RepoRoot $repoRoot -Path $PromptFile -MustExist
        $planPath = Resolve-RepoChild -RepoRoot $repoRoot -Path $Plan -MustExist
        $handoffPath = Resolve-RepoChild -RepoRoot $repoRoot -Path $Handoff -MustExist
        $reportPath = Resolve-RepoChild -RepoRoot $repoRoot -Path $Report
        $reviewPath = Resolve-RepoChild -RepoRoot $repoRoot -Path $Review
        $claude = Get-ClaudeExecutable -Requested $ClaudeCommand

        $body = Get-Content -LiteralPath $promptPath -Raw
        Write-Utf8File -Path $paths.prompt -Content (New-ExecutorPrompt -Body $body)
        $now = [DateTime]::UtcNow.ToString('o')
        $state = [pscustomobject][ordered]@{
            schema_version = 1
            task_id = $Id
            repo = $repoRoot
            branch = (@(Invoke-Git -RepoRoot $repoRoot -Arguments @('branch', '--show-current')))[0]
            baseline_sha = (@(Invoke-Git -RepoRoot $repoRoot -Arguments @('rev-parse', 'HEAD')))[0]
            claude_session_id = $null
            claude_command = $claude
            worker_pid = $null
            round = 1
            mode = 'start'
            state = 'WORKER_STARTING'
            prompt_source_path = $promptPath
            prompt_path = $paths.prompt
            plan_path = $planPath
            handoff_path = $handoffPath
            report_path = $reportPath
            review_path = $reviewPath
            stdout_path = $paths.stdout
            stderr_path = $paths.stderr
            result_path = $paths.result
            heartbeat_path = $paths.heartbeat
            created_at = $now
            updated_at = $now
            started_at = $null
            finished_at = $null
            exit_code = $null
            last_error = $null
        }
        Write-StateAtomic -Path $paths.state -State $state
        $null = Start-WorkerHost -RepoRoot $repoRoot -Id $Id -State $state -Paths $paths
        Convert-StateToOutput -State $state -WorkerAlive $true -HeartbeatAgeSeconds $null
    }
    finally {
        Exit-TaskLock -Path $paths.lock
    }
}

function Invoke-Resume {
    param(
        [string]$RepoPath,
        [string]$Id
    )

    Assert-TaskId -Value $Id
    $repoRoot = Resolve-RepoPath -Path $RepoPath
    $paths = Get-RuntimePaths -RepoRoot $repoRoot -Id $Id
    Enter-TaskLock -Path $paths.lock
    try {
        $state = Read-State -Path $paths.state
        if ($state.state -ne 'AWAITING_CODEX_REVIEW') {
            throw "Task '$Id' cannot resume from state $($state.state)"
        }
        if ([string]::IsNullOrWhiteSpace([string]$state.claude_session_id)) {
            throw 'Cannot resume without a recorded Claude session ID'
        }
        $reviewCandidate = if ([string]::IsNullOrWhiteSpace($Review)) { [string]$state.review_path } else { $Review }
        $reviewPath = Resolve-RepoChild -RepoRoot $repoRoot -Path $reviewCandidate -MustExist
        $reviewBody = Get-Content -LiteralPath $reviewPath -Raw
        if ($reviewBody -notmatch '(?im)^\s*(Verdict:\s*)?(REVISE|BLOCK)\b') {
            throw 'Resume requires a Codex review containing REVISE or BLOCK'
        }
        if (-not [string]::IsNullOrWhiteSpace($ClaudeCommand)) {
            $state.claude_command = Get-ClaudeExecutable -Requested $ClaudeCommand
        }
        Write-Utf8File -Path $paths.prompt -Content (New-ExecutorPrompt -Body @"
Codex Controller review for round $($state.round):

$reviewBody

Revise the existing implementation in the same Claude session. Update the worker
report at: $($state.report_path)
"@)
        $state.round = [int]$state.round + 1
        $state.mode = 'resume'
        $state.state = 'WORKER_STARTING'
        $state.worker_pid = $null
        $state.review_path = $reviewPath
        $state.exit_code = $null
        $state.last_error = $null
        $state.finished_at = $null
        $state.updated_at = [DateTime]::UtcNow.ToString('o')
        Write-StateAtomic -Path $paths.state -State $state
        $null = Start-WorkerHost -RepoRoot $repoRoot -Id $Id -State $state -Paths $paths
        Convert-StateToOutput -State $state -WorkerAlive $true -HeartbeatAgeSeconds $null
    }
    finally {
        Exit-TaskLock -Path $paths.lock
    }
}

function Invoke-Worker {
    param(
        [string]$RepoPath,
        [string]$Id
    )

    $repoRoot = Resolve-RepoPath -Path $RepoPath
    $paths = Get-RuntimePaths -RepoRoot $repoRoot -Id $Id
    $state = $null
    for ($attempt = 0; $attempt -lt 50; $attempt++) {
        $state = Read-State -Path $paths.state
        if ($null -ne $state.worker_pid) { break }
        Start-Sleep -Milliseconds 100
    }
    if ($null -eq $state.worker_pid) {
        throw 'Worker host did not receive its recorded PID'
    }

    $state.state = 'WORKER_RUNNING'
    $state.started_at = [DateTime]::UtcNow.ToString('o')
    $state.updated_at = $state.started_at
    Write-Utf8File -Path $paths.heartbeat -Content $state.started_at
    Write-StateAtomic -Path $paths.state -State $state

    $exitCode = 1
    $parsedResult = $null
    $failure = $null
    try {
        $promptText = Get-Content -LiteralPath $paths.prompt -Raw
        $claudeArguments = if ($Mode -eq 'resume') {
            @('--resume', [string]$state.claude_session_id, '-p', '--output-format', 'json')
        }
        else {
            @('-p', '--output-format', 'json')
        }
        $rawLines = @($promptText | & $state.claude_command @claudeArguments 2> $paths.stderr)
        $exitCode = $LASTEXITCODE
        $rawText = $rawLines -join [Environment]::NewLine
        Write-Utf8File -Path $paths.stdout -Content $rawText
        if ($exitCode -ne 0) {
            throw "Claude exited with code $exitCode"
        }
        try {
            $parsedResult = $rawText | ConvertFrom-Json
        }
        catch {
            throw 'Claude output was not valid JSON'
        }
        if ($parsedResult.is_error -eq $true) {
            throw 'Claude returned is_error=true'
        }
        if ([string]::IsNullOrWhiteSpace([string]$parsedResult.session_id)) {
            throw 'Claude output did not include a session ID'
        }
        if ([string]::IsNullOrWhiteSpace([string]$state.claude_session_id)) {
            $state.claude_session_id = [string]$parsedResult.session_id
        }
        Write-Utf8File -Path $paths.result -Content ($parsedResult | ConvertTo-Json -Depth 10)
        $state.state = 'AWAITING_CODEX_REVIEW'
    }
    catch {
        $failure = $_.Exception.Message
        $state.state = 'PAUSED'
    }
    finally {
        $finished = [DateTime]::UtcNow.ToString('o')
        Write-Utf8File -Path $paths.heartbeat -Content $finished
        $state.exit_code = $exitCode
        $state.last_error = $failure
        $state.finished_at = $finished
        $state.updated_at = $finished
        Write-StateAtomic -Path $paths.state -State $state
    }
}

function Invoke-Status {
    param(
        [string]$RepoPath,
        [string]$Id
    )

    $repoRoot = Resolve-RepoPath -Path $RepoPath
    $paths = Get-RuntimePaths -RepoRoot $repoRoot -Id $Id
    $state = Read-State -Path $paths.state
    $alive = Test-ProcessAlive -PidValue $state.worker_pid
    $heartbeatAge = $null
    if (Test-Path -LiteralPath $paths.heartbeat -PathType Leaf) {
        $heartbeatAge = [Math]::Round(([DateTime]::UtcNow - (Get-Item -LiteralPath $paths.heartbeat).LastWriteTimeUtc).TotalSeconds, 3)
    }
    Convert-StateToOutput -State $state -WorkerAlive $alive -HeartbeatAgeSeconds $heartbeatAge
}

function Invoke-Collect {
    param(
        [string]$RepoPath,
        [string]$Id
    )

    $repoRoot = Resolve-RepoPath -Path $RepoPath
    $paths = Get-RuntimePaths -RepoRoot $repoRoot -Id $Id
    $state = Read-State -Path $paths.state
    if ($state.state -ne 'AWAITING_CODEX_REVIEW') {
        throw "Task '$Id' is not awaiting Codex review"
    }
    if ([string]::IsNullOrWhiteSpace([string]$state.claude_session_id)) {
        throw 'Worker result has no Claude session ID'
    }
    if (-not (Test-Path -LiteralPath $state.report_path -PathType Leaf)) {
        throw "Worker report does not exist: $($state.report_path)"
    }
    if (-not (Test-Path -LiteralPath $paths.result -PathType Leaf)) {
        throw 'Worker result JSON does not exist'
    }
    $resultObject = Get-Content -LiteralPath $paths.result -Raw | ConvertFrom-Json
    [ordered]@{
        task_id = $Id
        state = $state.state
        round = $state.round
        claude_session_id = $state.claude_session_id
        report_path = $state.report_path
        result = $resultObject.result
    } | ConvertTo-Json -Depth 10 -Compress
}

function Invoke-Cancel {
    param(
        [string]$RepoPath,
        [string]$Id
    )

    $repoRoot = Resolve-RepoPath -Path $RepoPath
    $paths = Get-RuntimePaths -RepoRoot $repoRoot -Id $Id
    $null = Read-State -Path $paths.state
    Enter-TaskLock -Path $paths.lock
    try {
        $state = Read-State -Path $paths.state
        if ($null -eq $state.worker_pid -or -not (Test-ProcessAlive -PidValue $state.worker_pid)) {
            throw 'Task has no live recorded worker PID to cancel'
        }
        $recordedPid = [int]$state.worker_pid
        Stop-Process -Id $recordedPid -Force -ErrorAction Stop
        $state.state = 'CANCELLED'
        $state.exit_code = -1
        $state.last_error = 'Cancelled by Codex Controller'
        $state.finished_at = [DateTime]::UtcNow.ToString('o')
        $state.updated_at = $state.finished_at
        Write-StateAtomic -Path $paths.state -State $state
        Convert-StateToOutput -State $state -WorkerAlive $false -HeartbeatAgeSeconds $null
    }
    finally {
        Exit-TaskLock -Path $paths.lock
    }
}

function Invoke-Preflight {
    param(
        [string]$RepoPath,
        [string]$Id
    )

    Assert-TaskId -Value $Id
    try {
        $repoRoot = Resolve-RepoPath -Path $RepoPath
    }
    catch {
        throw "$RepoPath is not a Git worktree"
    }

    $branch = @(Invoke-Git -RepoRoot $repoRoot -Arguments @('branch', '--show-current'))
    $head = @(Invoke-Git -RepoRoot $repoRoot -Arguments @('rev-parse', 'HEAD'))
    $dirty = @(Invoke-Git -RepoRoot $repoRoot -Arguments @('status', '--short'))

    [ordered]@{
        schema_version = 1
        task_id = $Id
        repo = $repoRoot
        state = 'PREFLIGHT'
        branch = if ($branch.Count -eq 1) { $branch[0] } else { '' }
        head = $head[0]
        dirty = $dirty
    } | ConvertTo-Json -Depth 5 -Compress
}

try {
    switch ($Action) {
        'preflight' { Invoke-Preflight -RepoPath $Repo -Id $TaskId }
        'start' { Invoke-Start -RepoPath $Repo -Id $TaskId }
        'resume' { Invoke-Resume -RepoPath $Repo -Id $TaskId }
        'status' { Invoke-Status -RepoPath $Repo -Id $TaskId }
        'collect' { Invoke-Collect -RepoPath $Repo -Id $TaskId }
        'cancel' { Invoke-Cancel -RepoPath $Repo -Id $TaskId }
        'worker' { Invoke-Worker -RepoPath $Repo -Id $TaskId }
    }
}
catch {
    [Console]::Error.WriteLine($_.Exception.Message)
    exit 1
}
