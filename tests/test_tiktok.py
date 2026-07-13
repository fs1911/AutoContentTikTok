"""Tests für den TikTok-Client (reine Logik, kein Netzwerk)."""
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from autocontent import tiktok
from autocontent.tiktok import plan_chunks, MIN_CHUNK, MAX_CHUNK


class TestChunkPlanning(unittest.TestCase):
    def test_small_file_single_chunk(self):
        p = plan_chunks(1_500_000)
        self.assertEqual(p.total_chunk_count, 1)
        self.assertEqual(p.chunk_size, 1_500_000)
        self.assertEqual(p.ranges(), [(0, 1_499_999)])

    def test_large_file_multi_chunk_last_carries_rest(self):
        size = MIN_CHUNK * 3 + 123  # 3 volle 5MB-Chunks + Rest
        p = plan_chunks(size, chunk_size=MIN_CHUNK)
        self.assertEqual(p.total_chunk_count, 3)
        ranges = p.ranges()
        # letzter Chunk endet bei size-1 (Rest inklusive)
        self.assertEqual(ranges[-1][1], size - 1)
        # keine Lücken, lückenlose Abdeckung
        self.assertEqual(ranges[0][0], 0)
        for (s0, e0), (s1, _e1) in zip(ranges, ranges[1:]):
            self.assertEqual(e0 + 1, s1)

    def test_chunk_size_clamped(self):
        p = plan_chunks(MAX_CHUNK * 5, chunk_size=MAX_CHUNK * 10)
        self.assertLessEqual(p.chunk_size, MAX_CHUNK)
        self.assertGreaterEqual(p.chunk_size, MIN_CHUNK)


class TestAuthUrl(unittest.TestCase):
    def test_auth_url_requires_config(self):
        from autocontent.config import CONFIG
        CONFIG.tiktok_client_key = ""
        with self.assertRaises(tiktok.TikTokError):
            tiktok.authorization_url()

    def test_auth_url_built(self):
        from autocontent.config import CONFIG
        CONFIG.tiktok_client_key = "ckey"
        CONFIG.tiktok_redirect_uri = "https://example.com/cb"
        url = tiktok.authorization_url(scopes="video.publish")
        self.assertIn("client_key=ckey", url)
        self.assertIn("scope=video.publish", url)
        self.assertIn("response_type=code", url)
        CONFIG.tiktok_client_key = ""
        CONFIG.tiktok_redirect_uri = ""


class TestPublisherSelection(unittest.TestCase):
    def test_dry_run_default(self):
        from autocontent.config import CONFIG
        from autocontent.providers.publishing import get_publisher, DryRunPublisher
        CONFIG.publish_mode = "dry_run"
        self.assertIsInstance(get_publisher(), DryRunPublisher)

    def test_real_publisher_when_creds(self):
        from autocontent.config import CONFIG
        from autocontent.providers.publishing import get_publisher, TikTokPublisher
        CONFIG.publish_mode = "direct_post"
        CONFIG.tiktok_access_token = "tok"
        self.assertIsInstance(get_publisher(), TikTokPublisher)
        CONFIG.tiktok_access_token = ""
        CONFIG.publish_mode = "dry_run"


if __name__ == "__main__":
    unittest.main()
