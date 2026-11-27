<#
Task C decoding runs for ft-g7 (docs/TUNING_PROTOCOL.md). Windows PowerShell version of
scripts/task_c_decode.sh, with the same run names, settings and prompts.

Run from the repository root (Windows PowerShell 5.1 or PowerShell 7):

  powershell -ExecutionPolicy Bypass -File scripts\task_c_decode.ps1 tune
      all 11 tuning runs, back to back (folds 0-2, 93 clips)
  powershell -ExecutionPolicy Bypass -File scripts\task_c_decode.ps1 compare
      each tuning run vs c2-base (paired bootstrap)
  powershell -ExecutionPolicy Bypass -File scripts\task_c_decode.ps1 combined -Settings beam8,vad
      protocol rule 4: one tuning run with several helpful settings together
  powershell -ExecutionPolicy Bypass -File scripts\task_c_decode.ps1 report -Settings beam8
      final setting + baseline on the report folds (3-4, 62 clips), scored once
      (-Settings base when no setting helped: only the baseline is decoded)

C3 (system combination, no decoding; docs/TUNING_PROTOCOL.md "C3"):

  .\scripts\task_c_decode.ps1 c3-combine
      builds the incumbent c3-ftg7-breaks and the 9 combinations c3-<method>-<set>
  .\scripts\task_c_decode.ps1 c3-tune
      scores all 9 on the tuning folds -> reports\baselines\c3-tune.json
  .\scripts\task_c_decode.ps1 c3-report -Settings c3-rover-order-s4
      the chosen combination, once, on the report folds (overall and per speaker)

Add -DryRun to any stage to print the commands without running them.
Setting names for -Settings: prompt-none prompt-p1 prompt-p2 beam1 beam8 vad rep1.1
notempfb lang-en lang-es.

A run whose reports\baselines\<run>.json already exists is skipped, so an interrupted
sweep can be restarted. Needs artifacts\models\ft-g7\, the dev set, and the fold files
(docs/WORK_SPLIT.md, C1). Set $env:MODEL or $env:THREADS to override the defaults; the
protocol fixes 8 threads, so keep that unless you record a deviation.

This file is kept ASCII-only on purpose: Windows PowerShell 5.1 reads a .ps1 without a
byte-order mark in the ANSI code page, which would corrupt accented characters. The
prompts are built from character codes instead, and checked against the SHA-256 that
whisper_baseline.py records, before anything runs.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [ValidateSet('tune', 'compare', 'combined', 'report', 'c3-combine', 'c3-tune', 'c3-report')]
    [string]$Stage,
    [string[]]$Settings = @(),
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)

$Model = if ($env:MODEL) { $env:MODEL } else { 'artifacts/models/ft-g7' }
$Threads = if ($env:THREADS) { $env:THREADS } else { '8' }
$Tune = 'data/processed/folds/tune.txt'
$Report = 'data/processed/folds/report.txt'

# --- prompts -----------------------------------------------------------------------------
$iq = [char]0x00BF  # inverted question mark
$a = [char]0x00E1; $e = [char]0x00E9; $i = [char]0x00ED; $o = [char]0x00F3; $n = [char]0x00F1
$Prompts = @{
    P0 = "Hola, ${iq}c${o}mo est${a}s? I'm good, gracias. Vamos a la tienda later, okay?"
    P1 = "So, ${iq}qu${e} hiciste ayer? Nada, I just stayed home y vi una pel${i}cula."
    P2 = "Mi mam${a} dice que, you know, tenemos que ir al doctor ma${n}ana. Okay, pero after work."
}
$PromptSha256 = @{
    P0 = 'c44393b079a8e80f96f323d97983005f0e913c95f1981c766cfa8c8be1a8321d'  # the existing ft-g7 run
    P1 = '5ef08a06e74cf4f39f677824adff03f77e97b98c15198df53e978fb56edad9ee'
    P2 = '86cb503d9a7ded565d44ddf248d5ab9c988f1705d1dd146c5379008ee6c75eb0'
}

function Get-Sha256([string]$Text) {
    $sha = [System.Security.Cryptography.SHA256]::Create()
    $bytes = $sha.ComputeHash([System.Text.Encoding]::UTF8.GetBytes($Text))
    return -join ($bytes | ForEach-Object { $_.ToString('x2') })
}
foreach ($key in $Prompts.Keys) {
    if ((Get-Sha256 $Prompts[$key]) -ne $PromptSha256[$key]) {
        throw "prompt $key does not match its pinned SHA-256; do not run (encoding problem?)"
    }
}

