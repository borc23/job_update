import unittest
from datetime import date

from job_alerts.core.notify import message
from tests.fakes import job


class Message(unittest.TestCase):
    def test_escapes_fields_and_skips_empty_ones(self):
        posting = job(
            "a",
            company="Acme & Co",
            job_type="fulltime, contract",
            description="Salaris: €4.000 - €5.000 bruto per maand",
            job_url="https://nl.indeed.com/viewjob?jk=a&from=x",
            date_posted=date(2026, 10, 1),
        )
        self.assertEqual(
            message(posting),
            "🏢 Acme &amp; Co<br>💶 €4,000 – €5,000 / month<br>💼 Full-time, Contract<br>📅 Posted 1 Oct 2026"
            '<br><a href="https://nl.indeed.com/viewjob?jk=a&amp;from=x">View on Indeed →</a>',
        )
