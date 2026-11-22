param([string]$Branch)
$ErrorActionPreference = 'Stop'
$env:GIT_TERMINAL_PROMPT = '0'
if (-not $Branch) {
    $Branch = (& git branch --show-current).Trim()
    if ($LASTEXITCODE -ne 0 -or -not $Branch) { throw 'Select a local branch before pushing.' }
}
$failed = @()
foreach ($target in @('origin', 'gitlab')) {
    Write-Output "Pushing $Branch to $target"
    & git -c credential.interactive=false push $target $Branch
    if ($LASTEXITCODE -ne 0) { $failed += $target }
}
if ($failed.Count) {
    Write-Output ('Push incomplete: ' + ($failed -join ', ') + '. Check credentials/network and retry this script.')
    exit 1
}
Write-Output 'Both repositories are up to date.'
