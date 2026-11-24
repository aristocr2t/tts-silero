"""Конвейер подготовки текста: от исходной строки до кириллицы с ударениями.

Порядок важен:

1. собственные замены произношения (твёрдое «тэ» в «тест», «синтез»);
2. символы, которые Silero теряет: плюс, равно, сравнения, стрелки;
3. числа: порядковые, количественные, проценты, «15к»;
4. единицы измерения: «10 мс», «5 кг/м³», «1500 руб/шт»;
5. латиница по произношению: tts -> ти-ти-эс, bash -> бэш;
6. ударения по контексту в самом конце, когда текст уже только кириллица.
"""

import re

from .accent import accentize
from .latin import pronounce, pronounce_russian
from .numbers import (
  GENITIVE_NUMBER,
  NUMBER,
  ORDINAL,
  number_phrase,
  number_phrase_genitive,
  ordinal_phrase,
)
from .operators import ARITHMETIC_PLUS, EQUALS, OPERATOR, PLUS, operator_phrase
from .units import (
  COMPOUND,
  GENITIVE_UNIT,
  KILO,
  UNIT,
  compound_phrase,
  genitive_unit_phrase,
  kilo_phrase,
  unit_phrase,
)

LATIN_WORD = re.compile(r'([A-Za-z][A-Za-z0-9]*)')

TIME_ZONE_WORDS = {
  'MSK': 'по московскому времени',
  'MSD': 'по московскому летнему времени',
  'UTC': 'по ю-ти-си',
  'GMT': 'по гринвичу',
  'WET': 'по западноевропейскому времени',
  'WEST': 'по западноевропейскому летнему времени',
  'CET': 'по центральноевропейскому времени',
  'CEST': 'по центральноевропейскому летнему времени',
  'EET': 'по восточноевропейскому времени',
  'EEST': 'по восточноевропейскому летнему времени',
  'EST': 'по восточному времени США',
  'EDT': 'по восточному летнему времени США',
  'CST': 'по центральному времени США',
  'CDT': 'по центральному летнему времени США',
  'MST': 'по горному времени США',
  'MDT': 'по горному летнему времени США',
  'PST': 'по тихоокеанскому времени США',
  'PDT': 'по тихоокеанскому летнему времени США',
  'IST': 'по индийскому времени',
  'JST': 'по японскому времени',
  'KST': 'по корейскому времени',
  'SGT': 'по сингапурскому времени',
  'HKT': 'по гонконгскому времени',
  'AEST': 'по австралийскому восточному времени',
  'AEDT': 'по австралийскому восточному летнему времени',
}

# зона читается только заглавными и только сразу после времени: 17:00 MSK
TIME_ZONE = re.compile(
  r'(?<=\d\d:\d\d)(\s+)(' + '|'.join(sorted(TIME_ZONE_WORDS, key=len, reverse=True)) + r')(?![A-Za-zА-Яа-яЁё])',
)

# смещение для UTC/GMT: 17:00 UTC+3, 17:00 UTC+5:30
TIME_ZONE_OFFSET = re.compile(
  r'(?<=\d\d:\d\d)(\s+)(UTC|GMT)(?P<sign>[+-])(?P<offset>\d{1,2})'
  r'(?::(?P<minutes>\d{2}))?(?!\d)',
)

# ruaccent дописывает «+» к слову, у которого метка уже стоит в начале: ++оба
REPEATED_STRESS = re.compile(r'\+{2,}')

# маркер паузы: после экранирования превращается в SSML <break>
BREAK_TOKEN = '\u2401'


def collapse_repeated_stress(text: str) -> str:
  # Две метки подряд Silero не понимает: «++оба» -> «+оба».
  return REPEATED_STRESS.sub('+', text)


# путь и имя файла: «/Users/x/.pi/agent», «mcp.json»
PATH_SLASH = re.compile(r'(?<=[A-Za-z0-9._~-])/|/(?=[A-Za-z0-9._~-])')
# точку в «3.5» разбирают числа, поэтому внутри числа точка не трогается
PATH_DOT = re.compile(r'(?<!\d)\.(?=[A-Za-z0-9])')
# версия после латинской буквы: v2.0 -> v2 точка 0
VERSION_AFTER_LATIN = re.compile(r'(?<=[A-Za-z])\d+(?:\.\d+)+')
# «~30 минут» — это приближение, «~/Repos» — домашний каталог
APPROXIMATE_TILDE = re.compile(r'~(?=\s?\d)')
PATH_TILDE = re.compile(r'~(?=[A-Za-z0-9._/-])')
# подчёркивания в идентификаторах: mcp__page__fetch -> три слова
IDENTIFIER_UNDERSCORES = re.compile(r'_+')
FILE_TOKEN = re.compile(r'[A-Za-z0-9_.*\-/~]+')
# расширения: «.sh» -> «точка эс аш», иначе одиночная «ш» слипается со словом
FILE_EXTENSIONS = {
  'sh': 'эс аш',
  'py': 'пи вай',
  'json': 'джейсон',
  'js': 'джей эс',
  'ts': 'ти эс',
  'tsx': 'ти эс икс',
  'md': 'эм ди',
  'txt': 'ти икс ти',
  'yml': 'ямл',
  'yaml': 'ямл',
  'toml': 'томл',
  'cfg': 'си эф джи',
  'ini': 'и эн и',
  'log': 'лог',
  'csv': 'си эс ви',
  'html': 'эйч ти эм эл',
  'css': 'си эс эс',
  'go': 'гоу',
  'java': 'джава',
  'zip': 'зип',
  'rar': 'рар',
  'gz': 'джи зед',
  'tar': 'тар',
  'env': 'энв',
  'plist': 'пи лист',
  'wav': 'вав',
  'mp3': 'эм пэ три',
  'png': 'пи эн джи',
  'jpg': 'джей пей джи',
}

