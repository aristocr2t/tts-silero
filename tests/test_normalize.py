"""Тесты подготовки текста: числа, единицы, символы, произношение.

Запуск: python -m unittest discover -s tests
Ударения выключены (VOICE_ACCENT=0), иначе результат зависит от ruaccent.
"""

import os
import tempfile
import unittest
from pathlib import Path

os.environ['VOICE_ACCENT'] = '0'
# изоляция от ~/.config/tts-silero.json: тесты не должны зависеть от машины
os.environ['VOICE_CONFIG'] = str(Path(tempfile.gettempdir()) / f'tts-silero-absent-{os.getpid()}.json')

from tts.normalize import BREAK_TOKEN, collapse_repeated_stress, to_cyrillic  # noqa: E402


class NumbersTestCase(unittest.TestCase):
  # Числа: количественные, порядковые, дроби, проценты.

  def test_cardinal(self) -> None:
    self.assertEqual(to_cyrillic('2024'), 'две тысячи двадцать четыре')

  def test_decimal(self) -> None:
    self.assertEqual(
      to_cyrillic('1 234,5'),
      'тысяча двести тридцать четыре целых пять десятых',
    )

  def test_thousands_commas_are_groups_not_fraction(self) -> None:
    self.assertEqual(
      to_cyrillic('1,234,567'),
      'один миллион двести тридцать четыре тысячи пятьсот шестьдесят семь',
    )
    self.assertEqual(to_cyrillic('1,5'), 'одна целая пять десятых')
    self.assertEqual(to_cyrillic('1,2,3'), 'один запятая два запятая три')

  def test_percent_after_preposition(self) -> None:
    self.assertEqual(to_cyrillic('более 50%'), 'более пятидесяти процентов')
    self.assertEqual(to_cyrillic('около 15%'), 'около пятнадцати процентов')
    self.assertEqual(to_cyrillic('более 1%'), 'более одного процента')
    self.assertEqual(to_cyrillic('около 1,5%'), 'около одной целой пяти десятых процента')
    self.assertEqual(to_cyrillic('около 21%'), 'около двадцати одного процента')
    self.assertEqual(to_cyrillic('более 11%'), 'более одиннадцати процентов')

  def test_thousands_commas_after_preposition(self) -> None:
    self.assertEqual(
      to_cyrillic('более 1,234,567'),
      'более одного миллиона двухсот тридцати четырёх тысяч пятисот шестидесяти семи',
    )

  def test_percent_agrees_with_number(self) -> None:
    self.assertEqual(to_cyrillic('21%'), 'двадцать один процент')
    self.assertEqual(to_cyrillic('5%'), 'пять процентов')
    self.assertEqual(to_cyrillic('-5%'), 'минус пять процентов')
    self.assertEqual(to_cyrillic('-1%'), 'минус один процент')

  def test_ordinal(self) -> None:
    self.assertEqual(to_cyrillic('5-го'), 'пятого')

  def test_ordinal_with_scale(self) -> None:
    self.assertEqual(to_cyrillic('2000-й'), 'двухтысячный')
    self.assertEqual(to_cyrillic('3000-м году'), 'трёхтысячном году')
    self.assertEqual(to_cyrillic('в 2000-х годах'), 'в двухтысячных годах')
    self.assertEqual(to_cyrillic('1000000-й'), 'миллионный')
    self.assertEqual(to_cyrillic('1002000-й'), 'один миллион двухтысячный')

  def test_negative(self) -> None:
    self.assertEqual(to_cyrillic('-3,5'), 'минус три целых пять десятых')


