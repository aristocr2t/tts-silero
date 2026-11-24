# Тесты синтеза: SSML, план кусков и запись одного wav.

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np
import soundfile as sf

os.environ['VOICE_ACCENT'] = '0'
# изоляция от ~/.config/tts-silero.json: тесты не должны зависеть от машины
os.environ['VOICE_CONFIG'] = str(Path(tempfile.gettempdir()) / f'tts-silero-absent-{os.getpid()}.json')

from tts import synth  # noqa: E402
from tts.normalize import BREAK_TOKEN  # noqa: E402
from tts.synth import (  # noqa: E402
  MAX_MODEL_CHARS,
  SynthesisError,
  build_ssml,
  plan_segments,
  synthesize_segment,
  synthesize_text,
)


class SsmlTestCase(unittest.TestCase):
  # SSML: экранирование, пауза после латиницы, просодия. Тип интонации выбирает модель.

  def test_question_is_passed_through(self) -> None:
    self.assertEqual(
      build_ssml('Ты уже сделал гит пуш?', 'medium', 'medium'),
      '<speak>Ты уже сделал гит пуш?</speak>',
    )

  def test_statement_is_passed_through(self) -> None:
    self.assertEqual(
      build_ssml('Ты уже сделал гит пуш.', 'medium', 'medium'),
      '<speak>Ты уже сделал гит пуш.</speak>',
    )

  def test_break_tag_after_latin_is_kept(self) -> None:
    with mock.patch.dict(os.environ, {'VOICE_BREAK_MS': '120'}):
      ssml = build_ssml(f'ти-ти-эс{BREAK_TOKEN}?', 'medium', 'medium')

    self.assertEqual(ssml, '<speak>ти-ти-эс<break time="120ms"/>?</speak>')

  def test_prosody_wraps_whole_text(self) -> None:
    self.assertEqual(
      build_ssml('Который час?', 'fast', 'high'),
      '<speak><prosody rate="fast" pitch="high">Который час?</prosody></speak>',
    )


class PlanSegmentsTestCase(unittest.TestCase):
  # Куски после нормализации обязаны влезать в предел модели.

  def test_segments_fit_model_limit(self) -> None:
    text = 'Проверка 1000 рублей. ' * 60
    segments = plan_segments(text, 400)

    self.assertTrue(segments)
    self.assertTrue(all(len(segment) <= MAX_MODEL_CHARS for segment in segments), segments)

  def test_expanded_numbers_are_split(self) -> None:
    # цифры разворачиваются в слова и удлиняют кусок
    segments = plan_segments('1 234 567 рублей. ' * 30, 900)

    self.assertTrue(all(len(segment) <= MAX_MODEL_CHARS for segment in segments), segments)

  def test_empty_text_gives_no_segments(self) -> None:
    self.assertEqual(plan_segments('   \n\n  ', 900), [])


class SynthesisSegmentTestCase(unittest.TestCase):
  # Сбой куска не превращается в молча пропущенную часть текста.

  def test_raw_keeps_user_accent(self) -> None:
    # в --raw метки пользователя неприкосновенны, иначе их сдвинет акценатор модели
    seen = {}

    class RecordingModel:
      def apply_tts(self, **kwargs):
        seen.update(kwargs)

        return mock.Mock(numpy=lambda: mock.Mock())

    synthesize_segment(RecordingModel(), 'короткий кусок', 'xenia', 'medium', 'medium', 48000,
                       raw=True)

    self.assertIs(seen['put_accent'], False)

  def test_normal_mode_lets_model_fill_stress(self) -> None:
    # ruaccent размечает не все слова: «ваши» без метки звучит как «вши»
    seen = {}

    class RecordingModel:
      def apply_tts(self, **kwargs):
        seen.update(kwargs)

        return mock.Mock(numpy=lambda: mock.Mock())

    synthesize_segment(RecordingModel(), 'короткий кусок', 'xenia', 'medium', 'medium', 48000)

    self.assertIs(seen['put_accent'], True)

  def test_short_segment_failure_raises(self) -> None:
    class FailingModel:
      def apply_tts(self, **kwargs):
        raise RuntimeError('слишком длинный текст')

    with self.assertRaises(SynthesisError):
      synthesize_segment(FailingModel(), 'короткий кусок', 'xenia', 'medium', 'medium', 48000)

  def test_failed_half_raises_instead_of_partial_audio(self) -> None:
    class HalfFailingModel:
      def __init__(self) -> None:
        self.calls = 0

      def apply_tts(self, **kwargs):
        self.calls += 1

        if self.calls == 1 or self.calls >= 3:
          raise RuntimeError('слишком длинный текст')

        return mock.Mock()

    text = ' '.join(['слово'] * 40)

    with self.assertRaises(SynthesisError):
      synthesize_segment(HalfFailingModel(), text, 'xenia', 'medium', 'medium', 48000)


class SynthesizeTextTestCase(unittest.TestCase):
  # Текст пишется в один wav, cwd возвращается на место после синтеза.

  def test_one_wav_and_cwd_restored(self) -> None:
    class Model:
      def apply_tts(self, **kwargs):
        return mock.Mock(numpy=lambda: np.zeros(8, dtype=np.float32))

    fake_silero = mock.Mock()
    fake_silero.silero_tts.return_value = (Model(), None)

    work_dir = tempfile.TemporaryDirectory()
    self.addCleanup(work_dir.cleanup)

    root = Path(work_dir.name)
    start = root / 'start'
    start.mkdir()
    output = root / 'speech.wav'
    previous = os.getcwd()

    os.chdir(start)

    try:
      with mock.patch.object(synth, 'CONFIG_DIR', root / 'cache'), \
           mock.patch.dict(sys.modules, {'silero': fake_silero}):
        count = synthesize_text('Да. Нет.', 'xenia', 'medium', 'medium', 8000, 4, output)

      self.assertEqual(os.path.realpath(Path.cwd()), os.path.realpath(start))
    finally:
      os.chdir(previous)

    self.assertEqual(count, 2)
    self.assertTrue(output.is_file())
    self.assertFalse(list(root.glob('*.part.wav')), 'временный wav остался')

    audio, rate = sf.read(output)

    self.assertEqual(rate, 8000)
    # два куска по 8 сэмплов и пауза 0,25 с между ними
    self.assertEqual(len(audio), 8 + 2000 + 8)

  def test_failure_keeps_previous_file(self) -> None:
    class HalfFailingModel:
      calls = 0

      def apply_tts(self, **kwargs):
        HalfFailingModel.calls += 1

        if HalfFailingModel.calls > 1:
          raise RuntimeError('сбой синтеза')

        return mock.Mock(numpy=lambda: np.zeros(8, dtype=np.float32))

    fake_silero = mock.Mock()
    fake_silero.silero_tts.return_value = (HalfFailingModel(), None)

    work_dir = tempfile.TemporaryDirectory()
    self.addCleanup(work_dir.cleanup)

    root = Path(work_dir.name)
    output = root / 'speech.wav'

    output.write_bytes(b'old wav')

    with self.assertRaises(SynthesisError):
      with mock.patch.object(synth, 'CONFIG_DIR', root / 'cache'), \
           mock.patch.dict(sys.modules, {'silero': fake_silero}):
        synthesize_text('Да. Нет.', 'xenia', 'medium', 'medium', 8000, 4, output)

    self.assertEqual(output.read_bytes(), b'old wav')
    self.assertFalse(list(root.glob('*.part.wav')), 'временный wav остался')


if __name__ == '__main__':
  unittest.main()
