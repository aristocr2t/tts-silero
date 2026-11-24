"""Числа словами: количественные, порядковые, дроби, проценты, разряды.

Silero выбрасывает цифры, поэтому числа переводятся в слова до синтеза:
2024 -> две тысячи двадцать четыре, 21% -> двадцать один процент,
5-го -> пятого, -3,5 -> минус три целых пять десятых.

HALF_SCALE живёт здесь: «полтора/полторы» — числительное, а не единица.
"""

import re

DIGITS = ('ноль', 'один', 'два', 'три', 'четыре', 'пять', 'шесть', 'семь',
          'восемь', 'девять')
UNITS_M = ('',) + DIGITS[1:]                    # один, два, три ...
UNITS_F = ('', 'одна', 'две') + DIGITS[3:]      # одна тысяча, две тысячи ...
TEENS = ('десять', 'одиннадцать', 'двенадцать', 'тринадцать', 'четырнадцать',
         'пятнадцать', 'шестнадцать', 'семнадцать', 'восемнадцать', 'девятнадцать')
TENS = ('', '', 'двадцать', 'тридцать', 'сорок', 'пятьдесят', 'шестьдесят',
    'семьдесят', 'восемьдесят', 'девяносто')
HUNDREDS = ('', 'сто', 'двести', 'триста', 'четыреста', 'пятьсот', 'шестьсот',
      'семьсот', 'восемьсот', 'девятьсот')
SCALES = (                                       # разряды от старшего к младшему
  (10 ** 9, ('миллиард', 'миллиарда', 'миллиардов'), UNITS_M),
  (10 ** 6, ('миллион', 'миллиона', 'миллионов'), UNITS_M),
  (1000, ('тысяча', 'тысячи', 'тысяч'), UNITS_F),
)

# окончание порядкового числа -> форма слова
ORD_FORMS = {
  'й': 'm', 'ый': 'm', 'ой': 'm',
  'я': 'f', 'ая': 'f',
  'е': 'n', 'ое': 'n',
  'го': 'gen', 'ого': 'gen',
  'му': 'dat', 'ому': 'dat',
  'м': 'prep', 'ом': 'prep',
  'ю': 'acc_f', 'ую': 'acc_f',
  'х': 'pl_gen', 'ых': 'pl_gen',
}

# количественное слово -> порядковое (мужской род, именительный)
ORD = dict(zip(DIGITS[1:], ('первый', 'второй', 'третий', 'четвёртый', 'пятый',
              'шестой', 'седьмой', 'восьмой', 'девятый')))
ORD['ноль'] = 'нулевой'
ORD['тысяча'] = 'тысячный'
ORD.update({w: w[:-2] + 'тый' for w in TEENS})   # десять -> десятый
ORD.update({
  'двадцать': 'двадцатый', 'тридцать': 'тридцатый', 'сорок': 'сороковой',
  'пятьдесят': 'пятидесятый', 'шестьдесят': 'шестидесятый',
  'семьдесят': 'семидесятый', 'восемьдесят': 'восьмидесятый',
  'девяносто': 'девяностый', 'сто': 'сотый', 'двести': 'двухсотый',
  'триста': 'трёхсотый', 'четыреста': 'четырёхсотый', 'пятьсот': 'пятисотый',
  'шестьсот': 'шестисотый', 'семьсот': 'семисотый',
  'восемьсот': 'восьмисотый', 'девятьсот': 'девятисотый',
})

SCALE_ORDINALS = {                     # разряд -> порядковое слово
  'тысячи': 'тысячный',
  'тысяч': 'тысячный',
  'миллион': 'миллионный',
  'миллиона': 'миллионный',
  'миллионов': 'миллионный',
  'миллиард': 'миллиардный',
  'миллиарда': 'миллиардный',
  'миллиардов': 'миллиардный',
}

PERCENT_FORMS = ('процент', 'процента', 'процентов')

SEPARATORS = {
  '.': 'точка',
  '/': 'дробь',
  ':': '',
  ',': 'запятая',
}

# знаков после запятой -> формы знаменателя («пять десятых»)
FRACTIONS = {
  1: ('десятая', 'десятых', 'десятых'),
  2: ('сотая', 'сотых', 'сотых'),
  3: ('тысячная', 'тысячных', 'тысячных'),
  4: ('десятитысячная', 'десятитысячных', 'десятитысячных'),
  5: ('стотысячная', 'стотысячных', 'стотысячных'),
  6: ('миллионная', 'миллионных', 'миллионных'),
}


