# GameLink Agent bootstrap: make a fresh clone runnable without manual setup.
#
# Responsibilities:
#   1. find a usable Python (>= 3.10, < 3.15), or install a private copy under .python
#   2. (re)create the .venv when it is missing or broken
#   3. install the package with every optional dependency (CLI + local web UI)
#
# gla.cmd only calls this when the existing .venv cannot import the full
# dependency set, so the normal fast path never pays for PowerShell startup.

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$Root = Split-Path -Parent $PSScriptRoot
$VenvDir = Join-Path $Root '.venv'
$VenvPy = Join-Path $VenvDir 'Scripts\python.exe'
$LocalPythonDir = Join-Path $Root '.python'
$LocalPython = Join-Path $LocalPythonDir 'python.exe'
$DownloadDir = Join-Path $Root '.bootstrap'
$PythonVersion = '3.12.10'

function Write-Step([string]$Message) {
    Write-Host "[GameLink Agent] $Message"
}

function Write-Fail([string]$Message) {
    [Console]::Error.WriteLine("[GameLink Agent] ERROR: $Message")
}

# Native programs routinely write progress/warnings to stderr. Windows
# PowerShell 5.1 turns that into a terminating error while
# $ErrorActionPreference is 'Stop', so every native call goes through one of
# these two helpers and we judge success by the exit code instead.
function Invoke-NativeVisible([string]$Exe, [string[]]$Arguments) {
    $previous = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        & $Exe @Arguments | Out-Host
        return $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previous
    }
}

function Invoke-NativeQuiet([string]$Exe, [string[]]$Arguments) {
    $previous = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        & $Exe @Arguments 2>$null 1>$null
        return $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previous
    }
}

# The project targets Python >= 3.10 and is tested through 3.14.
function Test-Interpreter([string]$Exe, [string[]]$Prefix) {
    if (-not (Test-Path -LiteralPath $Exe)) { return $false }
    $probe = 'import sys; raise SystemExit(0 if (3, 10) <= sys.version_info < (3, 15) else 1)'
    $code = Invoke-NativeQuiet $Exe (@($Prefix) + @('-c', $probe))
    return ($code -eq 0)
}

function Find-SystemPython {
    if ($env:GAMELINK_BOOTSTRAP_IGNORE_SYSTEM_PYTHON -eq '1') { return $null }
    $tries = @(
        @{ Exe = 'py'; Prefix = @('-3.12') },
        @{ Exe = 'py'; Prefix = @('-3.11') },
        @{ Exe = 'py'; Prefix = @('-3.13') },
        @{ Exe = 'py'; Prefix = @('-3.10') },
        @{ Exe = 'py'; Prefix = @('-3.14') },
        @{ Exe = 'py'; Prefix = @('-3') },
        @{ Exe = 'python'; Prefix = @() },
        @{ Exe = 'python3'; Prefix = @() }
    )
    foreach ($candidate in $tries) {
        $command = Get-Command $candidate.Exe -ErrorAction SilentlyContinue
        if ($null -eq $command) { continue }
        $exe = $command.Source
        # Skip the Microsoft Store execution alias: running it opens the Store
        # instead of a Python interpreter.
        if ($exe -like '*\WindowsApps\python*.exe') { continue }
        if (Test-Interpreter -Exe $exe -Prefix $candidate.Prefix) {
            return @{ Exe = $exe; Prefix = $candidate.Prefix }
        }
    }
    return $null
}

