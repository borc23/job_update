"""Send new Indeed.nl jobs matching config.toml to Telegram (or any Apprise channel)."""

import os
import sys
import time
import tomllib
from pathlib import Path

import apprise
from jobspy import scrape_jobs

HERE = Path(__file__).parent
CONFIG = tomllib.loads((HERE / "config.toml").read_text(encoding="utf-8"))
SEEN_FILE = HERE / "seen.txt"
NOTIFIER = apprise.Apprise(os.environ.get("NOTIFY_URL"))


def fetch_jobs() -> dict:
    """Search every configured city; keyed by job id so overlapping results collapse."""
    return {
        job.id: job
        for city, km in CONFIG["locations"].items()
        for job in scrape_jobs(
            **CONFIG["search"],
            location=city,
            distance=round(km / 1.609),  # JobSpy expects miles
        ).itertuples()
    }


def send(job) -> bool:
    time.sleep(1)  # Telegram allows ~1 message/second per chat
    return NOTIFIER.notify(
        title=job.title,
        body=f"{job.company} · {job.location}\n{job.job_url}",
        body_format=apprise.NotifyFormat.TEXT,
    )


def main() -> None:
    if not NOTIFIER:
        sys.exit("Set NOTIFY_URL to a valid Apprise URL, e.g. tgram://<bot_token>/<chat_id>")

    seen = set(SEEN_FILE.read_text().split()) if SEEN_FILE.exists() else set()
    jobs = fetch_jobs()
    if not jobs:
        sys.exit("No jobs found in any city: Indeed may be blocking the search.")

    failed = {job_id for job_id, job in jobs.items() if job_id not in seen and not send(job)}
    SEEN_FILE.write_text("\n".join(sorted(seen | (jobs.keys() - failed))) + "\n")
    if failed:
        sys.exit(f"{len(failed)} notifications failed; they will be retried next run.")


if __name__ == "__main__":
    main()
