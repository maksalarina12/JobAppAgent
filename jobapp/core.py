from __future__ import annotations

import json
import html
import os
import re
import sqlite3
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import urlencode
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


REMOTIVE_URL = "https://remotive.com/api/remote-jobs?limit=100"
REMOTEOK_URL = "https://remoteok.com/api"
USER_AGENT = "JobAppAgent/0.1 (+https://remotive.com; Remote OK feed consumer)"


@dataclass
class Job:
    source: str
    source_id: str
    company: str
    title: str
    location: str
    description: str
    url: str
    published: str = ""
    score: int = 0
    verified: bool = False
    source_url: str = ""

    @property
    def key(self) -> str:
        return f"{self.source}:{self.source_id}"


def _request(url: str, timeout: int = 12, method: str = "GET") -> bytes:
    req = Request(url, headers={"User-Agent": USER_AGENT}, method=method)
    with urlopen(req, timeout=timeout) as response:
        if not 200 <= response.status < 400:
            raise URLError(f"unexpected status {response.status}")
        return response.read(3_000_000)


def _fetch_remotive(query: str = "") -> list[Job]:
    url = REMOTIVE_URL
    if query:
        url += "&search=" + urlencode({"q": query})[2:]
    payload = json.loads(_request(url))
    return [Job("remotive", str(row.get("id", "")), row.get("company_name", ""),
                row.get("title", ""), row.get("candidate_required_location", ""),
                row.get("description", ""), row.get("url", ""), row.get("publication_date", ""),
                source_url=row.get("url", "")) for row in payload.get("jobs", [])]


def _fetch_remoteok() -> list[Job]:
    payload = json.loads(_request(REMOTEOK_URL))
    jobs = []
    for row in payload if isinstance(payload, list) else []:
        if not isinstance(row, dict) or not row.get("id") or not row.get("position"):
            continue  # first element is commonly a feed notice
        jobs.append(Job("remoteok", str(row["id"]), row.get("company", ""), row.get("position", ""),
                        ", ".join(row.get("location", []) if isinstance(row.get("location"), list) else [row.get("location", "")]),
                        row.get("description", ""), row.get("url", ""), row.get("date", ""),
                        source_url=row.get("url", "")))
    return jobs


def _fetch_jobicy(query: str = "") -> list[Job]:
    params = {"count": 100}
    if query:
        params["tag"] = query[:50]
    payload = json.loads(_request("https://jobicy.com/api/jobs?" + urlencode(params)))
    return [Job("jobicy", str(row.get("id", "")), row.get("companyName", ""),
                row.get("jobTitle", ""), row.get("jobGeo", ""),
                row.get("jobDescription", row.get("jobExcerpt", "")), row.get("url", ""),
                row.get("pubDate", ""), source_url=row.get("url", ""))
            for row in payload.get("jobs", [])]


def _fetch_himalayas(query: str = "") -> list[Job]:
    endpoint = "https://himalayas.app/jobs/api/search" if query else "https://himalayas.app/jobs/api"
    params = {"q": query, "sort": "recent", "page": 1} if query else {"limit": 20}
    payload = json.loads(_request(endpoint + "?" + urlencode(params)))
    jobs = []
    for row in payload.get("jobs", []):
        company = row.get("companyName", "")
        slug = row.get("companySlug", "")
        title_slug = row.get("slug", "")
        source_url = row.get("guid", "")
        if not str(source_url).startswith("https://"):
            source_url = f"https://himalayas.app/jobs/{slug}/{title_slug}" if slug and title_slug else "https://himalayas.app/jobs"
        restrictions = row.get("locationRestrictions") or []
        location = ", ".join(restrictions) if restrictions else "Worldwide remote"
        application_url = row.get("applicationLink") or source_url
        published = row.get("pubDate", "")
        if isinstance(published, (int, float)):
            published = datetime.fromtimestamp(published, timezone.utc).isoformat()
        jobs.append(Job("himalayas", str(row.get("guid", source_url)), company, row.get("title", ""),
                        location, row.get("description", row.get("excerpt", "")), application_url,
                        str(published), source_url=source_url))
    return jobs


def _fetch_weworkremotely() -> list[Job]:
    """Read We Work Remotely's public RSS feed (attribution stays on every result)."""
    root = ET.fromstring(_request("https://weworkremotely.com/remote-jobs.rss"))
    jobs = []
    for item in root.findall(".//item"):
        raw_title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        if not raw_title or not link:
            continue
        company, separator, title = raw_title.partition(":")
        if not separator:
            company, title = "We Work Remotely listing", raw_title
        jobs.append(Job("weworkremotely", (item.findtext("guid") or link).strip(),
                        company.strip(), title.strip(), "Remote", item.findtext("description") or "",
                        link, (item.findtext("pubDate") or "").strip(), source_url=link))
    return jobs


