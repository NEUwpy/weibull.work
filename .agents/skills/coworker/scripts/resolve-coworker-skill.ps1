[CmdletBinding()]
param(
    [string]$GlobalPath = (Join-Path $env:USERPROFILE ".agents\skills\coworker"),

    [Parameter(Mandatory = $true)]
    [string]$ProjectPath
)

$ErrorActionPreference = "Stop"

function Get-CopyInfo {
    param([Parameter(Mandatory)][string]$Path, [Parameter(Mandatory)][string]$Kind)

    if (-not (Test-Path -LiteralPath $Path -PathType Container)) {
        return [pscustomobject]@{
            kind = $Kind
            path = $Path
            exists = $false
            version = [version]"0.0.0"
            version_text = "0.0.0"
            updated_at = [DateTimeOffset]::MinValue
            updated_at_text = $null
            fingerprint = $null
        }
    }

    $resolved = (Resolve-Path -LiteralPath $Path).Path
    $versionFile = Join-Path $resolved "VERSION.json"
    if (Test-Path -LiteralPath $versionFile) {
        $metadata = Get-Content -LiteralPath $versionFile -Raw | ConvertFrom-Json
        $versionText = [string]$metadata.version
        $updatedText = [string]$metadata.updated_at
        try {
            $parsedVersion = [version]$versionText
            $parsedUpdated = [DateTimeOffset]::Parse($updatedText)
        }
        catch {
            throw "Invalid VERSION.json in ${resolved}: $($_.Exception.Message)"
        }
    }
    else {
        $versionText = "0.0.0"
        $updatedText = $null
        $parsedVersion = [version]"0.0.0"
        $parsedUpdated = [DateTimeOffset]::MinValue
    }

    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        $lines = Get-ChildItem -LiteralPath $resolved -Recurse -File |
            Where-Object {
                $_.FullName -notmatch "[\\/](?:__pycache__|\.pytest_cache)[\\/]"
            } |
            Sort-Object { $_.FullName.Substring($resolved.Length + 1) } |
            ForEach-Object {
                $relative = $_.FullName.Substring($resolved.Length + 1).Replace("\", "/")
                $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $_.FullName).Hash.ToLowerInvariant()
                "$relative`t$hash"
            }
        $payload = [System.Text.Encoding]::UTF8.GetBytes(($lines -join "`n"))
        $fingerprint = ([BitConverter]::ToString($sha.ComputeHash($payload))).Replace("-", "").ToLowerInvariant()
    }
    finally {
        $sha.Dispose()
    }

    return [pscustomobject]@{
        kind = $Kind
        path = $resolved
        exists = $true
        version = $parsedVersion
        version_text = $versionText
        updated_at = $parsedUpdated
        updated_at_text = $updatedText
        fingerprint = $fingerprint
    }
}

$global = Get-CopyInfo $GlobalPath "global"
$project = Get-CopyInfo $ProjectPath "project"

if (-not $global.exists -and -not $project.exists) {
    throw "Neither global nor project coworker skill exists."
}

if (-not $global.exists) {
    $selected = $project
    $reason = "global_missing"
}
elseif (-not $project.exists) {
    $selected = $global
    $reason = "project_missing"
}
elseif ($global.version -gt $project.version) {
    $selected = $global
    $reason = "newer_version"
}
elseif ($project.version -gt $global.version) {
    $selected = $project
    $reason = "newer_version"
}
elseif ($global.updated_at -gt $project.updated_at) {
    $selected = $global
    $reason = "newer_updated_at"
}
elseif ($project.updated_at -gt $global.updated_at) {
    $selected = $project
    $reason = "newer_updated_at"
}
elseif ($global.fingerprint -ne $project.fingerprint) {
    [pscustomobject]@{
        event = "VERSION_CONFLICT"
        global = [pscustomobject]@{
            path = $global.path
            version = $global.version_text
            updated_at = $global.updated_at_text
            fingerprint = $global.fingerprint
        }
        project = [pscustomobject]@{
            path = $project.path
            version = $project.version_text
            updated_at = $project.updated_at_text
            fingerprint = $project.fingerprint
        }
    } | ConvertTo-Json -Depth 5
    exit 2
}
else {
    $selected = $global
    $reason = "identical"
}

[pscustomobject]@{
    event = "selected"
    selected_kind = $selected.kind
    selected_path = $selected.path
    version = $selected.version_text
    updated_at = $selected.updated_at_text
    fingerprint = $selected.fingerprint
    reason = $reason
    synchronization_needed = (
        $global.exists -and $project.exists -and
        $global.fingerprint -ne $project.fingerprint
    )
} | ConvertTo-Json -Depth 5