# --- settings: each changes one row of the baseline (docs/TUNING_PROTOCOL.md) -------------
$Baseline = @{ Language = 'auto'; Beam = 5; Prompt = 'P0'; Flags = @() }
$SettingTable = [ordered]@{
    'prompt-none' = @{ Row = 'prompt';      Prompt = 'none' }
    'prompt-p1'   = @{ Row = 'prompt';      Prompt = 'P1' }
    'prompt-p2'   = @{ Row = 'prompt';      Prompt = 'P2' }
    'beam1'       = @{ Row = 'beam';        Beam = 1 }
    'beam8'       = @{ Row = 'beam';        Beam = 8 }
    'vad'         = @{ Row = 'vad';         Flags = @('--vad-filter') }
    'rep1.1'      = @{ Row = 'repetition';  Flags = @('--repetition-penalty', '1.1') }
    'notempfb'    = @{ Row = 'temperature'; Flags = @('--no-temperature-fallback') }
    'lang-en'     = @{ Row = 'language';    Language = 'en' }
    'lang-es'     = @{ Row = 'language';    Language = 'es' }
}

function Get-Config([string[]]$Names) {
    $config = @{ Language = $Baseline.Language; Beam = $Baseline.Beam
                 Prompt = $Baseline.Prompt; Flags = @() }
    $rows = @{}
    foreach ($name in $Names) {
        if (-not $SettingTable.Contains($name)) {
            throw "unknown setting '$name'; choose from: $($SettingTable.Keys -join ', ')"
        }
        $setting = $SettingTable[$name]
        if ($rows.ContainsKey($setting.Row)) {
            throw "'$name' and '$($rows[$setting.Row])' change the same setting ($($setting.Row))"
        }
        $rows[$setting.Row] = $name
        if ($setting.ContainsKey('Language')) { $config.Language = $setting.Language }
        if ($setting.ContainsKey('Beam')) { $config.Beam = $setting.Beam }
        if ($setting.ContainsKey('Prompt')) { $config.Prompt = $setting.Prompt }
        if ($setting.ContainsKey('Flags')) { $config.Flags += $setting.Flags }
    }
    return $config
}

