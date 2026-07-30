[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("init", "send", "wait", "status", "set-mode")]
    [string]$Action,

    [Parameter(Mandatory = $true)]
    [string]$Repo,

    [Parameter(Mandatory = $true)]
    [ValidatePattern("^[A-Za-z0-9._-]+$")]
    [string]$TaskId,

    [ValidateSet("codex", "opencode")]
    [string]$Role,

    [ValidateSet("task", "report", "revise", "approve", "block", "note")]
    [string]$Type = "note",

    [string]$BodyFile,

    [ValidateSet("auto", "manual", "cancel")]
    [string]$Mode,

    [ValidateRange(1, 3600)]
    [int]$TimeoutSeconds = 55,

    [ValidateRange(100, 10000)]
    [int]$PollMilliseconds = 500
)

$ErrorActionPreference = "Stop"

function Write-JsonAtomic {
    param([Parameter(Mandatory)]$Value, [Parameter(Mandatory)][string]$Path)
    $tmp = "$Path.tmp.$PID"
    $Value | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $tmp -Encoding utf8
    Move-Item -LiteralPath $tmp -Destination $Path -Force
}

function Write-TextAtomic {
    param([Parameter(Mandatory)][string]$Value, [Parameter(Mandatory)][string]$Path)
    $tmp = "$Path.tmp.$PID"
    Set-Content -LiteralPath $tmp -Value $Value -Encoding utf8
    Move-Item -LiteralPath $tmp -Destination $Path -Force
}

function Read-Control {
    param([Parameter(Mandatory)][string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        return [pscustomobject]@{ mode = "auto"; updated_at = $null }
    }
    return Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json
}

function Acquire-Lock {
    param([Parameter(Mandatory)][string]$Path)
    try {
        $stream = [System.IO.File]::Open(
            $Path,
            [System.IO.FileMode]::CreateNew,
            [System.IO.FileAccess]::Write,
            [System.IO.FileShare]::None
        )
        $bytes = [System.Text.Encoding]::UTF8.GetBytes(
            ([pscustomobject]@{
                pid = $PID
                created_at = [DateTimeOffset]::Now.ToString("o")
            } | ConvertTo-Json -Compress)
        )
        $stream.Write($bytes, 0, $bytes.Length)
        $stream.Flush()
        return $stream
    }
    catch {
        throw "Mailbox lock already exists or cannot be acquired: $Path"
    }
}

function Release-Lock {
    param($Stream, [Parameter(Mandatory)][string]$Path)
    if ($null -ne $Stream) {
        $Stream.Dispose()
    }
    if (Test-Path -LiteralPath $Path) {
        Remove-Item -LiteralPath $Path -Force
    }
}

function Get-NextMessageId {
    param([Parameter(Mandatory)][string]$Root)
    $max = 0
    Get-ChildItem -LiteralPath $Root -Recurse -File -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -match "^(\d{6})-" } |
        ForEach-Object {
            $value = [int]$Matches[1]
            if ($value -gt $max) { $max = $value }
        }
    return $max + 1
}

function Get-LatestOppositeId {
    param(
        [Parameter(Mandatory)][string]$Root,
        [Parameter(Mandatory)][string]$Sender
    )
    $opposite = if ($Sender -eq "codex") { "opencode" } else { "codex" }
    $match = Get-ChildItem -LiteralPath $Root -Recurse -File -ErrorAction SilentlyContinue |
        Where-Object {
            $_.Name -match "^(\d{6})-$opposite-" -and
            $_.Name -like "*.ready.md"
        } |
        Sort-Object Name -Descending |
        Select-Object -First 1
    if ($null -eq $match) { return $null }
    return [int]([regex]::Match($match.Name, "^(\d{6})-").Groups[1].Value)
}

