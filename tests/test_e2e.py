"""Echter End-to-End-Test: erzeugt ein kleines Video und prüft die Datei.

Läuft real durch ffmpeg. Mit AUTOCONTENT_SKIP_E2E=1 überspringbar.
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@unittest.skipIf(os.environ.get("AUTOCONTENT_SKIP_E2E") == "1", "E2E übersprungen")
class TestEndToEnd(unittest.TestCase):
    def test_prompt_to_published_video(self):
        # Isolierte Ausgabe/DB pro Testlauf
        tmp = Path(tempfile.mkdtemp())
        from autocontent.config import CONFIG
        CONFIG.output_dir = tmp
        CONFIG.assets_dir = tmp / "assets"
        CONFIG.db_path = tmp / "t.db"
        CONFIG.ensure_dirs()

        from autocontent.db import JobStore
        from autocontent import pipeline

        store = JobStore(CONFIG.db_path)
        store.add_whitelist("UC_OWN_DEMO_CHANNEL", "Demo", "OWN")
        job = store.create("PROMPT", "3 Gründe warum Projekte scheitern")
        job = pipeline.run_job(store, job["job_id"])

        self.assertEqual(job["status"], "OPTIMIZED", msg=job.get("reason_if_blocked"))
        self.assertEqual(job["publish_status"], "PUBLISHED")
        video = Path(job["video_url"])
        self.assertTrue(video.exists())
        self.assertGreater(video.stat().st_size, 10_000)
        self.assertGreater(job["quality_score"], 60)


if __name__ == "__main__":
    unittest.main()