function Invoke-Uv([string[]]$Arguments, [switch]$AllowFailure) {
    if ($DryRun) {
        $shown = $Arguments | ForEach-Object { if ($_ -match '\s') { "`"$_`"" } else { $_ } }
        Write-Host "uv $($shown -join ' ')"
        return
    }
    & uv @Arguments
    if ($LASTEXITCODE -ne 0 -and -not $AllowFailure) {
        throw "command failed with exit code ${LASTEXITCODE}: uv $($Arguments -join ' ')"
    }
}

function Invoke-Decode([string]$RunName, [string]$IdsFile, [hashtable]$Config) {
    if (Test-Path "reports/baselines/$RunName.json") {
        Write-Host "skip $RunName (report exists)"
        return
    }
    Write-Host "=== $RunName  ($(Get-Date -Format 'HH:mm:ss'))"
    $arguments = @('run', '--no-sync', 'python', 'scripts/whisper_baseline.py',
                   '--model', $Model, '--compute-type', 'int8', '--threads', $Threads,
                   '--ids', "@$IdsFile", '--run-name', $RunName,
                   '--language', $Config.Language, '--beam-size', [string]$Config.Beam)
    if ($Config.Prompt -ne 'none') { $arguments += @('--initial-prompt', $Prompts[$Config.Prompt]) }
    $arguments += $Config.Flags
    Invoke-Uv $arguments
}

function Assert-Exists([string[]]$Paths) {
    foreach ($path in $Paths) { if (-not (Test-Path $path)) { throw "missing: $path" } }
}

function Invoke-Compare([string]$Candidate, [string]$Incumbent) {
    Invoke-Uv @('run', '--no-sync', 'python', 'scripts/compare_matched.py', $Candidate, $Incumbent) -AllowFailure
}

# --- C3: combinations of existing full-dev runs (docs/TUNING_PROTOCOL.md, "C3") -------------
$FtG7 = 'ft-g7-turbo-auto-int8-b5-prompt'
$C3Incumbent = 'c3-ftg7-breaks'
$C3Rule = 'sentence-breaks-keep-ellipsis'
$C3Sets = [ordered]@{
    s3 = @($FtG7, 'large-v3-turbo-auto-int8-b5-prompt-guard', 'Qwen3-ASR-1.7B-auto-cpu-float32-ctx')
    s4 = @($FtG7, 'large-v3-turbo-auto-int8-b5-prompt-guard', 'Qwen3-ASR-1.7B-es-cpu-float32',
           'Qwen3-ASR-1.7B-en-cpu-float32')
    s5 = @($FtG7, 'ft-s2-turbo-auto-int8-b5-prompt', 'large-v3-turbo-auto-int8-b5-prompt-guard',
           'Qwen3-ASR-1.7B-auto-cpu-float32-ctx', 'Qwen3-ASR-1.7B-es-cpu-float32')
}
$C3Methods = @('mbr', 'rover-backbone', 'rover-order')
$C3Names = @(foreach ($set in $C3Sets.Keys) { foreach ($method in $C3Methods) { "c3-$method-$set" } })

function Assert-Predictions([string[]]$Runs) {
    $missing = @()
    foreach ($run in $Runs) {
        foreach ($suffix in @('.csv', '.reference.csv')) {
            if (-not (Test-Path "data/interim/predictions/$run$suffix")) { $missing += "$run$suffix" }
        }
    }
    if ($missing.Count) {
        throw "missing shared predictions in data\interim\predictions: $($missing -join ', ')"
    }
}

if (-not $DryRun -and -not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw 'uv is not on PATH; install it and open a new PowerShell window'
}

switch ($Stage) {
    'tune' {
        if ($Settings.Count) { throw "tune runs every setting; -Settings is for 'combined' and 'report'" }
        if (-not $DryRun) { Assert-Exists @($Model, $Tune) }
        Invoke-Decode 'c2-base' $Tune (Get-Config @())
        foreach ($name in $SettingTable.Keys) {
            Invoke-Decode "c2-$name" $Tune (Get-Config @($name))
        }
    }
    'compare' {
        # Reproducibility check first: the re-run baseline vs the existing full-dev run.
        Invoke-Compare 'c2-base' 'ft-g7-turbo-auto-int8-b5-prompt'
        foreach ($run in @($SettingTable.Keys | ForEach-Object { "c2-$_" }) + 'c2-combined') {
            if ($DryRun -or (Test-Path "reports/baselines/$run.json")) { Invoke-Compare $run 'c2-base' }
        }
    }
    'combined' {
        if ($Settings.Count -lt 2) { throw 'combined needs two or more settings, e.g. -Settings beam8,vad' }
        if (-not $DryRun) { Assert-Exists @($Model, $Tune) }
        Invoke-Decode 'c2-combined' $Tune (Get-Config $Settings)
        Invoke-Compare 'c2-combined' 'c2-base'
    }
    'report' {
        if (-not $Settings.Count) { throw 'report needs the chosen setting(s), e.g. -Settings beam8 (or -Settings base)' }
        if (-not $DryRun) { Assert-Exists @($Model, $Report) }
        if ($Settings.Count -eq 1 -and $Settings[0] -eq 'base') {
            # Selection rule 2: nothing helped, so the baseline is the final setting.
            Invoke-Decode 'c2-base-report' $Report (Get-Config @())
            Write-Host 'final setting = baseline; its report-fold score is in reports/baselines/c2-base-report.json'
            return
        }
        $final = Get-Config $Settings  # validates the names before any decode starts
        Invoke-Decode 'c2-base-report' $Report (Get-Config @())
        Invoke-Decode 'c2-final-report' $Report $final
        Invoke-Compare 'c2-final-report' 'c2-base-report'
    }
    'c3-combine' {
        $inputs = @($C3Sets.Values | ForEach-Object { $_ }) | Sort-Object -Unique
        if (-not $DryRun) { Assert-Predictions $inputs; Assert-Exists @('data/raw/dev/enspa_dev/metadata.tsv') }
        if (Test-Path "reports/baselines/$C3Incumbent.json") {
            Write-Host "skip $C3Incumbent (report exists)"
        } else {
            Write-Host "=== $C3Incumbent"
            Invoke-Uv @('run', '--no-sync', 'python', 'scripts/combine_runs.py', $FtG7,
                        '--name', $C3Incumbent, '--method', $C3Rule)
        }
        foreach ($set in $C3Sets.Keys) {
            foreach ($method in $C3Methods) {
                $name = "c3-$method-$set"
                if (Test-Path "reports/baselines/$name.json") { Write-Host "skip $name (report exists)"; continue }
                Write-Host "=== $name"
                Invoke-Uv (@('run', '--no-sync', 'python', 'scripts/combine_runs.py') + $C3Sets[$set] +
                           @('--name', $name, '--method', $method, '--preprocess', $C3Rule))
            }
        }
        Write-Host 'Full-dev WERs above include the report folds: do not choose from them. Next: c3-tune'
    }
    'c3-tune' {
        if (-not $DryRun) { Assert-Exists @($Tune) }
        Invoke-Uv (@('run', '--no-sync', 'python', 'scripts/score_folds.py') + $C3Names +
                   @('--incumbent', $C3Incumbent, '--ids', "@$Tune",
                     '--output', 'reports/baselines/c3-tune.json'))
    }
    'c3-report' {
        if ($Settings.Count -ne 1 -or $C3Names -notcontains $Settings[0]) {
            throw "c3-report needs the one chosen combination, e.g. -Settings c3-rover-order-s4; choose from: $($C3Names -join ', ')"
        }
        if (-not $DryRun) { Assert-Exists @($Report) }
        $chosen = $Settings[0]
        # Headline: the combination's own gain, against ft-g7 with the same post-processing.
        Invoke-Uv @('run', '--no-sync', 'python', 'scripts/score_folds.py', $chosen,
                    '--incumbent', $C3Incumbent, '--ids', "@$Report", '--by-speaker',
                    '--output', 'reports/baselines/c3-report.json')
        # Secondary: total gain over C2's final setting (post-processing + combination).
        Invoke-Uv @('run', '--no-sync', 'python', 'scripts/score_folds.py', $chosen,
                    '--incumbent', $FtG7, '--ids', "@$Report", '--allow-mismatch',
                    '--output', 'reports/baselines/c3-report-vs-plain.json')
    }
}