function Update-Status {
    param(
        [Parameter(Mandatory)][string]$Root,
        [string]$LastEvent = "none",
        [string]$LastMessage = "none"
    )
    $control = Read-Control (Join-Path $Root "control.json")
    $toCodex = @(Get-ChildItem -LiteralPath (Join-Path $Root "to-codex") -Filter "*.ready.md" -File -ErrorAction SilentlyContinue).Count
    $toOpenCode = @(Get-ChildItem -LiteralPath (Join-Path $Root "to-opencode") -Filter "*.ready.md" -File -ErrorAction SilentlyContinue).Count
    $archiveCount = @(Get-ChildItem -LiteralPath (Join-Path $Root "archive") -Recurse -Filter "*.ready.md" -File -ErrorAction SilentlyContinue).Count
    $now = [DateTimeOffset]::Now.ToString("o")
    $state = [ordered]@{
        task_id = $TaskId
        mode = $control.mode
        updated_at = $now
        last_event = $LastEvent
        last_message = $LastMessage
        queued_to_codex = $toCodex
        queued_to_opencode = $toOpenCode
        archived_messages = $archiveCount
    }
    Write-JsonAtomic $state (Join-Path $Root "state.json")
    $status = @"
# Coworker Duplex Mailbox Status

- Task: $TaskId
- Mode: $($control.mode)
- Updated: $now
- Last event: $LastEvent
- Last message: $LastMessage
- Queued to Codex: $toCodex
- Queued to OpenCode: $toOpenCode
- Archived messages: $archiveCount
"@
    Write-TextAtomic $status (Join-Path $Root "STATUS.md")
}

$repoPath = (Resolve-Path -LiteralPath $Repo).Path
$runtimeRoot = Join-Path $repoPath "coworker\runtime\$TaskId"
$controlPath = Join-Path $runtimeRoot "control.json"

if ($Action -eq "init") {
    foreach ($path in @(
        $runtimeRoot,
        (Join-Path $runtimeRoot "to-codex"),
        (Join-Path $runtimeRoot "to-opencode"),
        (Join-Path $runtimeRoot "archive\to-codex"),
        (Join-Path $runtimeRoot "archive\to-opencode"),
        (Join-Path $runtimeRoot "logs")
    )) {
        New-Item -ItemType Directory -Path $path -Force | Out-Null
    }
    if (-not (Test-Path -LiteralPath $controlPath)) {
        Write-JsonAtomic ([ordered]@{
            mode = "auto"
            updated_at = [DateTimeOffset]::Now.ToString("o")
        }) $controlPath
    }
    if (-not (Test-Path -LiteralPath (Join-Path $runtimeRoot "TRANSCRIPT.md"))) {
        Write-TextAtomic "# Coworker Duplex Mailbox Transcript`n" (Join-Path $runtimeRoot "TRANSCRIPT.md")
    }
    Update-Status $runtimeRoot "initialized" "none"
    [pscustomobject]@{
        event = "initialized"
        task_id = $TaskId
        runtime_root = $runtimeRoot
    } | ConvertTo-Json -Compress
    exit 0
}

if (-not (Test-Path -LiteralPath $runtimeRoot)) {
    throw "Mailbox is not initialized: $runtimeRoot"
}

if ($Action -eq "set-mode") {
    if ([string]::IsNullOrWhiteSpace($Mode)) {
        throw "-Mode is required for set-mode"
    }
    Write-JsonAtomic ([ordered]@{
        mode = $Mode
        updated_at = [DateTimeOffset]::Now.ToString("o")
    }) $controlPath
    Update-Status $runtimeRoot "mode_changed" $Mode
    [pscustomobject]@{ event = "mode_changed"; mode = $Mode } |
        ConvertTo-Json -Compress
    exit 0
}

if ($Action -eq "status") {
    Update-Status $runtimeRoot "status_checked" "none"
    Get-Content -LiteralPath (Join-Path $runtimeRoot "state.json") -Raw
    exit 0
}

if ([string]::IsNullOrWhiteSpace($Role)) {
    throw "-Role is required for $Action"
}

