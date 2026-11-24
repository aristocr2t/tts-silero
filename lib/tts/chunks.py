"""Деление текста на куски для синтеза.

Silero синтезирует кусками: длинная фраза разваливается по внутренним лимитам,
а книга целиком не влезает в память. Режем по границам предложений, длинное
предложение — по словам, чтобы кусок не превышал max_chars.
"""

import re

from .units import UNITS

DEFAULT_CHUNK_CHARS = 900
SENTENCE_END = re.compile(r'(?<=[.!?…])\s+')
SPACES = re.compile(r'[ \t\u00a0]+')
# тысячи пробелом и пара «число + единица» не должны попасть на границу кусков
GROUPED_INTEGER = re.compile(r'(?<=\d)[ \u00a0](?=\d{3}(?!\d))')
NUMBER_UNIT_SPACE = re.compile(
  r'(?<=\d)[ \u00a0](?='
  + '|'.join(re.escape(unit) for unit in sorted(UNITS, key=len, reverse=True))
  + r'(?![A-Za-zА-Яа-яЁё0-9/]))',
)


def split_text(text: str, max_chars: int = DEFAULT_CHUNK_CHARS) -> list[str]:
  # Делит текст на куски не длиннее max_chars, сохраняя порядок слов.
  if max_chars < 1:
    raise ValueError(f'max_chars должен быть положительным, получено {max_chars}')

  chunks: list[str] = []
  pending = ''

  for paragraph in text.splitlines():
    line = SPACES.sub(' ', paragraph).strip()

    if not line:
      continue

    line = _protect_numbers(line)

    for sentence in SENTENCE_END.split(line):
      for piece in _split_sentence(sentence, max_chars):
        candidate = f'{pending} {piece}'.strip()

        if len(candidate) <= max_chars:
          pending = candidate

          continue

        if pending:
          chunks.append(pending)

        pending = piece

  if pending:
    chunks.append(pending)

  return [chunk.replace('\u00a0', ' ') for chunk in chunks]


def _protect_numbers(line: str) -> str:
  # Склеивает число с его разрядом и единицей неразрывным пробелом.
  line = GROUPED_INTEGER.sub('\u00a0', line)

  return NUMBER_UNIT_SPACE.sub('\u00a0', line)


def _split_sentence(sentence: str, max_chars: int) -> list[str]:
  # Одно предложение -> куски по max_chars: сначала по словам, потом жёстко.
  if len(sentence) <= max_chars:
    return [sentence]

  pieces: list[str] = []
  pending = ''

  for word in sentence.split(' '):
    candidate = f'{pending} {word}'.strip()

    if len(candidate) <= max_chars:
      pending = candidate

      continue

    if pending:
      pieces.append(pending)

    while len(word) > max_chars:
      pieces.append(word[:max_chars])
      word = word[max_chars:]

    pending = word

  if pending:
    pieces.append(pending)

  return pieces
