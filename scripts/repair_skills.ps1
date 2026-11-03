[CmdletBinding()]
param(
    [ValidateSet('Audit', 'Report', 'Gate')]
    [string]$Mode = 'Audit',

    [string]$Root = '',

    [string[]]$IncludeSkills,

    [string[]]$ExcludeSkills = @(),

    [int]$LineThreshold = 500,

    # Estimated-token ceiling for SKILL.md. Line count alone lets a dense
    # Chinese body stay invisible: 85 lines at 118 bytes/line is far more
    # context than 85 lines of short English. Calibrated so the current
    # library keeps its headroom (max ~6600 tokens); tighten deliberately.
    [int]$TokenThreshold = 8000,

    [string]$ReportDir = ''
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($Root)) {
    $Root = Split-Path -Parent $PSScriptRoot
}
$Root = (Resolve-Path -LiteralPath $Root).Path

if ([string]::IsNullOrWhiteSpace($ReportDir)) {
    $ReportDir = Join-Path $Root 'reports'
}

$DeprecatedPatterns = [ordered]@{
    invoke_subagent = '(?i)\binvoke_subagent\b'
    call_mcp_tool = '(?i)\bcall_mcp_tool\b'
    run_command = '(?i)\brun_command\b'
    write_to_file = '(?i)\bwrite_to_file\b'
    view_file = '(?i)\bview_file\b'
    ask_question = '(?i)\bask_question\b'
    mcp_vector_lake = '(?i)\bmcp_vector-lake\b'
    vector_lake_mcp = '(?i)\bvector-lake-mcp\b'
    legacy_knowledge_server_alias = '(?i)\bmentat-mind-mcp\b'
    request_feedback = '(?i)RequestFeedback\s*='
}

$ForeignRuntimePatterns = [ordered]@{
    gemini_path = '(?i)(?:[A-Z]:\\Users\\[^\s`"''<>]+\\\.gemini|\.gemini[\\/])'
    kimi_path = '(?i)(?:/app/\.kimi|\.kimi[\\/])'
    app_data_macro = '(?i)<appDataDir>'
    conversation_brain = '(?i)brain[\\/]<(?:conversation-)?id>'
    v11_runtime = '(?i)\bV11(?:\.\d+)?\b'
    ir_native = '(?i)IR Native'
    fable_runtime = '(?i)Fable\s*5'
}

$ForbiddenReasoningPatterns = [ordered]@{
    thought_xml = '(?i)<\/?thought>'
    thinking_xml = '(?i)<\/?thinking>'
    reasoning_draft = '(?i)(?<!\u4E0D)(?<!\u4E0D\u5F97)(?<!\u7981\u6B62)(?:\u8F93\u51FA|\u5C55\u793A|\u5199\u51FA|\u8BB0\u5F55|\u4FDD\u5B58|provide|show|write|include)[^\r\n]{0,24}(?:\u601D\u7EF4\u7A3F|\u63A8\u7406\u8349\u7A3F|\u5185\u90E8\u63A8\u7406|chain[- ]of[- ]thought)'
}

$HardcodedModelPatterns = [ordered]@{
    openai_version = '(?i)\bgpt-[0-9][A-Za-z0-9._-]*'
    gemini_version = '(?i)\bgemini-[0-9][A-Za-z0-9._-]*'
    claude_version = '(?i)\bclaude-(?:[0-9]|opus|sonnet|haiku)[A-Za-z0-9._-]*'
}