class UnitsTestCase(unittest.TestCase):
  # Единицы измерения: род, падеж, составные и множитель «к».

  def test_base_units(self) -> None:
    self.assertEqual(to_cyrillic('10 мс'), 'десять миллисекунд')
    self.assertEqual(to_cyrillic('10 м/с'), 'десять метров в секунду')
    self.assertEqual(to_cyrillic('5 кг'), 'пять килограммов')

  def test_feminine_agreement(self) -> None:
    self.assertEqual(to_cyrillic('1 мс'), 'одна миллисекунда')
    self.assertEqual(to_cyrillic('21 мс'), 'двадцать одна миллисекунда')

  def test_one_and_half(self) -> None:
    self.assertEqual(to_cyrillic('1,5 с'), 'полторы секунды')
    self.assertEqual(to_cyrillic('1,5 м'), 'полтора метра')

  def test_half_scale(self) -> None:
    self.assertEqual(to_cyrillic('1500 руб'), 'полторы тысячи рублей')

  def test_thousands_commas_in_units(self) -> None:
    self.assertEqual(
      to_cyrillic('1,234,567 руб'),
      'один миллион двести тридцать четыре тысячи пятьсот шестьдесят семь рублей',
    )

  def test_thousands_commas_in_compound(self) -> None:
    self.assertEqual(
      to_cyrillic('1,234,567 кг/м³'),
      'один миллион двести тридцать четыре тысячи пятьсот шестьдесят семь '
      'килограммов на кубический метр',
    )

  def test_year_is_not_half_scale(self) -> None:
    self.assertEqual(to_cyrillic('в 1500 году'), 'в тысяча пятьсот году')

  def test_kilo_suffix(self) -> None:
    self.assertEqual(to_cyrillic('15к'), 'пятнадцать тысяч')
    self.assertEqual(to_cyrillic('1500к'), 'полтора миллиона')

  def test_compound(self) -> None:
    self.assertEqual(
      to_cyrillic('5 кг/м³'),
      'пять килограммов на кубический метр',
    )
    self.assertEqual(to_cyrillic('10 руб/шт'), 'десять рублей за штуку')

  def test_latin_units(self) -> None:
    self.assertEqual(to_cyrillic('10 ms'), 'десять миллисекунд')
    self.assertEqual(to_cyrillic('8 GB'), 'восемь гигабайт')
    self.assertEqual(to_cyrillic('10 km/h'), 'десять километров в час')

  def test_unit_case_is_significant(self) -> None:
    # «гб» — не «ГБ»: неизвестная единица не роняет нормализацию
    self.assertEqual(to_cyrillic('около 5 гб'), 'около пяти гб')

  def test_fraction_stays_a_fraction(self) -> None:
    self.assertEqual(to_cyrillic('1/2'), 'один дробь два')

  def test_genitive_before_units(self) -> None:
    self.assertEqual(to_cyrillic('около 5 мин'), 'около пяти минут')
    self.assertEqual(to_cyrillic('до 2 ГБ'), 'до двух гигабайт')
    self.assertEqual(to_cyrillic('от 10 до 20 мс'), 'от десяти до двадцати миллисекунд')
    self.assertEqual(to_cyrillic('около 1 ГБ'), 'около одного гигабайта')
    self.assertEqual(
      to_cyrillic('около 5 кг/м³'),
      'около пяти килограммов на кубический метр',
    )


class SymbolsTestCase(unittest.TestCase):
  # Символы, которые Silero проглатывает.

  def test_plus_keeps_words_apart(self) -> None:
    self.assertEqual(to_cyrillic('«Лады» + фото'), 'Лады, плюс фото')

  def test_arithmetic_plus(self) -> None:
    self.assertEqual(to_cyrillic('2+2=4'), 'два плюс два равно четыре')

  def test_equals(self) -> None:
    self.assertEqual(to_cyrillic('«Оки» = «Окей»'), 'Оки, равно Окей')

  def test_comparison_and_arrow(self) -> None:
    # одиночные латинские буквы читаются как названия: a -> эй
    self.assertEqual(to_cyrillic('a >= b'), 'эй больше или равно би')
    self.assertEqual(to_cyrillic('Оки → Окей'), 'Оки следовательно Окей')

  def test_double_plus_is_spoken(self) -> None:
    # «+» — наш знак ударения, поэтому ++ обязан стать словами
    self.assertEqual(to_cyrillic('язык C++'), 'язык си плюс плюс')

  def test_percent_fraction(self) -> None:
    self.assertEqual(to_cyrillic('3,5%'), 'три целых пять десятых процента')


