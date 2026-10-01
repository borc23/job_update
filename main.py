"""Send new Indeed.nl jobs matching config.toml to Telegram (or any Apprise channel)."""

import html
import os
import re
import sys
import time
import tomllib
from pathlib import Path

import apprise
import pandas as pd
from jobspy import scrape_jobs

HERE = Path(__file__).parent
CONFIG = tomllib.loads((HERE / "config.toml").read_text(encoding="utf-8"))
SEEN_FILE = HERE / "seen.txt"
NOTIFIER = apprise.Apprise(os.environ.get("NOTIFY_URL"))

CURRENCIES = {"EUR": "€", "USD": "$", "GBP": "£"}
PER = {"yearly": "year", "monthly": "month", "weekly": "week", "daily": "day", "hourly": "hour"}
JOB_TYPES = {
    "fulltime": "Full-time",
    "parttime": "Part-time",
    "contract": "Contract",
    "temporary": "Temporary",
    "internship": "Internship",
}

AMOUNT = r"(\d{1,3}(?:[.,]\d{3})+|\d+)(?:[.,](?:\d{2}|-))?\s*(k\b)?"
EURO_RANGE = re.compile(rf"(?:€|EUR)\s*{AMOUNT}(?:\s*(?:-|–|tot|en|to|and)\s*(?:€|EUR)?\s*{AMOUNT})?", re.I)
PAY_WORDS = re.compile(
    r"salar|bruto|gross|\bpay\b|loon|beloning|verdien|\bschaal \d|stagevergoeding|internship allowance", re.I
)
INTERVAL = re.compile(r"(maand|month)|(jaar|year|annual)|(per uur|uurloon|per hour|hourly)", re.I)
UP_TO = re.compile(r"(?:tot|max\w*|up to)\W*$", re.I)
FROM = re.compile(r"(?:vanaf|from|min\w*|starting at)\W*$", re.I)


def fetch_jobs() -> dict:
    """Search every configured city; keyed by job id so overlapping results collapse."""
    return {
        job.id: job
        for city, km in CONFIG["locations"].items()
        for job in scrape_jobs(
            **CONFIG["search"],
            location=city,
            distance=round(km / 1.609),
        ).itertuples()
    }


def text(value) -> str:
    """A job field escaped for Telegram's HTML; '' when Indeed left it empty (NaN)."""
    return "" if pd.isna(value) else html.escape(str(value), quote=False)


def pay(amounts, per=None, symbol="€", prefix="") -> str:
    """E.g. '€4,000 – €5,500 / month' or 'up to €6,200'."""
    span = " – ".join(f"{symbol}{a:,.2f}".removesuffix(".00") for a in dict.fromkeys(amounts))
    return f"{prefix}{span} / {per}" if per else f"{prefix}{span}"


def salary(job) -> str:
    """The salary from Indeed's own fields, else from the job text; '' if neither has one."""
    amounts = [a for a in (job.min_amount, job.max_amount) if not pd.isna(a)]
    if amounts:
        return pay(amounts, PER.get(job.interval), CURRENCIES.get(job.currency, f"{job.currency} "))
    return salary_in_text("" if pd.isna(job.description) else job.description)


def salary_in_text(description: str) -> str:
    """Indeed.nl rarely fills its salary fields, so read it from the description instead.

    Salary lines have a € amount and a pay word ('bruto maandsalaris tussen €4.487 en €6.494')
    or are only a € range ('* €3.706 - €5.760'); the first that names the interval wins.
    """
    lines = description.translate({ord("\\"): None, 0x200B: None}).splitlines()  # markdown escapes
    found = [(line, m) for line in lines if (m := EURO_RANGE.search(line))]
    salary_lines = [
        (line, m)
        for line, m in found
        if PAY_WORDS.search(line) or (m[3] and not EURO_RANGE.sub("", line).strip(" *+-|\t"))
    ]
    if not salary_lines:
        return ""
    line, m = min(salary_lines, key=lambda c: (not INTERVAL.search(c[0]), not PAY_WORDS.search(c[0])))

    low = int(re.sub(r"\D", "", m[1])) * (1000 if m[2] else 1)
    high = int(re.sub(r"\D", "", m[3])) * (1000 if m[4] else 1) if m[3] else 0
    interval = INTERVAL.search(line, m.end()) or INTERVAL.search(line[: m.start()])
    per = ("month", "year", "hour")[interval.lastindex - 1] if interval else None
    if high >= low:  # a range; 'en' can also join unrelated amounts, e.g. '€4.000 en €500 reiskosten'
        return pay([low, high], per)
    before = line[: m.start()]
    prefix = "up to " if UP_TO.search(before) else "from " if FROM.search(before) else ""
    return pay([low], per, prefix=prefix)


def message(job) -> str:
    """The job's details, one per line, skipping any Indeed didn't fill in."""
    job_type = ", ".join(JOB_TYPES.get(t, t) for t in text(job.job_type).split(", ") if t)
    details = {"🏢": text(job.company), "📍": text(job.location), "💶": salary(job), "💼": job_type}
    return "<br>".join(
        [f"{icon} {value}" for icon, value in details.items() if value]
        + [f'<a href="{html.escape(job.job_url)}">View on Indeed →</a>']
    )


def send(job) -> bool:
    time.sleep(1)
    return NOTIFIER.notify(
        title=text(job.title),
        body=message(job),
        body_format=apprise.NotifyFormat.HTML,
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
