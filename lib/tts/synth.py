"""Синтез речи: текст со stdin -> один wav.

Модель Silero загружается один раз на весь текст. Текст режется на куски так,
чтобы каждый укладывался в предел движка (около 1000 символов), а кусок, на
котором синтез всё же упал, делится пополам и синтезируется по частям. Куски
пишутся в один открытый wav сразу, поэтому книга не занимает место дважды.

Пример:
  printf 'Привет, мир' | python -m tts.synth --voice xenia --output /tmp/p.wav
"""

import argparse
import html
import os
import sys
from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf

from .chunks import DEFAULT_CHUNK_CHARS, split_text
from .normalize import BREAK_TOKEN, to_cyrillic

CONFIG_DIR = Path(os.environ.get('XDG_CACHE_HOME', Path.home() / '.cache')) / 'silero'
SPEAKER_MODEL = ('ru', 'v5_5_ru')

# Silero предупреждает с 1000 символов и падает выше; держим запас.
# Это верхняя граница и для --chunk-chars: больше движок не примет.
MAX_MODEL_CHARS = 900
MIN_RETRY_CHARS = 80
SILENCE_SECONDS = 0.25
# пауза после английского слова выключена: SSML break ломает интонацию фразы
# (VOICE_BREAK_MS=120 включает обратно)
DEFAULT_BREAK_MS = 0


class SynthesisError(RuntimeError):
  # Кусок текста не озвучен: неполный результат отдавать нельзя.
  pass


def build_argument_parser() -> argparse.ArgumentParser:
  # Разбирает параметры синтеза; текст приходит со stdin.
  parser = argparse.ArgumentParser(prog='tts.synth', add_help=True)
  parser.add_argument('--voice', required=True)
  parser.add_argument('--rate', default='medium')
  parser.add_argument('--pitch', default='medium')
  parser.add_argument('--sr', type=int, default=48000)
  parser.add_argument('--chunk-chars', type=int, default=DEFAULT_CHUNK_CHARS)
  parser.add_argument('--output', required=True, help='готовый wav')

  return parser


def break_tag() -> str:
  # SSML-пауза после английских слов; VOICE_BREAK_MS=0 выключает её.
  try:
    milliseconds = int(os.environ.get('VOICE_BREAK_MS', DEFAULT_BREAK_MS))
  except ValueError:
    milliseconds = DEFAULT_BREAK_MS

  if milliseconds <= 0:
    return ''

  return f'<break time="{milliseconds}ms"/>'


def ssml_body(text: str) -> str:
  # Ровно то, что получит модель: экранирование и пауза после латиницы.
  return html.escape(text).replace(BREAK_TOKEN, break_tag())


def build_ssml(text: str, rate: str, pitch: str) -> str:
  # Готовит SSML: тело и обёртка просодии по параметрам.
  body = ssml_body(text)

  if rate == 'medium' and pitch == 'medium':
    return f'<speak>{body}</speak>'

  return f'<speak><prosody rate="{rate}" pitch="{pitch}">{body}</prosody></speak>'


def plan_segments(text: str, chunk_chars: int, raw: bool = False) -> list[str]:
  # Текст -> куски, каждый в пределах MAX_MODEL_CHARS; raw — без нормализации.
  segments: list[str] = []

  for chunk in split_text(text, chunk_chars):
    normalized = chunk if raw else to_cyrillic(chunk, breaks=True)

    if not normalized.strip():
      continue

    segments.extend(split_text(normalized, MAX_MODEL_CHARS))

  return segments


def synthesize_segment(
  model: Any,
  segment: str,
  voice: str,
  rate: str,
  pitch: str,
  sample_rate: int,
  raw: bool = False,
) -> np.ndarray:
  """Синтез куска; на переполнении делит его пополам и синтезирует по частям.

  Если хоть одна половина не озвучена, поднимает SynthesisError: молча
  выброшенный кусок — это потерянная фраза в готовом файле.
  """

  try:
    audio = model.apply_tts(
      ssml_text=build_ssml(segment, rate, pitch),
      speaker=voice,
      sample_rate=sample_rate,
      # в raw пользователь сам расставил ударения: модель их не переставляет
      put_accent=not raw,
    )
  except Exception as err:
    halves = split_text(segment, max(len(segment) // 2, MIN_RETRY_CHARS))

    if len(halves) < 2:
      raise SynthesisError(f'кусок не озвучен: {err}') from err

    return np.concatenate([
      synthesize_segment(model, half, voice, rate, pitch, sample_rate, raw) for half in halves
    ])

  return audio.numpy()


def silence(sample_rate: int) -> np.ndarray:
  # Короткая пауза между кусками, чтобы стык не звучал слипшимся.
  return np.zeros(int(sample_rate * SILENCE_SECONDS), dtype=np.float32)


def synthesize_text(
  text: str,
  voice: str,
  rate: str,
  pitch: str,
  sample_rate: int,
  chunk_chars: int,
  output_path: Path,
  raw: bool = False,
) -> int:
  # Синтезирует текст в один wav; при сбое куска поднимает SynthesisError.
  segments = plan_segments(text, chunk_chars, raw)

  if not segments:
    return 0

  output_path = Path(output_path).resolve()
  output_path.parent.mkdir(parents=True, exist_ok=True)

  # Silero пишет latest_silero_models.yml в текущий каталог: уводим его в кэш.
  # wav пишется по абсолютному пути во временный файл и заменяет целевой в конце.
  CONFIG_DIR.mkdir(parents=True, exist_ok=True)
  previous_dir = os.getcwd()
  gap = silence(sample_rate)
  part_path = output_path.with_name(f'{output_path.stem}.part{output_path.suffix}')

  try:
    os.chdir(CONFIG_DIR)

    from silero import silero_tts

    language, speaker_model = SPEAKER_MODEL
    model, _ = silero_tts(language=language, speaker=speaker_model)

    with sf.SoundFile(str(part_path), 'w', samplerate=sample_rate, channels=1) as output:
      for index, segment in enumerate(segments, start=1):
        audio = synthesize_segment(model, segment, voice, rate, pitch, sample_rate, raw)

        if index > 1:
          output.write(gap)

        output.write(audio)

        if len(segments) > 1:                     # одиночный кусок не шумит
          print(f'[voice] кусок {index}/{len(segments)}', file=sys.stderr)

    part_path.replace(output_path)
  finally:
    os.chdir(previous_dir)
    part_path.unlink(missing_ok=True)             # недописанный wav не остаётся

  return len(segments)


def main() -> int:
  # Отладочная точка входа: текст со stdin, служебные пути флагами.
  args = build_argument_parser().parse_args()
  text = sys.stdin.read()

  if not text.strip():
    print('[voice] пустой текст', file=sys.stderr)

    return 2

  try:
    count = synthesize_text(
      text=text,
      voice=args.voice,
      rate=args.rate,
      pitch=args.pitch,
      sample_rate=args.sr,
      chunk_chars=args.chunk_chars,
      output_path=Path(args.output),
    )
  except SynthesisError as err:
    print(f'[voice] {err}', file=sys.stderr)

    return 1

  if not count:
    print('[voice] синтез не дал аудио', file=sys.stderr)

    return 1

  return 0


if __name__ == '__main__':
  sys.exit(main())
