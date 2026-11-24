"""Работа с медиа: поиск ffmpeg, темп, сохранение и проигрывание.

Всё внешнее и платформенное собрано здесь, чтобы cli.py оставался про логику.
ffmpeg ищется в PATH и в обычных каталогах установки: из расширений и
планировщиков PATH часто пустой.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

FFMPEG_CANDIDATES = (
  '/opt/homebrew/bin/ffmpeg',
  '/usr/local/bin/ffmpeg',
  '/usr/bin/ffmpeg',
  r'C:\ffmpeg\bin\ffmpeg.exe',
  r'C:\ProgramData\chocolatey\bin\ffmpeg.exe',
)


class MediaError(RuntimeError):
  # Ошибка внешнего инструмента: сообщение уже готово для пользователя.
  pass


def find_ffmpeg() -> str:
  # Путь к ffmpeg или MediaError с подсказкой по установке.
  found = shutil.which('ffmpeg')

  if found:
    return found

  for candidate in FFMPEG_CANDIDATES:
    if Path(candidate).is_file():
      return candidate

  raise MediaError(
    'ffmpeg не найден; macOS: brew install ffmpeg, Windows: winget install ffmpeg, '
    'Debian/Ubuntu: sudo apt install ffmpeg',
  )


def find_player() -> str | None:
  # Проигрыватель для готового wav: afplay, ffplay или winsound.
  for name in ('afplay', 'ffplay'):
    found = shutil.which(name)

    if found:
      return found

  if sys.platform == 'win32':
    return 'winsound'

  return None


def run_command(arguments: list[str]) -> None:
  # Запускает внешнюю команду и поднимает MediaError при ошибке.
  try:
    subprocess.run(arguments, check=True, stdout=subprocess.DEVNULL)
  except FileNotFoundError as err:
    raise MediaError(f'{arguments[0]} не найден') from err
  except subprocess.CalledProcessError as err:
    raise MediaError(f'{Path(arguments[0]).name} завершился с кодом {err.returncode}') from err


def apply_effects(
  ffmpeg: str,
  wav_path: Path,
  pitch_shift: float,
  tempo: float,
  sample_rate: int,
) -> None:
  # Питч-шифт и ускорение без изменения тона; результат на месте wav.
  filtered_path = wav_path.with_suffix('.filtered.wav')

  if pitch_shift not in (1, 1.0):
    run_command([
      ffmpeg,
      '-y',
      '-v',
      'error',
      '-i',
      str(wav_path),
      '-af',
      f'asetrate={sample_rate}*{pitch_shift},aresample={sample_rate},atempo={1 / pitch_shift:.6f}',
      str(filtered_path),
    ])

    filtered_path.replace(wav_path)

  if tempo not in (1, 1.0):
    run_command([
      ffmpeg,
      '-y',
      '-v',
      'error',
      '-i',
      str(wav_path),
      '-filter:a',
      f'atempo={tempo}',
      str(filtered_path),
    ])

    filtered_path.replace(wav_path)


def save_audio(ffmpeg: str, wav_path: Path, save_dir: Path) -> Path:
  # Кладёт wav и mp3 в каталог сохранения, возвращает путь к mp3.
  try:
    save_dir.mkdir(parents=True, exist_ok=True)
  except OSError as err:
    raise MediaError(f'не удалось создать {save_dir}: {err.strerror or err}') from err

  stamp = f'{time_stamp()}-{os.getpid()}'
  saved_wav = save_dir / f'voice-{stamp}.wav'
  saved_mp3 = save_dir / f'voice-{stamp}.mp3'

  try:
    shutil.copy2(wav_path, saved_wav)
  except OSError as err:
    raise MediaError(f'не удалось сохранить {saved_wav}: {err.strerror or err}') from err

  run_command([
    ffmpeg,
    '-y',
    '-v',
    'error',
    '-i',
    str(saved_wav),
    '-c:a',
    'libmp3lame',
    '-q:a',
    '3',
    str(saved_mp3),
  ])

  return saved_mp3


def time_stamp() -> str:
  # Отметка времени для имени файла.
  import datetime

  return datetime.datetime.now().strftime('%Y%m%d-%H%M%S')


def play_audio(wav_path: Path, player: str) -> None:
  # Проигрывает wav найденным плеером.
  if player == 'winsound':
    import winsound

    winsound.PlaySound(str(wav_path), winsound.SND_FILENAME)

    return

  if Path(player).name.startswith('ffplay'):
    run_command([player, '-nodisp', '-autoexit', '-loglevel', 'quiet', str(wav_path)])

    return

  run_command([player, str(wav_path)])
