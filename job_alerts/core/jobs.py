"""Job postings from Indeed, via JobSpy."""

from jobspy import scrape_jobs

KM_PER_MILE = 1.609  # config.toml has km, JobSpy takes miles


def fetch_jobs(config: dict) -> dict:
    """Search every configured city; keyed by job id so overlapping results collapse. Empty fields are None."""
    jobs = {}
    for city, km in config["locations"].items():
        found = scrape_jobs(**config["search"], location=city, distance=round(km / KM_PER_MILE))
        jobs |= {job.id: job for job in found.astype(object).where(found.notna(), None).itertuples()}
    return jobs