class PronunciationTestCase(unittest.TestCase):
  # Латиница, аббревиатуры и твёрдые согласные.

  def test_acronyms(self) -> None:
    self.assertEqual(to_cyrillic('tts'), 'ти-ти-эс')
    self.assertEqual(to_cyrillic('ssh'), 'эс-эс-эйч')
    self.assertEqual(to_cyrillic('ssr'), 'эс-эс-ар')
    self.assertEqual(to_cyrillic('pdf'), 'пэ-дэ-эф')

  def test_words_dictionary(self) -> None:
    self.assertEqual(to_cyrillic('xenia'), 'ксения')
    self.assertEqual(to_cyrillic('ffmpeg'), 'эф-эф-эм-пэг')

  def test_words_from_user_reports(self) -> None:
    self.assertEqual(to_cyrillic('improver'), 'импрувер')
    self.assertEqual(to_cyrillic('snapshot'), 'снапшот')
    self.assertEqual(to_cyrillic('to'), 'ту')

  def test_paths_and_file_names(self) -> None:
    self.assertEqual(to_cyrillic('mcp.json'), 'эм-си-пи точка джейсон')
    self.assertEqual(
      to_cyrillic('/Users/aristocr2t/.pi/agent'),
      'слэш йузэрз слэш аристокр два ти слэш точка пай слэш эйджэнт',
    )
    self.assertEqual(to_cyrillic('webpage'), 'веб-пэйдж')
    self.assertEqual(to_cyrillic('mcp__page__fetch'), 'эм-си-пи пэйдж фэч')

  def test_repeated_stress_is_collapsed(self) -> None:
    # ruaccent дописывает метку к слову, где она уже стоит: ++оба
    self.assertEqual(collapse_repeated_stress('++оба и +два'), '+оба и +два')

  def test_break_marker_follows_latin_words(self) -> None:
    # после английского слова ставится маркер паузы
    self.assertEqual(to_cyrillic('fetch для', breaks=True), f'фэч{BREAK_TOKEN} для')
    self.assertEqual(to_cyrillic('fetch для'), 'фэч для')
    self.assertEqual(to_cyrillic('для документации', breaks=True), 'для документации')

  def test_file_masks(self) -> None:
    self.assertEqual(
      to_cyrillic('remote-*.sh'),
      'римоут дефис звёздочка точка эс аш',
    )
    self.assertEqual(
      to_cyrillic('tts-ogg.sh'),
      'ти-ти-эс дефис о-джи-джи точка эс аш',
    )
    self.assertEqual(to_cyrillic('/tmp удалила'), 'слэш ти-эм-пи удалила')

  def test_versions_and_files_with_digits(self) -> None:
    self.assertEqual(to_cyrillic('v2.0'), 'ви два точка ноль')
    self.assertEqual(
      to_cyrillic('/tmp/voice-2.sh'),
      'слэш ти-эм-пи слэш войс дефис два точка эс аш',
    )
    self.assertEqual(
      to_cyrillic('python3.11.md'),
      'пайтэн три точка одиннадцать точка эм ди',
    )

  def test_asterisk_is_spoken(self) -> None:
    self.assertEqual(to_cyrillic('2 * 3'), 'два звёздочка три')

  def test_words_mentioning_both(self) -> None:
    self.assertEqual(to_cyrillic('Chromium'), 'хромиум')

  def test_time_zone(self) -> None:
    self.assertEqual(to_cyrillic('17:00 MSK'), 'семнадцать ноль ноль по московскому времени')
    self.assertEqual(
      to_cyrillic('09:30 CET'),
      'ноль девять тридцать по центральноевропейскому времени',
    )
    self.assertEqual(
      to_cyrillic('17:00 UTC+3'),
      'семнадцать ноль ноль плюс три по ю-ти-си',
    )
    self.assertEqual(
      to_cyrillic('17:00 UTC+5:30'),
      'семнадцать ноль ноль плюс пять тридцать по ю-ти-си',
    )
    self.assertEqual(
      to_cyrillic('17:00 GMT-3:30'),
      'семнадцать ноль ноль минус три тридцать по гринвичу',
    )
    # только заглавные и только после времени
    self.assertEqual(to_cyrillic('msk'), 'мск')
    self.assertEqual(to_cyrillic('MSK время'), 'эм-эс-кей время')

  def test_tilde_before_number_means_about(self) -> None:
    self.assertEqual(to_cyrillic('~30 минут назад'), 'около тридцати минут назад')
    self.assertEqual(to_cyrillic('~/Repos'), 'тильда слэш рипоуз')

  def test_genitive_after_prepositions(self) -> None:
    self.assertEqual(
      to_cyrillic('68 символов вместо 106'),
      'шестьдесят восемь символов вместо ста шести',
    )
    self.assertEqual(to_cyrillic('около 5 минут'), 'около пяти минут')
    self.assertEqual(to_cyrillic('от 10 до 20'), 'от десяти до двадцати')

  def test_quotes_do_not_glue_words(self) -> None:
    self.assertEqual(to_cyrillic('«to» уместно'), 'ту, уместно')
    self.assertEqual(to_cyrillic('слово «так».'), 'слово так.')
    self.assertEqual(to_cyrillic('«слово»'), 'слово')

  def test_shell_tools(self) -> None:
    self.assertEqual(to_cyrillic('PATH'), 'паф')
    self.assertEqual(to_cyrillic('uvx'), 'ю-ви-икс')
    self.assertEqual(to_cyrillic('rg'), 'эр-гэ')
    self.assertEqual(to_cyrillic('⌘Q'), 'комманд кью')

  def test_hard_consonant(self) -> None:
    self.assertEqual(to_cyrillic('тест'), 'тэст')
    self.assertEqual(to_cyrillic('синтез'), 'синтэз')

  def test_stress_from_user_reports(self) -> None:
    # «зап+ушен», «п+айтон» — правки, которые просил автор голоса
    self.assertEqual(to_cyrillic('запушен'), 'зап+ушен')
    self.assertEqual(to_cyrillic('пайтон'), 'п+айтон')
    self.assertEqual(to_cyrillic('оба хоста'), 'оба хост+а')
    self.assertEqual(to_cyrillic('по-твоему'), 'потв+оему')
    self.assertEqual(to_cyrillic('по-моему'), 'пом+оему')
    self.assertEqual(to_cyrillic('маркетплейсы'), 'маркетпл+эйсы')

  def test_push_stress(self) -> None:
    # ruaccent ударяет «пуш+у»; правильные формы — п+ушу, п+ушить
    self.assertEqual(to_cyrillic('пушу'), 'п+ушу')
    self.assertEqual(to_cyrillic('пушить'), 'п+ушить')
    self.assertEqual(to_cyrillic('запушу'), 'зап+ушу')
    # эти слова ударены на другом слоге и меняться не должны
    self.assertEqual(to_cyrillic('распушить'), 'распушить')
    self.assertEqual(to_cyrillic('пушок'), 'пушок')

  def test_address_is_spelled(self) -> None:
    self.assertEqual(
      to_cyrillic('10.0.0.1'),
      'десять точка ноль точка ноль точка один',
    )


if __name__ == '__main__':
  unittest.main()
