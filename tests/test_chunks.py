# Тесты деления текста на куски синтеза.

import unittest

from tts.chunks import DEFAULT_CHUNK_CHARS, split_text


class SplitTextTestCase(unittest.TestCase):
  # Куски ограничены по длине и не теряют слов.

  def test_short_text_is_one_chunk(self) -> None:
    self.assertEqual(split_text('Привет, мир.'), ['Привет, мир.'])

  def test_chunks_fit_limit(self) -> None:
    text = 'Это первое предложение. Это второе предложение. Это третье предложение.'
    chunks = split_text(text, 30)

    self.assertTrue(all(len(chunk) <= 30 for chunk in chunks), chunks)

  def test_words_are_preserved(self) -> None:
    text = 'Раз два три четыре пять шесть семь восемь девять десять.'
    chunks = split_text(text, 20)
    merged = ' '.join(chunks).split()

    self.assertEqual(merged, text.split())

  def test_long_word_is_cut_hard(self) -> None:
    chunks = split_text('а' * 25, 10)

    self.assertTrue(all(len(chunk) <= 10 for chunk in chunks), chunks)
    self.assertEqual(''.join(chunks), 'а' * 25)

  def test_empty_paragraphs_are_dropped(self) -> None:
    self.assertEqual(split_text('\n\nабзац\n\n'), ['абзац'])

  def test_zero_limit_is_rejected(self) -> None:
    with self.assertRaises(ValueError):
      split_text('текст', 0)

  def test_number_and_unit_do_not_split(self) -> None:
    text = 'слово ' * 16 + '1 234 руб'
    chunks = split_text(text, 100)

    self.assertIn('1 234 руб', chunks[-1])
    self.assertTrue(all(len(chunk) <= 100 for chunk in chunks), chunks)

  def test_default_limit_fits_silero(self) -> None:
    # Silero падает выше 1000 символов; выход за предел должен ломать тест
    self.assertLessEqual(DEFAULT_CHUNK_CHARS, 900)


if __name__ == '__main__':
  unittest.main()