def _fetch_arbeitnow(base_url: str, source: str) -> list[Job]:
    """Free keyless API; listings are sourced largely from employer ATS systems."""
    payload = json.loads(_request(base_url))
    jobs = []
    for row in payload.get("data", []):
        if not row.get("remote") or not row.get("url"):
            continue
        published = row.get("created_at", "")
        if isinstance(published, (int, float)):
            published = datetime.fromtimestamp(published, timezone.utc).isoformat()
        jobs.append(Job(source, str(row.get("slug", row["url"])), row.get("company_name", ""),
                        row.get("title", ""), row.get("location", "Remote"), row.get("description", ""),
                        row["url"], str(published), source_url=row["url"]))
    return jobs


def fetch_jobs(query: str = "") -> list[Job]:
    """Query four public feeds in parallel; one source failing does not hide others."""
    sources = {
        "Remotive": lambda: _fetch_remotive(query),
        "Remote OK": _fetch_remoteok,
        "Jobicy": lambda: _fetch_jobicy(query),
        "Himalayas": lambda: _fetch_himalayas(query),
        "We Work Remotely RSS": _fetch_weworkremotely,
        "Arbeitnow Germany": lambda: _fetch_arbeitnow("https://www.arbeitnow.com/api/job-board-api", "arbeitnow_de"),
        "Arbeitnow UK": lambda: _fetch_arbeitnow("https://www.arbeitnow.co.uk/api/job-board-api", "arbeitnow_uk"),
    }
    jobs: list[Job] = []
    failures: list[str] = []
    with ThreadPoolExecutor(max_workers=len(sources)) as pool:
        pending = {pool.submit(fetch): name for name, fetch in sources.items()}
        for future in as_completed(pending):
            name = pending[future]
            try:
                jobs.extend(future.result())
            except Exception as exc:
                failures.append(f"{name}: {type(exc).__name__}")
    # Keep the most useful duplicate and do not let an unavailable API erase partial results.
    unique = {job.key: job for job in jobs if job.key.split(":", 1)[1]}
    if not unique and failures:
        raise RuntimeError("All job feeds failed: " + "; ".join(failures))
    if failures:
        print("Job feed unavailable: " + "; ".join(failures))
    return list(unique.values())


def search_web_jobs(query: str) -> list[dict]:
    """Optional live web fallback through Brave Search; never scrape result pages."""
    token = os.getenv("BRAVE_SEARCH_API_KEY", "").strip()
    if not token:
        return []
    search_query = f'"{query}" job hiring remote careers'
    url = "https://api.search.brave.com/res/v1/web/search?" + urlencode({"q": search_query, "count": 8, "country": "us"})
    req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json", "X-Subscription-Token": token})
    with urlopen(req, timeout=12) as response:
        payload = json.loads(response.read(1_000_000))
    results = []
    for row in payload.get("web", {}).get("results", []):
        link = row.get("url", "")
        if urlparse(link).scheme == "https":
            results.append({"title": row.get("title", "Job search result"), "url": link,
                            "description": row.get("description", "")})
    return results


def search_hn_forum_jobs(query: str) -> list[dict]:
    """Search Hacker News hiring-thread comments as unverified community leads."""
    params = {"query": query, "tags": "comment", "hitsPerPage": 30}
    payload = json.loads(_request("https://hn.algolia.com/api/v1/search_by_date?" + urlencode(params)))
    results = []
    for row in payload.get("hits", []):
        thread = html.unescape(str(row.get("story_title") or ""))
        body = html.unescape(re.sub(r"<[^>]*>", " ", str(row.get("comment_text") or "")))
        if "who is hiring" not in thread.lower() or not body.strip():
            continue
        title = next((line.strip() for line in body.splitlines() if line.strip()), "Hiring thread comment")[:180]
        results.append({"title": title, "url": f"https://news.ycombinator.com/item?id={row.get('objectID', '')}",
                        "description": re.sub(r"\s+", " ", body)[:320], "posted": row.get("created_at", "")})
    return results[:8]


