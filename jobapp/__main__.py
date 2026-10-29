from __future__ import annotations

import argparse
import os
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlencode, urlparse

from .core import JobStore, ingest, load_profile


def config():
    # Load this project's simple KEY=value file without requiring an extra package.
    env_file = Path(".env")
    if env_file.is_file():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key, value = key.strip(), value.strip().strip("\"'")
            if key and key.replace("_", "").isalnum():
                os.environ.setdefault(key, value)
    profile_path = os.getenv("JOBAPP_PROFILE_PATH", "profile.json")
    db_path = os.getenv("JOBAPP_DB_PATH", "data/jobs.sqlite3")
    return JobStore(db_path), load_profile(profile_path)


def render(jobs) -> str:
    if not jobs:
        return "No matching verified jobs found."
    grouped = defaultdict(list)
    for job in jobs:
        grouped[job.source].append(job)
    sections = []
    labels = {"remotive": "Remotive API", "remoteok": "Remote OK API", "jobicy": "Jobicy API",
              "himalayas": "Himalayas API", "weworkremotely": "We Work Remotely RSS",
              "arbeitnow_de": "Arbeitnow Germany API", "arbeitnow_uk": "Arbeitnow UK API"}
    for source in ("remotive", "remoteok", "jobicy", "himalayas", "weworkremotely", "arbeitnow_de", "arbeitnow_uk"):
        if source not in grouped:
            continue
        cards = []
        for job in grouped[source]:
            source_link = f"<{job.source_url}|source>" if job.source_url and urlparse(job.source_url).scheme == "https" else "source"
            posted = f" · posted {job.published[:10]}" if job.published else ""
            cards.append(
                f"*{job.title}* — {job.company} (match {job.score}/100)\n"
                f"<{job.url}|Open posting> · {job.location or 'Location unspecified'} · {source_link}{posted}\n"
                "Link check passed; confirm the role is still open on the employer's site."
            )
        sections.append(f"*Jobs from {labels[source]}*\n" + "\n\n".join(cards))
    return "\n\n".join(sections)


def render_fallback(query: str, web_results: list[dict], forum_results: list[dict], api_failed: bool = False) -> str:
    def escape(text: str) -> str:
        return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    sections = ["The job-board feeds " + ("were unreachable; showing fallback sources." if api_failed else
                                          "returned no matching verified listings; showing fallback sources.")]
    if web_results:
        cards = [f"<{r['url']}|{escape(r['title'])}>\n{escape(r.get('description', '')[:240])}" for r in web_results]
        sections.append("*Web search results — verify on the employer site*\n" + "\n\n".join(cards))
    if forum_results:
        cards = [f"<{r['url']}|{escape(r['title'])}>\n{escape(r.get('description', '')[:240])} · community post, unverified"
                 for r in forum_results]
        sections.append("*Forum leads: Hacker News Who is Hiring — unverified*\n" + "\n\n".join(cards))
    encoded = urlencode({"sc.keyword": query})
    encoded_q = urlencode({"q": query})
    portal_links = [
        f"<https://www.linkedin.com/jobs/search/?{encoded_q}|LinkedIn Jobs>",
        f"<https://www.glassdoor.com/Job/jobs.htm?{encoded}|Glassdoor Jobs>",
        f"<https://www.upwork.com/nx/search/jobs/?{encoded_q}|Upwork jobs>",
        f"<https://www.freelancer.com/jobs/?{encoded_q}|Freelancer jobs>",
    ]
    sections.append("*Search portals directly*\n" + " · ".join(portal_links) +
                    "\nThese links open each portal's own search; portal listings are not scraped.")
    return "\n\n".join(sections)


def main():
    parser = argparse.ArgumentParser(prog="jobapp")
    sub = parser.add_subparsers(dest="command", required=True)
    search = sub.add_parser("search", help="Fetch, verify, and search jobs")
    search.add_argument("--query", default="")
    search.add_argument("--limit", type=int, default=10)
    sub.add_parser("scheduled", help="Ingest jobs and send new matches to Slack")
    sub.add_parser("slack", help="Run the Slack Socket Mode command listener")
    args = parser.parse_args()
    store, profile = config()
    if args.command in ("search", "scheduled"):
        try:
            new_count, eligible = ingest(store, profile, query=args.query if args.command == "search" else "")
        except Exception as exc:
            print(f"Search failed: {exc}")
            raise SystemExit(1) from None
        print(f"Ingested {new_count} new listings; {eligible} verified new match(es) are eligible.")
        if args.command == "search":
            print(render(store.search(args.query, max(1, min(args.limit, 25)), profile)))
            return
        from slack_sdk import WebClient
        token = os.environ["SLACK_BOT_TOKEN"]
        channel = os.environ["SLACK_CHANNEL_ID"]
        client = WebClient(token=token)
        jobs = store.unnotified(profile["minimum_score"])
        for job in jobs[:10]:
            client.chat_postMessage(channel=channel, text=render([job]), mrkdwn=True)
            store.mark_notified(job)
        print(f"Posted {min(len(jobs), 10)} match(es) to Slack.")
        return
    if args.command == "slack":
        from .slack_app import run
        run(store, profile)


if __name__ == "__main__":
    main()
