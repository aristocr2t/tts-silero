"""Командная строка озвучки: аргументы, очередь, синтез, эффекты, проигрывание.

Один и тот же код работает на macOS, Linux и Windows: платформенные детали
(ffmpeg, плеер, каталоги) спрятаны в media.py, входные обёртки — bin/voice
для POSIX и bin/voice.cmd для Windows.

Приоритет настроек: аргументы CLI, затем переменные окружения, затем секция
voice пользовательского конфига, затем встроенные значения.
"""

import argparse
import errno
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path
from typing import BinaryIO, Callable

from . import media
from .settings import (
  PITCHES,
  RATES,
  SAMPLE_RATES,
  SPEAKERS,
  collect_defaults,
)
from .synth import SynthesisError, plan_segments, ssml_body, synthesize_text

DEFAULTS = {
  'speaker': 'eugene',
  'rate': 'medium',
  'pitch': 'medium',
  'sample_rate': 48000,
  'tempo': 1,
  'pitch_shift': 1,
  'chunk': 900,
  'pause': 0.5,
}

ENVIRONMENT = {
  'speaker': 'VOICE_SPEAKER',
  'rate': 'VOICE_RATE',
  'pitch': 'VOICE_PITCH',
  'sample_rate': 'VOICE_SR',
  'tempo': 'VOICE_TEMPO',
  'pitch_shift': 'VOICE_PITCH_SHIFT',
  'chunk': 'VOICE_CHUNK_CHARS',
  'pause': 'VOICE_PAUSE',
}

USAGE_EPILOG = '''примеры:
  voice "привет, это проверка"
  voice --file book.txt
  printf 'текст' | voice -

Английские слова читаются по произношению (bash -> бэш), аббревиатуры по буквам.
Числа: 1 234,5 -> тысяча двести тридцать четыре целых пять десятых, 21% -> двадцать
один процент, 5-го -> пятого. Единицы: 10 мс -> десять миллисекунд, 10 м/с ->
десять метров в секунду, 1,5 с -> полторы секунды, 1500 руб -> полторы тысячи
рублей. Ударения по контексту ставит ruaccent, если он установлен
(VOICE_ACCENT=0 выключает). Настройки по умолчанию — в ~/.config/tts-silero.json.
'''

CHOICES = {
  'speaker': (SPEAKERS, '--voice'),
  'rate': (RATES, '--rate'),
  'pitch': (PITCHES, '--pitch'),
  'sample_rate': (SAMPLE_RATES, '--sr'),
}

NUMERIC_CASTS = (
  ('sample_rate', int),
  ('tempo', float),
  ('pitch_shift', float),
  ('chunk', int),
  ('pause', float),
)

LOCK_POLL_SECONDS = 0.2


def use_utf8_streams() -> None:
  # Windows-консоль по умолчанию cp1252: русский текст в справке её роняет.
  for stream in (sys.stdout, sys.stderr):
    reconfigure = getattr(stream, 'reconfigure', None)

    if reconfigure is not None:
      try:
        reconfigure(encoding='utf-8')
      except (ValueError, OSError):
        continue


def normalize_save_args(argv: list[str] | None) -> list[str]:
  # Голый `--save` -> `--save=`: иначе argparse съест следующий текст как каталог.
  if argv is None:
    argv = sys.argv[1:]

  normalized = []

  for index, token in enumerate(argv):
    if token == '--':
      return normalized + argv[index:]

    normalized.append('--save=' if token == '--save' else token)

  return normalized


class VoiceArgumentParser(argparse.ArgumentParser):
  # Явный каталог — только `--save=DIR`, голый `--save` берёт каталог по умолчанию.

  def parse_args(
    self,
    args: list[str] | None = None,
    namespace: argparse.Namespace | None = None,
  ) -> argparse.Namespace:
    argv = normalize_save_args(args)
    parsed, remainder = super().parse_known_args(argv, namespace)
    unknown = [item for item in remainder if item.startswith('-')]

    if unknown:
      self.error('unrecognized arguments: ' + ' '.join(unknown))

    # argparse теряет текст, который стоит между опциями: «--save dir --pause 0 текст»
    parsed.text = [*parsed.text, *(item for item in remainder if not item.startswith('-'))]

    return parsed


