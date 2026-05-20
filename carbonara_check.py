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
    """Render the SvelteKit page in headless Chromium and return body text.

    The dishes live inside accordion panels that may lazy-render their
    content only after the toggle is clicked. We try several expansion
    strategies and dump diagnostic output so failures are easy to debug.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(locale="de-AT")
        page = context.new_page()
        page.goto(MENU_URL, wait_until="networkidle", timeout=30_000)
        page.wait_for_timeout(2000)  # let SvelteKit hydrate

        # Multi-strategy expansion: try standard a11y patterns first, then
        # fall back to clicking anything that looks like a day heading.
        diag = page.evaluate(
            """() => {
                const days = ['Montag','Dienstag','Mittwoch','Donnerstag',
                              'Freitag','Samstag','Sonntag'];
                const log = {ariaToggles: 0, details: 0, dayHeadings: 0};

                // 1. Standard aria-expanded toggles
                const ariaToggles = document.querySelectorAll(
                    '[aria-expanded="false"]'
                );
                log.ariaToggles = ariaToggles.length;
                ariaToggles.forEach(el => { try { el.click(); } catch(e) {} });

                // 2. <details> elements
                const details = document.querySelectorAll('details:not([open])');
                log.details = details.length;
                details.forEach(d => d.open = true);

                // 3. Click elements whose text starts with a day name.
                //    Only run if strategies 1 and 2 didn't find anything,
                //    otherwise we risk toggling things back closed.
                if (log.ariaToggles === 0 && log.details === 0) {
                    const headings = [];
                    document.querySelectorAll(
                        'h1,h2,h3,h4,h5,button,[role="button"],div,a'
                    ).forEach(el => {
                        const text = (el.textContent || '').trim();
                        if (text.length === 0 || text.length > 60) return;
                        if (!days.some(d => text.startsWith(d))) return;
                        // Skip if a child element also matches (prefer
                        // the most specific element).
                        const childMatches = Array.from(el.children).some(c => {
                            const ct = (c.textContent || '').trim();
                            return ct.length < 60 &&
                                   days.some(d => ct.startsWith(d));
                        });
                        if (childMatches) return;
                        headings.push(el);
                    });
                    log.dayHeadings = headings.length;
                    headings.forEach(el => {
                        try { el.click(); } catch(e) {}
                    });
                }
                return log;
            }"""
        )
        print(f"Expansion strategies: {diag}")
        page.wait_for_timeout(2000)  # wait for content to render after clicks

        text = page.locator("body").text_content() or ""

        # Diagnostics — printed on every run so the Actions log shows
        # exactly what was scraped.
        print(f"Body text length: {len(text)}")
        print(f"Contains 'carbonara': {'carbonara' in text.lower()}")
        for day in DAYS:
            if day in text:
                idx = text.find(day)
                snippet = text[idx:idx + 200].replace("\n", " ")
                print(f"  {day}: {snippet!r}")

        browser.close()
    return text


def parse_days(text: str) -> Dict[str, str]:
    """Split text into per-day buckets keyed by German weekday name.

    text_content() returns a single string without newlines, so we split
    between consecutive day-name occurrences rather than line by line.
    """
    sections: Dict[str, str] = {d: "" for d in DAYS}
    pattern = re.compile(rf"\b({'|'.join(DAYS)})\b")
    matches = list(pattern.finditer(text))
    for i, m in enumerate(matches):
        day = m.group(1)
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections[day] += text[start:end]
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