def plural(n: int, forms: tuple[str, str, str]) -> str:
  # plural(21, ('процент', 'процента', 'процентов')) -> 'процент'.
  tail = n % 100

  if 11 <= tail <= 14:
    return forms[2]

  tail %= 10

  if tail == 1:
    return forms[0]

  return forms[1] if 2 <= tail <= 4 else forms[2]


def triplet(n: int, units: tuple[str, ...]) -> list[str]:
  words = []
  hundreds, rest = divmod(n, 100)

  if hundreds:
    words.append(HUNDREDS[hundreds])

  if 10 <= rest <= 19:
    words.append(TEENS[rest - 10])
  else:
    tens, ones = divmod(rest, 10)

    if tens:
      words.append(TENS[tens])

    if ones:
      words.append(units[ones])

  return words


def cardinal(n: int, units: tuple[str, ...] = UNITS_M) -> list[str]:
  """Целое число -> список слов: 2024 -> две тысячи двадцать четыре.

  units — род последней группы: UNITS_F для «одна целая», «две десятых»."""

  if n == 0:
    return ['ноль']

  words = []

  for value, forms, scale_units in SCALES:
    count, n = divmod(n, value)

    if count:
      # «тысяча», а не «одна тысяча»: так говорят по-русски
      if count == 1 and forms[0] == 'тысяча':
        words.append(forms[0])
      else:
        words += triplet(count, scale_units) + [plural(count, forms)]

  if n:
    words += triplet(n, units)

  return words


def digit_by_digit(digits: str) -> list[str]:
  return [DIGITS[int(c)] for c in digits]


def integer_words(digits: str, units: tuple[str, ...] = UNITS_M) -> list[str]:
  # Цифровая запись целого -> слова; длинное число и ведущий ноль — по цифрам.
  if len(digits) > 12 or (len(digits) > 1 and digits[0] == '0'):
    return digit_by_digit(digits)
  return cardinal(int(digits), units)


def decimal_words(whole: str, fraction: str) -> list[str]:
  # 3,5 -> три целых пять десятых; 0,93 -> ноль целых девяносто три сотых.
  if len(fraction) > 6:                   # мельче миллионных — читаем по цифрам
    return integer_words(whole, UNITS_F) + ['запятая'] + digit_by_digit(fraction)
  words = integer_words(whole, UNITS_F) + [plural(int(whole), ('целая', 'целых', 'целых'))]
  numerator = int(fraction)              # 0,05 -> знаменатель сотых, числитель пять
  words += integer_words(str(numerator), UNITS_F)
  words.append(plural(numerator, FRACTIONS[len(fraction)]))

  return words


def drop_comma_groups(raw: str) -> str:
  # 1,234,567 -> 1234567; одиночная запятая остаётся дробью (1,5).
  return re.sub(
    r'^(\d{1,3}(?:,\d{3}){2,})(?=[.,]|$)',
    lambda match: match.group(1).replace(',', ''),
    raw,
  )


def number_words(raw: str, units: tuple[str, ...] = UNITS_M) -> str:
  """Строка числа -> слова. Запятая — десятичная дробь, остальные разделители
  читаются по своему имени.

  '1 234,5' -> тысяча двести тридцать четыре целых пять десятых;
  '-3,5' -> минус три целых пять десятых;
  '0.93.0' -> ноль точка девяносто три точка ноль;
  '10:30' -> десять тридцать (двоеточие как пауза);
  длинные номера и числа с ведущим нулём читаются по цифрам.
  """
  raw = raw.replace('\u00a0', ' ').replace(' ', '')
  minus = raw.startswith('-')
  raw = raw.lstrip('-+')

  if not raw:
    return ''

  # 1,234,567 — разряды через запятую; одиночная запятая остаётся дробью (1,5)
  raw = drop_comma_groups(raw)

  groups = re.split(r'([.,:/])', raw)

  if len(groups) == 3 and groups[1] == ',' and groups[2]:
    words = decimal_words(groups[0], groups[2])
  else:
    words = integer_words(groups[0], units)

    for i in range(1, len(groups), 2):
      separator, part = groups[i], groups[i + 1]

      if not part:
        continue

      if SEPARATORS[separator]:
        words.append(SEPARATORS[separator])

      words += integer_words(part, units)

  if minus:
    words.insert(0, 'минус')

  return ' '.join(words)


