[CmdletBinding(SupportsShouldProcess)]
param(
    [string]$Root = '',
    [string[]]$IncludeSkills,
    [string[]]$ExcludeSkills = @(),
    [switch]$Check
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
# The worker's -X utf8 diagnostics must survive the wrapper's redirected console.
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

if ([string]::IsNullOrWhiteSpace($Root)) {
    $Root = Split-Path -Parent $PSScriptRoot
}
# Preflight reads only: no write-permission test and no traversal of skill contents.
$rootPath = Resolve-Path -LiteralPath $Root
if ($rootPath.Provider.Name -ne 'FileSystem' -or
    -not (Test-Path -LiteralPath $rootPath.Path -PathType Container)) {
    throw "Resource manifest root must be a filesystem directory: $Root"
}
$Root = $rootPath.ProviderPath
$entries = [System.IO.Directory]::EnumerateFileSystemEntries($Root).GetEnumerator()
try { $null = $entries.MoveNext() } finally { $entries.Dispose() }
$worker = Join-Path $PSScriptRoot 'resource_manifest.py'
$reader = [System.IO.File]::OpenRead($worker)
try { $null = $reader.ReadByte() } finally { $reader.Dispose() }

$pythonExe = if ($env:PAI_PYTHON -and (Test-Path $env:PAI_PYTHON)) {
    $env:PAI_PYTHON
} else {
    $cmd = Get-Command python -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($cmd) { $cmd.Source } else { $null }
}
if ($null -eq $pythonExe) {
    throw 'Python application is required to generate or validate resource manifests.'
}

$mode = if ($Check) { 'check' } else { 'generate' }
if (-not $Check -and -not $PSCmdlet.ShouldProcess($Root, 'Generate scoped resource manifests')) {
    $mode = 'check'
}

$arguments = @(
    '-B', '-X', 'utf8',
    $worker,
    $mode,
    '--root', $Root,
    '--json'
)
foreach ($skill in @($IncludeSkills)) {
    if (-not [string]::IsNullOrWhiteSpace($skill)) {
        $arguments += @('--include-skill', $skill)
    }
}
foreach ($skill in @($ExcludeSkills)) {
    if (-not [string]::IsNullOrWhiteSpace($skill)) {
        $arguments += @('--exclude-skill', $skill)
    }
}

# Only this adjacent worker is launched. Help is a fixed, read-only interface probe.
# Redirect both pipes independently; native stderr must not become a PS exception.
foreach ($phase in @('probe', 'main')) {
    $start = [System.Diagnostics.ProcessStartInfo]::new()
    $start.FileName = $pythonExe
    $start.WorkingDirectory = $Root
    $start.UseShellExecute = $false
    $start.RedirectStandardOutput = $true
    $start.RedirectStandardError = $true
    $start.StandardOutputEncoding = [System.Text.Encoding]::UTF8
    $start.StandardErrorEncoding = [System.Text.Encoding]::UTF8
    $phaseArguments = if ($phase -eq 'probe') { @('-B', '-X', 'utf8', $worker, '--help') } else { $arguments }
    # Windows argv quoting also supports Windows PowerShell 5.1's .NET Framework.
    $start.Arguments = ($phaseArguments | ForEach-Object {
        '"' + ($_ -replace '(\\*)"', '$1$1\"' -replace '(\\+)$', '$1$1') + '"'
    }) -join ' '
    $process = [System.Diagnostics.Process]::new()
    $process.StartInfo = $start
    try {
        $null = $process.Start()
        $stdoutTask = $process.StandardOutput.ReadToEndAsync()
        $stderrTask = $process.StandardError.ReadToEndAsync()
        if ($phase -eq 'probe' -and -not $process.WaitForExit(5000)) {
            # This fixed argparse help worker does not create child processes.
            $process.Kill()
            $null = $process.WaitForExit(1000)
            if ($stderrTask.Wait(1000)) { [Console]::Error.Write($stderrTask.Result) }
            throw 'Resource manifest worker help probe timed out (5000 ms).'
        }
        $process.WaitForExit()
        $exitCode = $process.ExitCode
        $output = $stdoutTask.GetAwaiter().GetResult()
        [Console]::Error.Write($stderrTask.GetAwaiter().GetResult())
    } finally {
        $process.Dispose()
    }
    if ($phase -eq 'probe') {
        if ($exitCode -ne 0) { exit $exitCode }
        foreach ($option in @('--root', '--json', '--include-skill', '--exclude-skill', '{generate,check}')) {
            if (-not $output.Contains($option)) {
                throw "Resource manifest worker help interface missing: $option"
            }
        }
    }
}

try {
    if ([string]::IsNullOrWhiteSpace($output)) { throw 'empty stdout' }
    if (-not $output.TrimStart().StartsWith('{')) { throw 'expected JSON object' }
    $result = ConvertFrom-Json -InputObject $output
    if ($result -isnot [pscustomobject]) { throw 'expected JSON object' }
    $counts = if ($mode -eq 'check') { @('checked', 'stale') } else { @('checked', 'written', 'unchanged', 'failed') }
    foreach ($name in $counts) {
        if ($null -eq $result.PSObject.Properties[$name] -or
            ($result.$name -isnot [int] -and $result.$name -isnot [long]) -or $result.$name -lt 0) {
            throw "invalid count: $name"
        }
    }
    if ($null -eq $result.PSObject.Properties['issues'] -or $result.issues -isnot [array]) { throw 'invalid issues array' }
    foreach ($issue in $result.issues) {
        if ($issue -isnot [pscustomobject] -or
            $issue.skill -isnot [string] -or $issue.detail -isnot [string]) { throw 'invalid issue' }
        if ($mode -eq 'check' -and $issue.code -isnot [string]) { throw 'invalid issue code' }
    }
    if ($mode -eq 'check') {
        if ($null -eq $result.PSObject.Properties['stale_skills'] -or $result.stale_skills -isnot [array]) { throw 'invalid stale_skills array' }
        foreach ($skill in $result.stale_skills) {
            if ($skill -isnot [string]) { throw 'invalid stale skill' }
        }
    }
    if ($exitCode -eq 0) {
        if ($result.issues.Count -ne 0) { throw 'success contains issues' }
        if ($mode -eq 'check') {
            if ($result.stale -ne 0 -or $result.stale_skills.Count -ne 0) { throw 'success contains stale manifests' }
        } elseif ($result.failed -ne 0 -or $result.written + $result.unchanged -ne $result.checked) {
            throw 'inconsistent generation counts'
        }
    }
} catch {
    [Console]::Error.WriteLine("Resource manifest worker returned invalid protocol: $($_.Exception.Message)")
    if ($exitCode -ne 0) { exit $exitCode }
    exit 1
}
if ($mode -eq 'check') {
    Write-Host "Resource manifests checked: $($result.checked); stale: $($result.stale)"
} else {
    Write-Host "Resource manifests checked: $($result.checked); written: $($result.written); unchanged: $($result.unchanged); failed: $($result.failed)"
}
foreach ($issue in @($result.issues)) {
    Write-Warning "$($issue.skill): $($issue.detail)"
}
if ($exitCode -ne 0) {
    exit $exitCode
}
