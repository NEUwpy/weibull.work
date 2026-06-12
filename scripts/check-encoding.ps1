$ErrorActionPreference = 'Stop'

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot '..')
$utf8 = New-Object System.Text.UTF8Encoding($false, $true)

$textExtensions = @(
  '.css', '.html', '.js', '.json', '.jsx', '.md', '.mjs',
  '.py', '.ps1', '.ts', '.tsx', '.txt', '.yaml', '.yml'
)

$excludedDirs = @(
  '\.git\',
  '\.next\',
  '\_archive\',
  '\node_modules\'
)

$invalidUtf8 = New-Object System.Collections.Generic.List[string]
$replacementChars = New-Object System.Collections.Generic.List[string]

Get-ChildItem -LiteralPath $repoRoot -Recurse -File | ForEach-Object {
  $path = $_.FullName
  $relative = $path.Substring($repoRoot.Path.Length + 1)

  foreach ($dir in $excludedDirs) {
    if ($path -like "*$dir*") {
      return
    }
  }

  if ($textExtensions -notcontains $_.Extension.ToLowerInvariant()) {
    return
  }

  $bytes = [System.IO.File]::ReadAllBytes($path)
  try {
    $text = $utf8.GetString($bytes)
  } catch {
    $invalidUtf8.Add($relative)
    return
  }

  if ($text.Contains([char]0xFFFD)) {
    $replacementChars.Add($relative)
  }
}

if ($invalidUtf8.Count -eq 0 -and $replacementChars.Count -eq 0) {
  Write-Host 'Encoding check passed: all scanned text files are valid UTF-8 and contain no replacement characters.'
  exit 0
}

if ($invalidUtf8.Count -gt 0) {
  Write-Host 'Invalid UTF-8 files:'
  $invalidUtf8 | Sort-Object | ForEach-Object { Write-Host "  $_" }
}

if ($replacementChars.Count -gt 0) {
  Write-Host 'Files containing U+FFFD replacement characters:'
  $replacementChars | Sort-Object | ForEach-Object { Write-Host "  $_" }
}

exit 1
