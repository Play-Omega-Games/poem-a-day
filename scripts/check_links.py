#!/usr/bin/env python3
"""Check every link in plans/poems.json against the live web.

For each unique page: HTTP 200. For each entry: the #anchor (if any) exists
in that page, and the poem's first line appears in the page text.
Usage, from the repo root: python3 scripts/check_links.py [plans/poems.json]
"""
import html, json, re, sys, time, urllib.request
from urllib.parse import urldefrag

PLAN = sys.argv[1] if len(sys.argv) > 1 else "plans/poems.json"
UA = {"User-Agent": "Mozilla/5.0 (poem-a-day link check)"}

def get(url, tries=3):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                return r.status, r.read().decode("utf-8", "replace")
        except Exception as e:
            err = e
            time.sleep(2 * (i + 1))
    return getattr(err, "code", 0) or 0, ""

def letters(s):
    s = html.unescape(re.sub(r"<[^>]+>", " ", s))
    return re.sub(r"[^a-z]", "", s.lower())

days = json.load(open(PLAN))["days"]
pages = {}
for d in days:
    pages.setdefault(urldefrag(d["full_text_link"])[0], []).append(d)

bad = []
for n, (url, ds) in enumerate(sorted(pages.items()), 1):
    status, body = get(url)
    print(f"[{n}/{len(pages)}] {status} {url} ({len(ds)} entries)", flush=True)
    if status != 200:
        bad.append((url, f"HTTP {status}")); continue
    ids = set(re.findall(r'\b(?:id|name)="([^"]+)"', body))
    text = letters(body)
    for d in ds:
        frag = urldefrag(d["full_text_link"])[1]
        if frag and frag not in ids:
            bad.append((d["full_text_link"], f"day {d['day']}: anchor #{frag} missing"))
        if letters(d["first_line"])[:30] not in text:
            bad.append((url, f"day {d['day']}: first line not found on page"))
    time.sleep(0.5)

anchored = sum(1 for d in days if "#" in d["full_text_link"])
print(f"\n{len(days)} entries, {len(pages)} unique pages, {anchored} links with a poem anchor")
if bad:
    print(f"{len(bad)} PROBLEMS"); [print(" ", u, why) for u, why in bad]; sys.exit(1)
print("ALL LINKS OK: every page returned 200, every anchor exists, every first line is on its page")
