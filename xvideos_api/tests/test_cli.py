import os
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from xvideos_api.api import create_parser, run_main


class TestCLI(unittest.IsolatedAsyncioTestCase):
    def test_parser_defaults(self):
        parser = create_parser()
        args = parser.parse_args(["--output", "/tmp/out"])
        self.assertEqual(args.quality, "best")
        self.assertEqual(args.no_title, "False")
        self.assertEqual(args.output, "/tmp/out")
        self.assertIsNone(args.download)
        self.assertIsNone(args.file)

    def test_parser_custom_args(self):
        parser = create_parser()
        args = parser.parse_args([
            "--download", "https://xvideos.com/video123/test",
            "--output", "/tmp/out",
            "--quality", "worst",
            "--no-title", "True"
        ])
        self.assertEqual(args.download, "https://xvideos.com/video123/test")
        self.assertEqual(args.output, "/tmp/out")
        self.assertEqual(args.quality, "worst")
        self.assertEqual(args.no_title, "True")

    def test_parser_no_title_flag(self):
        parser = create_parser()
        args = parser.parse_args(["--output", "/tmp/out", "--no-title"])
        self.assertEqual(args.no_title, "True")

    async def test_run_main_download(self):
        mock_video = MagicMock()
        mock_video.title = "Sample Video"
        mock_video.download = AsyncMock()

        mock_client = MagicMock()
        mock_client.get_video = AsyncMock(return_value=mock_video)

        with patch("xvideos_api.api.Client", return_value=mock_client):
            await run_main(["--download", "https://xvideos.com/video123/test", "--output", "/tmp/out"])

        mock_client.get_video.assert_awaited_once_with("https://xvideos.com/video123/test", load_html=True)
        mock_video.download.assert_awaited_once()

    async def test_run_main_file(self):
        mock_video = MagicMock()
        mock_video.title = "Sample Video"
        mock_video.download = AsyncMock()

        mock_client = MagicMock()
        mock_client.get_video = AsyncMock(return_value=mock_video)

        with tempfile.NamedTemporaryFile("w+", delete=False) as f:
            f.write("https://xvideos.com/1\nhttps://xvideos.com/2\n")
            f.flush()
            temp_name = f.name

        try:
            with patch("xvideos_api.api.Client", return_value=mock_client):
                await run_main(["--file", temp_name, "--output", "/tmp/out"])

            self.assertEqual(mock_client.get_video.await_count, 2)
            self.assertEqual(mock_video.download.await_count, 2)
        finally:
            if os.path.exists(temp_name):
                os.remove(temp_name)

    async def test_real_download(self):
        """Integration test: verifies real video download via CLI."""
        url = "https://de.xvideos.com/video.ohplvhk02fd/meine_lesbische_freundin_hat_mich_beim_fremdgehen_mit_einem_zufalligen_typen_erwischt_aber_ich_kann_nicht_aufhoren_und_ficke_ihn_weiter_vor_ihren_augen_"
        with tempfile.TemporaryDirectory() as tmp_dir:
            await run_main(["--download", url, "--output", tmp_dir, "--quality", "worst"])
            files = [f for f in os.listdir(tmp_dir) if not f.endswith(".tmp")]
            self.assertTrue(len(files) > 0, "Expected downloaded video file in output directory")


if __name__ == "__main__":
    unittest.main()
