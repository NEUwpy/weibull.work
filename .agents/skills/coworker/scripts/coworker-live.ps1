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
        default { throw "Action '$Action' is not implemented yet" }
    }
}
catch {
    [Console]::Error.WriteLine($_.Exception.Message)
    exit 1
}
