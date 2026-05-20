#!/usr/bin/env python3
"""
Dolce Pensiero Carbonara Checker.

Scrapes https://dolcepensiero.at/menu/menu-der-woche, checks if any dish
named "Carbonara" appears on the weekly menu (preferably on Wednesday),
and posts the result to a Slack incoming webhook.

Exit codes:
    0  Check ran successfully (regardless of carbonara result).
    1  Page could not be loaded or Slack post failed.
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.request
from typing import Dict, List

from playwright.sync_api import sync_playwright

MENU_URL = "https://dolcepensiero.at/menu/menu-der-woche"
SLACK_WEBHOOK = os.environ.get("SLACK_WEBHOOK_URL")
TARGET_DISH = "carbonara"
PREFERRED_DAY = "Mittwoch"
DAYS = ["Montag", "Dienstag", "Mittwoch", "Donnerstag",
        "Freitag", "Samstag", "Sonntag"]


def fetch_menu_text() -> str:
    """Render the SvelteKit page in headless Chromium and return body text."""
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(locale="de-AT")
        page = context.new_page()
        page.goto(MENU_URL, wait_until="networkidle", timeout=30_000)
        # Give client-side rendering a moment to settle
        page.wait_for_timeout(1500)
        text = page.locator("body").inner_text()
        browser.close()
    return text


def parse_days(text: str) -> Dict[str, str]:
    """Split text into per-day buckets keyed by German weekday name."""
    sections: Dict[str, str] = {d: "" for d in DAYS}
    pattern = re.compile(rf"\b({'|'.join(DAYS)})\b[^\n]*")
    matches = list(pattern.finditer(text))
    for i, m in enumerate(matches):
        day = m.group(1)
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections[day] += text[start:end] + "\n"
    return sections


def find_carbonara(sections: Dict[str, str]) -> List[str]:
    """Return the weekdays whose section contains 'carbonara' (case-insensitive)."""
    return [day for day in DAYS if TARGET_DISH in sections[day].lower()]


def build_message(days_with: List[str], menu_empty: bool) -> dict:
    if menu_empty:
        text = (
            f":hourglass_flowing_sand: Das Wochenmenü von *Dolce Pensiero* "
            f"ist noch nicht veröffentlicht. <{MENU_URL}|Hier nachschauen>."
        )
    elif PREFERRED_DAY in days_with:
        text = (
            f":pasta: *Carbonara am Mittwoch!* Diese Woche im Programm bei "
            f"Dolce Pensiero. <{MENU_URL}|Menü öffnen>"
        )
    elif days_with:
        days_str = ", ".join(days_with)
        text = (
            f":pasta: Keine Carbonara am Mittwoch — aber am *{days_str}*. "
            f"<{MENU_URL}|Menü öffnen>"
        )
    else:
        text = (
            f":x: Diese Woche steht *keine Carbonara* auf dem Menü von "
            f"Dolce Pensiero. <{MENU_URL}|Menü öffnen>"
        )
    return {"text": text}


def post_to_slack(payload: dict) -> None:
    if not SLACK_WEBHOOK:
        print("SLACK_WEBHOOK_URL nicht gesetzt — Payload nur ausgegeben:")
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return
    req = urllib.request.Request(
        SLACK_WEBHOOK,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        if resp.status != 200:
            print(f"Slack antwortete mit {resp.status}", file=sys.stderr)
            sys.exit(1)


def main() -> None:
    print(f"Lade {MENU_URL} …")
    text = fetch_menu_text()
    sections = parse_days(text)

    menu_empty = not any(s.strip() for s in sections.values())
    days_with = [] if menu_empty else find_carbonara(sections)

    print(f"Menü leer:          {menu_empty}")
    print(f"Carbonara-Tage:     {days_with or '—'}")

    payload = build_message(days_with, menu_empty)
    print(f"Slack-Nachricht:    {payload['text']}")
    post_to_slack(payload)


if __name__ == "__main__":
    main()
