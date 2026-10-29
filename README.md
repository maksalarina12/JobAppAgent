# JobAppAgent

**A multi-source job discovery and alerting agent built with Python and Slack.** JobAppAgent collects public job listings, ranks them against a configurable candidate profile, checks application links, and surfaces matches in the terminal or Slack. It helps with discovery; it does not apply to jobs or contact employers.

<p align="center">
  <strong>Discover → Match → Check links → Get alerted</strong>
</p>

## Highlights

- Queries seven public job feeds concurrently, so one unavailable provider does not suppress results from the others.
- Scores listings against target role titles, skills, and location preferences in `profile.json`.
- Groups results by provider and preserves source and application links.
- Checks that application links use HTTPS and respond when checked.
- Stores listings and notification state in SQLite to reduce duplicate alerts.
- Provides a Slack slash command through Socket Mode and scheduled Slack alerts through GitHub Actions.
- Offers optional web search, Hacker News hiring-thread leads, and direct job-portal search links when the Slack search has no matching feed results.

## How it works

```text
Public job APIs and RSS feeds
             │
             ▼
       Profile matching
             │
             ▼
       HTTPS link check
             │
       ┌─────┴─────┐
       ▼           ▼
   Terminal      Slack
                 │
                 └─ If no feed match: optional web search,
                    Hacker News leads, and portal search links
```

Feed results are fetched in parallel and remain attributed to their providers. In Slack, when no feed result matches, the bot can try Brave Search (if configured), look for Hacker News “Who is Hiring” comments, and provide direct searches for LinkedIn, Glassdoor, Upwork, and Freelancer. These fallback results are presented as leads; they are not treated as verified feed listings.

## Data sources

| Source | Integration | Notes |
|---|---|---|
| Remotive | Public API | Remote job listings |
| Remote OK | Public API | Remote job listings |
| Jobicy | Public API | Remote job listings |
| Himalayas | Public API | Remote job listings |
| Arbeitnow Germany | Public API | Remote listings from the Germany feed |
| Arbeitnow UK | Public API | Remote listings from the UK feed |
| We Work Remotely | Public RSS feed | Original listing link is retained |
| Brave Search | Optional API | Requires `BRAVE_SEARCH_API_KEY`; used as a Slack fallback |
| Hacker News | Public Algolia search API | Hiring-thread comments are community leads and may be outdated or unverified |
| LinkedIn, Glassdoor, Upwork, Freelancer | Direct search links | The project does not scrape these portals |

Availability, coverage, and freshness depend on each provider. A successful HTTPS check only means that a page responded at check time; it does not prove that a vacancy is open, an employer is legitimate, or a listing is current. Always confirm details on the employer's own site.

The public API, RSS, and Hacker News paths do not require a paid API key. Brave Search is optional and may have usage limits or charges. The project does not claim official LinkedIn or Glassdoor API access.

## Requirements

- Python 3.11 or newer
- A Slack workspace and Slack app for Slack features
- A GitHub repository for scheduled alerts

## Installation

```bash
git clone https://github.com/<your-account>/JobAppAgent.git
cd JobAppAgent
python -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env
```

On Windows PowerShell, activate the environment with:

```powershell
.venv\Scripts\Activate.ps1
```

Edit `.env` for the integrations you plan to use:

```dotenv
SLACK_BOT_TOKEN=xoxb-...
SLACK_APP_TOKEN=xapp-...
SLACK_CHANNEL_ID=C...
JOBAPP_DB_PATH=data/jobs.sqlite3
JOBAPP_PROFILE_PATH=profile.json
BRAVE_SEARCH_API_KEY=
```

Slack variables are only needed for Slack features. `BRAVE_SEARCH_API_KEY` is optional.

## Use the command line

Search the feeds and display matching results:

```bash
python -m jobapp search --query "AI engineer"
```

Limit the number of displayed results:

```bash
python -m jobapp search --query "machine learning engineer" --limit 5
```

The query narrows feed results where supported and is also used in local matching. Results are stored in the configured SQLite database.

## Set up Slack

