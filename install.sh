#!/usr/bin/env bash
# Установка tts-silero: клонирует репозиторий, собирает venv и кладёт ссылку в PATH.
#
#   curl -fsSL https://raw.githubusercontent.com/aristocr2t/tts-silero/main/install.sh | bash
#
# Переменные окружения:
#   TTS_SILERO_DIR     куда ставить (по умолчанию ~/.local/share/tts-silero)
#   TTS_SILERO_BIN     куда положить ссылку voice (по умолчанию ~/.local/bin)
#   TTS_SILERO_PYTHON  готовый интерпретатор с зависимостями, venv не создаётся
#   TTS_SILERO_REPO    адрес репозитория (по умолчанию github.com/aristocr2t/tts-silero)
#   TTS_SILERO_REF     ветка или тег (по умолчанию main)

set -euo pipefail

INSTALL_DIR="${TTS_SILERO_DIR:-$HOME/.local/share/tts-silero}"
BIN_DIR="${TTS_SILERO_BIN:-$HOME/.local/bin}"
PYTHON_PATH="${TTS_SILERO_PYTHON:-}"
REPO_URL="${TTS_SILERO_REPO:-https://github.com/aristocr2t/tts-silero.git}"
REPO_REF="${TTS_SILERO_REF:-main}"
MIN_PYTHON='3.10'

say() {
  printf '[tts-silero] %s\n' "$*"
}

fail() {
  printf '[tts-silero] ошибка: %s\n' "$*" >&2

  exit 1
}

check_python_version() {
  local python

  python=$1

  "$python" -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" \
    || fail "$python старше Python $MIN_PYTHON; нужен 3.10+"
}

require_commands() {
  local missing=''

  command -v ffmpeg >/dev/null || missing="$missing ffmpeg"
  command -v git >/dev/null || missing="$missing git"

  if [[ -z $PYTHON_PATH ]]; then
    command -v uv >/dev/null || command -v python3 >/dev/null || missing="$missing python3"
  fi

  if [[ -n $missing ]]; then
    fail "не найдено:$missing. macOS: brew install$missing; Debian/Ubuntu: sudo apt install$missing"
  fi

  say "зависимости на месте"
}

fetch_source() {
  if [[ -n ${TTS_SILERO_SOURCE:-} ]]; then
    INSTALL_DIR=$TTS_SILERO_SOURCE

    say "использую локальный каталог $INSTALL_DIR"

    return
  fi

  if [[ -d $INSTALL_DIR/.git ]]; then
    say "обновляю $INSTALL_DIR"

    if [[ -n $(git -C "$INSTALL_DIR" status --porcelain) ]]; then
      fail "$INSTALL_DIR содержит незакоммиченные изменения; сохраните их или задайте TTS_SILERO_SOURCE"
    fi

    if git -C "$INSTALL_DIR" rev-parse --verify --quiet "origin/$REPO_REF" >/dev/null; then
      git -C "$INSTALL_DIR" fetch --quiet origin "$REPO_REF"

      if [[ $(git -C "$INSTALL_DIR" rev-list --count "origin/$REPO_REF..HEAD") != 0 ]]; then
        fail "$INSTALL_DIR содержит локальные коммиты поверх origin/$REPO_REF; сохраните их или задайте TTS_SILERO_SOURCE"
      fi

      git -C "$INSTALL_DIR" checkout --quiet "$REPO_REF"
      git -C "$INSTALL_DIR" reset --hard --quiet "origin/$REPO_REF"
    else
      git -C "$INSTALL_DIR" fetch --quiet --tags origin

      if [[ $(git -C "$INSTALL_DIR" rev-list --count "$REPO_REF..HEAD") != 0 ]]; then
        fail "$INSTALL_DIR содержит коммиты поверх $REPO_REF; сохраните их или задайте TTS_SILERO_SOURCE"
      fi

      git -C "$INSTALL_DIR" checkout --quiet "$REPO_REF"
    fi

    return
  fi

  if [[ -e $INSTALL_DIR ]]; then
    fail "$INSTALL_DIR уже существует и это не git-репозиторий; уберите каталог или задайте TTS_SILERO_DIR"
  fi

  say "клонирую в $INSTALL_DIR"

  mkdir -p "$(dirname "$INSTALL_DIR")"
  git clone --quiet --branch "$REPO_REF" "$REPO_URL" "$INSTALL_DIR"
}

install_python_dependencies() {
  if [[ -n $PYTHON_PATH ]]; then
    check_python_version "$PYTHON_PATH"

    say "использую готовый интерпретатор $PYTHON_PATH"

    return
  fi

  local venv_dir

  venv_dir="$INSTALL_DIR/.venv"

  if command -v uv >/dev/null; then
    say "создаю venv через uv"

    uv venv --quiet "$venv_dir"
    uv pip install --quiet --python "$venv_dir/bin/python" -r "$INSTALL_DIR/requirements.txt"
  else
    say "создаю venv через python3"

    python3 -m venv "$venv_dir"
    "$venv_dir/bin/python" -m pip install --quiet --upgrade pip
    "$venv_dir/bin/python" -m pip install --quiet -r "$INSTALL_DIR/requirements.txt"
  fi

  check_python_version "$venv_dir/bin/python"
}

link_binary() {
  mkdir -p "$BIN_DIR"

  local target
  local current

  target="$BIN_DIR/voice"
  current=''

  if [[ -L $target ]]; then
    current=$(readlink "$target")
  elif [[ -e $target ]]; then
    fail "$target уже существует и это не символическая ссылка; уберите файл вручную"
  fi

  if [[ -n $current && $current != "$INSTALL_DIR/bin/voice" ]]; then
    fail "$target уже указывает на $current; уберите ссылку или задайте TTS_SILERO_BIN"
  fi

  ln -sfn "$INSTALL_DIR/bin/voice" "$target"

  say "ссылка: $target -> $INSTALL_DIR/bin/voice"
}

verify_install() {
  local python

  python="${PYTHON_PATH:-$INSTALL_DIR/.venv/bin/python}"

  VOICE_PYTHON="$python" "$INSTALL_DIR/bin/voice" --help >/dev/null \
    || fail "проверка voice --help не прошла"

  say "проверка voice --help прошла"
}

print_next_steps() {
  cat <<EOF

Установлено. Дальше:

  voice "привет, это проверка"
  voice --file book.txt            # длинный текст целиком
  printf 'строка' | voice -        # текст со stdin

Если $BIN_DIR не в PATH, добавьте его в профиль:

  export PATH="$BIN_DIR:\$PATH"
EOF

  if [[ -n $PYTHON_PATH ]]; then
    cat <<EOF

Готовый интерпретатор прописан не будет: добавьте в профиль

  export VOICE_PYTHON=$PYTHON_PATH
EOF
  fi
}

main() {
  require_commands
  fetch_source
  install_python_dependencies
  link_binary
  verify_install
  print_next_steps
}

main "$@"
