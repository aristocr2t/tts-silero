# Установка tts-silero в Windows: клонирует репозиторий, собирает venv,
# кладёт запускатор voice.cmd в PATH и проверяет voice --help.
#
#   irm https://raw.githubusercontent.com/aristocr2t/tts-silero/main/install.ps1 | iex
#
# Переменные окружения:
#   TTS_SILERO_DIR     куда ставить (по умолчанию %LOCALAPPDATA%\tts-silero)
#   TTS_SILERO_BIN     куда положить запускатор (по умолчанию %LOCALAPPDATA%\Microsoft\WindowsApps)
#   TTS_SILERO_PYTHON  готовый интерпретатор с зависимостями, venv не создаётся
#   TTS_SILERO_REPO    адрес репозитория (по умолчанию github.com/aristocr2t/tts-silero)
#   TTS_SILERO_REF     ветка или тег (по умолчанию main)
#   TTS_SILERO_SOURCE  локальная копия вместо клонирования

$ErrorActionPreference = 'Stop'

$InstallDir = if ($env:TTS_SILERO_DIR) { $env:TTS_SILERO_DIR } else { Join-Path $env:LOCALAPPDATA 'tts-silero' }
$BinDir = if ($env:TTS_SILERO_BIN) { $env:TTS_SILERO_BIN } else { Join-Path $env:LOCALAPPDATA 'Microsoft\WindowsApps' }
$PythonPath = $env:TTS_SILERO_PYTHON
$RepoUrl = if ($env:TTS_SILERO_REPO) { $env:TTS_SILERO_REPO } else { 'https://github.com/aristocr2t/tts-silero.git' }
$RepoRef = if ($env:TTS_SILERO_REF) { $env:TTS_SILERO_REF } else { 'main' }

$SourceDir = Join-Path $InstallDir 'bin\voice.cmd'
$VenvDir = Join-Path $InstallDir '.venv'
$VenvPython = Join-Path $VenvDir 'Scripts\python.exe'


function Say {
  param([string]$Message)

  Write-Host "[tts-silero] $Message"
}


function Fail {
  param([string]$Message)

  Write-Host "[tts-silero] ошибка: $Message" -ForegroundColor Red

  exit 1
}


function Assert-Python {
  param([string]$Python)

  & $Python -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" 2>$null

  if ($LASTEXITCODE -ne 0) {
    Fail "$Python старше Python 3.10; нужен 3.10+"
  }
}


function Assert-Commands {
  $missing = @()

  if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) { $missing += 'ffmpeg' }
  if (-not (Get-Command git -ErrorAction SilentlyContinue)) { $missing += 'git' }

  if ($missing.Count -gt 0) {
    Fail ("не найдено: " + ($missing -join ', ') + '. Установите: winget install ' + ($missing -join ' '))
  }

  Say 'зависимости на месте'
}


function Get-Source {
  if ($env:TTS_SILERO_SOURCE) {
    $script:InstallDir = $env:TTS_SILERO_SOURCE
    $script:SourceDir = Join-Path $script:InstallDir 'bin\voice.cmd'
    $script:VenvDir = Join-Path $script:InstallDir '.venv'
    $script:VenvPython = Join-Path $script:VenvDir 'Scripts\python.exe'

    Say "использую локальный каталог $script:InstallDir"

    return
  }

  if (Test-Path (Join-Path $InstallDir '.git')) {
    Say "обновляю $InstallDir"

    if (git -C $InstallDir status --porcelain) {
      Fail "$InstallDir содержит незакоммиченные изменения; сохраните их или задайте TTS_SILERO_SOURCE"
    }

    git -C $InstallDir rev-parse --verify --quiet "origin/$RepoRef" *> $null

    if ($LASTEXITCODE -eq 0) {
      git -C $InstallDir fetch --quiet origin $RepoRef

      if ($LASTEXITCODE -ne 0) {
        Fail "git fetch не удался: $RepoRef"
      }

      $ahead = git -C $InstallDir rev-list --count "origin/$RepoRef..HEAD"

      if ($LASTEXITCODE -ne 0) {
        Fail "не удалось сравнить с origin/$RepoRef"
      }

      if ([int]$ahead -ne 0) {
        Fail "$InstallDir содержит локальные коммиты поверх origin/$RepoRef; сохраните их или задайте TTS_SILERO_SOURCE"
      }

      git -C $InstallDir checkout --quiet $RepoRef

      if ($LASTEXITCODE -ne 0) {
        Fail "не удалось переключиться на $RepoRef"
      }

      git -C $InstallDir reset --hard --quiet "origin/$RepoRef"
    } else {
      git -C $InstallDir fetch --quiet --tags origin

      if ($LASTEXITCODE -ne 0) {
        Fail 'git fetch --tags не удался'
      }

      $ahead = git -C $InstallDir rev-list --count "$RepoRef..HEAD"

      if ($LASTEXITCODE -ne 0) {
        Fail "не удалось сравнить с $RepoRef"
      }

      if ([int]$ahead -ne 0) {
        Fail "$InstallDir содержит коммиты поверх $RepoRef; сохраните их или задайте TTS_SILERO_SOURCE"
      }

      git -C $InstallDir checkout --quiet $RepoRef
    }

    if ($LASTEXITCODE -ne 0) {
      Fail "не удалось обновить $InstallDir до $RepoRef"
    }

    return
  }

  if (Test-Path $InstallDir) {
    Fail "$InstallDir уже существует и это не git-репозиторий; уберите каталог или задайте TTS_SILERO_DIR"
  }

  Say "клонирую в $InstallDir"

  New-Item -ItemType Directory -Force -Path (Split-Path $InstallDir) | Out-Null

  git clone --quiet --branch $RepoRef $RepoUrl $InstallDir

  if ($LASTEXITCODE -ne 0) {
    Fail "клон не удался: $RepoUrl"
  }
}