$MandatorySubagentPattern = '(?im)^\s*(?:[-*]\s*)?(?:\u5FC5\u987B|\u5F3A\u5236|\u52A1\u5FC5|must|required)[^\r\n]{0,80}(?:\u5B50\u4EE3\u7406|subagent)'
$MandatoryPersistencePattern = '(?im)^\s*(?:[-*]\s*)?(?:\u5FC5\u987B|\u5F3A\u5236|\u52A1\u5FC5|must|required)[^\r\n]{0,100}(?:Vector Lake|\u5165\u6E56|MEMORY|\u77E5\u8BC6\u5E93|\u957F\u671F\u8BB0\u5FC6|long[- ]term memory)'
$ArchiveTargetPattern = '(?i)(?:\u6863\u6848|\u5F52\u6863|\u7D22\u5F15|\u65E5\u5FD7|\u65E5\u8BB0|\u8D26\u672C|\u6570\u636E\u5E93|\u53BB\u91CD\u72B6\u6001|\u957F\u671F\u72B6\u6001|\u957F\u671F\u8BB0\u5FC6|archive|history\s+index|dedup(?:lication)?\s+state|canonical\s+(?:file|store)|diary|journal|ledger|database|MEMORY|\u77E5\u8BC6\u5E93|Vector Lake)'
$LocalFilePersistencePattern = '(?i)(?:\u751F\u6210|\u65E5\u5FD7|\u65E5\u8BB0|\u957F\u671F|\u6301\u4E45)[^\r\n]{0,40}(?:\u9ED8\u8BA4|\u81EA\u52A8|\u76F4\u63A5|\u65E0\u9700|\u65E0\u987B|\u4E0D\u518D)[^\r\n]{0,30}(?:\u5199\u5165|\u5199\u8FDB|\u5B58\u5165|\u5B58\u50A8|\u6301\u4E45\u5316|\u8FFD\u52A0|\u540C\u6B65|\u843D\u76D8|\u4FDD\u5B58)[^\r\n]{0,30}(?:\u672C\u5730\u6587\u4EF6|local\s+file)'
$AutomaticPersistenceBehaviorPattern = '(?i)(?:(?:\u9ED8\u8BA4(?:\u81EA\u52A8)?|\u81EA\u52A8|\u751F\u6210\u540E|\u5B8C\u6210\u540E)(?:\u4F1A)?[^\r\n]{0,20}(?:\u5C06|\u628A)?[^\r\n]{0,20}(?:\u7ED3\u679C|\u5185\u5BB9)?[^\r\n]{0,12}(?:\u4FDD\u5B58|\u5F52\u6863|\u5199\u5165|\u5199\u8FDB|\u5B58\u5165|\u5B58\u50A8|\u843D\u76D8)|\u76F4\u63A5[^\r\n]{0,20}(?:\u4FDD\u5B58|\u5F52\u6863|\u5199\u5165|\u5199\u8FDB|\u5B58\u5165|\u5B58\u50A8|\u843D\u76D8)|(?:\u8BF7\u6C42|\u751F\u6210|\u66F4\u65B0|\u8BB0\u5F55|\u5199)[^\r\n]{0,80}(?:\u6784\u6210|\u5373\u4E3A|\u89C6\u4E3A|\u540C\u65F6|\u5C31\u662F|\u672C\u8EAB\u5C31\u662F)[^\r\n]{0,40}(?:\u6388\u6743|\u8BB8\u53EF)[^\r\n]{0,40}(?:\u4FDD\u5B58|\u5F52\u6863|\u5199\u5165|\u5199\u8FDB|\u5B58\u5165|\u5B58\u50A8|\u843D\u76D8)|(?:\u65E0\u9700|\u65E0\u987B|\u4E0D\u518D)[^\r\n]{0,30}(?:\u8BE2\u95EE|\u8BF7\u6C42|\u989D\u5916)?[^\r\n]{0,12}(?:\u786E\u8BA4|\u6388\u6743)[^\r\n]{0,30}(?:\u4FDD\u5B58|\u5F52\u6863|\u5199\u5165|\u5199\u8FDB|\u5B58\u5165|\u5B58\u50A8|\u843D\u76D8)|(?:generate|update|record|request)[^\r\n]{0,80}(?:constitutes?|counts?\s+as|is)[^\r\n]{0,30}authori[sz](?:e|ation)[^\r\n]{0,40}(?:save|persist|archive|write|store)|(?:automatically|by\s+default|without\s+(?:another|separate|additional)\s+confirmation)[^\r\n]{0,50}(?:save|persist|archive|write|store)|(?:save|persist|archive|write|store|stored|archived)[^\r\n]{0,20}by\s+default|no\s+additional\s+confirmation[^\r\n]{0,40}(?:save|persist|archive|write|store))'
$DirectPersistenceNegationPattern = '(?i)(?:(?:\u7981\u6B62|\u4E25\u7981|\u4E0D\u5141\u8BB8|\u4E0D\u80FD|\u4E0D\u5F97|\u4E0D\u8981|\u4E0D\u53EF|\u4E0D\u5E94|\u4E0D\u4F1A|\u672A|\u4ECE\u4E0D|\u4E0D)\s*(?:\u5C06|\u628A)?[^\r\n]{0,20}(?:\u9ED8\u8BA4|\u81EA\u52A8|\u76F4\u63A5)?\s*(?:\u539F\u5B50|\u4E8B\u52A1\u5316?)?\s*(?:\u4FDD\u5B58|\u5F52\u6863|\u5199\u5165|\u5199\u8FDB|\u5B58\u5165|\u5B58\u50A8|\u6301\u4E45\u5316|\u8FFD\u52A0|\u540C\u6B65|\u843D\u76D8)|(?:do\s+not|does\s+not|never|must\s+not|shall\s+not)\s+(?:automatically\s+|by\s+default\s+)?(?:save|persist|archive|write|store|append|sync))'
$PersistenceVerbPattern = '(?i)(?:\u4FDD\u5B58|\u5F52\u6863|\u5199\u5165|\u5199\u8FDB|\u5B58\u5165|\u5B58\u50A8|\u6301\u4E45\u5316|\u8FFD\u52A0|\u540C\u6B65|\u843D\u76D8|save|persist(?:ed)?|archive(?:d)?|write|writ(?:e|ten)|store(?:d)?|append(?:ed)?|sync(?:ed)?)'
$AutomaticMarkerPattern = '(?i)(?:\u9ED8\u8BA4|\u81EA\u52A8|\u6BCF\u6B21\u6267\u884C\u90FD\u4F1A|automatically|by\s+default)'
$AuthorizationNegationPattern = '(?i)(?:\u4E0D\u6784\u6210|\u4E0D\u662F|\u4E0D\u89C6\u4E3A|\u975E)[^\r\n]{0,24}(?:\u4FDD\u5B58)?\u6388\u6743|(?:is\s+not|does\s+not\s+constitute|not)[^\r\n]{0,24}authori[sz]ation'
$AutomaticPersistenceOptOutTriggerPattern = '(?i)(?:\u8349\u7A3F|\u9884\u89C8|\u4E0D\u4FDD\u5B58|preview|draft|no[- ]?save)'
$AutomaticPersistenceOptOutEffectPattern = '(?i)(?:\u53EA\u8BFB|\u4FDD\u6301\u53EA\u8BFB|\u4E0D\u9002\u7528|\u4E0D\u8C03\u7528\u5F52\u6863|\u4E0D\u751F\u6210\u5199\u5165|\u4E0D\u5199\u5165|\u4E0D\u5F52\u6863|\u4E0D\u843D\u76D8|\u4E0D\u4FDD\u5B58|read[- ]?only|does\s+not\s+apply|do\s+not\s+(?:save|persist|archive|write))'
$AutomaticPersistenceOptOutRelationPattern = '(?i)(?:(?:\u82E5|\u5982\u679C|\u5F53|\u7528\u6237\u8981\u6C42|\u7528\u6237\u660E\u786E\u8981\u6C42)[^\r\n]{0,50}(?:\u8349\u7A3F|\u9884\u89C8|\u4E0D\u4FDD\u5B58|preview|draft|no[- ]?save)[^\r\n]{0,20}(?:\u65F6|\u5219|,|\uFF0C)[^\r\n]{0,40}(?:\u53EA\u8BFB|\u4FDD\u6301\u53EA\u8BFB|\u4E0D\u5199\u5165|\u4E0D\u5F52\u6863|\u4E0D\u843D\u76D8|\u4E0D\u4FDD\u5B58|read[- ]?only|do\s+not\s+(?:save|persist|archive|write))|\u8BE5\u4F8B\u5916\u4E0D\u9002\u7528\u4E8E[^\r\n]{0,50}(?:\u8349\u7A3F|\u9884\u89C8|\u4E0D\u4FDD\u5B58)|(?:if|when)[^\r\n]{0,30}(?:preview|draft|no[- ]?save)[^\r\n]{0,30}(?:read[- ]?only|do\s+not\s+(?:save|persist|archive|write)))'

function Get-AllSkillDirectories {
    Get-ChildItem -LiteralPath $Root -Directory |
        Where-Object {
            $_.Name -notin @('.system', 'scripts', 'shared', 'reports', 'examples') -and
            (Test-Path -LiteralPath (Join-Path $_.FullName 'SKILL.md'))
        } |
        Sort-Object Name
}

function Invoke-PythonJsonValidator {
    param(
        [string]$ScriptPath,
        [string[]]$Arguments
    )

    $pythonExe = if ($env:PAI_PYTHON -and (Test-Path $env:PAI_PYTHON)) {
        $env:PAI_PYTHON
    } else {
        $cmd = Get-Command python -ErrorAction SilentlyContinue
        if ($cmd) { $cmd.Source } else { $null }
    }
    if ($null -eq $pythonExe -or -not (Test-Path -LiteralPath $ScriptPath)) {
        return [PSCustomObject]@{
            Parsed = $false
            ExitCode = 1
            Payload = $null
            Error = 'python validator unavailable'
        }
    }

    $output = @(& $pythonExe '-B' '-X' 'utf8' $ScriptPath @Arguments 2>&1)
    $exitCode = $LASTEXITCODE
    try {
        $payload = ($output -join "`n") | ConvertFrom-Json
        return [PSCustomObject]@{
            Parsed = $true
            ExitCode = $exitCode
            Payload = $payload
            Error = ''
        }
    } catch {
        return [PSCustomObject]@{
            Parsed = $false
            ExitCode = $exitCode
            Payload = $null
            Error = "validator returned invalid JSON (exit $exitCode): $($_.Exception.Message); output: $(($output -join "`n").Substring(0, [math]::Min(2000, ($output -join "`n").Length)))"
        }
    }
}

