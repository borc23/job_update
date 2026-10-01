"""A job's salary as text, e.g. '€4,000 – €5,500 / month', from Indeed's fields or the description."""

import re
from typing import NamedTuple

CURRENCIES = {"EUR": "€", "USD": "$", "GBP": "£"}
INDEED_INTERVALS = {"yearly": "year", "monthly": "month", "weekly": "week", "daily": "day", "hourly": "hour"}
# What pay per interval can plausibly be: rules out amounts that aren't salaries ('€0,23 per km')
# and interval words that don't fit the amount ('€60.000 incl. 13e maand' is yearly)
PLAUSIBLE = {"month": (250, 15_000), "year": (10_000, 400_000), "hour": (5, 150)}

AMOUNT = r"(\d{1,3}(?:[.,]\d{3})+|\d+)(?:[.,](\d{1,2})|[.,]-)?\s*(k\b)?"  # 4.487, 18,50, 3.706,-, 4.5k
AMOUNT_PARTS = re.compile(AMOUNT, re.I)
EURO_RANGE = re.compile(
    rf"(?:€|EUR)\s*(?P<low>{AMOUNT})"
    rf"(?:\s*(?:[-–—]|\b(?:tot|t/m|en|to|and)\b)\s*(?:€|EUR)?\s*(?P<high>{AMOUNT}))?",
    re.I,
)
PAY_WORDS = re.compile(
    r"salar|bruto|gross|\bpay\b|loon|beloning|verdien|\bschaal \d|stagevergoeding|internship allowance", re.I
)
INTERVAL = re.compile(  # group names are PLAUSIBLE's keys
    r"\b(?P<month>maand\w*|month\w*|mnd\b)|\b(?P<year>jaar\w*|year\w*|annual\w*|per annum)"
    r"|(?P<hour>per uur|uurloon|uurtarief|per hour|hourly|/\s*uur\b|/\s*h(?:ou)?r\b)",
    re.I,
)
PREFIXES = {  # words right before a single amount: 'max. €5.000' is 'up to €5,000'
    "up to ": re.compile(r"\b(?:tot|max\w*|up to)\W*$", re.I),
    "from ": re.compile(r"\b(?:vanaf|from|min\w*|starting at)\W*$", re.I),
}
MARKDOWN_NOISE = {ord("\\"): None, 0x200B: None}  # escapes and zero-width spaces in JobSpy's markdown


class Salary(NamedTuple):
    amounts: list[float]
    per: str | None
    prefix: str = ""
    symbol: str = "€"
    named: bool = False  # the text names the interval, rather than it being inferred from the amount

    def __str__(self) -> str:
        span = " – ".join(f"{self.symbol}{a:,.2f}".removesuffix(".00") for a in dict.fromkeys(self.amounts))
        return f"{self.prefix}{span} / {self.per}" if self.per else f"{self.prefix}{span}"


def from_fields(low: float | None, high: float | None, interval: str | None, currency: str | None) -> str:
    """Indeed's own salary fields; '' when it left them empty."""
    amounts = [a for a in (low, high) if a is not None]
    symbol = CURRENCIES.get(currency, f"{currency} ") if currency else ""
    return str(Salary(amounts, INDEED_INTERVALS.get(interval), symbol=symbol)) if amounts else ""


def from_text(description: str) -> str:
    """Indeed.nl rarely fills its salary fields, so read it from the description instead.

    Salary lines have a € amount and a pay word ('bruto maandsalaris tussen €4.487 en €6.494')
    or are only a € range ('* €3.706 - €5.760'). Amounts that name a plausible interval win,
    then those on a pay-word line, then ranges, then the first.
    """
    ranked = []
    for line in description.translate(MARKDOWN_NOISE).splitlines():
        matches = list(EURO_RANGE.finditer(line))
        pay_line = bool(PAY_WORDS.search(line))
        only_a_range = any(m["high"] for m in matches) and not EURO_RANGE.sub("", line).strip(" *+-|\t")
        if not (pay_line or only_a_range):
            continue
        for i, m in enumerate(matches):
            # The words that belong to an amount are the ones up to its neighbouring amounts
            before = line[matches[i - 1].end() if i else 0 : m.start()]
            after = line[m.end() : matches[i + 1].start() if i + 1 < len(matches) else len(line)]
            if salary := _read(m, before, after):
                ranked.append(((not salary.named, not pay_line, len(salary.amounts) == 1), salary))
    return str(min(ranked, key=lambda r: r[0])[1]) if ranked else ""


def _read(m: re.Match, before: str, after: str) -> Salary | None:
    """The salary in one EURO_RANGE match, given the text around it; None if no interval's pay fits it."""
    low, high = _amount(m["low"]), m["high"] and _amount(m["high"])
    # 'en' can also join unrelated amounts, e.g. '€4.000 en €500 reiskosten'
    amounts = [low, high] if high and high >= low else [low]
    fits = [per for per, (lo, hi) in PLAUSIBLE.items() if all(lo <= a <= hi for a in amounts)]
    preceding = list(INTERVAL.finditer(before))
    interval = INTERVAL.search(after) or (preceding[-1] if preceding else None)
    named = interval.lastgroup if interval else None
    if named in fits:
        per = named
    elif fits:
        per = fits[0] if len(fits) == 1 else None  # €10k–15k could be a month or a year
    else:
        return None
    prefix = "" if len(amounts) > 1 else next((p for p, words in PREFIXES.items() if words.search(before)), "")
    return Salary(amounts, per, prefix, named=named in fits)


def _amount(text: str) -> float:
    """'4.487' -> 4487, '18,50' -> 18.5, '3.706,-' -> 3706, '4.5k' -> 4500."""
    whole, decimals, k = AMOUNT_PARTS.fullmatch(text).groups()
    value = int(re.sub(r"\D", "", whole)) + (int(decimals) / 10 ** len(decimals) if decimals else 0)
    return value * 1000 if k else value