def score_job(job: Job, profile: dict) -> int:
    text = f"{job.title} {job.description} {job.company}".lower()
    title = job.title.lower()

    def contains_phrase(haystack: str, phrase: str) -> bool:
        # Match whole words so e.g. "ai" does not match "paid".
        return bool(re.search(r"(?<!\w)" + re.escape(phrase.lower()) + r"(?!\w)", haystack))

    title_roles = [str(term).strip().lower() for term in profile.get("title_keywords", []) if str(term).strip()]
    title_match = any(contains_phrase(title, role) for role in title_roles)
    if profile.get("require_title_match") and not title_match:
        return 0

    terms = [str(term).strip().lower() for term in profile.get("keywords", []) if str(term).strip()]
    matched = {term for term in terms if contains_phrase(text, term)}
    if not title_roles:
        # Keep legacy/custom profiles without role-title rules working as before.
        points = sum(12 if contains_phrase(title, term) else 6 for term in matched)
        if any(x and x in job.location.lower() for x in profile.get("locations", [])):
            points += 15
        return min(points, 100)
    # A matching target role title is the main signal; skills add capped evidence.
    points = 50 if title_match else 0
    points += min(35, len(matched) * 5)
    loc = job.location.lower()
    location_terms = [str(x).lower() for x in profile.get("locations", [])]
    if any(x and x in loc for x in location_terms):
        points += 5
    return min(points, 100)


def verify_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
        return False
    try:
        _request(url, timeout=8, method="HEAD")
        return True
    except HTTPError as exc:
        # Some application sites reject HEAD; bounded GET still checks the landing page.
        if exc.code not in (403, 405, 501):
            return False
    except Exception:
        return False
    try:
        _request(url, timeout=8)
        return True
    except Exception:
        return False


class JobStore:
    def __init__(self, path: str | Path):
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS jobs (
                key TEXT PRIMARY KEY, payload TEXT NOT NULL, first_seen REAL NOT NULL,
                last_seen REAL NOT NULL, notified INTEGER NOT NULL DEFAULT 0)""")

    def _connect(self):
        return sqlite3.connect(self.path)

    def upsert(self, job: Job) -> bool:
        now = time.time()
        with self._connect() as db:
            row = db.execute("SELECT 1 FROM jobs WHERE key=?", (job.key,)).fetchone()
            db.execute("""INSERT INTO jobs(key,payload,first_seen,last_seen) VALUES(?,?,?,?)
                ON CONFLICT(key) DO UPDATE SET payload=excluded.payload,last_seen=excluded.last_seen""",
                       (job.key, json.dumps(asdict(job)), now, now))
        return row is None

    def mark_notified(self, job: Job) -> None:
        with self._connect() as db:
            db.execute("UPDATE jobs SET notified=1 WHERE key=?", (job.key,))

    def unnotified(self, minimum_score: int) -> list[Job]:
        with self._connect() as db:
            rows = db.execute("SELECT payload FROM jobs WHERE notified=0").fetchall()
        jobs = [Job(**json.loads(row[0])) for row in rows]
        return sorted((j for j in jobs if j.score >= minimum_score and j.verified), key=lambda j: j.score, reverse=True)

    def search(self, query: str, limit: int = 10, profile: dict | None = None) -> list[Job]:
        terms = [re.escape(x) for x in query.lower().split() if x]
        with self._connect() as db:
            rows = db.execute("SELECT payload FROM jobs").fetchall()
        jobs = [Job(**json.loads(row[0])) for row in rows]
        jobs = [job for job in jobs if job.verified]
        if profile is not None:
            # Re-score cached rows so profile changes apply immediately.
            for job in jobs:
                job.score = score_job(job, profile)
            jobs = [job for job in jobs if job.score >= profile["minimum_score"]]
        if terms:
            jobs = [j for j in jobs if all(re.search(term, f"{j.title} {j.company} {j.description}".lower()) for term in terms)]
        return sorted(jobs, key=lambda j: (j.score, j.published), reverse=True)[:limit]


def load_profile(path: str | Path) -> dict:
    with open(path, encoding="utf-8") as file:
        profile = json.load(file)
    profile["minimum_score"] = max(0, min(100, int(profile.get("minimum_score", 25))))
    return profile


def ingest(store: JobStore, profile: dict, jobs: list[Job] | None = None, check_urls: bool = True,
           query: str = "") -> tuple[int, int]:
    new_count = 0
    candidates = []
    for job in jobs if jobs is not None else fetch_jobs(query):
        if not job.url:
            continue
        job.score = score_job(job, profile)
        # Re-check cached candidates too; never preserve a stale successful link check.
        if check_urls and job.score >= profile["minimum_score"]:
            candidates.append(job)
        else:
            job.verified = False
        if store.upsert(job):
            new_count += 1
    if check_urls:
        with ThreadPoolExecutor(max_workers=8) as pool:
            checks = {pool.submit(verify_url, job.url): job for job in candidates}
            for future in as_completed(checks):
                job = checks[future]
                try:
                    job.verified = future.result()
                except Exception:
                    job.verified = False
                store.upsert(job)
    return new_count, len(store.unnotified(profile["minimum_score"]))
