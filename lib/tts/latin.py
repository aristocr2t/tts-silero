"""Латиница по-русски: IPA, словари произношения, аббревиатуры и транслит.

Silero падает на любом латинском символе ("Failed to parse SSML"), поэтому перед
синтезом латиница переводится в кириллицу по произношению: слово ищется в
словаре CMU (eng_to_ipa -> IPA -> русские буквы), аббревиатура читается по
буквам, незнакомое слово разбирается правилами DIGRAPHS.
"""

import re

import eng_to_ipa

from .config import load_custom
from .numbers import number_words

# IPA -> русские буквы. Порядок важен: длинные ключи разбираются первыми.
IPA = {
  'tʃ': 'ч',
  'ʧ': 'ч',
  'dʒ': 'дж',
  'ʤ': 'дж',
  'iː': 'и',
  'ɪ': 'и',
  'i': 'и',
  'eɪ': 'эй',
  'aɪ': 'ай',
  'ɔɪ': 'ой',
  'aʊ': 'ау',
  'əʊ': 'оу',
  'oʊ': 'оу',
  'ɪə': 'иа',
  'eə': 'эа',
  'ʊə': 'уа',
  'ɜː': 'ё',
  'ɜ': 'ё',
  'ɝ': 'ёр',
  'ɚ': 'эр',
  'æ': 'э',
  'ɛ': 'э',
  'e': 'э',
  'ə': 'э',
  'ʌ': 'а',
  'ɑː': 'а',
  'ɑ': 'а',
  'ɒ': 'о',
  'ɔː': 'о',
  'ɔ': 'о',
  'ʊ': 'у',
  'uː': 'у',
  'u': 'у',
  'θ': 'с',
  'ð': 'з',
  'ʃ': 'ш',
  'ʒ': 'ж',
  'ŋ': 'н',
  'ɹ': 'р',
  'ɾ': 'р',
  'ʔ': '',
  'b': 'б',
  'd': 'д',
  'f': 'ф',
  'g': 'г',
  'ɡ': 'г',
  'h': 'х',
  'j': 'й',
  'k': 'к',
  'l': 'л',
  'm': 'м',
  'n': 'н',
  'p': 'п',
  'r': 'р',
  's': 'с',
  't': 'т',
  'v': 'в',
  'w': 'в',
  'z': 'з',
  'ˈ': '',
  'ˌ': '',
  'ː': '',
  ' ': '',
  '-': '',
}

IPA_KEYS = sorted(IPA, key=len, reverse=True)

LETTERS = {
  'a': 'эй',
  'b': 'би',
  'c': 'си',
  'd': 'ди',
  'e': 'и',
  'f': 'эф',
  'g': 'джи',
  'h': 'эйч',
  'i': 'ай',
  'j': 'джей',
  'k': 'кей',
  'l': 'эл',
  'm': 'эм',
  'n': 'эн',
  'o': 'оу',
  'p': 'пи',
  'q': 'кью',
  'r': 'ар',
  's': 'эс',
  't': 'ти',
  'u': 'ю',
  'v': 'ви',
  'w': 'дабл-ю',
  'x': 'экс',
  'y': 'уай',
  'z': 'зед',
}

