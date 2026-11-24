@echo off
rem Точка входа для Windows: выбирает интерпретатор, проверяет версию и
rem зависимости, затем запускает тот же lib\tts\cli.py, что и bin/voice.
rem
rem Интерпретатор: VOICE_PYTHON -> .venv\Scripts\python.exe -> python -> py -3.

setlocal enabledelayedexpansion

set "TTS_ROOT=%~dp0.."
set "PYTHONPATH=%TTS_ROOT%\lib"
set "PYTHONWARNINGS=ignore"
rem русская справка и пути: консоль Windows по умолчанию cp1252
set "PYTHONUTF8=1"

if defined VOICE_PYTHON (
  if not exist "%VOICE_PYTHON%" (
    echo voice: VOICE_PYTHON не найден: %VOICE_PYTHON%>&2
    exit /b 2
  )
  set "PY_QUOTED="%VOICE_PYTHON%""
  goto :checked
)

if exist "%TTS_ROOT%\.venv\Scripts\python.exe" (
  set "PY_QUOTED="%TTS_ROOT%\.venv\Scripts\python.exe""
  goto :checked
)

where python >nul 2>nul
if not errorlevel 1 (
  set "PY_QUOTED=python"
  goto :checked
)

where py >nul 2>nul
if not errorlevel 1 (
  set "PY_QUOTED=py -3"
  goto :checked
)

echo voice: Python не найден; установите Python 3.10+ и зависимости из requirements.txt>&2
exit /b 2

:checked
%PY_QUOTED% -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" 2>nul
if errorlevel 1 (
  echo voice: %PY_QUOTED% старше Python 3.10>&2
  exit /b 2
)

%PY_QUOTED% -c "import eng_to_ipa, numpy, soundfile, silero" 2>nul
if errorlevel 1 (
  echo voice: в %PY_QUOTED% нет зависимостей: %PY_QUOTED% -m pip install -r %TTS_ROOT%\requirements.txt>&2
  exit /b 2
)

%PY_QUOTED% -m tts.cli %*
exit /b %ERRORLEVEL%
