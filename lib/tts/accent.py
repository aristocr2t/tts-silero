"""Ударения по контексту через ruaccent, с тихим откатом на текст без разметки.

ruaccent ставит «+» перед ударной гласной — тот же формат, который понимает
Silero, и решает омографы по соседним словам. Слова, где он ошибается, задаются
собственными правилами произношения в latin.py: их текст уже размечен «+», и
ruaccent такие слова не переставляет.

Окружение:
  VOICE_ACCENT=0            выключить акцентуацию
  VOICE_ACCENT_MODEL        размер модели омографов (по умолчанию turbo3.1)
  VOICE_ACCENT_DEBUG=1      печатать причину отключения в stderr
"""

import os
import sys
from typing import Any

DEFAULT_ACCENT_MODEL = 'turbo3.1'
DISABLED_VALUES = ('0', 'off', 'false', 'no', '')

_accentizer = None
_load_failed = False


def accent_enabled() -> bool:
  # Читает VOICE_ACCENT на каждом вызове: модуль можно настраивать после импорта.
  return os.environ.get('VOICE_ACCENT', '1').lower() not in DISABLED_VALUES


def find_accentizer() -> Any:
  # Загружает ruaccent один раз за процесс; None — если пакета или моделей нет.
  global _accentizer, _load_failed

  if _accentizer is not None:
    return _accentizer

  if _load_failed or not accent_enabled():
    _load_failed = True

    return None

  try:
    # прогресс-бары huggingface в stderr не нужны: озвучка должна быть тихой
    os.environ.setdefault('HF_HUB_DISABLE_PROGRESS_BARS', '1')
    os.environ.setdefault('HF_HUB_DISABLE_TELEMETRY', '1')

    from ruaccent import RUAccent

    accentizer = RUAccent()
    accentizer.load(
      omograph_model_size=os.environ.get('VOICE_ACCENT_MODEL', DEFAULT_ACCENT_MODEL),
      use_dictionary=True,
    )
  except Exception as err:
    if os.environ.get('VOICE_ACCENT_DEBUG'):
      print(f'[voice] ruaccent отключён: {err}', file=sys.stderr)

    _load_failed = True

    return None

  _accentizer = accentizer

  return _accentizer


def accentize(text: str) -> str:
  # Расставляет ударения по контексту; при любой проблеме возвращает текст как есть.
  accentizer = find_accentizer()

  if accentizer is None:
    return text

  try:
    accented = accentizer.process_all(text)
  except Exception as err:
    if os.environ.get('VOICE_ACCENT_DEBUG'):
      print(f'[voice] ruaccent сбой: {err}', file=sys.stderr)

    return text

  return accented
