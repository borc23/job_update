"""Send new Indeed.nl jobs matching config.toml to Telegram (or any Apprise channel)."""

import html
import os
import re
import sys
import time
import tomllib
from datetime import date, timedelta
from pathlib import Path

import apprise
import pandas as pd
from jobspy import scrape_jobs

HERE = Path(__file__).parent
CONFIG = tomllib.loads((HERE / "config.toml").read_text(encoding="utf-8"))
SEEN_FILE = HERE / "seen.txt"  # "<job id>\t<date it was last in the results>" per line
SEEN_DAYS = 30  # forget a job once it has been out of the results this long
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

AMOUNT = r"(\d{1,3}(?:[.,]\d{3})+|\d+)(?:[.,](\d{1,2})|[.,]-)?\s*(k\b)?"  # 4.487, 18,50, 3.706,-, 4.5k
EURO_RANGE = re.compile(
    rf"(?:€|EUR)\s*{AMOUNT}(?:\s*(?:[-–—]|\b(?:tot|t/m|en|to|and)\b)\s*(?:€|EUR)?\s*{AMOUNT})?", re.I
)
PAY_WORDS = re.compile(
    r"salar|bruto|gross|\bpay\b|loon|beloning|verdien|\bschaal \d|stagevergoeding|internship allowance", re.I
)
INTERVAL = re.compile(
    r"\b(maand\w*|month\w*|mnd\b)|\b(jaar\w*|year\w*|annual\w*|per annum)"
    r"|(per uur|uurloon|uurtarief|per hour|hourly|/\s*uur\b|/\s*h(?:ou)?r\b)",
    re.I,
)
UP_TO = re.compile(r"\b(?:tot|max\w*|up to)\W*$", re.I)
FROM = re.compile(r"\b(?:vanaf|from|min\w*|starting at)\W*$", re.I)
# What pay per interval can plausibly be: rules out amounts that aren't salaries ('€0,23 per km')
# and interval words that don't fit the amount ('€60.000 incl. 13e maand' is yearly)
PLAUSIBLE = {"month": (250, 15_000), "year": (10_000, 400_000), "hour": (5, 150)}


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
    or are only a € range ('* €3.706 - €5.760'). Amounts that name a plausible interval win,
    then those on a pay-word line, then ranges, then the first.
    """
    lines = description.translate({ord("\\"): None, 0x200B: None}).splitlines()  # markdown escapes
    candidates = []
    for line in lines:
        matches = list(EURO_RANGE.finditer(line))
        pay_line = bool(PAY_WORDS.search(line))
        if not (pay_line or (any(m[4] for m in matches) and not EURO_RANGE.sub("", line).strip(" *+-|\t"))):
            continue
        for i, m in enumerate(matches):
            # The words that belong to an amount are the ones up to its neighbouring amounts
            before = line[matches[i - 1].end() if i else 0 : m.start()]
            after = line[m.end() : matches[i + 1].start() if i + 1 < len(matches) else len(line)]
            if found := read_salary(m, before, after):
                named, is_range, salary_text = found
                candidates.append(((not named, not pay_line, not is_range), salary_text))
    return min(candidates, key=lambda c: c[0])[1] if candidates else ""


def read_salary(m: re.Match, before: str, after: str) -> tuple[bool, bool, str] | None:
    """(names its interval, is a range, the salary) for one EURO_RANGE match; None if no interval fits."""
    low = amount(*m.group(1, 2, 3))
    high = amount(*m.group(4, 5, 6)) if m[4] else None
    # 'en' can also join unrelated amounts, e.g. '€4.000 en €500 reiskosten'
    amounts = [low, high] if high is not None and high >= low else [low]
    fits = [per for per, (lo, hi) in PLAUSIBLE.items() if all(lo <= a <= hi for a in amounts)]
    preceding = list(INTERVAL.finditer(before))
    interval = INTERVAL.search(after) or (preceding[-1] if preceding else None)
    named = interval and ("month", "year", "hour")[interval.lastindex - 1]
    if named in fits:
        per = named
    elif fits:
        per = fits[0] if len(fits) == 1 else None  # €10k–15k could be a month or a year
    else:
        return None
    if len(amounts) > 1:
        return named in fits, True, pay(amounts, per)
    prefix = "up to " if UP_TO.search(before) else "from " if FROM.search(before) else ""
    return named in fits, False, pay(amounts, per, prefix=prefix)


def amount(digits: str, decimals: str | None, k: str | None) -> float:
    """One AMOUNT's groups as a number: ('4.487', None, None) -> 4487, ('4', '5', 'k') -> 4500."""
    value = int(re.sub(r"\D", "", digits)) + (int(decimals) / 10 ** len(decimals) if decimals else 0)
    return value * 1000 if k else value


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


def load_seen() -> dict[str, str] | None:
    """Job id -> date it was last in the results; None on the first run."""
    if not SEEN_FILE.exists():
        return None
    today = date.today().isoformat()
    lines = (line.partition("\t") for line in SEEN_FILE.read_text().splitlines() if line)
    return {job_id: day or today for job_id, _, day in lines}  # lines without a date predate them


def save_seen(seen: dict[str, str]) -> None:
    """Rewrite seen.txt, forgetting jobs that have been out of the results for SEEN_DAYS."""
    cutoff = (date.today() - timedelta(days=SEEN_DAYS)).isoformat()
    SEEN_FILE.write_text("".join(f"{job_id}\t{day}\n" for job_id, day in sorted(seen.items()) if day >= cutoff))


def main() -> None:
    if not NOTIFIER:
        sys.exit("Set NOTIFY_URL to a valid Apprise URL, e.g. tgram://<bot_token>/<chat_id>")

    seen = load_seen()
    jobs = fetch_jobs()
    if not jobs:
        sys.exit("No jobs found in any city: Indeed may be blocking the search.")

    today = date.today().isoformat()
    if seen is None:  # first run: start from what's listed now instead of sending days of backlog
        save_seen(dict.fromkeys(jobs, today))
        if not NOTIFIER.notify(
            title="Job alerts are on",
            body=f"Tracking {len(jobs)} current jobs; you'll get new ones as they're posted.",
            body_format=apprise.NotifyFormat.TEXT,
        ):
            sys.exit("Couldn't send the first-run message; check NOTIFY_URL.")
        return

    save_seen(seen | {job_id: today for job_id in jobs if job_id in seen})
    failed = 0
    with SEEN_FILE.open("a") as f:
        for job_id, job in jobs.items():
            if job_id in seen:
                continue
            try:
                sent = send(job)
            except Exception as e:  # one malformed posting mustn't stop the rest
                print(f"{job_id}: {e!r}", file=sys.stderr)
                sent = False
            if sent:
                f.write(f"{job_id}\t{today}\n")
                f.flush()  # saved right away, so a crash later in the run can't re-send it
            else:
                failed += 1
    if failed:
        sys.exit(f"{failed} notifications failed; they will be retried next run.")


if __name__ == "__main__":
    main()