ASTERISK = re.compile(r'\*')
OPENING_QUOTES = re.compile(r'[«“]')
CLOSING_QUOTE_BEFORE_PUNCT = re.compile(r'[»”](?=[.,!?;:…)])')
CLOSING_QUOTE_AT_END = re.compile(r'[»”]\s*$')
CLOSING_QUOTE = re.compile(r'[»”]')
NUMBER_SIGN = '№'


def time_zone_phrase(match: re.Match[str]) -> str:
  # «17:00 MSK» -> «17:00 по московскому времени».
  return f'{match.group(1)}{TIME_ZONE_WORDS[match.group(2)]}'


def time_zone_offset_phrase(match: re.Match[str]) -> str:
  """«17:00 UTC+3» -> «17:00 плюс 3 по ю-ти-си»: сначала смещение, потом зона.

  Минуты отдаются числам вместе со смещением: UTC+5:30 -> плюс 5:30.
  """
  adjective = 'плюс' if match.group('sign') == '+' else 'минус'
  offset = match.group('offset')

  if match.group('minutes'):
    offset = f"{offset}:{match.group('minutes')}"

  zone = TIME_ZONE_WORDS[match.group(2)]

  return f"{match.group(1)}{adjective} {offset} {zone}"


def spell_file_names(text: str) -> str:
  # Имена файлов и маски: «remote-*.sh» -> ремоут дефис звёздочка точка ш.
  def replace_token(match: re.Match[str]) -> str:
    token = match.group()
    extension = re.search(r'\.([A-Za-z0-9]+)$', token)
    known = extension.group(1).lower() in FILE_EXTENSIONS if extension else False

    if '*' not in token and not known:
      return token

    base = token[:extension.start()] if known else token

    for symbol, word in (
      ('/', ' слэш '),
      ('-', ' дефис '),
      ('*', ' звёздочка '),
      ('.', ' точка '),
    ):
      base = base.replace(symbol, word)

    if not known:
      return base

    return f'{base} точка {FILE_EXTENSIONS[extension.group(1).lower()]}'.strip()

  return FILE_TOKEN.sub(replace_token, text)


def spell_version(match: re.Match[str]) -> str:
  # «v2.0» -> «v2 точка 0», чтобы числа не слипались.
  return match.group().replace('.', ' точка ')


def spell_paths(text: str) -> str:
  """Пути и имена файлов: «/» -> слэш, «.» -> точка, «~» -> тильда.

  Silero проглатывает слэш и читает точку как паузу, поэтому разделители
  называются словами: «mcp точка json», «слэш юзерс слэш пай».
  """
  text = IDENTIFIER_UNDERSCORES.sub(' ', text)
  text = PATH_TILDE.sub(' тильда ', text)
  text = PATH_SLASH.sub(' слэш ', text)
  text = PATH_DOT.sub(' точка ', text)

  return text


def repair_quotes(text: str) -> str:
  """Кавычки Silero выбрасывает, и соседние слова слипаются.

  Закрывающая перед словом становится запятой (пауза), открывающая — пробелом,
  чтобы «слово» не приклеилось к предыдущему.
  """
  text = CLOSING_QUOTE_BEFORE_PUNCT.sub('', text)
  text = CLOSING_QUOTE_AT_END.sub('', text)
  text = CLOSING_QUOTE.sub(', ', text)
  text = OPENING_QUOTES.sub(' ', text)

  return text


def to_cyrillic(text: str, breaks: bool = False) -> str:
  # Переводит текст в кириллицу; breaks=True помечает паузы после латиницы.
  text = repair_quotes(text)
  text = APPROXIMATE_TILDE.sub('около ', text)
  text = TIME_ZONE_OFFSET.sub(time_zone_offset_phrase, text)
  text = TIME_ZONE.sub(time_zone_phrase, text)
  text = pronounce_russian(text)

  text = PLUS.sub('плюс ', text)
  text = ARITHMETIC_PLUS.sub(' плюс ', text)
  text = OPERATOR.sub(operator_phrase, text)
  text = EQUALS.sub(' равно ', text)
  text = text.replace(NUMBER_SIGN, ' номер ')

  # файловые токены разбираются до чисел, иначе цифры рвут имя на части
  text = spell_file_names(text)
  text = VERSION_AFTER_LATIN.sub(spell_version, text)

  text = ORDINAL.sub(ordinal_phrase, text)
  text = KILO.sub(kilo_phrase, text)
  text = GENITIVE_UNIT.sub(genitive_unit_phrase, text)
  text = COMPOUND.sub(compound_phrase, text)
  text = UNIT.sub(unit_phrase, text)
  text = GENITIVE_NUMBER.sub(number_phrase_genitive, text)
  text = NUMBER.sub(number_phrase, text)

  # пути после чисел: «1/2» и «km/h» должны достаться дробям и единицам
  text = spell_paths(text)
  text = ASTERISK.sub(' звёздочка ', text)

  parts = LATIN_WORD.split(text)
  silence = BREAK_TOKEN if breaks else ''

  merged = ''.join(
    f'{pronounce(part)}{silence}' if index % 2 else part
    for index, part in enumerate(parts)
  )

  spaced = ' '.join(merged.split())

  return collapse_repeated_stress(accentize(spaced))