# «1500 году» — количество, а не «полторы тысячи»
YEAR_AFTER = re.compile(
  r'\s*(?:год|года|году|годом|годе|годы|годов|годах|гг?\.)(?![А-Яа-яЁё])',
  re.IGNORECASE,
)

# целое число: разряды пробелом или запятыми (1,234,567), дробная часть — [.,]
INTEGER_BODY = r'-?\d+(?:[ \u00a0]\d{3}(?!\d)|(?:,\d{3}){2,})*'
NUMBER_BODY = INTEGER_BODY + r'(?:[.,]\d+)?'

# число: необязательный минус, разряды через пробел, дробная часть, знак %
# (перед латинской буквой цифра не трогается — ею занимается pronounce: k8s)
NUMBER = re.compile(r'(?<![A-Za-z0-9])(-?\d+(?:[ \u00a0]\d{3}(?!\d))*(?:[.,:/]\d+)*)(\s?%)?')
ORDINAL = re.compile(
  r'(?<![A-Za-z0-9])(\d+)-(' + '|'.join(sorted(ORD_FORMS, key=len, reverse=True)) + r')'
  r'(?![A-Za-zА-Яа-яЁё0-9])',
  re.IGNORECASE,
)


def number_phrase(match: re.Match[str]) -> str:
  plain = match.group(1).replace(' ', '').replace('\u00a0', '')
  sign, digits = ('минус ', plain[1:]) if plain.startswith('-') else ('', plain)

  if digits in HALF_SCALE and not match.group(2) \
      and not YEAR_AFTER.match(match.string, match.end()):
    return sign + HALF_SCALE[digits]              # 1500 -> полторы тысячи

  words = number_words(match.group(1))

  if match.group(2):                      # 21% -> двадцать один процент
    digits = re.fullmatch(r'-?\d+', match.group(1).strip())

    if digits:
      words += ' ' + plural(abs(int(digits.group())), PERCENT_FORMS)
    else:
      words += ' ' + PERCENT_FORMS[1]      # дробь: «пять десятых процента»

  return words


def inflect_ordinal(base: str, form: str = 'm') -> str:
  # первый + 'gen' -> первого, двухтысячный + 'prep' -> двухтысячном.
  if form == 'm':
    return base

  third = base.endswith('ий')             # третий -> третья, третьего
  endings = {
    'f': 'ья' if third else 'ая',        # первая, третья
    'n': 'ье' if third else 'ое',        # первое, третье
    'gen': 'ьего' if third else 'ого',   # первого, третьего
    'dat': 'ьему' if third else 'ому',   # первому, третьему
    'prep': 'ьем' if third else 'ом',    # первом, третьем
    'acc_f': 'ью' if third else 'ую',    # первую, третью
    'pl_gen': 'ьих' if third else 'ых',  # первых, третьих
    'pl_nom': 'ьи' if third else 'ые',   # первые, третьи
  }

  return base[:-2] + endings[form]


def ordinal_word(word: str, form: str = 'm') -> str:
  # первый + 'gen' -> первого, третий + 'f' -> третья.
  base = ORD.get(word)

  if base is None:
    return word

  return inflect_ordinal(base, form)


def ordinal_phrase(match: re.Match[str]) -> str:
  # 5-й -> пятый, 5-го -> пятого, 1920-х -> тысяча девятьсот двадцатых.
  raw = match.group(1)
  words = digit_by_digit(raw) if (len(raw) > 12 or (len(raw) > 1 and raw[0] == '0')) \
    else cardinal(int(raw))
  form = ORD_FORMS[match.group(2).lower()]

  # «1920-е годы» — это двадцатые, а не двадцатое: круглые числа от сотни
  # со средним окончанием читаются во множественном числе
  if form == 'n' and int(raw) % 10 == 0 and int(raw) >= 100:
    form = 'pl_nom'

  if words[-1] in ORD:
    words[-1] = ordinal_word(words[-1], form)
  elif len(words) >= 2:
    scale = scale_ordinal(words[-2], words[-1])

    if scale is not None:                    # 2000-й -> двухтысячный
      words = [*words[:-2], inflect_ordinal(scale, form)]

  return ' '.join(words)


# Ключ пишется как в тексте, регистр важен: МБ — байты, Мб — биты.
# Значение — три формы слова и род числительного (True — женский: одна секунда).

