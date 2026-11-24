# Тесты пользовательского конфига ~/.config/tts-silero.json.

import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path

os.environ['VOICE_ACCENT'] = '0'

from tts.config import load_custom  # noqa: E402
from tts.normalize import to_cyrillic  # noqa: E402


class CustomConfigTestCase(unittest.TestCase):
  # Свои слова и замены подмешиваются в общий словарь.

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

  def test_missing_file_gives_empty_customs(self) -> None:
    self.assertEqual(load_custom(), ({}, ()))

  def test_custom_word_wins_over_builtin(self) -> None:
    self.write_config({
      'words': {
        'geekideas': 'гикайдиас',
        'ssh': 'своё-эс',
      },
    })

    self.assertEqual(to_cyrillic('geekideas'), 'гикайдиас')
    self.assertEqual(to_cyrillic('ssh'), 'своё-эс')

  def test_custom_cyrillic_word(self) -> None:
    # словарь умеет и русские слова, а не только латиницу
    self.write_config({'words': {'гикайдеас': 'гик айд+иас'}})

    self.assertEqual(to_cyrillic('гикайдеас'), 'гик айд+иас')
    self.assertEqual(to_cyrillic('Гикайдеас'), 'Гик айд+иас')
    self.assertEqual(to_cyrillic('гикайдеасы'), 'гикайдеасы')

  def test_custom_replacement_applies(self) -> None:
    self.write_config({'replacements': [['кованый замок', 'кованый зам+ок']]})

    self.assertEqual(to_cyrillic('кованый замок'), 'кованый зам+ок')

  def test_empty_replacement_match_does_not_crash(self) -> None:
    self.write_config({'replacements': [['^', 'префикс']]})

    self.assertEqual(to_cyrillic('текст'), 'префикстекст')

  def test_custom_phrase_matches_any_case(self) -> None:
    self.write_config({'words': {'кованый замок': 'кованый зам+ок'}})

    self.assertEqual(to_cyrillic('Кованый замок'), 'Кованый зам+ок')
    self.assertEqual(to_cyrillic('некованый замок'), 'некованый замок')

  def test_broken_json_does_not_crash(self) -> None:
    self.config_path.write_text('{ не json', encoding='utf-8')

    self.assertEqual(load_custom(), ({}, ()))
    self.assertEqual(to_cyrillic('ssh'), 'эс-эс-эйч')

  def test_broken_json_is_reported_once(self) -> None:
    self.config_path.write_text('{ не json', encoding='utf-8')
    errors = io.StringIO()

    with redirect_stderr(errors):
      to_cyrillic('ssh ssh ssh')

    self.assertEqual(errors.getvalue().count('не прочитан'), 1)

  def test_malformed_sections_are_ignored(self) -> None:
    self.write_config({
      'words': [],
      'replacements': ['не пара', ['шаблон'], ['а', 'б']],
    })

    words, replacements = load_custom()

    self.assertEqual(words, {})
    self.assertEqual(replacements, (('а', 'б'),))

  def test_broken_replacement_is_skipped_with_one_note(self) -> None:
    self.write_config({'replacements': [['[', 'замена'], ['кованый замок', 'кованый зам+ок']]})
    errors = io.StringIO()

    with redirect_stderr(errors):
      self.assertEqual(to_cyrillic('кованый замок'), 'кованый зам+ок')

    self.assertEqual(errors.getvalue().count('пропущена'), 1)


if __name__ == '__main__':
  unittest.main()