1. Create a Slack app in your workspace and enable **Socket Mode**.
2. Add the bot scopes `chat:write`, `commands`, and `app_mentions:read`.
3. Create an app-level token with the `connections:write` scope.
4. Create the `/jobs` slash command. With Socket Mode enabled, no public request URL is required.
5. Enable the `app_mention` event if you want the bot to respond to mentions.
6. Install or reinstall the app to the workspace after changing scopes or commands.
7. Add the bot to the channel where you want scheduled alerts and set the values in `.env`.
8. Start the Socket Mode listener:

   ```bash
   python -m jobapp slack
   ```

Available slash command examples:

```text
/jobs
/jobs search AI engineer
/jobs help
```

The local listener must be running for interactive slash commands and mentions. GitHub Actions sends scheduled alerts, but it does not keep the Socket Mode listener online.

## Enable scheduled GitHub Actions alerts

The workflow at `.github/workflows/daily-search.yml` searches daily at **08:17 Asia/Jakarta time** and can also be started manually from **Actions → Job alerts → Run workflow**.

Add these values in **Settings → Secrets and variables → Actions**:

| Name | GitHub setting | Purpose |
|---|---|---|
| `SLACK_BOT_TOKEN` | Repository secret | Authenticates Slack message delivery |
| `SLACK_CHANNEL_ID` | Repository variable | Selects the destination channel |

The scheduled workflow needs the bot token and channel ID. It does not need `SLACK_APP_TOKEN`, which is used by the local Socket Mode listener. The workflow keeps SQLite state using the GitHub Actions cache on a best-effort basis; this is not durable database storage.

## Configure your matching profile

Edit `profile.json` to tune the discovery criteria:

- `title_keywords`: target job titles.
- `keywords`: skills and technologies used as supporting match signals.
- `locations`: location preferences.
- `minimum_score`: minimum score used for stored matches and scheduled alerts.
- `require_title_match`: require a target title to match before a listing can qualify.

The score is a transparent keyword-based ranking signal. It is not an assessment of qualifications, employer quality, or hiring probability.

## Configuration reference

| Variable | Required for | Default |
|---|---|---|
| `SLACK_BOT_TOKEN` | Slack listener and Slack alerts | — |
| `SLACK_APP_TOKEN` | Local Socket Mode listener | — |
| `SLACK_CHANNEL_ID` | Scheduled Slack alerts | — |
| `JOBAPP_DB_PATH` | SQLite storage | `data/jobs.sqlite3` |
| `JOBAPP_PROFILE_PATH` | Matching profile | `profile.json` |
| `BRAVE_SEARCH_API_KEY` | Optional Slack web-search fallback | Empty (disabled) |

## Security and limitations

- Keep Slack and Brave credentials in `.env` locally or GitHub Secrets. Never commit `.env`, access tokens, or the local database.
- The bot discovers and reports listings. It does not submit applications or message recruiters.
- Providers can change their APIs, feeds, rate limits, and listing coverage at any time.
- A reachable URL is not proof that the job is still open or the employer has been verified.
- SQLite and the GitHub Actions cache are suitable for a personal prototype, not durable multi-user storage.
- Brave Search is optional; without its key, Slack fallback still offers Hacker News leads and direct portal searches when available.

## Run the tests

```bash
python -m unittest discover -s tests -v
```

The unit tests use synthetic data and mocked HTTP responses. They do not validate live provider availability, Slack installation, or GitHub Actions execution.

## Project structure

```text
JobAppAgent/
├── .github/workflows/daily-search.yml  # Scheduled Slack alerts
├── jobapp/
│   ├── core.py                         # Feeds, scoring, URL checks, SQLite
│   ├── __main__.py                     # Command-line interface
│   └── slack_app.py                    # Slack Socket Mode listener
├── tests/                              # Unit tests
├── .env.example                        # Environment variable template
├── profile.json                        # Matching profile
└── pyproject.toml                      # Package metadata and dependencies
```

---

Built as a personal job-discovery automation prototype. Review every listing at its source before applying.
