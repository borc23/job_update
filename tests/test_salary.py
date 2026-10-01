import unittest

from job_alerts.core import salary


class FromText(unittest.TestCase):
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
                self.assertEqual(salary.from_text(line), expected)

    def test_named_interval_beats_earlier_bare_range(self):
        description = "Wat bieden we?\n* €3.000 - €4.000\n* Salaris €4.500 per maand"
        self.assertEqual(salary.from_text(description), "€4,500 / month")


class FromFields(unittest.TestCase):
    CASES = {
        (4000.0, 5500.0, "monthly", "EUR"): "€4,000 – €5,500 / month",
        (60000.0, 60000.0, "yearly", "USD"): "$60,000 / year",
        (25.5, None, "hourly", "CHF"): "CHF 25.50 / hour",
        (4000.0, None, None, None): "4,000",
        (None, None, "monthly", "EUR"): "",
    }

    def test_fields(self):
        for fields, expected in self.CASES.items():
            with self.subTest(fields):
                self.assertEqual(salary.from_fields(*fields), expected)

