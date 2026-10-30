# JobAppAgent

<p align="center">
  <strong>A personal job-discovery agent that reads seven public job boards,
  verifies application links, ranks listings against your profile,
  and reports matches to Slack — on a schedule, without a server.</strong>
</p>

<p align="center">
  <a href="#-quick-start">Quick Start</a> ·
  <a href="#-how-it-works">How It Works</a> ·
  <a href="#-slack-slash-command">Slack</a> ·
  <a href="#-daily-slack-alerts-via-github-actions">Scheduled Alerts</a> ·
  <a href="#-roadmap">Roadmap</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11%2B-informational" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/license-MIT-green" alt="MIT License">
  <img src="https://img.shields.io/badge/dependency-slack--bolt-4A154B" alt="slack-bolt">
  <a href="https://github.com/maksalarina12/JobAppAgent/actions/workflows/daily-search.yml">
    <img src="https://github.com/maksalarina12/JobAppAgent/actions/workflows/daily-search.yml/badge.svg" alt="Daily search workflow">
  </a>
  <a href="https://github.com/maksalarina12/JobAppAgent/actions/workflows/tests.yml">
    <img src="https://github.com/maksalarina12/JobAppAgent/actions/workflows/tests.yml/badge.svg" alt="Unit tests">
  </a>
</p>

---

JobAppAgent is a **personal automation prototype** for the part of job hunting
that is pure drudgery: checking board after board every day, opening dead
links, and scrolling past roles you would never take.

It collects public listings, scores them against a configurable candidate
profile, checks that application links actually respond over HTTPS, stores
everything in SQLite to cut duplicate alerts, and pushes the results to your
terminal or Slack. It helps with **discovery** only — it never applies to
jobs and never contacts employers on your behalf.

## ✨ Highlights

| | |
|---|---|
| 🌐 **7 parallel sources** | Remotive, Remote OK, Jobicy, Himalayas, We Work Remotely (RSS), Arbeitnow DE, Arbeitnow UK — fetched concurrently, so one slow or down provider never suppresses the others |
| 🎯 **Profile-based scoring** | Transparent keyword scoring against target titles, skills, and location preferences in `profile.json` |
| 🔗 **Link verification** | Application URLs are checked for HTTPS and liveness before they reach you |
| 💾 **SQLite deduplication** | Listings and alert state are persisted, so repeated runs don't re-alert the same jobs |
| 💬 **Slack `/jobs` command** | Slash command via Socket Mode — no public webhook URL required |
| ⏰ **Serverless scheduling** | Daily alerts run on GitHub Actions (08:17 Asia/Jakarta) — nothing to keep running 24/7 |
| 🧭 **Fallback leads** | When no feed matches, optional Brave Search, Hacker News hiring-thread comments, and direct portal search links |

> **Honest disclaimers up front.** A passing HTTPS check means the page
> responded *at check time* — it is not proof a vacancy is open or an employer
> is legitimate. Scores are keyword signals, not assessments of your
> qualifications or hiring odds. Fallback results from search/HN are leads,
> not verified listings. Every listing should be confirmed at its source.

## 🚀 Quick Start

```bash
git clone https://github.com/maksalarina12/JobAppAgent.git
cd JobAppAgent
python -m venv .venv
source .venv/bin/activate          # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -e .
cp .env.example .env
```

Edit `.env` with your chosen integrations:

```dotenv
SLACK_BOT_TOKEN=xoxb-...
SLACK_APP_TOKEN=xapp-...
SLACK_CHANNEL_ID=C...
JOBAPP_DB_PATH=data/jobs.sqlite3
JOBAPP_PROFILE_PATH=profile.json
BRAVE_SEARCH_API_KEY=              # optional
```

Only the Slack credentials are needed for Slack features; the terminal-only
path works out of the box without them.

## 🔁 How It Works

```text
   7 public job APIs & RSS feeds
                │  (fetched in parallel)
                ▼
          PROFILE MATCHING
       title keywords · skills · locations
                │
                ▼
         HTTPS LINK CHECK
       is the application URL alive?
                │
        ┌───────┴───────┐
        ▼               ▼
    Terminal         Slack
                    │
                    └── no feed match? → optional fallback:
                        Brave Search · HN "Who is Hiring" comments
                        · direct LinkedIn / Glassdoor / Upwork /
                        Freelancer search links
```

Feed results stay attributed to their provider, and both the source link and
the application link are preserved on every result.

## 🖥 Use the CLI

```bash
python -m jobapp search --query "AI engineer"
python -m jobapp search --query "machine learning engineer" --limit 5
```

The query narrows provider results where supported and is also used by local
matching. Retrieved results are stored in the configured SQLite database.

## 💬 Slack Slash Command

Set up Socket Mode — **no public request URL needed**:

1. Create a Slack app.
2. Add scopes `chat:write`, `commands`, and `app_mentions:read`.
3. Create an app-level token with `connections:write`.
4. Create the `/jobs` command; enable the `app_mention` event if wanted.
5. Reinstall the app to the workspace.
6. Set your credentials in `.env` (`SLACK_BOT_TOKEN`, `SLACK_APP_TOKEN`) and add the bot to the channel.
7. Start the Socket Mode listener:

```bash
python -m jobapp slack
```

Then, from within Slack:

```text
/jobs
/jobs search AI engineer
/jobs help
```

The listener must be running for live slash commands and mentions. Scheduled
alerts via GitHub Actions do **not** keep the Socket Mode listener online.

## ⏰ Daily Slack Alerts via GitHub Actions

The workflow at `.github/workflows/daily-search.yml` runs every day at
**08:17 Asia/Jakarta** (cron `17 1 * * * UTC`) and can be run manually
via **Actions → Run workflow**.

Add these to **Settings → Secrets and variables → Actions**:

| Name | GitHub type | Purpose |
|---|---|---|
| `SLACK_BOT_TOKEN` | Repository secret | Slack message delivery |
| `SLACK_CHANNEL_ID` | Repository variable | Destination channel |

Only the bot token and channel ID are needed — the scheduled flow doesn't
use `SLACK_APP_TOKEN`, which is for the local Socket Mode listener. Local
SQLite state is preserved across runs via the Actions cache on a **best-effort
basis**; GitHub Actions cache is not durable database storage.

## 🎛 Matching Profile (`profile.json`)

- `title_keywords` — roles you're actually targeting.
- `keywords` — supporting skill signals.
- `locations` — preferred locations.
- `minimum_score` — cutoff for stored matches and scheduled alerts.
- `require_title_match` — require a title match before a listing qualifies.

The score is a **transparent keyword signal**. It deliberately does not claim
to measure your qualifications, employer quality, or hiring probability.

## ⚙️ Configuration Reference

| Variable | Required for | Default |
|---|---|---|
| `SLACK_BOT_TOKEN` | Slack listener and scheduled alerts | — |
| `SLACK_APP_TOKEN` | Local Socket Mode listener | — |
| `SLACK_CHANNEL_ID` | Scheduled Slack alerts | — |
| `JOBAPP_DB_PATH` | SQLite storage | `data/jobs.sqlite3` |
| `JOBAPP_PROFILE_PATH` | Matching profile | `profile.json` |
| `BRAVE_SEARCH_API_KEY` | Optional Slack web-search fallback | *(empty, disabled)* |

## 🧪 Tests

```bash
python -m unittest discover -s tests -v
```

Unit tests use synthetic data and mocked HTTP responses. They validate
scoring behavior, SQLite dedup/search, ingestion persistence, and HTTPS
verification — **not** live provider availability, real Slack installs, or
GitHub Actions execution.

## 🗺 Roadmap

**Shipped**

- [x] Multi-source concurrent ingestion
- [x] Keyword-based profile scoring
- [x] HTTPS application-link verification
- [x] SQLite persistence and dedup
- [x] Slack `/jobs` slash command (Socket Mode)
- [x] Daily scheduled alerts via GitHub Actions
- [x] Fallback leads (Brave Search, Hacker News, portal deep-links)
- [x] MIT license + CI for the unit tests (Python 3.11 & 3.13 matrix)

**Next up (rough order)**

- [ ] Richer matching: structured skill/seniority/contract reasoning with
     explanations of each match and mismatch
- [ ] Company-legitimacy checks — domain and identity signals surfaced as
     **risk flags with cited evidence**, not accusations
- [ ] Application tracking — `saved → shortlisted → applied → interview →
     rejected/offer/archived` with follow-up reminders
- [ ] Structured logs and per-run summaries

## 📁 Project Structure

```text
JobAppAgent/
├── .github/workflows/daily-search.yml   # Scheduled Slack alerts
├── jobapp/
│   ├── core.py                          # Feeds, scoring, URL checks, SQLite
│   ├── __main__.py                      # CLI: search · slack · scheduled
│   └── slack_app.py                     # Slack Socket Mode listener
├── tests/                               # Unit tests (synthetic data, mocked HTTP)
├── .env.example                         # Env template
├── profile.json                         # Matching profile
└── pyproject.toml                       # Package metadata
```

## 🔒 Security and Limitations

- Keep Slack and Brave credentials in `.env` (git-ignored) and GitHub
  Secrets. **Never commit** `.env`, access tokens, or the local database.
- The bot discovers and reports listings; it never submits applications or
  messages recruiters.
- Providers can change APIs, feeds, rate limits, and coverage at any time.
- A reachable URL is not proof a job is open or an employer is verified.
- SQLite + Actions cache suit a **personal prototype**, not multi-user storage.
- Without a Brave key, fallback still offers HN leads and direct portal links.

---

*JobAppAgent is a personal job-discovery automation prototype. Always review
every listing at its source before applying.*