# слова, где словарь даёт неверное или неудобное произношение
WORDS = {
  'agile': 'эджайл',
  'ai': 'эй-ай',
  'anyconnect': 'эни-коннект',
  'api': 'эй-пи-ай',
  'async': 'эйсинк',
  'auth': 'ауф',
  'bashrc': 'бэш-эр-си',
  'bitbucket': 'битбакет',
  'callback': 'колбэк',
  'changelog': 'чейнджлог',
  'chatgpt': 'чат-джи-пи-ти',
  'chromium': 'хромиум',
  'ci': 'си-ай',
  'cli': 'си-эл-ай',
  'cloudflare': 'клаудфлэйр',
  'csrf': 'си-эс-ар-эф',
  'css': 'си-эс-эс',
  'db': 'ди-би',
  'denojs': 'дено-джей-эс',
  'devops': 'девопс',
  'dockerfile': 'докер-файл',
  'dockerhub': 'докер-хаб',
  'dotenv': 'дот-энв',
  'frontend': 'фронтенд',
  'fullstack': 'фулстек',
  'github': 'гитхаб',
  'gitignore': 'гит-игнор',
  'graphql': 'графкьюэл',
  'grpc': 'джи-эр-пи-си',
  'guard': 'гуард',
  'html': 'эйч-ти-эм-эл',
  'http': 'эйч-ти-ти-пи',
  'id': 'ай-ди',
  'ikev': 'ай-кей-ви',
  'ios': 'ай-ос',
  'ipsec': 'ай-пи-сек',
  'iptables': 'ай-пи-тейблс',
  'js': 'джей-эс',
  'json': 'джейсон',
  'jwt': 'джи-ви-ти',
  'k8s': 'кейтс',
  'kubernetes': 'кубернетес',
  'l2tp': 'эл-ту-ти-пи',
  'launchctl': 'лонч си-ти-эл',
  'launchd': 'лонч-ди',
  'max': 'макс',
  'mcp': 'эм-си-пи',
  'merge': 'мерж',
  'mongodb': 'монго-ди-би',
  'mtproto': 'эм-ти-прото',
  'mtproxy': 'эм-ти-прокси',
  'mysql': 'май-эс-кью-эл',
  'nginx': 'энджинкс',
  'nodejs': 'нод-джэ-эс',
  'npm': 'эн-пи-эм',
  'npmjs': 'эн-пи-эм джэ-эс',
  'npx': 'эн-пи-икс',
  'oauth': 'оауф',
  'improver': 'импрувер',
  'openai': 'опен-эй-ай',
  'openconnect': 'опен-коннект',
  'openssh': 'опен-эс-эс-эйч',
  'openssl': 'опен-эс-эс-эл',
  'openvpn': 'опен-ви-пи-эн',
  'opus': 'опус',
  'pdf': 'пэ-дэ-эф',
  'postgres': 'постгрес',
  'postgresql': 'постгрес-кью-эл',
  'pptp': 'пи-пи-ти-пи',
  'python': 'пайтэн',
  'ratelimit': 'рейт-лимит',
  'readme': 'ридми',
  'rebase': 'ребэйз',
  'redis': 'редис',
  'refactor': 'рефактор',
  'snapshot': 'снапшот',
  'to': 'ту',
  'ru': 'ру',
  'safari': 'сафари',
  'scrum': 'скрам',
  'signup': 'сайнап',
  'silero': 'силеро',
  'sql': 'эс-кью-эл',
  'sqlite': 'эс-кью-эл-лайт',
  'sqllite': 'эс-кью-эл-лайт',
  'ssh': 'эс-эс-эйч',
  'sshd': 'эс-эс-эйч-дэ',
  'sshkey': 'эс-эс-эйч-ключ',
  'stunnel': 'эс-таннел',
  'systemd': 'систем-ди',
  'ui': 'ю-ай',
  'unsetenv': 'ансет энв',
  'url': 'ю-ар-эл',
  'ux': 'ю-икс',
  'webhook': 'вебхук',
  'webpage': 'веб-пэйдж',
  'wireguard': 'вайр-гуард',
  'xenia': 'ксения',
  'xss': 'икс-эс-эс',
  'yml': 'ямл',
  'zsh': 'зэ-эс-аш',
  'zshrc': 'зэ-эс-аш-эр-си',
}

