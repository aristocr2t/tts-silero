# Тесты командной строки: приоритет настроек, текст, очередь проигрывания.
import errno
import io
import os
import sys
import tempfile
import threading
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

os.environ['VOICE_ACCENT'] = '0'

from tts import cli  # noqa: E402
from tts.cli import (  # noqa: E402
  DEFAULTS,
  LOCK_POLL_SECONDS,
  SpeechLock,
  build_parser,
  build_settings,
  find_option,
  lock_file,
  read_text,
  resolve_save_dir,
)
from tts.media import MediaError  # noqa: E402
from tts.synth import SynthesisError  # noqa: E402

ABSENT_CONFIG = str(Path(tempfile.gettempdir()) / f'tts-silero-absent-{os.getpid()}.json')

CLEAN_ENVIRONMENT = {
  name: ''
  for name in (
    'VOICE_SPEAKER',
    'VOICE_RATE',
    'VOICE_PITCH',
    'VOICE_SR',
    'VOICE_TEMPO',
    'VOICE_PITCH_SHIFT',
    'VOICE_CHUNK_CHARS',
    'VOICE_PAUSE',
    'VOICE_SAVE_DIR',
  )
}
CLEAN_ENVIRONMENT['VOICE_CONFIG'] = ABSENT_CONFIG


class SettingsCase(unittest.TestCase):
  # Настройки собираются из CLI, окружения и конфига по приоритету.

  def setUp(self) -> None:
    self.work_dir = tempfile.TemporaryDirectory()
    self.environment = mock.patch.dict(
      os.environ,
      {
        **CLEAN_ENVIRONMENT,
        'VOICE_CONFIG': str(Path(self.work_dir.name) / 'config.json'),
      },
    )
    self.environment.start()

  def tearDown(self) -> None:
    self.environment.stop()
    self.work_dir.cleanup()

  def test_cli_wins_over_environment(self) -> None:
    os.environ['VOICE_SPEAKER'] = 'aidar'

    self.assertEqual(find_option('speaker', 'baya', {}), 'baya')

  def test_environment_wins_over_config(self) -> None:
    os.environ['VOICE_SPEAKER'] = 'aidar'

    self.assertEqual(find_option('speaker', None, {'speaker': 'eugene'}), 'aidar')

  def test_config_wins_over_default(self) -> None:
    self.assertEqual(find_option('speaker', None, {'speaker': 'eugene'}), 'eugene')

  def test_default_applies_last(self) -> None:
    self.assertEqual(find_option('speaker', None, {}), DEFAULTS['speaker'])

  def test_settings_are_typed(self) -> None:
    args = build_parser().parse_args(['--sr', '24000', '--tempo', '1.2', 'текст'])
    settings = build_settings(args)

    self.assertEqual(settings['sample_rate'], 24000)
    self.assertIsInstance(settings['tempo'], float)

  def test_out_of_range_exits(self) -> None:
    args = build_parser().parse_args(['--chunk', '5000', 'текст'])

    with self.assertRaises(SystemExit):
      build_settings(args)

  def test_undocumented_values_exit(self) -> None:
    for option in (
      ['--voice', 'no-such-voice'],
      ['--rate', 'no-such-rate'],
      ['--pitch', 'no-such-pitch'],
      ['--sr', '44100'],
    ):
      with self.subTest(option=option), self.assertRaises(SystemExit):
        build_settings(build_parser().parse_args([*option, 'текст']))

  def test_environment_value_is_checked(self) -> None:
    with mock.patch.dict(os.environ, {'VOICE_SR': '44100'}):
      with self.assertRaises(SystemExit):
        build_settings(build_parser().parse_args(['текст']))

  def test_environment_comma_decimal_is_accepted(self) -> None:
    os.environ['VOICE_TEMPO'] = '1,2'

    settings = build_settings(build_parser().parse_args(['текст']))

    self.assertEqual(settings['tempo'], 1.2)

  def test_bad_environment_number_names_variable(self) -> None:
    for env_name, value in (
      ('VOICE_SR', '44k'),
      ('VOICE_PAUSE', 'abc'),
    ):
      with self.subTest(env_name=env_name), mock.patch.dict(
        os.environ,
        {env_name: value},
      ):
        with self.assertRaises(SystemExit) as raised:
          build_settings(build_parser().parse_args(['текст']))

      self.assertIn(env_name, str(raised.exception))