function New-Venv {
  param([string]$Path)

  if (Get-Command python -ErrorAction SilentlyContinue) {
    & python -m venv $Path
  } elseif (Get-Command py -ErrorAction SilentlyContinue) {
    & py -3 -m venv $Path
  } else {
    Fail 'не найден Python 3.10+; установите его с python.org или задайте TTS_SILERO_PYTHON'
  }

  if ($LASTEXITCODE -ne 0) {
    Fail "не удалось создать venv в $Path"
  }
}


function Install-Dependencies {
  if ($PythonPath) {
    Assert-Python $PythonPath

    Say "использую готовый интерпретатор $PythonPath"

    return
  }

  $requirements = Join-Path $InstallDir 'requirements.txt'

  if (Get-Command uv -ErrorAction SilentlyContinue) {
    Say 'создаю venv через uv'

    uv venv --quiet $VenvDir

    if ($LASTEXITCODE -ne 0) {
      Fail 'uv venv не удался'
    }

    uv pip install --quiet --python $VenvPython -r $requirements

    if ($LASTEXITCODE -ne 0) {
      Fail 'uv pip install не удался'
    }
  } else {
    Say 'создаю venv через python'

    New-Venv $VenvDir

    & $VenvPython -m pip install --quiet --upgrade pip
    & $VenvPython -m pip install --quiet -r $requirements

    if ($LASTEXITCODE -ne 0) {
      Fail 'pip install не удался'
    }
  }

  Assert-Python $VenvPython
}


function Write-Shim {
  param([string]$Path, [string]$Content)

  $encoding = [System.Text.Encoding]::ASCII

  if ($Content -match '[^\x20-\x7E]') {
    # кириллица в пути: cmd.exe читает .cmd в OEM-кодировке
    try {
      $encoding = [System.Text.Encoding]::GetEncoding(866)
    } catch {
      $encoding = [System.Text.Encoding]::Default
    }
  }

  [System.IO.File]::WriteAllText($Path, $Content, $encoding)
}


function Install-Shim {
  New-Item -ItemType Directory -Force -Path $BinDir | Out-Null

  $target = Join-Path $BinDir 'voice.cmd'

  if ((Test-Path $target) -and -not (Select-String -Path $target -Pattern ([regex]::Escape($SourceDir)) -Quiet)) {
    Fail "$target уже существует и указывает не на $SourceDir; уберите файл или задайте TTS_SILERO_BIN"
  }

  Write-Shim $target "@echo off`r`ncall `"$SourceDir`" %*"

  Say "запускатор: $target"
}


function Test-Install {
  $python = if ($PythonPath) { $PythonPath } else { $VenvPython }

  $env:VOICE_PYTHON = $python

  & $SourceDir --help *> $null

  if ($LASTEXITCODE -ne 0) {
    Fail 'проверка voice --help не прошла'
  }

  Say 'проверка voice --help прошла'
}


function Show-NextSteps {
  Say @'

Установлено. Дальше:

  voice "привет, это проверка"
  voice --file book.txt            # длинный текст целиком
  type file.txt | voice -          # текст из stdin

Если %LOCALAPPDATA%\Microsoft\WindowsApps не в PATH, добавьте его в переменную PATH.
'@

  if ($PythonPath) {
    Say "готовый интерпретатор прописан не будет: добавьте в профиль `$env:VOICE_PYTHON = '$PythonPath'"
  }
}


function Start-Install {
  Assert-Commands
  Get-Source
  Install-Dependencies
  Install-Shim
  Test-Install
  Show-NextSteps
}


Start-Install
