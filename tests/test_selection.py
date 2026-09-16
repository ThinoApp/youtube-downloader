import unittest

from youtube_downloader.downloader import _video_format
from youtube_downloader.selection import build_range, normalize_custom_selection


class SelectionTests(unittest.TestCase):
    def test_normalizes_friendly_ranges(self) -> None:
        self.assertEqual(normalize_custom_selection("1, 3, 10-15"), "1,3,10:15")

    def test_keeps_native_slices(self) -> None:
        self.assertEqual(normalize_custom_selection("1,5:20:2"), "1,5:20:2")

    def test_rejects_reversed_range(self) -> None:
        with self.assertRaises(ValueError):
            normalize_custom_selection("9-4")

    def test_build_range(self) -> None:
        self.assertEqual(build_range(10, 25), "10:25")


class VideoFormatTests(unittest.TestCase):
    def test_mp4_requests_h264_and_aac(self) -> None:
        selector = _video_format("mp4", 720)
        self.assertIn("vcodec^=avc1", selector)
        self.assertIn("acodec^=mp4a", selector)
        self.assertIn("height<=720", selector)
        self.assertNotIn("/best", selector)

    def test_webm_keeps_existing_fallbacks(self) -> None:
        selector = _video_format("webm", None)
        self.assertIn("ext=webm", selector)
        self.assertTrue(selector.endswith("/best"))


if __name__ == "__main__":
    unittest.main()