class TextCase(unittest.TestCase):
  # Текст берётся из аргументов, файла или stdin.

  def test_arguments_are_joined(self) -> None:
    args = build_parser().parse_args(['привет', 'мир'])

    self.assertEqual(read_text(args), 'привет мир')

  def test_file_is_read(self) -> None:
    with tempfile.TemporaryDirectory() as work_dir:
      path = Path(work_dir) / 'book.txt'
      path.write_text('абзац', encoding='utf-8')

      args = build_parser().parse_args(['--file', str(path)])

      self.assertEqual(read_text(args), 'абзац')

  def test_missing_file_exits(self) -> None:
    args = build_parser().parse_args(['--file', '/нет/такого/файла'])

    with self.assertRaises(SystemExit):
      read_text(args)

  def test_unreadable_file_exits_with_message(self) -> None:
    with tempfile.TemporaryDirectory() as work_dir:
      path = Path(work_dir) / 'bad.txt'
      path.write_bytes(b'\xff\xfe')
      args = build_parser().parse_args(['--file', str(path)])

      with self.assertRaises(SystemExit) as raised:
        read_text(args)

    self.assertIn('не прочитан', str(raised.exception))

  def test_stdin_dash(self) -> None:
    args = build_parser().parse_args(['-'])

    with mock.patch('sys.stdin', io.StringIO('из stdin')):
      self.assertEqual(read_text(args), 'из stdin')

  def test_empty_text_exits(self) -> None:
    args = build_parser().parse_args([])

    with self.assertRaises(SystemExit):
      read_text(args)