function Get-NonNegativeIntegerProperty {
    param(
        [object]$Object,
        [string]$Name
    )

    if ($null -eq $Object -or $Object.PSObject.Properties.Name -notcontains $Name) {
        return $null
    }
    $parsed = 0
    if ([int]::TryParse([string]$Object.$Name, [ref]$parsed) -and $parsed -ge 0) {
        return $parsed
    }
    return $null
}

function Get-PatternHits {
    param(
        [string]$Text,
        [System.Collections.IDictionary]$Patterns
    )

    foreach ($entry in $Patterns.GetEnumerator()) {
        if ($Text -match $entry.Value) {
            $entry.Key
        }
    }
}

function Test-AutomaticPersistence {
    param(
        [string]$Text,
        [string]$SkillName = ''
    )

    foreach ($line in $Text -split '\r?\n') {
        if ($line -match '(?i)Schema[^\r\n]{0,80}\u6570\u636E\u5E93\u53D8\u5316[^\r\n]{0,80}(?:\u4E0D\u5F97|\u4E0D\u80FD|\u7981\u6B62)[^\r\n]{0,30}\u89E6\u53D1[^\r\n]{0,20}\u56DE\u9000') {
            continue
        }
        if ($line -match '(?i)Schema[^\r\n]{0,220}\u6570\u636E\u5E93\u53D8\u5316[^\r\n]{0,220}(?:\u56DE\u9000|\u56DE\u9000)') {
            continue
        }
        if ($line -match '(?i)Schema' -and $line -match '(?:\u6570\u636E\u5E93\u53D8\u5316|\u6570\u636E\u5E93\u53D8\u5316)' -and $line -match '(?:\u56DE\u9000|\u56DE\u9000)') {
            continue
        }
        if ($line -match $AuthorizationNegationPattern) {
            continue
        }
        foreach ($clause in $line -split '[,，。；;]') {
            if ($clause -match '(?i)(?:Schema|\u5B8C\u6574\u6027|\u6570\u636E\u5E93\u53D8\u5316|\u8BFB\u53D6\u9519\u8BEF)[^\r\n]{0,30}(?:\u4E0D\u5F97|\u4E0D\u80FD|\u7981\u6B62)[^\r\n]{0,30}(?:\u89E6\u53D1|trigger)[^\r\n]{0,20}(?:\u56DE\u9000|fallback)') {
                continue
            }
            if ($clause -match '(?i)(?:(?:\u4E0D|\u672A|\u7981\u6B62|\u4E0D\u5F97|\u4E0D\u5141\u8BB8)[^\r\n]{0,20}(?:\u81EA\u52A8|\u9ED8\u8BA4)[^\r\n]{0,20}(?:\u6269\u5927|\u540C\u6B65|\u4FDD\u5B58|\u5199\u5165|\u6301\u4E45\u5316)|(?:\u81EA\u52A8|\u9ED8\u8BA4)[^\r\n]{0,20}(?:\u6269\u5927|\u540C\u6B65|\u4FDD\u5B58|\u5199\u5165|\u6301\u4E45\u5316)[^\r\n]{0,20}(?:\u4E0D|\u672A|\u7981\u6B62|\u4E0D\u5F97|\u4E0D\u5141\u8BB8)|(?:do\s+not|does\s+not|never|must\s+not|shall\s+not)[^\r\n]{0,20}(?:automatically|by\s+default)[^\r\n]{0,20}(?:expand|sync|save|write|persist)|(?:automatically|by\s+default)[^\r\n]{0,20}(?:expand|sync|save|write|persist)[^\r\n]{0,20}(?:do\s+not|does\s+not|never|must\s+not|shall\s+not))') {
                continue
            }
            if ($clause -match '(?i)(?:(?:\u5FC5\u987B|\u9700\u8981|\u4ECD\u9700|\u53EA\u6709|\u4EC5\u5728|\u53E6\u884C|\u660E\u786E)[^\r\n]{0,40}(?:\u6388\u6743|\u540C\u610F|\u786E\u8BA4)[^\r\n]{0,60}(?:\u540C\u6B65|\u4FDD\u5B58|\u5199\u5165|\u6301\u4E45\u5316)|(?:\u540C\u6B65|\u4FDD\u5B58|\u5199\u5165|\u6301\u4E45\u5316)[^\r\n]{0,50}(?:\u5FC5\u987B|\u9700\u8981|\u4ECD\u9700|\u53EA\u6709|\u4EC5\u5728|\u53E6\u884C|\u660E\u786E)[^\r\n]{0,30}(?:\u6388\u6743|\u540C\u610F|\u786E\u8BA4)|(?:must|required|only\s+with|explicit)[^\r\n]{0,30}(?:authori[sz]ation|consent|confirmation)[^\r\n]{0,40}(?:sync|save|write|persist)|(?:sync|save|write|persist)[^\r\n]{0,40}(?:must|required|only\s+with|explicit)[^\r\n]{0,30}(?:authori[sz]ation|consent|confirmation))') {
                continue
            }
            if ($clause -match '(?i)(?:\u9ED8\u8BA4\u6388\u6743[^\r\n]{0,30}\u4E0D\u5305\u542B|default\s+authori[sz]ation[^\r\n]{0,30}does\s+not\s+include)[^\r\n]{0,120}(?:\u540C\u6B65|\u4FDD\u5B58|\u5199\u5165|\u6301\u4E45\u5316|sync|save|write|persist)') {
                continue
            }
            $candidate = [regex]::Replace($clause, $DirectPersistenceNegationPattern, '')
            if (
                (
                    $candidate -match $ArchiveTargetPattern -and
                    $candidate -match $AutomaticPersistenceBehaviorPattern
                ) -or
                $candidate -match $LocalFilePersistencePattern
            ) {
                return $true
            }
            if (
                $candidate -match $ArchiveTargetPattern -and
                $candidate -match $PersistenceVerbPattern -and
                $candidate -match $AutomaticMarkerPattern
            ) {
                return $true
            }
        }
        if ($line -match '(?:\u8BF7\u6C42|\u751F\u6210|\u66F4\u65B0|\u8BB0\u5F55|\u5199)[^\r\n]{0,80}(?:\u6784\u6210|\u5373\u4E3A|\u89C6\u4E3A|\u540C\u65F6|\u5C31\u662F|\u672C\u8EAB\u5C31\u662F)[^\r\n]{0,40}(?:\u6388\u6743|\u8BB8\u53EF)[^\r\n]{0,50}(?:\u4FDD\u5B58|\u5F52\u6863|\u5199\u5165|\u5199\u8FDB|\u5B58\u5165|\u5B58\u50A8|\u843D\u76D8)' -and $line -match $ArchiveTargetPattern) {
            return $true
        }
    }
    return $false
}

