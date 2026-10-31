# Poem a Day

365 public-domain poems, one a day, for the 🪶 Poem a Day Grok Bot template by Omega Games. Each day holds the full poem, its first line, the book it first appeared in and a link to the full text. Openers come first, then 56 poets are interleaved so no poet appears twice in a row and each one's work spreads across the year.

## Quick start

```
curl -sO https://raw.githubusercontent.com/Play-Omega-Games/poem-a-day/main/plans/poems.json
python3 tests/test_plan.py
python3 scripts/build.py --fetch
python3 scripts/check_links.py
```

A bot loads the plan from `https://raw.githubusercontent.com/Play-Omega-Games/poem-a-day/main/plans/poems.json`. If that fails, it downloads `scripts/build.py` and `scripts/books.py` and rebuilds the plan from the public sources.

## Plan format

`plans/poems.json` has `meta` and `days`. Each day: `day`, `title`, `author`, `first_line`, `published` (book and year), `lines`, `text` (the full poem), `full_text_link`, `link_lands_on_poem`, `verified` and `source_notes`.

## Files

- `plans/poems.json`: the 365-day plan.
- `scripts/books.py`: the fixed list of source books, all published before 1931. `scripts/build.py`: `python3 scripts/build.py --fetch` downloads the sources into `./src` and rebuilds `plans/poems.json` (standard library only).
- `scripts/check_links.py`: checks every link live (HTTP 200, the anchor exists, the first line is on the page).
- `tests/test_plan.py`: offline checks on the plan. Run `python3 tests/test_plan.py`.
- `MANIFEST.txt`: every file with its size and SHA-256, for loading by raw URL.

## License

The plan is CC0 1.0. Code is MIT. See `LICENSE`. Every poem was published before 1931 and is in the public domain in the United States.

Questions or ideas? Contact Omega Games at john@playomega.games.