function Install-PrivatePython {
    $arch = 'amd64'
    if ($env:PROCESSOR_ARCHITECTURE -eq 'ARM64') { $arch = 'arm64' }
    $name = "python-$PythonVersion-$arch.exe"
    $url = "https://www.python.org/ftp/python/$PythonVersion/$name"
    $installer = Join-Path $DownloadDir $name

    Write-Step "Python 3.10+ not found; downloading Python $PythonVersion ($arch, about 26 MB) ..."
    New-Item -ItemType Directory -Force -Path $DownloadDir | Out-Null
    try {
        Invoke-WebRequest -Uri $url -OutFile $installer -UseBasicParsing
    } catch {
        throw ("Could not download Python. Install Python 3.10+ from https://www.python.org/downloads/ " +
               "then run gla.cmd again. ($($_.Exception.Message))")
    }

    $signature = Get-AuthenticodeSignature -FilePath $installer
    if ($signature.Status -ne 'Valid') {
        throw 'The downloaded Python installer failed signature verification; refusing to run it.'
    }
    if ($signature.SignerCertificate.Subject -notmatch 'Python Software Foundation') {
        throw 'The downloaded Python installer is not signed by the Python Software Foundation; refusing to run it.'
    }

    Write-Step "Installing a private Python into .python (no admin rights, system PATH untouched) ..."
    $installArgs = @(
        '/quiet',
        'InstallAllUsers=0',
        "TargetDir=$LocalPythonDir",
        'Include_pip=1',
        'Include_launcher=0',
        'Include_test=0',
        'Include_doc=0',
        'Include_tcltk=0',
        'Include_tools=0',
        'Shortcuts=0',
        'AssociateFiles=0',
        'PrependPath=0'
    )
    Invoke-NativeVisible $installer $installArgs | Out-Null
    if (-not (Test-Path -LiteralPath $LocalPython)) {
        throw "The Python installer did not produce $LocalPython."
    }
    if (-not (Test-Interpreter -Exe $LocalPython -Prefix @())) {
        throw "The private Python at $LocalPython is not usable."
    }
    return @{ Exe = $LocalPython; Prefix = @() }
}

function Resolve-Python {
    if (Test-Interpreter -Exe $LocalPython -Prefix @()) {
        return @{ Exe = $LocalPython; Prefix = @() }
    }
    $system = Find-SystemPython
    if ($null -ne $system) { return $system }
    return Install-PrivatePython
}

try {
    $venvUsable = Test-Interpreter -Exe $VenvPy -Prefix @()
    if (-not $venvUsable -and (Test-Path -LiteralPath $VenvDir)) {
        Write-Step 'The existing .venv is not usable on this machine; rebuilding it ...'
        try {
            Remove-Item -LiteralPath $VenvDir -Recurse -Force
        } catch {
            throw ("Could not remove the broken .venv; close any running gla/web process and retry. " +
                   "($($_.Exception.Message))")
        }
    }

    if (-not $venvUsable) {
        $python = Resolve-Python
        Write-Step 'Creating the virtual environment (.venv) ...'
        $prefix = @($python.Prefix)
        $code = Invoke-NativeVisible $python.Exe ($prefix + @('-m', 'venv', $VenvDir))
        if ($code -ne 0 -or -not (Test-Path -LiteralPath $VenvPy)) {
            throw "Could not create the virtual environment with $($python.Exe)."
        }
    }

    $importProbe = 'import gamelink, fastapi, uvicorn'
    $code = Invoke-NativeQuiet $VenvPy @('-c', $importProbe)
    if ($code -ne 0) {
        Write-Step 'Installing dependencies (needs network, may take a minute) ...'
        $code = Invoke-NativeVisible $VenvPy @(
            '-m', 'pip', 'install', '--disable-pip-version-check', '--upgrade', 'pip'
        )
        if ($code -ne 0) {
            Write-Step 'Could not upgrade pip; continuing with the bundled version.'
        }
        Push-Location $Root
        try {
            $code = Invoke-NativeVisible $VenvPy @(
                '-m', 'pip', 'install', '--disable-pip-version-check', '-e', '.[web]'
            )
        } finally {
            Pop-Location
        }
        if ($code -ne 0) {
            throw ("Dependency installation failed. Check the network/proxy, then run: " +
                   ".venv\Scripts\python -m pip install -e `".[web]`"")
        }
        $code = Invoke-NativeQuiet $VenvPy @('-c', $importProbe)
        if ($code -ne 0) {
            throw 'Dependencies were installed but the package still cannot be imported.'
        }
        Write-Step 'Setup complete.'
    }
} catch {
    Write-Fail $_.Exception.Message
    exit 1
}

exit 0
