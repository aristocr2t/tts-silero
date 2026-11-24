"""Настройки голоса по умолчанию из ~/.config/tts-silero.json.

Секция `voice` задаёт параметры синтеза, чтобы не повторять их в командной
строке. Приоритет: аргументы CLI > переменные окружения > конфиг > встроенные
значения. Модуль печатает строки `ключ=значение` для bash-обёртки; некорректные
значения пропускаются, чтобы опечатка в конфиге не ломала озвучку.

{
  "voice": {
    "speaker": "eugene",
    "rate": "medium",
    "pitch": "medium",
    "sample_rate": 48000,
    "tempo": 1,
    "pitch_shift": 1,
    "chunk": 900,
    "pause": 2
  }
}
"""

import sys

from .config import find_config_path, load_raw

RATES = ('x-slow', 'slow', 'medium', 'fast', 'x-fast')
PITCHES = ('x-low', 'low', 'medium', 'high', 'x-high')
SPEAKERS = ('eugene', 'aidar', 'baya', 'kseniya', 'xenia')
SAMPLE_RATES = (8000, 24000, 48000)

# ключ конфига -> проверка значения
FIELDS = (
  ('speaker', lambda value: isinstance(value, str) and value in SPEAKERS),
  ('rate', lambda value: isinstance(value, str) and value in RATES),
  ('pitch', lambda value: isinstance(value, str) and value in PITCHES),
  ('sample_rate', lambda value: is_choice(value, SAMPLE_RATES)),
  ('tempo', lambda value: is_number(value, 0.5, 2.0)),
  ('pitch_shift', lambda value: is_number(value, 1.0, 1.2)),
  ('chunk', lambda value: is_integer(value, 100, 900)),
  ('pause', lambda value: is_number(value, 0, 60)),
)


def is_choice(value: object, choices: tuple) -> bool:
  # Целое значение из списка; строка «24000» из конфига тоже принимается.
  if isinstance(value, bool):
    return False

  if isinstance(value, int):
    return value in choices

  return isinstance(value, str) and value.isdigit() and int(value) in choices


def is_number(value: object, minimum: float, maximum: float) -> bool:
  # Число в диапазоне; строки с запятой тоже принимаются.
  if isinstance(value, bool):
    return False

  candidate = value.replace(',', '.') if isinstance(value, str) else value

  try:
    number = float(candidate)
  except (TypeError, ValueError):
    return False

  return minimum <= number <= maximum


def is_integer(value: object, minimum: float, maximum: float) -> bool:
  # Целое число в диапазоне: 400.0 и «4e2» подходят, 400.5 — нет.
  if isinstance(value, bool):
    return False

  candidate = value.replace(',', '.') if isinstance(value, str) else value

  try:
    number = float(candidate)
  except (TypeError, ValueError):
    return False

  return number.is_integer() and minimum <= number <= maximum


def find_voice_section() -> dict:
  # Секция voice из конфига; отсутствие или порча дают пустой словарь.
  section = load_raw().get('voice')

  return section if isinstance(section, dict) else {}


def collect_defaults() -> list[tuple[str, str]]:
  # Пары «ключ bash = значение» для корректных полей конфига.
  section = find_voice_section()
  pairs = []

  for config_key, check in FIELDS:
    if config_key not in section:
      continue

    value = section[config_key]

    if not check(value):
      print(f'[voice] конфиг: {config_key}={value!r} пропущено', file=sys.stderr)

      continue

    text = str(value).replace(',', '.')

    if config_key == 'chunk':
      text = str(int(float(text)))

    pairs.append((config_key, text))

  return pairs


def main() -> int:
  # Печатает настройки для bash: по строке `ключ=значение`.
  for key, value in collect_defaults():
    print(f'{key}={value}')

  return 0


if __name__ == '__main__':
  sys.exit(main())