# аббревиатуры и сокращения: читаются по буквам, а не по правилам чтения
ACRONYMS = {
  'asr': 'а-эс-эр',
  'aws': 'эй-дабл-ю-эс',
  'azure': 'ажур',
  'cd': 'си-ди',
  'cpu': 'си-пи-ю',
  'crm': 'си-ар-эм',
  'crud': 'круд',
  'csv': 'си-эс-ви',
  'dns': 'ди-эн-эс',
  'doh': 'ди-оу-эйч',
  'eap': 'и-эй-пи',
  'esp': 'и-эс-пи',
  'ffmpeg': 'эф-эф-эм-пэг',
  'ftp': 'эф-ти-пи',
  'gcp': 'джи-си-пи',
  'gif': 'гиф',
  'gpu': 'джи-пи-ю',
  'hdd': 'эйч-ди-ди',
  'https': 'эйч-ти-ти-пи-эс',
  'ide': 'ай-ди-и',
  'imap': 'ай-мап',
  'ip': 'ай-пи',
  'jira': 'джира',
  'jpg': 'джей-пей-джи',
  'kafka': 'кафка',
  'kpi': 'кей-пи-ай',
  'md': 'эм-ди',
  'mfa': 'эм-эф-эй',
  'mp3': 'эм-пэ-три',
  'mp4': 'эм-пэ-четыре',
  'mtu': 'эм-ти-ю',
  'nat': 'нат',
  'nvim': 'эн-вим',
  'oc': 'оу-си',
  'ogg': 'о-джи-джи',
  'orm': 'орм',
  'path': 'паф',
  'tmp': 'ти-эм-пи',
  'png': 'пи-эн-джи',
  'rg': 'эр-гэ',
  'pr': 'пи-ар',
  'psk': 'пи-эс-кей',
  'qr': 'кью-ар',
  'ram': 'рам',
  'scp': 'эс-си-пи',
  'sdk': 'эс-ди-кей',
  'smtp': 'эс-эм-ти-пи',
  'ssd': 'эс-эс-ди',
  'ssr': 'эс-эс-ар',
  'ssl': 'эс-эс-эл',
  'sso': 'эс-эс-оу',
  'stt': 'эс-ти-ти',
  'tcp': 'ти-си-пи',
  'tls': 'ти-эл-эс',
  'toml': 'томл',
  'tts': 'ти-ти-эс',
  'udp': 'ю-ди-пи',
  'uvx': 'ю-ви-икс',
  'uri': 'ю-ар-ай',
  'uuid': 'уу-и-дд',
  'vk': 'ви-кей',
  'vpn': 'ви-пи-эн',
  'vscode': 'в-эс-код',
  'ws': 'ви-эс',
  'wss': 'ви-эс-эс',
  'xml': 'экс-эм-эл',
  'yaml': 'ямл',
}


def preserve_case(source: str, target: str) -> str:
  if not source:
    return target

  if source.isupper():
    return target.upper()
  if source[0].isupper():
    return target[0].upper() + target[1:]
  return target


def pronounce_russian(text: str) -> str:
  # Только произношение: Silero путает «е»/«э» после твёрдых согласных.
  # Ударения здесь не ставятся — этим занимается ruaccent по контексту.
  custom_words, custom_replacements = load_custom()
  replacements = (
    ('тест', 'тэст'),                 # произношение: твёрдое «тэ»
    ('синтез(?!ирова)', 'синтэз'),    # произношение: твёрдое «тэ»; ударение ставит ruaccent
    ('запуш', 'зап+уш'),              # зап+ушен, зап+ушить, зап+ушу
    ('коммит', 'комм+ит'),            # комм+ит, комм+иты: ruaccent ставит к+оммит
    # без «за-»: п+ушу, п+ушить; «распушить» и «пушок» ударены иначе
    ('(?<!рас)пуш(?=[уи])', 'п+уш'),
    ('пайтон', 'п+айтон'),            # п+айтон: ударение на «а»
    ('хоста', 'хост+а'),              # хост+а: ruaccent ставит х+оста
    # дефис Silero читает как границу слов и ударяет «по» отдельно: пишем слитно
    ('по-твоему', 'потв+оему'),
    ('по-моему', 'пом+оему'),
    ('по-своему', 'посв+оему'),
    ('маркетплейс', 'маркетпл+эйс'),  # маркетпл+эйс: твёрдое «э», все формы
  ) + custom_replacements

  for source, target in replacements:
    text = re.sub(
      source,
      lambda match: preserve_case(match.group(), target),
      text,
      flags=re.IGNORECASE,
    )

  return apply_custom_cyrillic_words(text, custom_words)


def apply_custom_cyrillic_words(text: str, custom_words: dict[str, str]) -> str:
  """Русские слова из конфига: «гикайдеас» -> «гик айд+иас».

  Ключ ищется целым словом, чтобы не портить однокоренные; латиница сюда не
  попадает — её обрабатывает pronounce().
  """
  cyrillic = re.compile(r'[А-Яа-яЁё]')

  for word, spoken in custom_words.items():
    if not cyrillic.search(word):
      continue

    text = re.sub(
      rf'(?<![А-Яа-яЁё]){re.escape(word)}(?![А-Яа-яЁё])',
      lambda match, target=spoken: preserve_case(match.group(), target),
      text,
      flags=re.IGNORECASE,
    )

  return text


