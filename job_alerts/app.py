"""The run: fetch the jobs, send the ones not seen before, and remember what was sent."""

import os
import sys
import tomllib
from pathlib import Path

import apprise

from .core.jobs import fetch_jobs
from .core.notify import send
from .core.seen import SeenJobs

ROOT = Path(__file__).resolve().parents[1]
CONFIG_FILE = ROOT / "config.toml"
SEEN_FILE = ROOT / "seen.txt"


def main() -> None:
    notifier = apprise.Apprise(os.environ.get("NOTIFY_URL"))
    if not notifier:
        sys.exit("Set NOTIFY_URL to a valid Apprise URL, e.g. tgram://<bot_token>/<chat_id>")
    jobs = fetch_jobs(tomllib.loads(CONFIG_FILE.read_text(encoding="utf-8")))
    if not jobs:
        sys.exit("No jobs found in any city: Indeed may be blocking the search.")
    run(notifier, SeenJobs(SEEN_FILE), jobs)


def run(notifier: apprise.Apprise, seen: SeenJobs, jobs: dict) -> None:
    """Send the jobs not seen before. The first run only records what's listed, instead of days of backlog."""
    if seen.first_run:
        seen.refresh(jobs)
        if not notifier.notify(
            title="Job alerts are on",
            body=f"Tracking {len(jobs)} current jobs; you'll get new ones as they're posted.",
            body_format=apprise.NotifyFormat.TEXT,
        ):
            sys.exit("Couldn't send the first-run message; check NOTIFY_URL.")
        return

    new = {job_id: job for job_id, job in jobs.items() if job_id not in seen}
    seen.refresh(jobs.keys() - new.keys())
    failed = 0
    for job_id, job in new.items():
        if send(notifier, job):
            seen.add(job_id)
        else:
            failed += 1
    if failed:
        sys.exit(f"{failed} notifications failed; they will be retried next run.")
