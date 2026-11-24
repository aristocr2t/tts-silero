# Тесты сохранения аудио: ошибки файловой системы — короткий MediaError.

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tts.media import MediaError, save_audio


class SaveAudioTestCase(unittest.TestCase):
  # mkdir и copy2 не должны выпускать OSError с traceback наружу.

  def test_mkdir_error_becomes_media_error(self) -> None:
    with tempfile.TemporaryDirectory() as work_dir:
      save_dir = Path(work_dir) / 'out'
      wav_path = Path(work_dir) / 'in.wav'
      wav_path.write_bytes(b'')

      with mock.patch.object(
        Path,
        'mkdir',
        side_effect=OSError(13, 'Permission denied'),
      ):
        with self.assertRaises(MediaError) as raised:
          save_audio('ffmpeg', wav_path, save_dir)

    self.assertIn(str(save_dir), str(raised.exception))
    self.assertIn('Permission denied', str(raised.exception))

  def test_copy_error_becomes_media_error(self) -> None:
    with tempfile.TemporaryDirectory() as work_dir:
      save_dir = Path(work_dir) / 'out'
      wav_path = Path(work_dir) / 'in.wav'
      wav_path.write_bytes(b'')

      with mock.patch(
        'tts.media.shutil.copy2',
        side_effect=OSError(13, 'Permission denied'),
      ):
        with self.assertRaises(MediaError) as raised:
          save_audio('ffmpeg', wav_path, save_dir)

    self.assertIn(str(save_dir), str(raised.exception))
    self.assertIn('Permission denied', str(raised.exception))


if __name__ == '__main__':
  unittest.main()