class PipelineCase(unittest.TestCase):
  # Синтез идёт без лока, прерывание завершает работу тихо.

  def setUp(self) -> None:
    self.work_dir = tempfile.TemporaryDirectory()
    self.lock_dir = Path(self.work_dir.name) / 'voice.lock'
    self.environment = mock.patch.dict(
      os.environ,
      {
        **CLEAN_ENVIRONMENT,
        'VOICE_LOCK_DIR': str(self.lock_dir),
      },
    )
    self.environment.start()

  def tearDown(self) -> None:
    self.environment.stop()
    self.work_dir.cleanup()

  def test_lock_is_free_during_synthesis(self) -> None:
    observed = {}

    def fake_synthesis(text, settings, work_dir, raw=False):
      observed['lock_present'] = self.lock_dir.exists()
      path = Path(work_dir) / 'speech.wav'
      path.write_bytes(b'')

      return path

    with mock.patch('tts.cli.run_synthesis', side_effect=fake_synthesis), \
         mock.patch('tts.media.apply_effects'), \
         mock.patch('tts.media.play_audio'), \
         mock.patch('tts.media.find_ffmpeg', return_value='ffmpeg'), \
         mock.patch('tts.media.find_player', return_value='afplay'):
      code = cli.main(['--pause', '0', 'текст'])

    self.assertEqual(code, 0)
    self.assertFalse(observed['lock_present'], 'синтез не должен держать лок')

    lock = SpeechLock(self.lock_dir)

    lock.acquire()
    lock.release()

  def test_interrupt_exits_quietly(self) -> None:
    with mock.patch('tts.cli.run', side_effect=KeyboardInterrupt):
      self.assertEqual(cli.main([]), 130)

  def test_default_pause_is_half_a_second(self) -> None:
    self.assertEqual(DEFAULTS['pause'], 0.5)

  def test_voice_defaults(self) -> None:
    self.assertEqual(DEFAULTS['speaker'], 'eugene')
    self.assertEqual(DEFAULTS['tempo'], 1)
    self.assertEqual(DEFAULTS['pitch_shift'], 1)

  def test_media_error_is_short_and_nonzero(self) -> None:
    errors = io.StringIO()
    save = f'--save={self.work_dir.name}/out'

    with mock.patch(
      'tts.media.find_ffmpeg',
      side_effect=MediaError('ffmpeg не найден'),
    ), redirect_stderr(errors):
      code = cli.main(['--no-play', save, 'текст'])

    self.assertEqual(code, 1)
    self.assertEqual(errors.getvalue(), 'voice: ffmpeg не найден\n')
    self.assertNotIn('Traceback', errors.getvalue())

  def test_synthesis_error_is_not_success(self) -> None:
    errors = io.StringIO()
    save = f'--save={self.work_dir.name}/out'

    with mock.patch(
      'tts.media.find_ffmpeg',
      return_value='ffmpeg',
    ), mock.patch(
      'tts.cli.run_synthesis',
      side_effect=SynthesisError('кусок не озвучен'),
    ), redirect_stderr(errors):
      code = cli.main(['--no-play', save, 'текст'])

    self.assertEqual(code, 1)
    self.assertIn('voice: кусок не озвучен', errors.getvalue())

  def test_missing_player_stops_before_synthesis(self) -> None:
    with mock.patch('tts.media.find_ffmpeg', return_value='ffmpeg'), \
         mock.patch('tts.media.find_player', return_value=None), \
         mock.patch('tts.cli.run_synthesis') as synthesis:
      with self.assertRaises(SystemExit):
        cli.main(['текст'])

    synthesis.assert_not_called()

  def test_print_text_also_plays(self) -> None:
    output = io.StringIO()

    def fake_synthesis(text, settings, work_dir, raw=False):
      path = Path(work_dir) / 'speech.wav'
      path.write_bytes(b'')

      return path

    with redirect_stdout(output), \
         mock.patch('tts.cli.run_synthesis', side_effect=fake_synthesis), \
         mock.patch('tts.media.apply_effects'), \
         mock.patch('tts.media.play_audio') as play, \
         mock.patch('tts.media.find_ffmpeg', return_value='ffmpeg'), \
         mock.patch('tts.media.find_player', return_value='afplay'):
      code = cli.main(['--pause', '0', '--print', '1500 руб'])

    self.assertEqual(code, 0)
    self.assertIn('полторы тысячи рублей', output.getvalue())
    play.assert_called_once()

  def test_print_text_shows_text_for_model(self) -> None:
    output = io.StringIO()

    with redirect_stdout(output), mock.patch('tts.cli.run_synthesis'):
      code = cli.main(['-P', '--no-play', '1500 руб'])

    self.assertEqual(code, 0)
    self.assertEqual(output.getvalue().strip(), 'полторы тысячи рублей')

  def test_raw_keeps_text_and_skips_accent(self) -> None:
    output = io.StringIO()
    marked = 'т+ы уж+е сд+елал г+ит п+уш?'

    with redirect_stdout(output), mock.patch('tts.cli.run_synthesis'):
      code = cli.main(['-P', '--raw', '--no-play', marked])

    self.assertEqual(code, 0)
    self.assertEqual(output.getvalue().strip(), marked)
    self.assertNotIn('*', output.getvalue())

  def test_no_play_prints_text_without_audio(self) -> None:
    output = io.StringIO()

    with redirect_stdout(output), \
         mock.patch('tts.media.find_ffmpeg') as ffmpeg, \
         mock.patch('tts.media.find_player') as player, \
         mock.patch('tts.cli.run_synthesis') as synthesis:
      code = cli.main(['--print', '--no-play', '10 мс'])

    self.assertEqual(code, 0)
    self.assertIn('десять миллисекунд', output.getvalue())
    ffmpeg.assert_not_called()
    player.assert_not_called()
    synthesis.assert_not_called()

  def test_no_play_without_save_says_nothing_is_produced(self) -> None:
    errors = io.StringIO()

    with redirect_stderr(errors), mock.patch('tts.cli.run_synthesis') as synthesis:
      code = cli.main(['--no-play', 'текст'])

    self.assertEqual(code, 0)
    self.assertIn('--no-play без --save', errors.getvalue())
    synthesis.assert_not_called()


