"""One message per job, as HTML for Telegram (Apprise converts it for other channels)."""

import html
import sys
import time

import apprise

from . import salary

SEND_INTERVAL = 1  # seconds; Telegram allows about 1 message per second per chat
JOB_TYPES = {"fulltime": "Full-time", "parttime": "Part-time"}  # the rest just get a capital: 'Contract'


def send(notifier: apprise.Apprise, job) -> bool:
    """Notify about one job; False if that failed, so it's retried next run."""
    time.sleep(SEND_INTERVAL)
    try:
        return bool(notifier.notify(title=escape(job.title), body=message(job), body_format=apprise.NotifyFormat.HTML))
    except Exception as e:  # one malformed posting mustn't stop the rest
        print(f"{job.id}: {e!r}", file=sys.stderr)
        return False


def message(job) -> str:
    """The job's details, one per line, skipping any Indeed didn't fill in."""
    pay = salary.from_fields(job.min_amount, job.max_amount, job.interval, job.currency)
    job_types = ", ".join(JOB_TYPES.get(t, t.capitalize()) for t in escape(job.job_type).split(", ") if t)
    details = {
        "🏢": escape(job.company),
        "📍": escape(job.location),
        "💶": pay or salary.from_text(job.description or ""),
        "💼": job_types,
    }
    return "<br>".join(
        [f"{icon} {value}" for icon, value in details.items() if value]
        + [f'<a href="{html.escape(job.job_url)}">View on Indeed →</a>']
    )


def escape(value) -> str:
    """A job field escaped for Telegram's HTML; '' when it's empty."""
    return html.escape(str(value), quote=False) if value else ""