def build_parser() -> argparse.ArgumentParser:
  # Аргументы с None по умолчанию: так видно, что задал пользователь.
  parser = VoiceArgumentParser(
    prog='voice',
    description='Озвучка русского текста голосом Silero.',
    epilog=USAGE_EPILOG,
    formatter_class=argparse.RawDescriptionHelpFormatter,
    allow_abbrev=False,
  )
  parser.add_argument('text', nargs='*', help='текст; «-» читает stdin')
  parser.add_argument(
    '--voice',
    dest='speaker',
    help='голос: %s' % ', '.join(('eugene', 'aidar', 'baya', 'kseniya', 'xenia')),
  )
  parser.add_argument('--rate', help='x-slow | slow | medium | fast | x-fast')
  parser.add_argument('--pitch', help='x-low | low | medium | high | x-high')
  parser.add_argument('--sr', dest='sample_rate', type=int, help='8000 | 24000 | 48000')
  parser.add_argument('--tempo', type=float, help='темп без изменения тона, 0.5..2.0')
  parser.add_argument('--pitch-shift', type=float, help='подъём питча, 1.0..1.2')
  parser.add_argument('--chunk', type=int, help='символов в куске синтеза, 100..900')
  parser.add_argument('--pause', type=float, help='пауза после проигрывания, секунды (0.5)')
  parser.add_argument(
    '--save',
    nargs='?',
    const='',
    metavar='DIR',
    help='сохранить wav и mp3; свой каталог: --save=DIR',
  )
  parser.add_argument('--file', dest='input_file', help='прочитать текст из файла')
  parser.add_argument(
    '--no-play',
    dest='no_play',
    action='store_true',
    help='не проигрывать; без --save аудио не создаётся',
  )
  parser.add_argument(
    '-P',
    '--print',
    dest='print_text',
    action='store_true',
    help='напечатать текст, который получит синтезатор (с акцентом), и продолжить озвучку',
  )
  parser.add_argument(
    '--raw',
    action='store_true',
    help='текст уже размечен: без нормализации и без автоакцента',
  )
  parser.add_argument('--version', action='version', version='tts-silero')

  return parser


def find_option(name: str, cli_value: object, config: dict) -> object:
  # Значение по приоритету: CLI, окружение, конфиг, встроенное значение.
  if cli_value is not None:
    return cli_value

  env_name = ENVIRONMENT[name]
  env_value = os.environ.get(env_name)

  if env_value:
    return env_value

  return config.get(name, DEFAULTS[name])


def numeric_option(name: str, value: object, cast: Callable[[str], int | float]) -> int | float:
  # Число из CLI/env/config; запятая — десятичный разделитель, ошибка с именем env.
  try:
    return cast(str(value).replace(',', '.'))
  except (TypeError, ValueError):
    raise SystemExit(
      f'voice: {ENVIRONMENT[name]}: ожидалось число, получено {value!r}',
    ) from None


def build_settings(args: argparse.Namespace) -> dict:
  # Собирает все настройки озвучки из четырёх источников.
  config = dict(collect_defaults())
  settings = {name: find_option(name, getattr(args, name), config) for name in DEFAULTS}

  for name, cast in NUMERIC_CASTS:
    settings[name] = numeric_option(name, settings[name], cast)

  validate_settings(settings)

  return settings


def validate_settings(settings: dict) -> None:
  # Отбрасывает значения вне диапазонов и не из документированных списков.
  for name, (choices, option) in CHOICES.items():
    value = settings[name]

    if value not in choices:
      allowed = ', '.join(str(choice) for choice in choices)

      raise SystemExit(
        f'voice: {option}: недопустимое значение {value!r}; допустимо: {allowed}',
      )

  ranges = {
    'tempo': (0.5, 2.0),
    'pitch_shift': (1.0, 1.2),
    'chunk': (100, 900),
    'pause': (0, 60),
  }

  for name, (minimum, maximum) in ranges.items():
    value = settings[name]

    if not minimum <= value <= maximum:
      raise SystemExit(
        f'voice: --{name.replace("_", "-")} вне диапазона {minimum}..{maximum}: {value}',
      )


def read_text(args: argparse.Namespace) -> str:
  # Текст из аргументов, файла или stdin.
  if args.input_file:
    path = Path(args.input_file).expanduser()

    if not path.is_file():
      raise SystemExit(f'voice: файл не найден: {args.input_file}')

    try:
      return path.read_text(encoding='utf-8')
    except (OSError, UnicodeError) as err:
      raise SystemExit(f'voice: файл не прочитан: {args.input_file}: {err}') from err

  if args.text[:1] == ['-']:
    return sys.stdin.read()

  if not args.text:
    raise SystemExit('voice: пустой текст; справка: voice --help')

  return ' '.join(args.text)


class SpeechLock:
  """Очередь проигрывания: одновременно говорит только один процесс.

  Блокировка файловая и принадлежит ОС: демон или зависший процесс не держит
  очередь вечно, а выход процесса освобождает её автоматически. Каталог
  VOICE_LOCK_DIR может оставаться постоянным.
  """

  def __init__(self, lock_dir: Path) -> None:
    self.lock_dir = lock_dir
    self.lock_path = lock_dir / 'lock'
    self.handle: BinaryIO | None = None

  def acquire(self) -> None:
    # Ждёт свободный файл блокировки и держит его до release.
    self.lock_dir.mkdir(parents=True, exist_ok=True)
    handle = open(self.lock_path, 'a+b', buffering=0)

    try:
      lock_file(handle)
    except BaseException:
      handle.close()

      raise

    self.handle = handle

  def release(self) -> None:
    # Снимает свою блокировку; чужие блокировки не трогает.
    handle = self.handle

    if handle is None:
      return

    try:
      unlock_file(handle)
    finally:
      handle.close()
      self.handle = None


