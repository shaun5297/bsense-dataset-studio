import io
import tempfile
import unittest
import wave
from pathlib import Path

from bsense_dataset_studio.app.audio import (
    cue_wav_path,
    play_cue,
    render_cue,
    synthesize_wav,
)


class AudioTests(unittest.TestCase):
    def test_synthesize_wav_is_valid_mono_16bit(self) -> None:
        data = synthesize_wav([(880.0, 0.1), (0.0, 0.05)], sample_rate=8000)
        with wave.open(io.BytesIO(data), "rb") as wav:
            self.assertEqual(wav.getnchannels(), 1)
            self.assertEqual(wav.getsampwidth(), 2)
            self.assertEqual(wav.getframerate(), 8000)
            self.assertEqual(wav.getnframes(), int(8000 * 0.15))

    def test_unknown_cue_falls_back_to_default_beep(self) -> None:
        self.assertEqual(render_cue("no_such_cue"), render_cue("no_such_cue"))
        self.assertNotEqual(render_cue("no_such_cue"), ())

    def test_cue_wav_path_caches_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            first = cue_wav_path("start", Path(directory))
            self.assertTrue(first.exists())
            before = first.stat().st_mtime_ns
            second = cue_wav_path("start", Path(directory))
            self.assertEqual(first, second)
            self.assertEqual(first.stat().st_mtime_ns, before)

    def test_play_cue_invokes_player_with_existing_file(self) -> None:
        played = []
        play_cue("start", player=lambda path: played.append(path))
        self.assertEqual(len(played), 1)
        self.assertTrue(played[0].exists())
        self.assertEqual(played[0].suffix, ".wav")

    def test_play_cue_without_name_is_noop(self) -> None:
        play_cue(None, player=lambda path: self.fail("player should not run"))
        play_cue("", player=lambda path: self.fail("player should not run"))

    def test_play_cue_falls_back_to_bell_on_failure(self) -> None:
        bells = []

        def failing_player(path: Path) -> None:
            raise OSError("no audio device")

        play_cue("start", bell=lambda: bells.append(True), player=failing_player)
        self.assertEqual(bells, [True])


if __name__ == "__main__":
    unittest.main()
