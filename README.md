# Indeed job alerts

Checks Indeed.nl every 2 hours for AI / Machine Learning / Python jobs around Rotterdam, Den Haag, Utrecht, Amsterdam and Eindhoven, and sends each new posting to Telegram.

[JobSpy](https://github.com/speedyapply/JobSpy) does the searching and [Apprise](https://github.com/caronc/apprise) the messaging, so `main.py` stays small.

## Configure

Edit [config.toml](config.toml), no code changes needed:

- `search_term`: Indeed search syntax. `title:(...)` matches job titles only; `OR`, `"exact phrase"` and `-exclude` also work.
- `[locations]`: city = radius in km.
- Any other [scrape_jobs parameter](https://github.com/speedyapply/JobSpy#parameters-for-scrape_jobs) can go under `[search]`.

The schedule is the `cron` line in [.github/workflows/job-alerts.yml](.github/workflows/job-alerts.yml).

## Setup (once)

1. **Telegram bot**: message [@BotFather](https://t.me/BotFather), send `/newbot` and copy the token. Send your new bot any message, then open `https://api.telegram.org/bot<TOKEN>/getUpdates` and copy the number after `"chat":{"id":`. Your notify URL is `tgram://<TOKEN>/<CHAT_ID>`.
2. **GitHub**: push this folder to a **private** repo, then add the notify URL as a secret named `NOTIFY_URL` (*Settings → Secrets and variables → Actions*). Never commit the token.
3. **Start**: *Actions → Job alerts → Run workflow*. The first run only records the jobs listed now and sends a "Job alerts are on" message; after that you get each new posting, every 2 hours.

## Good to know

- `seen.txt` lives on the `state` branch, which the workflow creates and commits to, so `main` only gets your commits. It holds the jobs already sent and the date each was last in the results; a job is forgotten once it has been gone for 30 days. Delete the `state` branch to start fresh: the next run records the current jobs again without sending them.
- If a run fails (e.g. Indeed blocks the search or the Telegram token is wrong), GitHub emails you.
- `NOTIFY_URL` accepts any [Apprise URL](https://github.com/caronc/apprise/wiki) (WhatsApp, email, Discord, ...); separate several with commas.
- The workflow has two jobs: `check` runs the scraper with a read-only token, and `commit` pushes `seen.txt` with nothing but git. GitHub bills each job in whole minutes, so a run costs at least 1 minute, plus 1 when there's something new to commit. At 12 runs a day that's up to about 730 of the 2,000 free minutes/month for private repos while `check` stays under a minute, or about 1,100 if it takes 2.
- `requirements.txt` is a lockfile: every package with its hash, so a tampered or swapped download fails the install. To change dependencies, edit `requirements.in` and regenerate it with the command at the top of that file.

## Run locally

```powershell
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
$env:NOTIFY_URL = Read-Host "Notify URL"  # paste it here, keeps the token out of shell history
.venv\Scripts\python main.py
```

Tests: `.venv\Scripts\python -m unittest`. Add a case to `SalaryInText.CASES` in [test_main.py](test_main.py) whenever a posting's salary comes out wrong.