if ($Action -eq "send") {
    if ([string]::IsNullOrWhiteSpace($BodyFile)) {
        throw "-BodyFile is required for send"
    }
    $bodyPath = (Resolve-Path -LiteralPath $BodyFile).Path
    $transportLockPath = Join-Path $runtimeRoot "transport.lock"
    $transportLock = $null
    try {
        $transportLock = Acquire-Lock $transportLockPath
        $recipient = if ($Role -eq "codex") { "opencode" } else { "codex" }
        $destination = Join-Path $runtimeRoot "to-$recipient"
        $messageId = Get-NextMessageId $runtimeRoot
        $replyTo = Get-LatestOppositeId $runtimeRoot $Role
        $timestamp = [DateTimeOffset]::Now.ToString("o")
        $body = Get-Content -LiteralPath $bodyPath -Raw
        $replyValue = if ($null -eq $replyTo) { "null" } else { "$replyTo" }
        $message = @"
---
task_id: $TaskId
message_id: $messageId
reply_to: $replyValue
from: $Role
to: $recipient
type: $Type
created_at: $timestamp
---

$body
"@
        $fileName = "{0:D6}-{1}-{2}.ready.md" -f $messageId, $Role, $Type
        Write-TextAtomic $message (Join-Path $destination $fileName)
        Add-Content -LiteralPath (Join-Path $runtimeRoot "TRANSCRIPT.md") `
            -Value "- $timestamp [$messageId] $Role -> $recipient ($Type): $fileName" `
            -Encoding utf8
        Update-Status $runtimeRoot "message_sent" $fileName
        [pscustomobject]@{
            event = "sent"
            message_id = $messageId
            recipient = $recipient
            path = (Join-Path $destination $fileName)
        } | ConvertTo-Json -Compress
    }
    finally {
        Release-Lock $transportLock $transportLockPath
    }
    exit 0
}

if ($Action -eq "wait") {
    $roleLockPath = Join-Path $runtimeRoot "$Role.lock"
    $roleLock = $null
    try {
        $roleLock = Acquire-Lock $roleLockPath
        $inbox = Join-Path $runtimeRoot "to-$Role"
        $archive = Join-Path $runtimeRoot "archive\to-$Role"
        $deadline = [DateTimeOffset]::Now.AddSeconds($TimeoutSeconds)
        while ([DateTimeOffset]::Now -lt $deadline) {
            $control = Read-Control $controlPath
            if ($control.mode -ne "auto") {
                Update-Status $runtimeRoot "control" $control.mode
                [pscustomobject]@{
                    event = "control"
                    mode = $control.mode
                } | ConvertTo-Json -Compress
                exit 0
            }
            $message = Get-ChildItem -LiteralPath $inbox -Filter "*.ready.md" -File |
                Sort-Object Name |
                Select-Object -First 1
            if ($null -ne $message) {
                $archivePath = Join-Path $archive $message.Name
                Move-Item -LiteralPath $message.FullName -Destination $archivePath
                $timestamp = [DateTimeOffset]::Now.ToString("o")
                Add-Content -LiteralPath (Join-Path $runtimeRoot "TRANSCRIPT.md") `
                    -Value "- $timestamp $Role consumed $($message.Name)" `
                    -Encoding utf8
                Update-Status $runtimeRoot "message_received" $message.Name
                [pscustomobject]@{
                    event = "message"
                    role = $Role
                    archive_path = $archivePath
                    file_name = $message.Name
                } | ConvertTo-Json -Compress
                exit 0
            }
            Start-Sleep -Milliseconds $PollMilliseconds
        }
        Update-Status $runtimeRoot "wait_timeout" "none"
        [pscustomobject]@{
            event = "timeout"
            role = $Role
            timeout_seconds = $TimeoutSeconds
        } | ConvertTo-Json -Compress
    }
    finally {
        Release-Lock $roleLock $roleLockPath
    }
    exit 0
}