def pronounce(word: str) -> str:
  low = word.lower()
  custom_words, _ = load_custom()

  if low in custom_words:                          # ~/.config/tts-silero.json
    return custom_words[low]

  if low in ACRONYMS:                              # aws, sdk, tcp -> по буквам
    return ACRONYMS[low]

  if low in WORDS:
    return WORDS[low]

  if low.endswith('s') and low[:-1] in WORDS:      # webhooks -> вебхук + с
    return WORDS[low[:-1]] + 'с'

  if any(ch.isdigit() for ch in word):             # k8s, json5, v2 -> части отдельно
    parts = re.findall(r'[A-Za-z]+|\d+', word)

    return ' '.join(pronounce(p) if p[0].isalpha() else number_words(p) for p in parts)

  if len(word) == 1 and word.isalpha():            # одиночная буква: Q -> кью
    return LETTERS.get(low, word)

  if word.isupper() and 1 < len(word) <= 5:
    return '-'.join(LETTERS.get(c.lower(), c) for c in word)

  phones = eng_to_ipa.convert(low)

  if not phones.endswith('*'):          # '*' — слова нет в словаре
    for key in IPA_KEYS:
      phones = phones.replace(key, IPA[key])

    if phones:
      return phones

  return translit(word)


# Правила чтения для слов, которых нет ни в CMU-словаре, ни в словарях выше
# (имена, технотермины). Сначала самые длинные сочетания, иначе 'sh' развалится
# на 's'+'h' и получится «схамил» вместо «шамил».
DIGRAPHS = [
  ('sch', 'ш'),
  ('tch', 'ч'),
  ('igh', 'ай'),
  ('eigh', 'эй'),
  ('ough', 'о'),
  ('sh', 'ш'),
  ('ch', 'ч'),
  ('ph', 'ф'),
  ('th', 'с'),
  ('wh', 'в'),
  ('ck', 'к'),
  ('qu', 'кв'),
  ('gh', 'г'),
  ('kn', 'н'),
  ('wr', 'р'),
  ('mn', 'м'),
  ('oo', 'у'),
  ('ee', 'и'),
  ('ea', 'и'),
  ('ai', 'эй'),
  ('ay', 'эй'),
  ('ey', 'эй'),
  ('oa', 'оу'),
  ('ow', 'оу'),
  ('ou', 'ау'),
  ('oi', 'ой'),
  ('oy', 'ой'),
  ('au', 'о'),
  ('aw', 'о'),
  ('ie', 'и'),
  ('ei', 'эй'),
  ('ue', 'у'),
  ('ew', 'ю'),
  ('ar', 'ар'),
  ('er', 'ер'),
  ('ir', 'ир'),
  ('or', 'ор'),
  ('ur', 'ур'),
]

SINGLE = {
  'a': 'а',
  'b': 'б',
  'c': 'к',
  'd': 'д',
  'e': 'э',
  'f': 'ф',
  'g': 'г',
  'h': 'х',
  'i': 'и',
  'j': 'дж',
  'k': 'к',
  'l': 'л',
  'm': 'м',
  'n': 'н',
  'o': 'о',
  'p': 'п',
  'q': 'к',
  'r': 'р',
  's': 'с',
  't': 'т',
  'u': 'у',
  'v': 'в',
  'w': 'в',
  'x': 'кс',
  'y': 'и',
  'z': 'з',
}


def translit(word: str) -> str:
  low = word.lower()
  out = []
  i = 0

  while i < len(low):
    # немое конечное 'e': name -> нэйм, drive -> драйв
    if i == len(low) - 1 and low[i] == 'e' and len(low) > 3 and not low[:-1].endswith(('l', 'r')):
      i += 1

      continue

    for length in (4, 3, 2):
      chunk = low[i:i + length]

      for src, dst in DIGRAPHS:
        if src == chunk:
          out.append(dst)
          i += length

          break
      else:
        continue

      break
    else:
      ch = low[i]

      # c читается «с» перед e/i/y, иначе «к»
      if ch == 'c':
        out.append('с' if low[i + 1:i + 2] in ('e', 'i', 'y') else 'к')
      elif ch == 'g' and low[i + 1:i + 2] == 'e':
        out.append('дж')
      else:
        out.append(SINGLE.get(ch, ch))

      i += 1

  result = ''.join(out)

  return result


# --- числа ---------------------------------------------------------------
# Silero выбрасывает цифры: "42" синтезируется как пауза. Поэтому числа
# переводятся в слова до синтеза: 2024 -> две тысячи двадцать четыре,
# 21% -> двадцать один процент, 5-го -> пятого, -3,5 -> минус три целых пять десятых.
