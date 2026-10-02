"""Stand-ins for a fetched job and for Apprise, shared by the tests."""

from types import SimpleNamespace

FIELDS = "title company location job_type description min_amount max_amount interval currency date_posted".split()


def job(job_id: str, **fields) -> SimpleNamespace:
    """A job as fetch_jobs returns it: empty fields are None, and the title is the id."""
    defaults = dict.fromkeys(FIELDS) | {"title": job_id, "job_url": f"https://nl.indeed.com/viewjob?jk={job_id}"}
    return SimpleNamespace(id=job_id, **defaults | fields)


class FakeNotifier:
    """Records the titles it's asked to send; returns or raises the given outcomes in turn, then succeeds."""

    def __init__(self, *outcomes):
        self.outcomes, self.titles = list(outcomes), []

    def notify(self, title, body, body_format):
        self.titles.append(title)
        outcome = self.outcomes.pop(0) if self.outcomes else True
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome
