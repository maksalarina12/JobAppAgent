# JobAppAgent

A small remote-job discovery and matching assistant. It reads public job-board feeds, checks each application URL, scores listings against a configurable skills profile, stores seen jobs in SQLite, and sends new matches to Slack. It never applies to jobs automatically.

## Components

- Sources: Remotive, Remote OK, Jobicy, Himalayas, Arbeitnow Germany, Arbeitnow UK, and We Work Remotely's public RSS feed. The app queries feeds in parallel and groups results by provider. Arbeitnow's public API aggregates postings largely from ATS systems and filters to remote roles. If there are no matches, it can use optional Brave web search (API key), Hacker News hiring-thread leads, then direct search links for LinkedIn, Glassdoor, Upwork, and Freelancer. The job APIs, RSS, and Hacker News fallback do not need keys. Coverage and freshness depend on each provider.
- Verification: requires a valid HTTPS posting/application URL and a successful live HTTP response (200–399). This catches dead links; it does **not** prove an employer is genuine or that a vacancy is still open. Open the linked source/employer posting and confirm before applying.
- Matching: transparent keyword overlap and optional location terms, no LLM or personal data required. Tune `profile.json`.
- Persistence: SQLite database (`data/jobs.sqlite3` by default). Scheduled Actions restores/saves it through GitHub Actions cache, which is best effort and is not a durable database. For durable history use a hosted database or run the Slack process on a persistent host with a mounted disk.
- Slack: Bolt Socket Mode; no public inbound server is needed. Create a Slack app, enable Socket Mode, add a bot token with `chat:write`, `commands`, and `app_mentions:read`, subscribe to `app_mention`, and add slash command `/jobs` with any placeholder request URL (Socket Mode delivers it over the socket). Install it and configure the two tokens below.
- Schedule: GitHub Actions runs daily at 08:17 WIB and can be started manually with **Run workflow**. Add repository secret `SLACK_BOT_TOKEN` and repository variable `SLACK_CHANNEL_ID` to post alerts; the scheduled workflow does not need `SLACK_APP_TOKEN`.

The Actions workflow assumes this project directory is the root of its own GitHub repository. This workspace currently has no Git repository for JobAppAgent, so the schedule will not run until the project is published to GitHub. Scheduled alerts are automated; interactive `/jobs` commands still require a running Socket Mode process. GitHub Actions is a short-lived runner, not a persistent bot host.

## Start

Python 3.11+ is recommended.

```sh
cd JobAppAgent
python -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env
python -m jobapp search --query "python developer"
```

Interactive Slack search runs as a persistent process:

```sh
python -m jobapp slack
```

In Slack while the Socket Mode listener is running: `/jobs` searches the configured AI-role profile; `/jobs search ai engineer` searches feeds for a query and ranks results. API results are grouped by source. When they return no matches, fallback sections show web results, community leads, and official portal search links. `/jobs help` shows usage. Scheduled alerts run separately through GitHub Actions. The same search can be run locally without Slack.

## Configuration

Edit `profile.json` to set `title_keywords`, `keywords`, `locations`, and `minimum_score` (0–100). With `require_title_match: true`, API results must match a target role title before skill scoring. To enable the live web fallback, create a Brave Search API key and set `BRAVE_SEARCH_API_KEY` in `.env`; keep usage within the plan's allowance. Environment settings can override database/profile paths and Slack credentials. Secrets belong in `.env` locally (ignored by git) or GitHub Actions secrets. Do not commit credentials or database files.

Search is read-only and does not submit applications or message employers. A high match score indicates title/skill keyword overlap only, not eligibility or endorsement. Sources may omit jobs, repeat expired listings, or return broken links. Verification requests are bounded by timeouts and limited to role matches. Results show source and publication date when provided; an HTTP link check is not employer verification.

LinkedIn, Glassdoor, and freelance marketplaces are not scraped. LinkedIn's job APIs require approved partner access, Glassdoor prohibits automated scraping without permission, and Upwork API access requires developer credentials and permissions. Until those credentials are approved, the fallback provides direct searches on each portal instead of representing scraped pages as verified job listings. Brave Search is optional and metered; leave `BRAVE_SEARCH_API_KEY` empty for the no-cost path.

## Slack setup (Socket Mode)

1. Buat Slack app di https://api.slack.com/apps (From scratch).
2. OAuth & Permissions → Bot Token Scopes: `chat:write`, `commands`, `app_mentions:read` → Install to Workspace → salin `xoxb-...` (`SLACK_BOT_TOKEN`).
3. Socket Mode → Enable → buat App-Level Token scope `connections:write` → salin `xapp-...` (`SLACK_APP_TOKEN`).
4. Slash Commands → buat `/jobs` (Request URL placeholder OK).
5. Event Subscriptions → subscribe `app_mention`.
6. Salin Channel ID target (`C...`) → `SLACK_CHANNEL_ID`. Invite bot ke channel.
7. Isi `.env` (jangan commit), lalu jalankan `python -m jobapp slack`.

## Status & audit

Lihat `docs/IMPLEMENTATION_AUDIT.md` untuk baseline dan update implementasi terakhir.
The optional `job-application-agent` (npx) package is not required by this Python app.

## Tests

```sh
python -m unittest discover -s tests -v
```

Tests use synthetic listings and mocked HTTP; they do not verify live feed availability, Slack installation/authentication, or the Actions schedule. Those integrations remain untested until run with real accounts and network access.
