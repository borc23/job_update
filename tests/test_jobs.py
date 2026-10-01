import unittest
from unittest import mock

import pandas as pd

from job_alerts.core import jobs

CONFIG = {"search": {"site_name": "indeed"}, "locations": {"Rotterdam": 25, "Den Haag": 10}}


class FetchJobs(unittest.TestCase):
    def test_merges_cities_and_turns_empty_fields_into_none(self):
        results = {  # 'b' is in both cities; NaN and None are how pandas leaves fields empty
            "Rotterdam": pd.DataFrame({"id": ["a", "b"], "company": ["Acme", None], "min_amount": [4000.0, None]}),
            "Den Haag": pd.DataFrame({"id": ["b"], "company": [None], "min_amount": [float("nan")]}),
        }
        with mock.patch.object(jobs, "scrape_jobs", side_effect=lambda location, **_: results[location]) as scrape:
            found = jobs.fetch_jobs(CONFIG)

        self.assertEqual(list(found), ["a", "b"])
        self.assertEqual((found["a"].company, found["a"].min_amount), ("Acme", 4000.0))
        self.assertEqual((found["b"].company, found["b"].min_amount), (None, None))
        self.assertEqual(scrape.call_args.kwargs["distance"], 6)  # 10 km in miles
