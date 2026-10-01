# Indeed job alerts

Checks Indeed.nl every hour for AI / Machine Learning / Python jobs around Rotterdam, Den Haag, Utrecht, Amsterdam and Eindhoven, and sends each new posting to Telegram.

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
3. **Start**: *Actions → Job alerts → Run workflow*. The first run sends the jobs from the last 3 days; after that only new postings, every hour.

## Good to know

- `seen.txt` holds the IDs of jobs already sent; the workflow commits it after each run. Delete it to start fresh.
- If a run fails (e.g. Indeed blocks the search or the Telegram token is wrong), GitHub emails you.
- `NOTIFY_URL` accepts any [Apprise URL](https://github.com/caronc/apprise/wiki) (WhatsApp, email, Discord, ...); separate several with commas.
- Hourly runs fit in the free 2,000 Actions minutes/month for private repos.

## Run locally

```powershell
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
$env:NOTIFY_URL = Read-Host "Notify URL"  # paste it here, keeps the token out of shell history
.venv\Scripts\python main.py
```
