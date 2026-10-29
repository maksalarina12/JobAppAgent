import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from jobapp.core import Job, JobStore, ingest, score_job, verify_url


class CoreTests(unittest.TestCase):
    def test_scoring_is_keyword_based_and_bounded(self):
        profile = {"keywords": ["python", "software engineer"], "locations": ["indonesia"]}
        job = Job("test", "1", "Acme", "Python Software Engineer", "Indonesia", "Python backend", "https://example.com")
        self.assertEqual(score_job(job, profile), 39)
        self.assertLessEqual(score_job(job, {"keywords": ["python"] * 100, "locations": []}), 100)

    def test_store_deduplicates_and_searches(self):
        with tempfile.TemporaryDirectory() as directory:
            store = JobStore(Path(directory) / "jobs.sqlite3")
            job = Job("test", "1", "Acme", "Python Engineer", "Remote", "Python work", "https://example.com", score=50, verified=True)
            self.assertTrue(store.upsert(job))
            self.assertFalse(store.upsert(job))
            self.assertEqual(len(store.search("python engineer")), 1)
            self.assertEqual(len(store.unnotified(25)), 1)
            store.mark_notified(job)
            self.assertEqual(store.unnotified(25), [])

    def test_ingest_persists_verification_and_score(self):
        with tempfile.TemporaryDirectory() as directory:
            store = JobStore(Path(directory) / "jobs.sqlite3")
            job = Job("test", "1", "Acme", "Python Engineer", "Worldwide", "Python", "https://example.com")
            count, eligible = ingest(store, {"keywords": ["python"], "locations": ["worldwide"], "minimum_score": 1}, [job], check_urls=False)
            self.assertEqual((count, eligible), (1, 0))  # unverified listings never alert
            job.verified = True
            store.upsert(job)
            self.assertEqual(len(store.unnotified(1)), 1)

    def test_url_verification_rejects_non_https_and_accepts_live_https(self):
        self.assertFalse(verify_url("http://example.com"))
        with patch("jobapp.core._request", return_value=b""):
            self.assertTrue(verify_url("https://example.com/apply"))


if __name__ == "__main__":
    unittest.main()