function Test-AutomaticPersistenceOptOut {
    param([string]$Text)

    # Direct enumerations must bind an explicit no-save trigger to a complete
    # negative persistence consequence, not merely mention preview/read-only.
    $enumeratedNoSave = '(?:\u4E8B\u5B9E\u95EE\u7B54|\u4E34\u65F6\u5206\u6790|\u9884\u89C8|\u8349\u7A3F)'
    $noSaveEffect = '(?:\u4E0D(?:\u843D\u76D8|\u5199\u5165|\u4FDD\u5B58|\u5F52\u6863)(?:\u62A5\u544A)?|\u4E0D\u6267\u884C(?:\u62A5\u544A)?(?:\u843D\u76D8|\u5199\u5165|\u4FDD\u5B58|\u5F52\u6863)(?:\u6216\u5F52\u6863)?(?:\s+validate/commit)?)'
    $directNoSavePattern = '(?:^|[\u3002\uFF1B;])\s*(?:[-*]\s+|\d+\.\s+)?(?:' + $enumeratedNoSave + '[\u3001/\u6216])*\s*(?:\u660E\u786E)?\u4E0D\u4FDD\u5B58\s*(?:\u53EA\u5728\u7B54\u590D\u4EA4\u4ED8[\uFF0C,]\s*)?' + $noSaveEffect + '\s*(?=\u3002|$)'

    foreach ($line in $Text -split '\r?\n') {
        if ($line -match $AutomaticPersistenceOptOutRelationPattern -or $line -match $directNoSavePattern) {
            return $true
        }
    }
    if ($Text -match '(?is)(?:\u7528\u6237\u660E\u786E\u8981\u6C42|\u82E5|\u5982\u679C|\u5F53)[^\r\n]{0,40}(?:\u4E0D\u4FDD\u5B58|no[- ]?save)[^\r\n]{0,160}(?:\u53EA\u8BFB|\u4E0D\u8C03\u7528\u5F52\u6863|\u4E0D\u5199\u5165|\u4E0D\u5F52\u6863|\u4E0D\u843D\u76D8|\u4E0D\u4FDD\u5B58|read[- ]?only|do\s+not\s+(?:save|persist|archive|write))') {
        return $true
    }
    return $false
}

# Vendored trees and build output are not skill content. Keep this list aligned
# with resource_manifest.py IGNORED_DIRECTORIES, otherwise a dependency dump
# inside a skill produces findings about libraries the skill never authored.
$IgnoredCorpusDirectories = [System.Collections.Generic.HashSet[string]]::new(
    [string[]]@(
        '__pycache__', '.ruff_cache', '.pytest_cache', '.jules', '.venv',
        '.venv_test', 'node_modules', '_runtime', 'garmin-output', 'output',
        'outputs', 'scratch', 'tmp', 'temp', 'dist', 'build'
    ),
    [System.StringComparer]::OrdinalIgnoreCase
)

function Get-EstimatedTokenCount {
    param([string]$Text)

    if ([string]::IsNullOrEmpty($Text)) {
        return 0
    }
    $wide = 0
    foreach ($character in $Text.ToCharArray()) {
        $code = [int]$character
        if (($code -ge 0x4E00 -and $code -le 0x9FFF) -or
            ($code -ge 0x3000 -and $code -le 0x303F) -or
            ($code -ge 0xFF00 -and $code -le 0xFFEF)) {
            $wide++
        }
    }
    # Wide characters cost about one token each; the rest about a quarter.
    return [int][math]::Ceiling($wide + (($Text.Length - $wide) / 4))
}

function Get-SkillTextCorpus {
    param([string]$SkillDirectory)

    $extensions = @('.md', '.txt', '.py', '.ps1', '.js', '.ts', '.mjs', '.json', '.yaml', '.yml', '.html', '.css', '.toml')
    $parts = foreach ($file in Get-ChildItem -LiteralPath $SkillDirectory -Recurse -File -ErrorAction Stop) {
        $relativePath = [IO.Path]::GetRelativePath($SkillDirectory, $file.FullName)
        $pathSegments = $relativePath -split '[\\/]'
        if (@($pathSegments | Where-Object { $IgnoredCorpusDirectories.Contains($_) }).Count -gt 0) {
            continue
        }
        if ($file.Name -eq 'resource-manifest.json' -or $file.Name -match '^(?:package-lock|pnpm-lock|yarn\.lock)') {
            continue
        }
        if ($file.Extension.ToLowerInvariant() -notin $extensions) {
            continue
        }
        try {
            [Text.UTF8Encoding]::new($false, $true).GetString([IO.File]::ReadAllBytes($file.FullName))
        } catch {
            throw "Cannot read skill resource '$relativePath': $($_.Exception.Message)"
        }
    }
    $parts -join "`n"
}

function Get-ManifestStatus {
    param([string]$SkillDirectory)

    $path = Join-Path $SkillDirectory 'resource-manifest.json'
    if (-not (Test-Path -LiteralPath $path)) {
        return [PSCustomObject]@{ Exists = $false; ParseError = $false; Missing = @() }
    }

    try {
        $manifest = Get-Content -LiteralPath $path -Raw -Encoding UTF8 | ConvertFrom-Json
        $missing = if ($null -eq $manifest.missing_declared_dependencies) {
            @()
        } else {
            @($manifest.missing_declared_dependencies)
        }
        [PSCustomObject]@{ Exists = $true; ParseError = $false; Missing = $missing }
    } catch {
        [PSCustomObject]@{ Exists = $true; ParseError = $true; Missing = @('__PARSE_ERROR__') }
    }
}