class SaveDirCase(unittest.TestCase):
  # Каталог сохранения: аргумент, переменная или временный каталог.

  def test_no_save_returns_none(self) -> None:
    args = build_parser().parse_args(['текст'])

    self.assertIsNone(resolve_save_dir(args, {}))

  def test_explicit_dir(self) -> None:
    args = build_parser().parse_args(['--save=/tmp/voice-out', 'текст'])

    self.assertEqual(resolve_save_dir(args, {}), Path('/tmp/voice-out'))

  def test_environment_dir(self) -> None:
    args = build_parser().parse_args(['--save'])

    with mock.patch.dict(os.environ, {'VOICE_SAVE_DIR': '/tmp/from-env'}):
      self.assertEqual(resolve_save_dir(args, {}), Path('/tmp/from-env'))

  def test_bare_save_keeps_next_word_as_text(self) -> None:
    args = build_parser().parse_args(['--save', 'new-output', 'привет'])

    self.assertEqual(args.save, '')
    self.assertEqual(args.text, ['new-output', 'привет'])

  def test_save_without_equals_keeps_argument_as_text(self) -> None:
    # явный каталог — только `--save=DIR`: без «=» это текст, а не каталог
    args = build_parser().parse_args(['--save', '/tmp/voice-out', 'текст'])

    self.assertEqual(args.save, '')
    self.assertEqual(args.text, ['/tmp/voice-out', 'текст'])

  def test_text_between_options(self) -> None:
    # раньше падало: unrecognized arguments
    args = build_parser().parse_args(['--save', '/tmp/out', '--pause', '0', 'привет', 'мир'])

    self.assertEqual(args.save, '')
    self.assertEqual(args.pause, 0.0)
    self.assertEqual(args.text, ['/tmp/out', 'привет', 'мир'])

  def test_option_abbreviation_is_rejected(self) -> None:
    errors = io.StringIO()

    with redirect_stderr(errors), self.assertRaises(SystemExit) as raised:
      build_parser().parse_args(['--sav', 'new-output', 'привет'])

    self.assertEqual(raised.exception.code, 2)
    self.assertIn('unrecognized arguments', errors.getvalue())

  def test_attached_dir_is_not_text(self) -> None:
    args = build_parser().parse_args(['--save=/tmp/voice-out', 'текст'])

    self.assertEqual(args.save, '/tmp/voice-out')
    self.assertEqual(args.text, ['текст'])


class SpeechLockCase(unittest.TestCase):
  # Очередь проигрывания: лок занимается, снимается и переживает падение.

  def setUp(self) -> None:
    self.work_dir = tempfile.TemporaryDirectory()
    self.lock_dir = Path(self.work_dir.name) / 'voice.lock'

  def tearDown(self) -> None:
    self.work_dir.cleanup()

  def test_acquire_and_release(self) -> None:
    lock = SpeechLock(self.lock_dir)

    lock.acquire()

    self.assertTrue(lock.lock_path.is_file())

    lock.release()

    second = SpeechLock(self.lock_dir)

    second.acquire()
    second.release()

  def test_two_locks_do_not_overlap(self) -> None:
    first = SpeechLock(self.lock_dir)
    second = SpeechLock(self.lock_dir)
    second_entered = threading.Event()
    observed = {'entered': False}

    def take_second() -> None:
      second.acquire()

      try:
        observed['entered'] = True
        second_entered.set()
      finally:
        second.release()

    first.acquire()
    thread = threading.Thread(target=take_second, daemon=True)
    thread.start()

    try:
      self.assertFalse(second_entered.wait(0.2), 'второй лок вошёл при живом первом')
      self.assertFalse(observed['entered'])
    finally:
      first.release()

    self.assertTrue(second_entered.wait(2), 'второй лок не дождался освобождения')
    thread.join(2)
    self.assertFalse(thread.is_alive())

  def test_help_does_not_need_lock(self) -> None:
    with redirect_stdout(io.StringIO()), self.assertRaises(SystemExit) as raised:
      build_parser().parse_args(['--help'])

    self.assertEqual(raised.exception.code, 0)


class WindowsLockCase(unittest.TestCase):
  # Windows-ветка lock_file: занятый lock ждёт и повторяет попытку.

  def test_windows_lock_retries_until_free(self) -> None:
    fake = mock.Mock()
    fake.LK_NBLCK = 1
    fake.locking.side_effect = [OSError(errno.EACCES, 'locked'), None]

    with tempfile.TemporaryDirectory() as work_dir:
      lock_path = Path(work_dir) / 'lock'

      with open(lock_path, 'a+b', buffering=0) as handle:
        with mock.patch.dict(sys.modules, {'msvcrt': fake}), \
             mock.patch.object(sys, 'platform', 'win32'), \
             mock.patch('tts.cli.time.sleep') as sleep:
          lock_file(handle)

        self.assertEqual(fake.locking.call_count, 2)
        self.assertEqual(fake.locking.call_args.args[1], fake.LK_NBLCK)
        sleep.assert_called_once_with(LOCK_POLL_SECONDS)
        self.assertEqual(handle.tell(), 0)


if __name__ == '__main__':
  unittest.main()