# Плюс между словами читается словом: сам символ движок проглатывает без паузы.
# Знак у числа (+7) и «C++» не трогаем.
HALF_SCALE = {                      # 1500 -> полторы тысячи рублей
  '1500': 'полторы тысячи',
  '1500000': 'полтора миллиона',
  '1500000000': 'полтора миллиарда',
}

# Родительный падеж числительных: «вместо 106» -> «вместо ста шести».
GENITIVE_WORDS = {
  'один': 'одного',
  'одна': 'одной',
  'два': 'двух',
  'две': 'двух',
  'три': 'трёх',
  'четыре': 'четырёх',
  'пять': 'пяти',
  'шесть': 'шести',
  'семь': 'семи',
  'восемь': 'восьми',
  'девять': 'девяти',
  'десять': 'десяти',
  'одиннадцать': 'одиннадцати',
  'двенадцать': 'двенадцати',
  'тринадцать': 'тринадцати',
  'четырнадцать': 'четырнадцати',
  'пятнадцать': 'пятнадцати',
  'шестнадцать': 'шестнадцати',
  'семнадцать': 'семнадцати',
  'восемнадцать': 'восемнадцати',
  'девятнадцать': 'девятнадцати',
  'двадцать': 'двадцати',
  'тридцать': 'тридцати',
  'сорок': 'сорока',
  'пятьдесят': 'пятидесяти',
  'шестьдесят': 'шестидесяти',
  'семьдесят': 'семидесяти',
  'восемьдесят': 'восьмидесяти',
  'девяносто': 'девяноста',
  'сто': 'ста',
  'двести': 'двухсот',
  'триста': 'трёхсот',
  'четыреста': 'четырёхсот',
  'пятьсот': 'пятисот',
  'шестьсот': 'шестисот',
  'семьсот': 'семисот',
  'восемьсот': 'восьмисот',
  'девятьсот': 'девятисот',
  'тысяча': 'тысячи',
  'тысячи': 'тысяч',
  'тысяч': 'тысяч',
  'миллион': 'миллиона',
  'миллиона': 'миллионов',
  'миллионов': 'миллионов',
  'миллиард': 'миллиарда',
  'миллиарда': 'миллиардов',
  'миллиардов': 'миллиардов',
  'полтора': 'полутора',
  'полторы': 'полутора',
  'целая': 'целой',
}

# предлоги, после которых число идёт в родительном падеже
GENITIVE_PREPOSITIONS = (
  'вместо', 'около', 'до', 'от', 'без', 'свыше', 'более', 'менее',
  'больше', 'меньше', 'порядка', 'из', 'среди',
)
GENITIVE_NUMBER = re.compile(
  r'(?P<prep>(?<![А-Яа-яЁё])'
  + '|'.join(sorted(GENITIVE_PREPOSITIONS, key=len, reverse=True))
  + r')(?P<space>\s+)(?P<number>' + NUMBER_BODY + r')'
  r'(?P<percent>\s?%)?',
  re.IGNORECASE,
)


def scale_ordinal(count_word: str, scale_word: str) -> str | None:
  # «две тысячи» -> двухтысячный, «один миллион» -> миллионный.
  base = SCALE_ORDINALS.get(scale_word)

  if base is None:
    return None

  if count_word == 'один':
    return base

  prefix = 'сто' if count_word == 'сто' else GENITIVE_WORDS.get(count_word)

  return None if prefix is None else f'{prefix}{base}'


def percent_word_genitive(number: str) -> str:
  # После предлога: 1 и дробь -> процента, остальные -> процентов.
  plain = drop_comma_groups(
    number.replace(' ', '').replace('\u00a0', ''),
  ).lstrip('-')

  if re.fullmatch(r'\d+', plain):
    value = int(plain)

    if value % 10 == 1 and value % 100 != 11:
      return PERCENT_FORMS[1]

    return PERCENT_FORMS[2]

  return PERCENT_FORMS[1] if re.fullmatch(r'\d+[.,]\d+', plain) else PERCENT_FORMS[2]


def number_phrase_genitive(match: re.Match[str]) -> str:
  # «вместо 106» -> «вместо ста шести»; нечисловые значения не трогаем.
  number = match.group('number')
  words = number_words(number)
  converted = [GENITIVE_WORDS.get(word, word) for word in words.split(' ')]
  tail = f' {percent_word_genitive(number)}' if match.group('percent') else ''

  return f"{match.group('prep')}{match.group('space')}{' '.join(converted)}{tail}"
