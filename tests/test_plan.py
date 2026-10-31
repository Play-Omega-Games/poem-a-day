"""Offline checks on plans/poems.json. Run: python3 -m pytest tests -q (or python3 tests/test_plan.py)."""
import json, os, re, collections

HERE = os.path.dirname(os.path.abspath(__file__))
PLAN = json.load(open(os.path.join(HERE, "..", "plans", "poems.json")))
DAYS = PLAN["days"]
EM = "\u2014"

def year(e):
    return int(re.findall(r"\b(1[5-9]\d\d)\b", e["published"])[-1])

def test_count_and_numbering():
    assert len(DAYS) == 365
    assert [e["day"] for e in DAYS] == list(range(1, 366))

def test_required_fields():
    for e in DAYS:
        for k in ("title", "author", "first_line", "published", "lines", "text", "full_text_link", "verified", "source_notes"):
            assert e.get(k) not in (None, ""), (e["day"], k)
        assert e["verified"] is True, e["day"]
        assert e["lines"] == len([l for l in e["text"].split("\n") if l.strip()]), e["day"]
        assert e["text"].split("\n")[0].strip() == e["first_line"], e["day"]

def test_published_before_1931():
    for e in DAYS:
        assert year(e) < 1931, (e["day"], e["published"])

def test_dickinson_1890s_editions_only():
    for e in DAYS:
        if e["author"] == "Emily Dickinson":
            assert re.search(r"\b189[016]\b", e["published"]), (e["day"], e["published"])
            assert "gutenberg.org/cache/epub/12242/" in e["full_text_link"], e["day"]
            for bad in ("Johnson", "Franklin"):
                assert bad not in e["published"] + e["source_notes"]

def test_links_are_public_domain_hosts():
    for e in DAYS:
        assert re.match(r"https://(www\.gutenberg\.org/cache/epub/\d+/pg\d+-images\.html|en\.wikisource\.org/wiki/)", e["full_text_link"]), e["day"]

def test_no_duplicates():
    for key in ("title", "first_line"):
        c = collections.Counter((e["author"], e[key].lower()) for e in DAYS)
        assert not [k for k, v in c.items() if v > 1], key
    c = collections.Counter(re.sub(r"[^a-z]", "", e["first_line"].lower())[:14] for e in DAYS)
    assert not [k for k, v in c.items() if v > 1]

def test_poems_are_real_and_short_enough():
    for e in DAYS:
        assert 4 <= e["lines"] <= 170, (e["day"], e["lines"])

def test_no_shakespeare():
    assert not [e for e in DAYS if "Shakespeare" in e["author"]]

def test_no_same_author_back_to_back():
    for a, b in zip(DAYS, DAYS[1:]):
        assert a["author"] != b["author"], (a["day"], a["author"])

def test_no_em_dash_in_our_words():
    for e in DAYS:
        for k in ("title", "author", "published", "source_notes"):
            assert EM not in e[k], (e["day"], k)
    assert EM not in json.dumps(PLAN["meta"], ensure_ascii=False)

def test_no_editorial_junk_in_text():
    junk = re.compile(r"Project Gutenberg|\[Illustration|\bFootnote\b|CONTENTS|\bINDEX\b|^\s*\d+\s*$|\[Pg|\{\d+\}", re.M)
    for e in DAYS:
        assert not junk.search(e["text"]), (e["day"], junk.search(e["text"]).group(0))

def test_author_spread():
    c = collections.Counter(e["author"] for e in DAYS)
    assert len(c) >= 40
    assert max(c.values()) <= 60

if __name__ == "__main__":
    import sys
    fails = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            try: fn(); print("ok  ", name)
            except AssertionError as ex: fails += 1; print("FAIL", name, ex)
    sys.exit(1 if fails else 0)
