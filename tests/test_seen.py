import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from job_alerts.core.seen import KEEP_DAYS, SeenJobs

TODAY = date.today().isoformat()
LONG_AGO = (date.today() - timedelta(days=KEEP_DAYS + 10)).isoformat()


class SeenJobsTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "seen.txt"

    def saved(self) -> dict[str, str]:
        return SeenJobs(self.path).last_listed

    def test_first_run_until_the_file_exists(self):
        self.assertTrue(SeenJobs(self.path).first_run)
        SeenJobs(self.path).refresh([])
        self.assertFalse(SeenJobs(self.path).first_run)

    def test_forgets_jobs_only_after_they_leave_the_results(self):
        self.path.write_text(f"gone\t{LONG_AGO}\nstill-listed\t{LONG_AGO}\n")
        SeenJobs(self.path).refresh(["still-listed", "new"])
        self.assertEqual(self.saved(), {"still-listed": TODAY, "new": TODAY})

    def test_add_is_saved_straight_away(self):
        self.path.write_text("")
        SeenJobs(self.path).add("a")
        self.assertIn("a", SeenJobs(self.path))

    def test_reads_ids_saved_before_dates_were_stored(self):
        self.path.write_text("a\n\nb\n")
        self.assertEqual(self.saved(), {"a": TODAY, "b": TODAY})

