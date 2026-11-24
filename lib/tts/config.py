"""Пользовательский словарь произношения из ~/.config/tts-silero.json.

Файл необязателен: без него работают только встроенные словари. Формат:

{
  "words": {
    "geekideas": "гикайдиас"
  },
  "replacements": [
    ["кованый замок", "кованый зам+ок"]
  ]
}

`words` — произношение латиницы и аббревиатур (как WORDS в latin.py),
`replacements` — регулярные выражения по русскому тексту (как замены
pronounce_russian); метка «+» ставит ударение. VOICE_CONFIG подменяет путь.
"""

import json
import os
import re
import sys
from pathlib import Path

DEFAULT_CONFIG_PATH = Path.home() / '.config' / 'tts-silero.json'

_raw_cache: dict[tuple[str, int, int], dict] = {}
_custom_cache: dict[tuple[str, int, int], tuple[dict[str, str], tuple[tuple[str, str], ...]]] = {}
_broken_patterns: set[str] = set()


def find_config_path() -> Path:
  # Путь к конфигу: VOICE_CONFIG, иначе ~/.config/tts-silero.json.
  override = os.environ.get('VOICE_CONFIG')

  return Path(override).expanduser() if override else DEFAULT_CONFIG_PATH


def cache_key(path: Path) -> tuple[str, int, int]:
  # Ключ кеша: путь, версия изменения и размер — правка в ту же секунду тоже видна.
  stat = path.stat()

  return str(path), stat.st_mtime_ns, stat.st_size


def load_raw() -> dict:
  # Сырой конфиг целиком; отсутствие или порча файла дают пустой словарь.
  path = find_config_path()

  try:
    key = cache_key(path)
  except OSError:
    return {}

  cached = _raw_cache.get(key)

  if cached is not None:
    return cached

  try:
    raw = json.loads(path.read_text(encoding='utf-8'))
  except (OSError, json.JSONDecodeError) as err:
    print(f'[voice] конфиг {path} не прочитан: {err}', file=sys.stderr)
    _raw_cache.clear()
    _raw_cache[key] = {}

    return {}

  if not isinstance(raw, dict):
    print(f'[voice] конфиг {path}: ожидался объект', file=sys.stderr)
    _raw_cache.clear()
    _raw_cache[key] = {}

    return {}

  _raw_cache.clear()
  _raw_cache[key] = raw

  return raw


def load_custom() -> tuple[dict[str, str], tuple[tuple[str, str], ...]]:
  # Слова и замены из конфига; порядок пар сохраняется.
  path = find_config_path()

  try:
    key = cache_key(path)
  except OSError:
    return {}, ()

  cached = _custom_cache.get(key)

  if cached is not None:
    return cached

  raw = load_raw()
  custom = (parse_words(raw), parse_replacements(raw))

  _custom_cache.clear()
  _custom_cache[key] = custom

  return custom


def parse_words(raw: dict) -> dict[str, str]:
  # Секция words: слово в нижнем регистре -> как произносить.
  section = raw.get('words')

  if not isinstance(section, dict):
    return {}

  return {
    str(word).lower(): str(spoken)
    for word, spoken in section.items()
    if str(word).strip() and str(spoken).strip()
  }


def parse_replacements(raw: dict) -> tuple[tuple[str, str], ...]:
  # Секция replacements: пары [шаблон, замена], порядок сохраняется.
  section = raw.get('replacements')

  if not isinstance(section, list):
    return ()

  pairs = []

  for pair in section:
    if not isinstance(pair, list) or len(pair) != 2:
      continue

    pattern, replacement = str(pair[0]), str(pair[1])

    if not pattern or not replacement:
      continue

    try:
      re.compile(pattern)
    except re.error as err:
      if pattern not in _broken_patterns:          # одна диагностика на шаблон
        _broken_patterns.add(pattern)
        print(f'[voice] конфиг: замена {pattern!r} пропущена: {err}', file=sys.stderr)

      continue

    pairs.append((pattern, replacement))

  return tuple(pairs)
