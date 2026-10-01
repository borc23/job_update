import tempfile
import unittest
from pathlib import Path
from unittest import mock

from job_alerts import app
from job_alerts.core import notify
from job_alerts.core.seen import SeenJobs
from tests.fakes import FakeNotifier, job


class Run(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "seen.txt"
        patcher = mock.patch.object(notify, "SEND_INTERVAL", 0)
        patcher.start()
        self.addCleanup(patcher.stop)

    def run_once(self, job_ids, *outcomes) -> list[str]:
        """One run over these jobs; returns the titles sent."""
        notifier = FakeNotifier(*outcomes)
        app.run(notifier, SeenJobs(self.path), {job_id: job(job_id) for job_id in job_ids})
        return notifier.titles

    def test_first_run_records_jobs_without_sending_them(self):
        self.assertEqual(self.run_once(["a", "b"]), ["Job alerts are on"])
        self.assertEqual(self.run_once(["a", "b"]), [])

    def test_sends_only_new_jobs(self):
        self.run_once(["a"])
        self.assertEqual(self.run_once(["a", "b"]), ["b"])

    def test_failed_and_crashing_sends_are_retried_next_run(self):
        self.path.write_text("")
        with self.assertRaises(SystemExit):
            self.run_once(["a", "b", "c"], True, False, ValueError("bad posting"))
        self.assertEqual(self.run_once(["a", "b", "c"]), ["b", "c"])

    def test_jobs_sent_before_the_run_dies_are_not_resent(self):
        class Cancelled(BaseException):
            pass

        self.path.write_text("")
        with self.assertRaises(Cancelled):
            self.run_once(["a", "b"], True, Cancelled())
        self.assertEqual(self.run_once(["a", "b"]), ["b"])
