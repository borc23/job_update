"""Run with: python -m unittest"""

import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import main

TODAY = date.today().isoformat()
LONG_AGO = (date.today() - timedelta(days=main.SEEN_DAYS + 10)).isoformat()


class SalaryInText(unittest.TestCase):
    CASES = {
        # Salary lines as Indeed.nl postings write them
        "Een bruto maandsalaris tussen €4.487 en €6.494": "€4,487 – €6,494 / month",
        "* €3.706 - €5.760": "€3,706 – €5,760 / month",
        "Salaris: € 3.500,- tot € 5.000,- bruto per maand": "€3,500 – €5,000 / month",
        "Salaris €4.000 — €5.000 per maand": "€4,000 – €5,000 / month",
        "Salaris max. €5.000 per maand": "up to €5,000 / month",
        "Salaris vanaf €3.200 per maand": "from €3,200 / month",
        "Salary: €70k–€90k": "€70,000 – €90,000 / year",
        "Salary €4.5k - €5.5k per month": "€4,500 – €5,500 / month",
        "Salary: €18,50 per hour": "€18.50 / hour",
        "Stagevergoeding €500 per maand": "€500 / month",
        # Other amounts on the same line
        "Reiskosten €0,23 per km en een salaris tot €4.000 per maand": "up to €4,000 / month",
        "Je krijgt een salaris van €500 bonus en €4.000 per maand": "€4,000 / month",
        "Salaris €4.000 en €500 reiskosten per maand": "€4,000 / month",
        # Interval words that don't belong to the amount
        "Salaris €60.000 incl. 13e maand en vakantiegeld": "€60,000 / year",
        "Gross salary €5,000 with 3 years of experience": "€5,000 / month",
        "Salaris: €4.000 per maand en jaarcontract": "€4,000 / month",
        # €10k–15k could be a month or a year, so only a named interval decides
        "Salaris €12.000 per jaar": "€12,000 / year",
        "Salaris €12.000": "€12,000",
        # Not salaries
        "Bruto reiskostenvergoeding €0,23 per km": "",
        "Wij investeren €50.000 in je opleiding": "",
        "": "",
    }

    def test_lines(self):
        for line, expected in self.CASES.items():
            with self.subTest(line):
                self.assertEqual(main.salary_in_text(line), expected)

    def test_named_interval_beats_earlier_bare_range(self):
        description = "Wat bieden we?\n* €3.000 - €4.000\n* Salaris €4.500 per maand"
        self.assertEqual(main.salary_in_text(description), "€4,500 / month")


class Run(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.seen_file = Path(tmp.name) / "seen.txt"
        self.notifier = mock.MagicMock()
        for name, value in [("SEEN_FILE", self.seen_file), ("NOTIFIER", self.notifier)]:
            patcher = mock.patch.object(main, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def run_main(self, job_ids, send_results=None):
        """Run main() on these job ids; returns the ids it tried to send."""
        jobs = {job_id: SimpleNamespace(id=job_id) for job_id in job_ids}
        send = mock.Mock(side_effect=send_results, return_value=True)
        with mock.patch.object(main, "fetch_jobs", return_value=jobs), mock.patch.object(main, "send", send):
            main.main()
        return [c.args[0].id for c in send.call_args_list]

    def seen(self):
        return dict(line.split("\t") for line in self.seen_file.read_text().splitlines())

    def test_first_run_records_jobs_without_sending_them(self):
        self.assertEqual(self.run_main(["a", "b"]), [])
        self.assertEqual(self.seen(), {"a": TODAY, "b": TODAY})
        self.notifier.notify.assert_called_once()

    def test_sends_only_new_jobs(self):
        self.seen_file.write_text(f"a\t{TODAY}\n")
        self.assertEqual(self.run_main(["a", "b"]), ["b"])
        self.assertEqual(self.seen(), {"a": TODAY, "b": TODAY})

    def test_failed_and_crashing_sends_are_retried_next_run(self):
        self.seen_file.write_text("")
        with self.assertRaises(SystemExit):
            self.run_main(["a", "b", "c"], send_results=[True, False, ValueError("bad posting")])
        self.assertEqual(self.seen(), {"a": TODAY})
        self.assertEqual(self.run_main(["a", "b", "c"]), ["b", "c"])

    def test_jobs_sent_before_the_run_dies_are_not_resent(self):
        class Cancelled(BaseException):
            pass

        self.seen_file.write_text("")
        with self.assertRaises(Cancelled):
            self.run_main(["a", "b"], send_results=[True, Cancelled()])
        self.assertEqual(self.seen(), {"a": TODAY})

    def test_forgets_jobs_only_after_they_leave_the_results(self):
        self.seen_file.write_text(f"gone\t{LONG_AGO}\nstill-listed\t{LONG_AGO}\n")
        self.assertEqual(self.run_main(["still-listed"]), [])
        self.assertEqual(self.seen(), {"still-listed": TODAY})

    def test_reads_ids_saved_before_dates_were_stored(self):
        self.seen_file.write_text("a\nb\n")
        self.assertEqual(self.run_main(["a", "b", "c"]), ["c"])
        self.assertEqual(self.seen(), {"a": TODAY, "b": TODAY, "c": TODAY})


if __name__ == "__main__":
    unittest.main()
