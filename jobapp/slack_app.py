import os

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from .core import ingest, search_hn_forum_jobs, search_web_jobs
from .__main__ import render, render_fallback


def run(store, profile):
    app = App(token=os.environ["SLACK_BOT_TOKEN"])

    @app.command("/jobs")
    def jobs_command(ack, command, respond):
        ack()
        text = (command.get("text") or "").strip()
        if text == "help":
            respond("Use `/jobs` to list new verified matches or `/jobs search <keywords>` to search fresh listings.", response_type="ephemeral")
            return
        query = text[7:].strip() if text.startswith("search ") else text
        if not query:
            query = profile.get("title_keywords", ["AI Engineer"])[0]
        found = []
        api_failed = False
        try:
            ingest(store, profile, query=query)
            found = store.search(query, 10, profile)
        except Exception as exc:
            # Keep fallback discovery available when the job APIs are unreachable.
            api_failed = True
            print(f"Job API search failed: {type(exc).__name__}")
        if found:
            respond(render(found), response_type="ephemeral")
            return

        web_results = []
        forum_results = []
        try:
            web_results = search_web_jobs(query)
        except Exception as exc:
            print(f"Web fallback failed: {type(exc).__name__}")
        try:
            forum_results = search_hn_forum_jobs(query)
        except Exception as exc:
            print(f"Forum fallback failed: {type(exc).__name__}")
        respond(render_fallback(query, web_results, forum_results, api_failed), response_type="ephemeral")

    @app.event("app_mention")
    def mention(event, say):
        try:
            ingest(store, profile)
            say(render(store.unnotified(profile["minimum_score"])[:5]))
        except Exception as exc:
            print(f"Mention search failed: {type(exc).__name__}")
            say("Job search could not complete. Please try again later.")

    SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"]).start()
