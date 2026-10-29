# Implementation Audit — JobAppAgent

Tanggal audit: 2026-10-29. Semua fakta di bawah diverifikasi dari file yang ada,
bukan asumsi.

## 1. Struktur repo

- Root: direktori `JobAppAgent/` — standalone Git repository initialized locally;
  GitHub remote has not yet been configured.
- File kunci: `pyproject.toml`, `README.md`, `profile.json`, `.env`/`.env.example`,
  `.gitignore`, `jobapp/` (core.py, __main__.py, slack_app.py, __init__.py),
  `tests/test_core.py`, `.github/workflows/daily-search.yml`, `data/jobs.sqlite3`.
- Dependensi: `slack-bolt>=1.20,<2`, Python `>=3.11`. Build backend setuptools.
- `.gitignore` mengabaikan `.env`, `.venv/`, `__pycache__/`, `*.py[cod]`, `data/`.

## 2. Komponen yang sudah ada (JobAppAgent Python)

- Discovery: Remotive, Remote OK, Jobicy, Himalayas, Arbeitnow Germany/UK APIs,
  and We Work Remotely RSS (`core.fetch_jobs`); HN and optional Brave fallbacks.
- Verifikasi URL: HTTPS + live HTTP 200–399, HEAD lalu fallback GET (`verify_url`).
- Scoring: title-role match is required by current `profile.json`; technical
  keyword overlap adds points (`score_job`).
- Persistensi: SQLite `data/jobs.sqlite3`, tabel `jobs` (key, payload, first_seen,
  last_seen, notified). Dedup via upsert.
- CLI: `search`, `scheduled`, `slack` (`__main__.py`).
- Slack: Bolt Socket Mode, perintah `/jobs`, `/jobs search ...`, `/jobs help`,
  event `app_mention` (`slack_app.py`). Membutuhkan `SLACK_BOT_TOKEN`,
  `SLACK_APP_TOKEN`, `SLACK_CHANNEL_ID`.
- Jadwal: GitHub Actions harian (cron `17 1 * * *` + workflow_dispatch), cache
  SQLite best-effort. Workflow mengasumsikan direktori ini menjadi root repo
  terpisah; push ke GitHub belum dilakukan.
- Env loading: parser KEY=value sederhana, `os.environ.setdefault`, default
  `profile.json` dan `data/jobs.sqlite3`. Override via `JOBAPP_PROFILE_PATH`,
  `JOBAPP_DB_PATH`.
- Tes: 4 unit test (scoring, store dedup/search, ingest, verify_url) — semua lulus
  (dijalankan 2026-10-29).

## 3. Profile configuration

- `profile.json` contains target role titles, skills, locations, and a minimum
  score. Keep it aligned with the profile the project owner wants to use.
- Resume files and private job-application material are not part of this repo.

## 4. Tooling & environment

- `job-application-agent` (npx) **belum terpasang** ("Not installed"). Spec
  MEGA_BUILD mengandalkannya; belum diinstal.
- Python: miniconda3 default; JobAppAgent punya `.venv` sendiri (python 3.13).
- Jaringan: search live ke Remotive/RemoteOK **berhasil** (75 listing, 28 eligible)
  pada 2026-10-29.

## 5. Slack

- Kode Slack sudah ada dan mengikuti pola Socket Mode (Bolt).
- Slack app dan Socket Mode sudah dikonfigurasi oleh pengguna; terminal menampilkan
  `Bolt app is running!` dan `/jobs help` berhasil membalas.
- Nilai token ada di `.env`; jangan tampilkan atau commit nilainya.
- Live search ke sumber lowongan belum diverifikasi pada environment agent ini.

## 6. GitHub Actions

- Workflow ada di `.github/workflows/daily-search.yml`, ditujukan untuk repo
  GitHub terpisah dengan JobAppAgent sebagai root.
- Jadwal dan tombol **Run workflow** mengirim alert lowongan baru ke Slack.
- Untuk mengaktifkan, push proyek ke GitHub lalu atur secret `SLACK_BOT_TOKEN`
  dan variable `SLACK_CHANNEL_ID`. Scheduled job tidak membutuhkan
  `SLACK_APP_TOKEN`.

## 7. Blocker & risiko

1. Tidak ada git di JobAppAgent → tidak bisa push/Actions/sync state.
2. `job-application-agent` (npx) belum terpasang → fitur spec yang bergantung padanya
   belum tersedia.
3. State SQLite lokal (`data/`) di-gitignore dan tidak sinkron antar mesin.
4. Belum ada test integrasi Slack/network yang terdokumentasi (hanya 4 unit test).
5. Workflow Actions cache SQLite = best-effort, bukan DB tahan lama.

## 8. Rekomendasi langkah berikutnya

1. Buat repo GitHub terpisah dari direktori `JobAppAgent/`, push, lalu isi secret
   dan variable workflow untuk mengaktifkan alert terjadwal.
2. Selaraskan `profile.json` dengan fakta CV (keywords/locations/minimum_score).
3. Pasang `job-application-agent` hanya jika fitur spec benar-benar dibutuhkan;
   JobAppAgent yang ada sudah menutupi discovery+Slack dasar.
4. Jika ingin `/jobs` tetap menjawab saat terminal lokal mati, deploy listener
   Socket Mode ke host persisten; GitHub Actions hanya menangani alert terjadwal.

## Update 2026-10-29 — multi-source search

- Slack Socket Mode was connected in the user's workspace; `/jobs help` returned the bot's help response.
- Search adapters now query Remotive, Remote OK, Jobicy, Himalayas, Arbeitnow Germany, Arbeitnow UK, and We Work Remotely RSS concurrently, then group matches by source.
- If no verified API matches are found, the bot can use optional Brave Search (`BRAVE_SEARCH_API_KEY`), Hacker News "Who is Hiring" comment search, and direct search links for LinkedIn, Glassdoor, Upwork, and Freelancer.
- LinkedIn, Glassdoor, and freelancer portal pages are not scraped. LinkedIn job API access requires approved partner access; Glassdoor automated scraping is disallowed without permission; Upwork API requires approved credentials/scopes.
- HTTP success only means a link responds. It does not establish that the employer or vacancy is legitimate/current.
- Brave web search is optional and metered; the API/RSS/Hacker News path needs no paid key.
- GitHub Actions was corrected to run when this directory is the repository root. It sends scheduled/manual alerts; it does not keep the Socket Mode slash-command listener alive.
- The agent environment could not reach the public job feeds during a live check, so the new adapters and fallbacks remain **live-unverified** here. No test suite was run for these changes.

Status: baseline local job search has 4/4 unit tests recorded as passing on 2026-10-29. Slack `/jobs help` was confirmed live by the user; multi-source search results remain unverified from this environment.