def lock_file(handle: BinaryIO) -> None:
  # Эксклюзивная блокировка файла средствами ОС.
  if sys.platform == 'win32':
    import msvcrt

    handle.seek(0, os.SEEK_END)

    if handle.tell() == 0:
      handle.write(b'\0')

    while True:
      handle.seek(0)

      try:
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
      except OSError as err:
        if err.errno not in (errno.EACCES, errno.EDEADLK):
          raise

        time.sleep(LOCK_POLL_SECONDS)

        continue

      return

  import fcntl

  fcntl.flock(handle.fileno(), fcntl.LOCK_EX)


def unlock_file(handle: BinaryIO) -> None:
  # Снимает блокировку, взятую lock_file.
  if sys.platform == 'win32':
    import msvcrt

    handle.seek(0)
    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)

    return

  import fcntl

  fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def resolve_save_dir(args: argparse.Namespace, settings: dict) -> Path | None:
  # Каталог сохранения: --save без аргумента берёт VOICE_SAVE_DIR или TEMP/voice.
  if args.save is None:
    return None

  if args.save:
    return Path(args.save).expanduser()

  configured = os.environ.get('VOICE_SAVE_DIR')

  if configured:
    return Path(configured).expanduser()

  return Path(tempfile.gettempdir()) / 'voice'


def run_synthesis(text: str, settings: dict, work_dir: Path, raw: bool = False) -> Path:
  # Синтезирует текст в один wav внутри рабочего каталога.
  wav_path = work_dir / 'speech.wav'

  count = synthesize_text(
    text=text,
    voice=settings['speaker'],
    rate=settings['rate'],
    pitch=settings['pitch'],
    sample_rate=settings['sample_rate'],
    chunk_chars=settings['chunk'],
    output_path=wav_path,
    raw=raw,
  )

  if not count:
    raise SystemExit('voice: синтез не дал аудио')

  return wav_path


def main(argv: list[str] | None = None) -> int:
  # Полный цикл; Ctrl-C завершается тихо, ожидаемые ошибки — одной строкой.
  try:
    return run(argv)
  except KeyboardInterrupt:
    return 130
  except (media.MediaError, SynthesisError) as err:
    print(f'voice: {err}', file=sys.stderr)

    return 1


def run(argv: list[str] | None = None) -> int:
  # Синтез без блокировки, затем короткая очередь только на проигрывание.
  use_utf8_streams()

  parser = build_parser()
  args = parser.parse_args(argv)

  settings = build_settings(args)
  text = read_text(args)

  if not text.strip():
    raise SystemExit('voice: пустой текст')

  save_dir = resolve_save_dir(args, settings)
  player = None if args.no_play else media.find_player()

  # без плеера и без --save синтез был бы неслышимой работой с тихим exit 0
  if not args.no_play and player is None and save_dir is None:
    raise SystemExit('voice: плеер не найден; сохраните файл: --save или --save=DIR')

  # разбор текста не требует ffmpeg, плеера и модели
  if args.print_text:
    for segment in plan_segments(text, settings['chunk'], args.raw):
      print(ssml_body(segment))

  # --no-play без --save: аудио никуда не идёт, синтез будет впустую
  if player is None and save_dir is None:
    if not args.print_text:
      print('voice: --no-play без --save: аудио не создаётся', file=sys.stderr)

    return 0

  ffmpeg = media.find_ffmpeg()

  lock = SpeechLock(Path(os.environ.get('VOICE_LOCK_DIR', Path(tempfile.gettempdir()) / 'voice.lock')))
  work_dir = Path(tempfile.mkdtemp(prefix='voice-'))

  try:
    # синтез идёт без лока: команда не ждёт чужую озвучку
    wav_path = run_synthesis(text, settings, work_dir, args.raw)

    media.apply_effects(
      ffmpeg,
      wav_path,
      settings['pitch_shift'],
      settings['tempo'],
      settings['sample_rate'],
    )

    if save_dir is not None:
      saved_mp3 = media.save_audio(ffmpeg, wav_path, save_dir)

      print(saved_mp3)

    if player is not None:
      play_with_queue(lock, wav_path, player, settings['pause'])
  finally:
    shutil.rmtree(work_dir, ignore_errors=True)

  return 0


def play_with_queue(lock: SpeechLock, wav_path: Path, player: str, pause: float) -> None:
  # Держит лок только пока звучит голос плюс короткая пауза после него.
  lock.acquire()

  try:
    media.play_audio(wav_path, player)

    if pause:
      time.sleep(pause)
  finally:
    lock.release()


if __name__ == '__main__':
  # torch при выходе тратит до полусекунды на уборку: озвучка уже закончена
  code = main()
  sys.stdout.flush()
  sys.stderr.flush()
  os._exit(code)
