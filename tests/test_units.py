"""Schnelle Unit-Tests für die deterministische Logik (kein Rendering)."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from autocontent.config import CONFIG
from autocontent.db import JobStore
from autocontent.llm import TemplateLLM
from autocontent.models import RightsStatus, Status
from autocontent import stages


class TestLLM(unittest.TestCase):
    def setUp(self):
        self.llm = TemplateLLM()

    def test_analyze_ranking_number(self):
        a = self.llm.analyze("10 Sommerdüfte")
        self.assertEqual(a["content_type"], "RANKING")
        self.assertEqual(a["item_count"], 10)

    def test_analyze_tips(self):
        a = self.llm.analyze("5 typische Fehler auf Baustellen")
        self.assertEqual(a["content_type"], "TIPS")
        self.assertEqual(a["item_count"], 5)

    def test_analyze_explainer_word_number(self):
        a = self.llm.analyze("Drei Gründe, warum Teams scheitern")
        self.assertEqual(a["content_type"], "EXPLAINER")
        self.assertEqual(a["item_count"], 3)

    def test_script_structure(self):
        a = self.llm.analyze("Top 7 WM-Momente")
        scenes = self.llm.write_script(a)
        roles = [s["role"] for s in scenes]
        self.assertEqual(roles[0], "HOOK")
        self.assertEqual(roles[-1], "CTA")
        self.assertEqual(roles.count("BODY"), a["item_count"])
        for s in scenes:
            self.assertTrue(s["voiceover_text"])
            self.assertTrue(s["subtitle_text"])

    def test_metadata(self):
        a = self.llm.analyze("10 Sommerdüfte")
        m = self.llm.write_metadata(a, self.llm.write_script(a))
        self.assertTrue(m["caption"])
        self.assertTrue(all(h.startswith("#") for h in m["hashtags"]))


class TestRights(unittest.TestCase):
    def test_prompt_approved(self):
        job = {"input_type": "PROMPT", "input_value": "10 Sommerdüfte", "topic": ""}
        r = stages.rights_check(job)
        self.assertEqual(r["rights_status"], RightsStatus.APPROVED.value)

    def test_banned_blocked(self):
        job = {"input_type": "PROMPT", "input_value": "Anleitung zur Gewalt", "topic": ""}
        r = stages.rights_check(job)
        self.assertEqual(r["rights_status"], RightsStatus.BLOCKED.value)
        self.assertIn("Verbotsliste", r["reason_if_blocked"])

    def test_link_unknown_blocked(self):
        job = {"input_type": "LINK", "input_value": "https://youtu.be/abc", "topic": ""}
        r = stages.rights_check(job)
        self.assertEqual(r["rights_status"], RightsStatus.BLOCKED.value)

    def test_link_whitelisted_approved(self):
        job = {"input_type": "LINK",
               "input_value": "https://youtu.be/abc?channel_id=UC_OWN_DEMO_CHANNEL",
               "topic": ""}
        r = stages.rights_check(job)
        self.assertEqual(r["rights_status"], RightsStatus.APPROVED.value)


class TestQuality(unittest.TestCase):
    def _job(self, **over):
        scenes = [
            {"role": "HOOK", "subtitle_text": "a", "image_path": "x", "duration": 3},
            {"role": "BODY", "subtitle_text": "b", "image_path": "x", "duration": 20},
            {"role": "CTA", "subtitle_text": "c", "image_path": "x", "duration": 3},
        ]
        job = {"script_json": scenes, "rights_status": "APPROVED"}
        job.update(over)
        return job

    def test_good_job_auto_publish(self):
        r = stages.quality_check(self._job())
        self.assertGreaterEqual(r["quality_score"], CONFIG.review_threshold)
        self.assertEqual(r["status"], Status.READY_TO_PUBLISH.value)

    def test_compliance_veto(self):
        r = stages.quality_check(self._job(rights_status="BLOCKED"))
        self.assertEqual(r["quality_score"], 0)
        self.assertEqual(r["status"], Status.BLOCKED.value)


class TestDB(unittest.TestCase):
    def test_roundtrip_and_unknown_column(self):
        with tempfile.TemporaryDirectory() as d:
            store = JobStore(Path(d) / "t.db")
            job = store.create("PROMPT", "10 Sommerdüfte")
            store.update(job["job_id"], script_json=[{"a": 1}], publish_payload="ignored")
            got = store.get(job["job_id"])
            self.assertEqual(got["script_json"], [{"a": 1}])
            self.assertNotIn("publish_payload", got)


class TestDuration(unittest.TestCase):
    def test_fit_total_within_window(self):
        scenes = [{"duration": 200.0}]
        stages._fit_total(scenes)
        self.assertLessEqual(scenes[0]["duration"], CONFIG.max_duration_s)


if __name__ == "__main__":
    unittest.main()
