"""The jobs already sent: a text file with one "<job id>\t<date it was last in the results>" per line."""

from collections.abc import Iterable
from datetime import date, timedelta
from pathlib import Path

KEEP_DAYS = 30  # forget a job once it has been out of the results this long


class SeenJobs:
    def __init__(self, path: Path):
        self.path = path
        self.today = date.today().isoformat()
        self.first_run = not path.exists()
        rows = [] if self.first_run else (line.partition("\t") for line in path.read_text().splitlines() if line)
        # Rows without a date are from before dates were stored
        self.last_listed = {job_id: day or self.today for job_id, _, day in rows}

    def __contains__(self, job_id: str) -> bool:
        return job_id in self.last_listed

    def refresh(self, listed: Iterable[str]) -> None:
        """Mark these jobs as in today's results, forget those gone for KEEP_DAYS, and rewrite the file."""
        self.last_listed |= dict.fromkeys(listed, self.today)
        cutoff = (date.today() - timedelta(days=KEEP_DAYS)).isoformat()
        self.last_listed = {job_id: day for job_id, day in self.last_listed.items() if day >= cutoff}
        self.path.write_text("".join(f"{job_id}\t{day}\n" for job_id, day in sorted(self.last_listed.items())))

    def add(self, job_id: str) -> None:
        """Record a sent job straight away, so a crash later in the run can't send it again."""
        self.last_listed[job_id] = self.today
        with self.path.open("a") as f:
            f.write(f"{job_id}\t{self.today}\n")