function Get-TriggerOwnershipStatus {
    param(
        [string[]]$KnownSkills,
        [string[]]$SelectedSkills = @(),
        [bool]$Scoped = $false
    )

    $path = Join-Path $Root 'shared\trigger-ownership-matrix.json'
    if (-not (Test-Path -LiteralPath $path)) {
        return [PSCustomObject]@{ Exists = $false; ClassCount = 0; Conflicts = @('__MISSING_MATRIX__') }
    }

    try {
        $matrix = Get-Content -LiteralPath $path -Raw -Encoding UTF8 | ConvertFrom-Json
    } catch {
        return [PSCustomObject]@{ Exists = $true; ClassCount = 0; Conflicts = @('__PARSE_ERROR__') }
    }

    $conflicts = [System.Collections.Generic.List[string]]::new()
    $owners = @{}
    $classCount = 0

    foreach ($domain in @($matrix.domains)) {
        foreach ($class in @($domain.classes)) {
            $classCount++
            $location = "$($domain.domain)/$($class.id)"
            $primary = [string]$class.primary_skill
            $secondarySkills = @($class.secondary_skills | ForEach-Object { [string]$_ })
            $classSkills = @($primary) + $secondarySkills
            $isRelevant = -not $Scoped -or @($classSkills | Where-Object { $_ -in $SelectedSkills }).Count -gt 0
            if ($isRelevant -and $KnownSkills -notcontains $primary) {
                $conflicts.Add("$location unknown primary_skill: $primary")
            }
            foreach ($secondary in $secondarySkills) {
                if ($isRelevant -and $KnownSkills -notcontains $secondary) {
                    $conflicts.Add("$location unknown secondary_skill: $secondary")
                }
            }
            $handoffSkills = if ($class.PSObject.Properties.Name -contains 'handoff_skills') {
                @($class.handoff_skills | ForEach-Object { [string]$_ })
            } else {
                @()
            }
            foreach ($handoff in $handoffSkills) {
                if (-not $isRelevant) {
                    continue
                }
                if ([string]::IsNullOrWhiteSpace($handoff)) {
                    $conflicts.Add("$location contains empty handoff_skill")
                } elseif ($handoff -notmatch '^(?:system|plugin):' -and $KnownSkills -notcontains $handoff) {
                    $conflicts.Add("$location unknown handoff_skill: $handoff")
                }
            }
            $positiveSignals = [System.Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
            foreach ($signal in @($class.request_signals)) {
                $normalized = ([string]$signal).Trim().ToLowerInvariant()
                if ([string]::IsNullOrWhiteSpace($normalized)) {
                    if ($isRelevant) {
                        $conflicts.Add("$location contains empty request_signal")
                    }
                } elseif ($owners.ContainsKey($normalized)) {
                    $previous = $owners[$normalized]
                    if ($isRelevant -or $previous.Relevant) {
                        $conflicts.Add("duplicate request_signal '$signal' in $($previous.Location) and $location")
                    }
                } else {
                    $owners[$normalized] = [PSCustomObject]@{ Location = $location; Relevant = $isRelevant }
                }
                if (-not [string]::IsNullOrWhiteSpace($normalized)) {
                    [void]$positiveSignals.Add($normalized)
                }
            }
            $negativeSignals = if ($class.PSObject.Properties.Name -contains 'should_not_trigger_signals') {
                @($class.should_not_trigger_signals)
            } else {
                @()
            }
            foreach ($signal in $negativeSignals) {
                $normalized = ([string]$signal).Trim().ToLowerInvariant()
                if (-not $isRelevant) {
                    continue
                }
                if ([string]::IsNullOrWhiteSpace($normalized)) {
                    $conflicts.Add("$location contains empty should_not_trigger_signal")
                } elseif ($positiveSignals.Contains($normalized)) {
                    $conflicts.Add("$location repeats a signal in both positive and negative sets: $signal")
                }
            }
        }
    }

    [PSCustomObject]@{ Exists = $true; ClassCount = $classCount; Conflicts = @($conflicts) }
}

$allSkillDirectories = @(Get-AllSkillDirectories)
$allSkillNames = @($allSkillDirectories | ForEach-Object Name)
$requestedIncludeSkills = @($IncludeSkills | Where-Object { -not [string]::IsNullOrWhiteSpace($_) } | Sort-Object -Unique)
$requestedExcludeSkills = @($ExcludeSkills | Where-Object { -not [string]::IsNullOrWhiteSpace($_) } | Sort-Object -Unique)
$unknownIncludeSkills = @($requestedIncludeSkills | Where-Object { $_ -notin $allSkillNames })
$unknownExcludeSkills = @($requestedExcludeSkills | Where-Object { $_ -notin $allSkillNames })
$scopeOverlapSkills = @($requestedIncludeSkills | Where-Object { $_ -in $requestedExcludeSkills })
$isScoped = $requestedIncludeSkills.Count -gt 0 -or $requestedExcludeSkills.Count -gt 0
$skillDirectories = @(
    $allSkillDirectories |
        Where-Object {
            ($requestedIncludeSkills.Count -eq 0 -or $_.Name -in $requestedIncludeSkills) -and
            $_.Name -notin $requestedExcludeSkills
        }
)
$validatorScopeArguments = [System.Collections.Generic.List[string]]::new()
$validatorScopeArguments.Add('--root')
$validatorScopeArguments.Add($Root)
$validatorScopeArguments.Add('--json')
foreach ($skillName in $requestedIncludeSkills) {
    $validatorScopeArguments.Add('--include-skill')
    $validatorScopeArguments.Add($skillName)
}
foreach ($skillName in $requestedExcludeSkills) {
    $validatorScopeArguments.Add('--exclude-skill')
    $validatorScopeArguments.Add($skillName)
}

$frontmatterValidation = Invoke-PythonJsonValidator `
    -ScriptPath (Join-Path $PSScriptRoot 'validate_openai_yaml.py') `
    -Arguments (@($validatorScopeArguments) + @('--frontmatter-only'))
$frontmatterBySkill = @{}
$frontmatterProtocolValid = $frontmatterValidation.Parsed -and
    $null -ne $frontmatterValidation.Payload.PSObject.Properties['records']
if ($frontmatterProtocolValid) {
    foreach ($record in @($frontmatterValidation.Payload.records)) {
        if ($null -eq $record -or
            $record.PSObject.Properties.Name -notcontains 'skill' -or
            $record.PSObject.Properties.Name -notcontains 'valid' -or
            $record.valid -isnot [bool] -or
            $record.PSObject.Properties.Name -notcontains 'keys' -or
            $record.PSObject.Properties.Name -notcontains 'unexpected_keys' -or
            $record.PSObject.Properties.Name -notcontains 'name' -or
            $record.PSObject.Properties.Name -notcontains 'description_has_trigger_context' -or
            $record.skill -notin $skillDirectories.Name -or
            $frontmatterBySkill.ContainsKey($record.skill)) {
            $frontmatterProtocolValid = $false
            continue
        }
        $frontmatterBySkill[$record.skill] = $record
    }
}
$frontmatterChecked = Get-NonNegativeIntegerProperty -Object $frontmatterValidation.Payload -Name 'checked'
$frontmatterFailures = Get-NonNegativeIntegerProperty -Object $frontmatterValidation.Payload -Name 'failures'
$frontmatterExitConsistent = (
    ($frontmatterValidation.ExitCode -eq 0 -and $frontmatterFailures -eq 0) -or
    ($frontmatterValidation.ExitCode -eq 1 -and $null -ne $frontmatterFailures -and $frontmatterFailures -gt 0)
)
$frontmatterValidatorIntegrationFailure = -not (
    $frontmatterProtocolValid -and $frontmatterBySkill.Count -eq $skillDirectories.Count -and
    $frontmatterChecked -eq $skillDirectories.Count -and $null -ne $frontmatterFailures -and
    $frontmatterExitConsistent
)
$records = @(foreach ($directory in $skillDirectories) {
    $skillPath = Join-Path $directory.FullName 'SKILL.md'
    $lines = @(Get-Content -LiteralPath $skillPath -Encoding UTF8)
    $text = $lines -join "`n"
    $corpus = Get-SkillTextCorpus -SkillDirectory $directory.FullName
    $frontmatter = if ($frontmatterBySkill.ContainsKey($directory.Name)) {
        $frontmatterBySkill[$directory.Name]
    } else {
        [PSCustomObject]@{ valid = $false; keys = @(); unexpected_keys = @(); name = ''; description_has_trigger_context = $null }
    }
    $manifest = Get-ManifestStatus -SkillDirectory $directory.FullName

    [PSCustomObject]@{
        Skill = $directory.Name
        Path = $skillPath
        LineCount = $lines.Count
        CharCount = $text.Length
        EstimatedTokens = Get-EstimatedTokenCount -Text $text
        FrontmatterValid = $frontmatter.valid
        FrontmatterKeys = @($frontmatter.keys)
        UnexpectedFrontmatterKeys = @($frontmatter.unexpected_keys)
        Name = $frontmatter.name
        DescriptionHasTriggerContext = $frontmatter.description_has_trigger_context
        HasResourceManifest = $manifest.Exists
        ManifestIssues = @($manifest.Missing)
        DeprecatedTokens = @(Get-PatternHits -Text $corpus -Patterns $DeprecatedPatterns)
        ForeignRuntime = @(Get-PatternHits -Text $corpus -Patterns $ForeignRuntimePatterns)
        ReasoningDirectives = @(Get-PatternHits -Text $corpus -Patterns $ForbiddenReasoningPatterns)
        HardcodedModels = @(Get-PatternHits -Text $corpus -Patterns $HardcodedModelPatterns)
        MandatorySubagent = [bool]($corpus -match $MandatorySubagentPattern)
        MandatoryPersistence = [bool]($corpus -match $MandatoryPersistencePattern)
        AutomaticPersistence = Test-AutomaticPersistence -Text $text -SkillName $directory.Name
        AutomaticPersistenceHasOptOut = Test-AutomaticPersistenceOptOut -Text $text
    }
})

$readmePath = Join-Path $Root 'README.md'
$declaredInventory = 0
$declaredAutomaticPersistenceRecords = @()
$automaticPersistenceTableMalformedRows = 0
$automaticPersistenceTableDuplicateSkills = 0
$automaticPersistenceTableSemanticFailures = 0
$automaticPersistenceTableIssues = [System.Collections.Generic.List[object]]::new()
if (Test-Path -LiteralPath $readmePath) {
    $readmeText = Get-Content -LiteralPath $readmePath -Raw -Encoding UTF8
    if ($readmeText -match '\u5F53\u524D\u5E93\u5B58\u4E3A\s*(?<count>\d+)\s*\u4E2A\u7528\u6237\u6280\u80FD') {
        $declaredInventory = [int]$Matches.count
    }
    if ($readmeText -match '(?s)<!-- automatic-persistence-exceptions:start -->(?<block>.*?)<!-- automatic-persistence-exceptions:end -->') {
        $tableRows = @(
            $Matches.block -split '\r?\n' |
                Where-Object {
                    $_ -match '^\s*\|' -and
                    $_ -notmatch '(?i)^\s*\|\s*Skill\s*\|' -and
                    $_ -notmatch '^\s*\|\s*:?-{3,}:?\s*\|'
                }
        )
        $parsedRows = [System.Collections.Generic.List[object]]::new()
        foreach ($row in $tableRows) {
            $rowSkill = if ($row -match '^\|\s*`?(?<skill>[a-z0-9]+(?:-[a-z0-9]+)*)`?\s*\|') {
                $Matches.skill.Trim()
            } else {
                ''
            }
            if ($row -match '^\|\s*`(?<skill>[a-z0-9]+(?:-[a-z0-9]+)*)`\s*\|\s*(?<trigger>[^|]+?)\s*\|\s*(?<target>[^|]+?)\s*\|\s*(?<optout>[^|]+?)\s*\|\s*$') {
                $record = [PSCustomObject]@{
                    Skill = $Matches.skill.Trim()
                    Trigger = $Matches.trigger.Trim()
                    Target = $Matches.target.Trim()
                    OptOut = $Matches.optout.Trim()
                }
                $emptyFields = @(
                    @($record.Trigger, $record.Target, $record.OptOut) |
                        Where-Object { [string]::IsNullOrWhiteSpace($_) -or $_ -match '^-+$' }
                )
                if ($emptyFields.Count -gt 0) {
                    $automaticPersistenceTableIssues.Add([PSCustomObject]@{ Type = 'Malformed'; Skill = $rowSkill })
                } else {
                    $genericFieldPattern = '(?i)^(?:anything|any|maybe|\u4EFB\u610F|\u4E0D\u9650|\u968F\u610F|\u672A\u5B9A)$'
                    $openTargetPattern = '(?i)(?:\u4EFB\u610F|\u4E0D\u9650|\u5916\u90E8\u7CFB\u7EDF|anything|anywhere|external\s+system)'
                    $targetClosed = (
                        $record.Target -match $ArchiveTargetPattern -and
                        $record.Target -notmatch $openTargetPattern
                    )
                    $optOutSpecific = (
                        $record.OptOut -match $AutomaticPersistenceOptOutTriggerPattern -and
                        $record.OptOut -notmatch $genericFieldPattern
                    )
                    if (
                        $record.Trigger -match $genericFieldPattern -or
                        -not $targetClosed -or
                        -not $optOutSpecific
                    ) {
                        $automaticPersistenceTableIssues.Add([PSCustomObject]@{ Type = 'Semantic'; Skill = $rowSkill })
                    } else {
                        $parsedRows.Add($record)
                    }
                }
            } else {
                $automaticPersistenceTableIssues.Add([PSCustomObject]@{ Type = 'Malformed'; Skill = $rowSkill })
            }
        }
        $declaredAutomaticPersistenceRecords = @($parsedRows)
        $duplicatePersistenceGroups = @(
            $declaredAutomaticPersistenceRecords |
                Group-Object Skill |
                Where-Object Count -gt 1
        )
        foreach ($group in $duplicatePersistenceGroups) {
            $automaticPersistenceTableIssues.Add([PSCustomObject]@{ Type = 'Duplicate'; Skill = $group.Name })
        }
    }
}

$selectedSkillNames = @($records | ForEach-Object Skill)
$automaticPersistenceTableIssuesForScope = @(
    if ($isScoped) {
        $automaticPersistenceTableIssues | Where-Object { $_.Skill -in $selectedSkillNames }
    } else {
        $automaticPersistenceTableIssues
    }
)
$automaticPersistenceTableMalformedRows = @($automaticPersistenceTableIssuesForScope | Where-Object Type -eq 'Malformed').Count
$automaticPersistenceTableDuplicateSkills = @($automaticPersistenceTableIssuesForScope | Where-Object Type -eq 'Duplicate').Count
$automaticPersistenceTableSemanticFailures = @($automaticPersistenceTableIssuesForScope | Where-Object Type -eq 'Semantic').Count
$declaredAutomaticPersistenceRecordsForScope = @(
    if ($isScoped) {
        $declaredAutomaticPersistenceRecords | Where-Object { $_.Skill -in $selectedSkillNames }
    } else {
        $declaredAutomaticPersistenceRecords
    }
)
$automaticPersistenceRecords = @($records | Where-Object AutomaticPersistence)
$automaticPersistenceSkills = @($automaticPersistenceRecords | ForEach-Object Skill)
$declaredAutomaticPersistenceExceptions = @($declaredAutomaticPersistenceRecordsForScope | ForEach-Object Skill)
$undeclaredAutomaticPersistence = @(
    $automaticPersistenceRecords |
        Where-Object { $_.Skill -notin $declaredAutomaticPersistenceExceptions }
)
$staleAutomaticPersistenceExceptions = @(
    $declaredAutomaticPersistenceExceptions |
        Where-Object { $_ -notin $automaticPersistenceSkills } |
        Sort-Object -Unique
)
$unknownAutomaticPersistenceExceptions = @(
    $declaredAutomaticPersistenceExceptions |
        Where-Object { $_ -notin $allSkillNames } |
        Sort-Object -Unique
)
$automaticPersistenceOptOutFailures = @(
    $automaticPersistenceRecords |
        Where-Object {
            $_.Skill -in $declaredAutomaticPersistenceExceptions -and
            -not $_.AutomaticPersistenceHasOptOut
        }
)

$hygieneRoots = if ($isScoped) { @($skillDirectories | ForEach-Object FullName) } else { @($Root) }
$skillJsonFiles = @(
    foreach ($scanRoot in $hygieneRoots) {
        Get-ChildItem -LiteralPath $scanRoot -Recurse -Filter 'skill.json' -File |
            Where-Object { $_.FullName -notmatch '[\\/]\.system[\\/]' }
    }
)
$nodeModules = @(
    foreach ($scanRoot in $hygieneRoots) {
        Get-ChildItem -LiteralPath $scanRoot -Recurse -Directory -Filter 'node_modules' -ErrorAction SilentlyContinue |
            Where-Object { $_.FullName -notmatch '[\\/]\.system[\\/]' }
    }
)
$triggerStatus = Get-TriggerOwnershipStatus `
    -KnownSkills $allSkillNames `
    -SelectedSkills $selectedSkillNames `
    -Scoped $isScoped

$resourceManifestValidation = Invoke-PythonJsonValidator `
    -ScriptPath (Join-Path $PSScriptRoot 'resource_manifest.py') `
    -Arguments (@('check') + @($validatorScopeArguments))
$resourceChecked = Get-NonNegativeIntegerProperty -Object $resourceManifestValidation.Payload -Name 'checked'
$resourceStale = Get-NonNegativeIntegerProperty -Object $resourceManifestValidation.Payload -Name 'stale'
$resourceExitConsistent = (
    ($resourceManifestValidation.ExitCode -eq 0 -and $resourceStale -eq 0) -or
    ($resourceManifestValidation.ExitCode -eq 1 -and $null -ne $resourceStale -and $resourceStale -gt 0)
)
$resourceValidatorIntegrationFailure = -not (
    $resourceManifestValidation.Parsed -and
    $null -ne $resourceChecked -and
    $resourceChecked -eq $records.Count -and
    $null -ne $resourceStale -and
    $resourceExitConsistent
)
$invalidResourceManifests = if ($null -ne $resourceStale) { $resourceStale } else { 0 }

$openAiMetadataValidation = Invoke-PythonJsonValidator `
    -ScriptPath (Join-Path $PSScriptRoot 'validate_openai_yaml.py') `
    -Arguments @($validatorScopeArguments)
$expectedMetadataChecks = @(
    $skillDirectories | Where-Object {
        Test-Path -LiteralPath (Join-Path $_.FullName 'agents\openai.yaml')
    }
).Count
$metadataChecked = Get-NonNegativeIntegerProperty -Object $openAiMetadataValidation.Payload -Name 'checked'
$metadataFailures = Get-NonNegativeIntegerProperty -Object $openAiMetadataValidation.Payload -Name 'failures'
$metadataWarnings = @()
if ($openAiMetadataValidation.Parsed -and
    $null -ne $openAiMetadataValidation.Payload.PSObject.Properties['warnings']) {
    $metadataWarnings = @($openAiMetadataValidation.Payload.warnings)
}
$metadataExitConsistent = (
    ($openAiMetadataValidation.ExitCode -eq 0 -and $metadataFailures -eq 0) -or
    ($openAiMetadataValidation.ExitCode -eq 1 -and $null -ne $metadataFailures -and $metadataFailures -gt 0)
)
$metadataValidatorIntegrationFailure = -not (
    $openAiMetadataValidation.Parsed -and
    $null -ne $metadataChecked -and
    $metadataChecked -eq $expectedMetadataChecks -and
    $null -ne $metadataFailures -and
    $metadataExitConsistent
)
$openAiMetadataFailures = if ($null -ne $metadataFailures) { $metadataFailures } else { 0 }
$validatorIntegrationFailures = [int]$frontmatterValidatorIntegrationFailure + [int]$resourceValidatorIntegrationFailure + [int]$metadataValidatorIntegrationFailure

$summary = [PSCustomObject]@{
    Root = $Root
    Scope = if ($isScoped) { 'Selection' } else { 'Repository' }
    DeclaredInventory = $declaredInventory
    AllSkillCount = $allSkillDirectories.Count
    SkillCount = $records.Count
    UnknownIncludeSkills = $unknownIncludeSkills.Count
    UnknownExcludeSkills = $unknownExcludeSkills.Count
    ScopeOverlapSkills = $scopeOverlapSkills.Count
    EmptySelection = [bool]($isScoped -and $records.Count -eq 0)
    RepositoryChecksSkipped = if ($isScoped) { 'inventory; unrelated skill hygiene; unrelated persistence rows; unrelated trigger classes' } else { '' }
    InventoryMismatch = -not $isScoped -and $declaredInventory -ne $allSkillDirectories.Count
    FrontmatterFailures = @($records | Where-Object { -not $_.FrontmatterValid }).Count
    OversizedSkills = @($records | Where-Object LineCount -gt $LineThreshold).Count
    OversizedByEstimatedTokens = @($records | Where-Object EstimatedTokens -gt $TokenThreshold).Count
    MaxEstimatedTokens = if ($records.Count -gt 0) { ($records | Measure-Object -Property EstimatedTokens -Maximum).Maximum } else { 0 }
    MissingResourceManifests = @($records | Where-Object { -not $_.HasResourceManifest }).Count
    ManifestDependencyIssues = @($records | Where-Object { $_.ManifestIssues.Count -gt 0 }).Count
    InvalidResourceManifests = $invalidResourceManifests
    OpenAiMetadataFailures = $openAiMetadataFailures
    OpenAiPolicyWarnings = $metadataWarnings.Count
    ValidatorIntegrationFailures = $validatorIntegrationFailures
    DeprecatedToolSkills = @($records | Where-Object { $_.DeprecatedTokens.Count -gt 0 }).Count
    ForeignRuntimeSkills = @($records | Where-Object { $_.ForeignRuntime.Count -gt 0 }).Count
    ReasoningDirectiveSkills = @($records | Where-Object { $_.ReasoningDirectives.Count -gt 0 }).Count
    HardcodedModelSkills = @($records | Where-Object { $_.HardcodedModels.Count -gt 0 }).Count
    MandatorySubagentSkills = @($records | Where-Object MandatorySubagent).Count
    MandatoryPersistenceSkills = @($records | Where-Object MandatoryPersistence).Count
    AutomaticPersistenceSkills = $automaticPersistenceRecords.Count
    DeclaredAutomaticPersistenceExceptions = $declaredAutomaticPersistenceRecordsForScope.Count
    UndeclaredAutomaticPersistenceSkills = $undeclaredAutomaticPersistence.Count
    StaleAutomaticPersistenceExceptions = $staleAutomaticPersistenceExceptions.Count
    UnknownAutomaticPersistenceExceptions = $unknownAutomaticPersistenceExceptions.Count
    AutomaticPersistenceTableMalformedRows = $automaticPersistenceTableMalformedRows
    AutomaticPersistenceTableDuplicateSkills = $automaticPersistenceTableDuplicateSkills
    AutomaticPersistenceTableSemanticFailures = $automaticPersistenceTableSemanticFailures
    AutomaticPersistenceOptOutFailures = $automaticPersistenceOptOutFailures.Count
    SkillJsonFiles = $skillJsonFiles.Count
    NodeModulesDirectories = $nodeModules.Count
    TriggerOwnershipClasses = $triggerStatus.ClassCount
    TriggerOwnershipConflicts = @($triggerStatus.Conflicts).Count
}

$failures = [System.Collections.Generic.List[string]]::new()
foreach ($entry in @(
    @{ Name = 'inventory_mismatch'; Value = [int]$summary.InventoryMismatch },
    @{ Name = 'unknown_include_skills'; Value = $summary.UnknownIncludeSkills },
    @{ Name = 'unknown_exclude_skills'; Value = $summary.UnknownExcludeSkills },
    @{ Name = 'scope_overlap_skills'; Value = $summary.ScopeOverlapSkills },
    @{ Name = 'empty_selection'; Value = [int]$summary.EmptySelection },
    @{ Name = 'frontmatter_failures'; Value = $summary.FrontmatterFailures },
    @{ Name = 'oversized_skills'; Value = $summary.OversizedSkills },
    @{ Name = 'oversized_by_estimated_tokens'; Value = $summary.OversizedByEstimatedTokens },
    @{ Name = 'missing_resource_manifests'; Value = $summary.MissingResourceManifests },
    @{ Name = 'manifest_dependency_issues'; Value = $summary.ManifestDependencyIssues },
    @{ Name = 'invalid_resource_manifests'; Value = $summary.InvalidResourceManifests },
    @{ Name = 'openai_metadata_failures'; Value = $summary.OpenAiMetadataFailures },
    @{ Name = 'validator_integration_failures'; Value = $summary.ValidatorIntegrationFailures },
    @{ Name = 'undeclared_automatic_persistence_skills'; Value = $summary.UndeclaredAutomaticPersistenceSkills },
    @{ Name = 'stale_automatic_persistence_exceptions'; Value = $summary.StaleAutomaticPersistenceExceptions },
    @{ Name = 'unknown_automatic_persistence_exceptions'; Value = $summary.UnknownAutomaticPersistenceExceptions },
    @{ Name = 'automatic_persistence_table_malformed_rows'; Value = $summary.AutomaticPersistenceTableMalformedRows },
    @{ Name = 'automatic_persistence_table_duplicate_skills'; Value = $summary.AutomaticPersistenceTableDuplicateSkills },
    @{ Name = 'automatic_persistence_table_semantic_failures'; Value = $summary.AutomaticPersistenceTableSemanticFailures },
    @{ Name = 'automatic_persistence_opt_out_failures'; Value = $summary.AutomaticPersistenceOptOutFailures },
    @{ Name = 'skill_json_files'; Value = $summary.SkillJsonFiles },
    @{ Name = 'node_modules_directories'; Value = $summary.NodeModulesDirectories },
    @{ Name = 'trigger_ownership_conflicts'; Value = $summary.TriggerOwnershipConflicts }
)) {
    if ($entry.Value -gt 0) {
        $failures.Add("$($entry.Name)=$($entry.Value)")
    }
}

$summary | Format-List
# Corpus matches cannot establish whether a quoted, negated or host-specific
# example is an instruction. The semantic review remains separate from this gate.
foreach ($record in $records) {
    $hits = @($record.DeprecatedTokens) + @($record.ForeignRuntime) +
        @($record.ReasoningDirectives) + @($record.HardcodedModels)
    if ($record.MandatorySubagent) { $hits += 'mandatory_subagent' }
    if ($record.MandatoryPersistence) { $hits += 'mandatory_persistence' }
    if ($hits.Count -gt 0) {
        Write-Warning "$($record.Skill): heuristic matches [$($hits -join ', ')]; semantic review required."
    }
}
foreach ($validation in @($frontmatterValidation, $resourceManifestValidation, $openAiMetadataValidation)) {
    if (-not $validation.Parsed) {
        Write-Warning $validation.Error
    } elseif ($validation.ExitCode -ne 0 -and $validation.Payload.PSObject.Properties.Name -contains 'issues') {
        foreach ($issue in @($validation.Payload.issues)) {
            Write-Warning "$($issue.skill): $($issue.code): $($issue.detail)"
        }
    }
}
# Invocation-policy warnings are surfaced but never block: choosing the missing
# side changes which hosts may auto-trigger a skill, so it stays a decision.
foreach ($warning in $metadataWarnings) {
    Write-Warning "$($warning.skill): $($warning.detail)"
}
$records |
    Select-Object Skill, LineCount, CharCount, EstimatedTokens, FrontmatterValid, HasResourceManifest, MandatorySubagent, MandatoryPersistence, AutomaticPersistence, AutomaticPersistenceHasOptOut |
    Format-Table -AutoSize

if ($Mode -eq 'Report') {
    if (-not (Test-Path -LiteralPath $ReportDir)) {
        New-Item -ItemType Directory -Path $ReportDir | Out-Null
    }
    [PSCustomObject]@{
        Summary = $summary
        Records = $records
        TriggerOwnership = $triggerStatus
        FrontmatterValidation = $frontmatterValidation.Payload
        ResourceManifestValidation = $resourceManifestValidation.Payload
        OpenAiMetadataValidation = $openAiMetadataValidation.Payload
    } | ConvertTo-Json -Depth 7 | Set-Content -LiteralPath (Join-Path $ReportDir 'skills-audit.json') -Encoding UTF8
}

if ($Mode -eq 'Gate') {
    if ($failures.Count -gt 0) {
        Write-Error ('Skill audit gate failed: ' + ($failures -join '; '))
        exit 1
    }
    Write-Host 'Skill audit gate passed.'
}
