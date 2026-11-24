# Тесты настроек голоса из секции voice пользовательского конфига.

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

os.environ['VOICE_ACCENT'] = '0'

from tts.cli import build_parser, build_settings  # noqa: E402
from tts.settings import collect_defaults  # noqa: E402


class SettingsTestCase(unittest.TestCase):
  # Корректные значения отдаются, некорректные молча пропускаются.

  def setUp(self) -> None:
    self.work_dir = tempfile.TemporaryDirectory()
    self.config_path = Path(self.work_dir.name) / 'tts-silero.json'
    self.previous = os.environ.get('VOICE_CONFIG')
    os.environ['VOICE_CONFIG'] = str(self.config_path)

  def tearDown(self) -> None:
    if self.previous is None:
      os.environ.pop('VOICE_CONFIG', None)
    else:
      os.environ['VOICE_CONFIG'] = self.previous

    self.work_dir.cleanup()

  def write_config(self, payload: dict) -> None:
    self.config_path.write_text(json.dumps(payload), encoding='utf-8')

  def test_absent_config_gives_nothing(self) -> None:
    self.assertEqual(collect_defaults(), [])

  def test_valid_values_are_returned(self) -> None:
    self.write_config({
      'voice': {
        'speaker': 'eugene',
        'rate': 'fast',
        'sample_rate': 24000,
        'tempo': 1.2,
        'chunk': 400,
      },
    })
    defaults = dict(collect_defaults())

    self.assertEqual(defaults['speaker'], 'eugene')
    self.assertEqual(defaults['rate'], 'fast')
    self.assertEqual(defaults['sample_rate'], '24000')
    self.assertEqual(defaults['tempo'], '1.2')
    self.assertEqual(defaults['chunk'], '400')

  def test_unknown_speaker_is_skipped(self) -> None:
    self.write_config({
      'voice': {
        'speaker': 'не-голос',
        'pause': 1,
      },
    })
    defaults = dict(collect_defaults())

    self.assertNotIn('speaker', defaults)
    self.assertEqual(defaults['pause'], '1')

  def test_out_of_range_numbers_are_skipped(self) -> None:
    self.write_config({
      'voice': {
        'tempo': 9,
        'pitch_shift': 0.1,
        'chunk': 5000,
      },
    })

    self.assertEqual(collect_defaults(), [])

  def test_unsupported_sample_rate_is_skipped(self) -> None:
    self.write_config({'voice': {'sample_rate': 44100}})

    self.assertEqual(collect_defaults(), [])

  def test_config_sample_rate_reaches_cli_settings(self) -> None:
    self.write_config({'voice': {'sample_rate': 24000}})

    with mock.patch.dict(os.environ, {'VOICE_SR': ''}):
      settings = build_settings(build_parser().parse_args(['текст']))

    self.assertEqual(settings['sample_rate'], 24000)

  def test_comma_decimal_is_accepted(self) -> None:
    self.write_config({'voice': {'tempo': '1,2'}})

    self.assertEqual(dict(collect_defaults())['tempo'], '1.2')

  def test_broken_voice_section_is_ignored(self) -> None:
    self.write_config({'voice': 'строка'})

    self.assertEqual(collect_defaults(), [])

  def test_chunk_value_is_converted_to_int(self) -> None:
    for value in (400.0, '4e2'):
      with self.subTest(value=value):
        work_dir = tempfile.TemporaryDirectory()
        self.addCleanup(work_dir.cleanup)

        path = Path(work_dir.name) / 'tts-silero.json'
        path.write_text(json.dumps({'voice': {'chunk': value}}), encoding='utf-8')

        with mock.patch.dict(os.environ, {'VOICE_CONFIG': str(path)}):
          self.assertEqual(dict(collect_defaults())['chunk'], '400')

  def test_non_integer_chunk_is_skipped(self) -> None:
    self.write_config({'voice': {'chunk': 400.5}})

    self.assertEqual(collect_defaults(), [])

  def test_boolean_pause_is_skipped(self) -> None:
    self.write_config({'voice': {'pause': True}})

    self.assertEqual(collect_defaults(), [])

  def test_integer_chunk_is_passed_as_int(self) -> None:
    self.write_config({'voice': {'chunk': 400}})

    self.assertEqual(dict(collect_defaults())['chunk'], '400')


if __name__ == '__main__':
  unittest.main()
