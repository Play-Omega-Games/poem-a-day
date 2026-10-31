#!/usr/bin/env python3
"""Build the Poem a Day plan (365 public-domain poems) from public-domain editions published before 1931.
Usage, from the repo root: python3 scripts/build.py [--fetch]   (--fetch downloads the source books into ./src first)
Output: plans/poems.json. Book list and quotas: scripts/books.py."""
import re, json, html, os, sys, time, unicodedata, urllib.request
from datetime import date
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from books import BOOKS
if os.path.basename(HERE) == "scripts": HERE = os.path.dirname(HERE)   # repo layout: scripts/build.py writes ../plans
SRC = os.path.join(HERE, "src")
PG = "https://www.gutenberg.org/cache/epub/{id}/pg{id}.txt"
PGH = "https://www.gutenberg.org/cache/epub/{id}/pg{id}-images.html"
UA = {"User-Agent": "PoemADayBuilder/1.0 (public-domain reading plan)"}
TOTAL = 365

def fetch():
    os.makedirs(SRC, exist_ok=True)
    for b in BOOKS:
        if not b.get("id"):
            for page, _ in b.get("pages", []): ws_html(page)
            continue
        for u in (PG.format(id=b["id"]), PGH.format(id=b["id"])):
            fn = os.path.join(SRC, os.path.basename(u))
            for attempt in range(3):
                if os.path.exists(fn) and os.path.getsize(fn) > 1000:
                    break
                try:
                    open(fn, "wb").write(urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=120).read())
                except Exception as e:
                    print("retry", u, e); time.sleep(3)
            time.sleep(0.3)

def load(i):
    t = open(os.path.join(SRC, f"pg{i}.txt"), encoding="utf-8", errors="replace").read().replace("\r", "")
    t = t[t.find("\n", t.find("*** START")) + 1:]
    return t[:t.find("*** END")] if "*** END" in t else t

def norm(s):
    s = unicodedata.normalize("NFKD", s)
    return re.sub(r"[^a-z]", "", s.lower().replace("’", "'"))

ROMAN = re.compile(r"^(?:[IVXLC]+|\d+)\.?$")
def is_caps(l):
    letters = re.sub(r"[^A-Za-z]", "", l)
    return len(letters) >= 2 and letters.isupper()

def clean_lines(body):
    out = []
    for l in body.split("\n"):
        l = l.replace("°", "").replace("_", "").rstrip()
        l = re.sub(r"\s{3,}\d+$", "", l)            # trailing line numbers
        l = re.sub(r"\[(?:\d+|[ivx]+|Footnote[^\]]*)\]", "", l)   # footnote markers
        if re.match(r"^\s*\[(Illustration|Footnote|Sidenote|Picture)", l) or ROMAN.match(l.strip()):
            continue
        out.append(l)
    while out and not out[0].strip(): out.pop(0)
    while out and not out[-1].strip(): out.pop()
    # collapse runs of blank lines, dedent
    res = []
    for l in out:
        if not l.strip():
            if res and res[-1] == "": continue
            res.append(""); continue
        res.append(l)
    ind = min((len(l) - len(l.lstrip()) for l in res if l.strip()), default=0)
    return [l[ind:] if l.strip() else "" for l in res]

SMALL = {"a", "an", "and", "the", "of", "in", "on", "to", "at", "by", "for", "with", "from", "upon", "into", "or", "is", "o'", "nor", "but", "as"}
def nice_title(t):
    t = t.replace("_", "").strip()
    t = re.sub(r"^\d+\.\s*", "", t)
    t = re.sub(r"^[IVXLC]+\.\s+(?=[A-Z])", "", t)
    t = re.sub(r"\[[^\]]*\]?", "", t).strip()
    t = re.sub(r"\s+", " ", t).rstrip(".:;,").strip()
    out = []
    for i, w in enumerate(t.split(" ")):
        core = re.sub(r"[^A-Za-z']", "", w)
        if len(re.sub(r"[^A-Za-z]", "", core)) >= 2 and core.upper() == core and not re.fullmatch(r"[IVXLC]+", core):
            lw = w.lower()
            if i and lw.strip("“\"'(") in SMALL:
                w = lw
            else:
                w = re.sub(r"[a-z]", lambda m: m.group(0).upper(), lw, count=1)
        elif i and w.lower() in SMALL and w[:1].isupper() and (t.split(" ")[0][:1].isupper()) and sum(x[:1].isupper() for x in t.split(" ")) == len(t.split(" ")):
            w = w.lower()   # "Ode To A Nightingale" style
        out.append(w)
    t = " ".join(out)
    t = t.strip()
    if t[:1] in "\"“" and (t.count('"') + t.count("“") + t.count("”")) % 2 == 1: t = t[1:]
    if len(t) > 2 and t[0] in "\"“" and t[-1] in "\"”": t = t[1:-1]
    t = re.sub(r"-([a-z])", lambda m: "-" + m.group(1).upper(), t) if is_caps(" ".join(out)) else t
    return t

def tidy_body(lines, title):
    """Drop leading subtitle lines: lines equal to the title, all-caps dedication lines, 'Tune' notes, asterisks, parenthetical notes."""
    sub = []
    def is_junk(l):
        x = l.strip()
        return (not x or norm(x) == norm(title) or re.fullmatch(r"[*\s.]+", x) or x.startswith("Tune") or (x.startswith("(") and x.endswith(")") and len(x) < 70)
                or (is_caps(x) and len(x) < 80))
    lines = [l for l in lines if not re.fullmatch(r"\s*(\*\s*){3,}", l)]
    while lines and is_junk(lines[0]) and not (norm(lines[0]) == norm(title) and not is_caps(lines[0]) and len(lines) > 1 and lines[1].strip()):
        if lines[0].strip(): sub.append(lines[0].strip())
        lines = lines[1:]
    return lines, sub

def fix_dropcaps(lines):
    """Printed books set a poem's first word in capitals ("THE world is charged"). Turn that back into normal case."""
    letters = lambda w: re.sub(r"[^A-Za-zÀ-ÿ]", "", w)
    for k, l in enumerate(lines):
        if not l.strip(): continue
        if not re.search(r"[a-z]", l): return lines
        lead_ws = l[:len(l) - len(l.lstrip())]
        ws = l.strip().split(" ")
        lead = 0
        while lead < len(ws) and letters(ws[lead]) and letters(ws[lead]).isupper():
            lead += 1
        if lead == 0 or (lead == 1 and len(letters(ws[0])) < 2): return lines
        single = len(letters(ws[0])) == 1
        def cap(w):
            m = re.search(r"[A-Za-zÀ-ÿ]", w)
            return w if not m else w[:m.start() + 1] + w[m.start() + 1:].lower()
        out = []
        for i, w in enumerate(ws):
            if i == 0 and i < lead: w = cap(w)
            elif i < lead: w = w.lower() if single else cap(w)
            out.append(w)
        lines = list(lines); lines[k] = lead_ws + " ".join(out)
        return lines
    return lines

def first_line_title(lines):
    fl = next(l.strip() for l in lines if l.strip())
    return re.sub(r"[,;:.\-—–]+$", "", fl).strip()

def poem(title, lines, author, book, extra=None):
    lines, sub = tidy_body(list(lines), title)
    if sub: extra = dict(extra or {}, subtitle=" ".join(sub))
    lines = fix_dropcaps(lines)
    cut = next((i for i, l in enumerate(lines) if re.match(r"^\s*(CONTENTS|INDEX|NOTES?|FOOTNOTES?)\.?\s*$", l)), None)
    if cut is not None: lines = lines[:cut]
    while lines and (not lines[-1].strip() or (is_caps(lines[-1]) and len(re.sub(r"[^A-Za-z]", "", lines[-1])) >= 4)):
        lines = lines[:-1]   # trailing section headings or printer's colophon
    n = len([l for l in lines if l.strip()])
    d = {"title": title, "author": author, "lines_text": lines, "n": n, "first_line": next((l.strip() for l in lines if l.strip()), "")}
    if extra: d.update(extra)
    return d

def blocks(t, th=3):
    out, pending = [], None
    for p in re.split(r"\n(?:[ \t]*\n){%d,}" % th, t):
        p = p.strip("\n")
        if not p.strip(): continue
        paras = re.split(r"\n[ \t]*\n", p)
        if len(paras) == 1 and "\n" not in p.strip() and len(p.strip()) < 70 and (is_caps(p) or ROMAN.match(p.strip())):
            pending = p.strip()   # a title standing alone; the last one before the poem wins
            continue
        if pending is not None:
            first = paras[0].strip()
            if not ("\n" not in first and len(first) < 70 and is_caps(first)):
                paras = [pending] + paras
            pending = None
        title = " ".join(l.strip() for l in paras[0].split("\n"))
        rest = paras[1:]
        p0 = [l for l in paras[0].split("\n") if l.strip()]
        if len(p0) >= 3 and rest and sum(bool(re.search(r"[a-z]", l)) for l in p0) >= 3 and not is_caps(p0[0]):
            title = paras[0].split("\n")[0].strip(); rest = paras   # untitled poem: first stanza is not a title
        if rest and "\n" not in rest[0].strip() and len(rest) > 1 and re.match(r"^[IVX]+\.\s+[A-Z][a-z]", rest[0].strip()) and len(rest[0]) < 60:
            title = rest[0].strip(); rest = rest[1:]   # numbered sonnet sequence: "I. Peace"
        if re.match(r"^BOOK [IVXL]+", title) and rest and "\n" not in rest[0].strip() and len(rest) > 1:
            title = rest[0].strip(); rest = rest[1:]   # Leaves of Grass: book heading, then the poem title
        out.append((title, "\n\n".join(rest)))
    return out

def drop_heads(body):
    """Remove leading numeral or all-caps heading paragraphs and bracketed headnotes."""
    paras = re.split(r"\n[ \t]*\n", body)
    head = []
    while paras and (ROMAN.match(paras[0].strip()) or (is_caps(paras[0]) and "\n" not in paras[0].strip() and len(paras) > 1)
                     or paras[0].strip().startswith("[") or not paras[0].strip()):
        head.append(paras.pop(0).strip())
    return "\n\n".join(paras), head

def parse_blocks(b):
    t = load(b["id"])
    if b.get("section"):
        s, e = b["section"]
        t = t[t.find(s):]; t = t[:t.find(e)] if e in t else t
    out = []
    for title, body in blocks(t, b.get("th", 3)):
        body2, head = drop_heads(body)
        if not body2.strip(): continue
        lines = clean_lines(body2)
        if not lines: continue
        tt = nice_title(title)
        if ROMAN.match(title.strip()) or ROMAN.match(tt) or not tt or tt.upper() in ("SONNET", "SONG", "ODE"):
            tt2 = nice_title(head[0]) if head and not ROMAN.match(head[0]) and tt.upper() not in ("SONNET",) else ""
            tt = tt2 if tt2 and tt.upper() in ("SONG", "ODE") else first_line_title(lines)
        out.append(poem(tt, lines, b["author"], b, {"raw_title": title, "heads": head}))
    return out

def parse_dickinson(b):
    t = load(b["id"])
    s2, s3 = t.find("Second Series"), t.find("Third Series")
    out = []
    pos = 0
    for title, body in blocks(t, 3):
        p = t.find(body[:80], pos) if body else -1
        if p > 0: pos = p
        if not ROMAN.match(title.split()[0].strip() if title.split() else ""):
            continue
        body2, head = drop_heads(body)
        if not body2.strip(): continue
        lines = clean_lines(body2)
        if len([l for l in lines if l.strip()]) < 2: continue
        series = 1 if pos < s2 else (2 if pos < s3 else 3)
        ed_title = next((h for h in head if is_caps(h) and not ROMAN.match(h)), None)
        out.append(poem(first_line_title(lines), lines, b["author"], b,
                        {"edition": {1: "Poems, First Series (1890)", 2: "Poems, Second Series (1891)", 3: "Poems, Third Series (1896)"}[series],
                         "editors_title": nice_title(ed_title) if ed_title else None}))
    # the prelude "This is my letter to the world" sits outside the numbered sections
    i = t.find("This is my letter to the world")
    if i > 0:
        seg = t[i:t.find("\n\n\n", i)]
        out.insert(0, poem("This is my letter to the world", clean_lines(seg), b["author"], b, {"edition": "Poems, First Series (1890)", "editors_title": None}))
    return out

GT_AUTHORS = {}
def gt_author(a):
    a = a.strip().rstrip(".")
    m = {"P. B. SHELLEY": "Percy Bysshe Shelley", "LORD BYRON": "Lord Byron", "S. T. COLERIDGE": "Samuel Taylor Coleridge", "J. KEATS": "John Keats",
         "R. HERRICK": "Robert Herrick", "R. LOVELACE": "Richard Lovelace", "B. JONSON": "Ben Jonson", "H. VAUGHAN": "Henry Vaughan", "J. MILTON": "John Milton",
         "A. MARVELL": "Andrew Marvell", "G. HERBERT": "George Herbert", "C. LAMB": "Charles Lamb", "W. S. LANDOR": "Walter Savage Landor", "T. NASH": "Thomas Nashe",
         "C. MARLOWE": "Christopher Marlowe", "R. BURNS": "Robert Burns", "T. HOOD": "Thomas Hood", "C. WOLFE": "Charles Wolfe", "W. COLLINS": "William Collins",
         "T. CAMPBELL": "Thomas Campbell", "SIR W. SCOTT": "Sir Walter Scott", "T. GRAY": "Thomas Gray", "E. WALLER": "Edmund Waller", "SIR H. WOTTON": "Sir Henry Wotton",
         "SIR P. SIDNEY": "Sir Philip Sidney", "J. LYLYE": "John Lyly", "J. LYLY": "John Lyly", "J. SHIRLEY": "James Shirley", "J. DONNE": "John Donne", "M. DRAYTON": "Michael Drayton",
         "W. DRUMMOND": "William Drummond", "T. CAMPION": "Thomas Campion", "T. DEKKER": "Thomas Dekker", "SIR J. SUCKLING": "Sir John Suckling", "W. BLAKE": "William Blake",
         "W. COWPER": "William Cowper", "O. GOLDSMITH": "Oliver Goldsmith", "A. POPE": "Alexander Pope", "J. DRYDEN": "John Dryden", "T. CAREW": "Thomas Carew",
         "SIR W. RALEIGH": "Sir Walter Raleigh", "E. SPENSER": "Edmund Spenser", "T. MOORE": "Thomas Moore", "L. HUNT": "Leigh Hunt", "J. KEBLE": "John Keble",
         "H. COLERIDGE": "Hartley Coleridge", "R. SOUTHEY": "Robert Southey", "T. L. PEACOCK": "Thomas Love Peacock", "LADY A. LINDSAY": "Lady Anne Lindsay",
         "J. HOGG": "James Hogg", "A. CUNNINGHAM": "Allan Cunningham", "W. WORDSWORTH": "WORDSWORTH", "W. SHAKESPEARE": "SHAKESPEARE", "SHAKESPEARE": "SHAKESPEARE",
         "G. WITHER": "George Wither", "R. CRASHAW": "Richard Crashaw", "H. KING": "Henry King", "A. COWLEY": "Abraham Cowley", "J. FLETCHER": "John Fletcher",
         "F. BEAUMONT": "Francis Beaumont", "J. WEBSTER": "John Webster", "T. HEYWOOD": "Thomas Heywood", "SIR E. DYER": "Sir Edward Dyer", "LORD VAUX": "Lord Vaux"}
    a2 = a.replace("P.B.", "P. B.").replace("COLONEL ", "R. ").replace("SIR T. WYAT", "SIR T. WYATT")
    extra = {"R. LOVELACE": "Richard Lovelace", "SIR T. WYATT": "Sir Thomas Wyatt", "ANON": "Anonymous", "SIR C. SEDLEY": "Sir Charles Sedley",
             "J. THOMSON": "James Thomson", "S. ROGERS": "Samuel Rogers", "WILLIAM DRUMMOND OF HAWTHORNDEN": "William Drummond", "H. CONSTABLE": "Henry Constable",
             "T. LODGE": "Thomas Lodge", "S. DANIEL": "Samuel Daniel", "J. GAY": "John Gay", "M. PRIOR": "Matthew Prior", "LADY NAIRN": "Lady Nairne",
             "-- COLLINS": "William Collins", "A L. BARBAULD": "Anna Laetitia Barbauld", "H. CAREY": "Henry Carey", "R. BARNEFIELD": "Richard Barnfield"}
    return m.get(a2) or extra.get(a2)

def parse_golden(b):
    t = load(b["id"])
    t = t[t.find("FIRST BOOK"):]
    t = t[:t.rfind("NOTES")] if t.rfind("NOTES") > 0 else t
    out = []
    for title, body in blocks(t, 3):
        if not re.match(r"^\d+\.", title.strip()):
            continue
        paras = re.split(r"\n[ \t]*\n", body)
        attrib = paras[-1].strip() if paras else ""
        a = gt_author(attrib) if "\n" not in attrib else None
        if not a:
            GT_AUTHORS[attrib[:40]] = GT_AUTHORS.get(attrib[:40], 0) + 1
            continue
        body2 = "\n\n".join(paras[:-1])
        lines = clean_lines(body2)
        if not lines: continue
        tt = nice_title(title)
        if not tt or ROMAN.match(tt): tt = first_line_title(lines)
        out.append(poem(tt, lines, a, b, {"gt_number": int(re.match(r"\d+", title.strip()).group(0))}))
    return out

def parse_titled(b):
    t = load(b["id"])
    L = t.split("\n")
    out = []
    for want in b["titles"]:
        cands = [i for i, l in enumerate(L) if norm(l) == norm(want) and norm(l) and (is_caps(l) or not is_caps(want))]
        best = None
        for i in cands:
            nxt = [x for x in L[i + 1:i + 16] if x.strip()]
            while nxt and is_caps(nxt[0]): nxt = nxt[1:]          # subtitle lines
            if nxt and nxt[0].strip().startswith("["):              # bracketed editor's note
                k2 = next((q for q, x in enumerate(nxt) if "]" in x), 0); nxt = nxt[k2 + 1:]
            verse = nxt[:6]
            if len(verse) >= 2 and sum(bool(re.search(r"[,;:.!?]['\"’”)]*\s*$", x)) for x in verse) >= 2 and not re.search(r"\s{2,}\d+\s*$", verse[0]):
                best = i  # keep the last occurrence followed by verse (body, not contents)
        if best is None:
            print("  not found:", b["author"], want); continue
        body, blank, j = [], 0, best + 1
        while j < len(L):
            l = L[j]
            if not l.strip():
                blank += 1
                if blank >= 3 and body: break
                body.append(l); j += 1; continue
            if body and blank >= 1 and is_caps(l) and len(re.sub(r"[^A-Za-z]", "", l)) >= 3 and not re.search(r"[a-z]", l) and len([x for x in body if x.strip()]) >= 4:
                break
            if re.match(r"^\s*\[", l) and not [x for x in body if x.strip()]:
                while j < len(L) and "]" not in L[j]: j += 1
                j += 1; blank = 0; continue
            blank = 0; body.append(l); j += 1
        paras = re.split(r"\n[ \t]*\n", "\n".join(body))
        while paras and (is_caps(paras[0]) and "\n" not in paras[0].strip()):
            paras.pop(0)  # subtitle lines
        lines = clean_lines("\n\n".join(paras))
        out.append(poem(nice_title(want), lines, b["author"], b))
    return out

def parse_hopkins(b):
    t = load(b["id"])
    t = t[t.find("_EARLY POEMS_"):t.find("UNFINISHED POEMS")]
    parts = re.split(r"\n_(\d+)\n", t)
    out = []
    for k in range(1, len(parts) - 1, 2):
        num, seg = parts[k], parts[k + 1]
        m = re.match(r"\s*(.*?)_\s*\n", seg, re.S)
        if m and len(m.group(1)) < 200:
            title = m.group(1).strip().split("\n")[0].strip().replace("--", "-"); body = seg[m.end():]
            title = re.sub(r"^\((.*)\)$", r"\1", title)
        else:
            title, body = None, seg
        lines = clean_lines(body)
        if not lines: continue
        tt = title.split(":")[0].strip() if title else first_line_title(lines)
        if tt == "": tt = first_line_title(lines)
        out.append(poem(tt, lines, b["author"], b, {"hopkins_number": int(num)}))
    return out

WS = "https://en.wikisource.org/wiki/"
def ws_url(title):
    import urllib.parse
    return WS + urllib.parse.quote(title.replace(" ", "_"), safe="/;,()'")

def ws_fetch(page):
    import urllib.parse
    os.makedirs(os.path.join(SRC, "ws"), exist_ok=True)
    fn = os.path.join(SRC, "ws", re.sub(r"[^A-Za-z0-9]+", "_", page) + ".json")
    if not os.path.exists(fn):
        u = ("https://en.wikisource.org/w/api.php?action=query&prop=revisions&rvprop=content&rvslots=main&redirects=1&format=json&formatversion=2&titles="
             + urllib.parse.quote(page))
        open(fn, "w").write(urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=60).read().decode())
        time.sleep(0.3)
    d = json.load(open(fn))["query"]["pages"][0]
    return d["title"], d["revisions"][0]["slots"]["main"]["content"]

def ws_text(w):
    m = re.search(r"<poem[^>]*>(.*?)</poem>", w, re.S)
    if m:
        body = m.group(1)
    else:
        body = w[w.find("}}\n", w.find("{{header")) + 3:] if "{{header" in w else w
    body = re.sub(r"<ref[^>]*>.*?</ref>|<ref[^>]*/>", "", body, flags=re.S)
    body = re.sub(r"<br\s*/?>", "", body)
    body = re.sub(r"\[\[Category:[^\]]*\]\]", "", body)
    for _ in range(3):
        body = re.sub(r"\{\{(?:gap|em|nop|clear|dhr|rule|smallrefs|PD-[^}]*|authority control)[^{}]*\}\}", "", body, flags=re.I)
        body = re.sub(r"\{\{(?:sc|smallcaps|uc|larger|smaller|small|x-larger|c|center|right|float right|fine|lang\|[a-z]+)\|([^{}]*)\}\}", r"\1", body, flags=re.I)
    body = re.sub(r"\{\{[^{}]*\}\}", "", body)
    body = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", body)
    body = re.sub(r"'{2,}", "", body)
    body = re.sub(r"<[^>]+>", "", body)
    body = html.unescape(body).replace("&nbsp;", " ")
    return clean_lines(body)

def ws_html(page):
    import urllib.parse
    fn = os.path.join(SRC, "ws", re.sub(r"[^A-Za-z0-9]+", "_", page) + ".html.json")
    if not os.path.exists(fn):
        u = ("https://en.wikisource.org/w/api.php?action=parse&prop=text&redirects=1&format=json&formatversion=2&page=" + urllib.parse.quote(page))
        open(fn, "w").write(urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=60).read().decode())
        time.sleep(0.3)
    d = json.load(open(fn))["parse"]
    return d["title"], d["text"]

def ws_poem_lines(h):
    h = re.sub(r"<(style|script)[^>]*>.*?</\1>", "", h, flags=re.S)
    h = re.sub(r'<span><span class="pagenum.*?</span></span></span>|<span class="pagenum.*?</span></span>', "\x00PB\x00", h, flags=re.S)
    h = re.sub(r'<sup[^>]*class="reference".*?</sup>', "", h, flags=re.S)
    ms = list(re.finditer(r'<div class="poem">(.*?)</div>', h, flags=re.S))
    if not ms:   # plain paragraphs with line breaks
        start = h.find('id="headertemplate"')
        ms = [m for m in re.finditer(r"<p>(.*?)</p>", h, flags=re.S) if "<br" in m.group(1) and m.start() > start]
    if not ms:
        return []
    parts, prev_end = [], None
    for m in ms:
        x = m.group(1).replace("\x00PB\x00", "")
        x = re.sub(r'<span class="wst-gap[^>]*></span>', "    ", x)
        x = re.sub(r"(?:</p>|<br\s*/?>|\s)+$", "", x.strip())
        if parts:
            gap = h[prev_end:m.start()]
            parts.append("\n" if "\x00PB\x00" in gap else "\n\n")   # a page break is not a stanza break
        parts.append(x); prev_end = m.end()
    t = "".join(parts)
    t = re.sub(r"<br\s*/?>\n?", "\n", t)
    t = re.sub(r"</p>\s*", "\n\n", t)
    t = html.unescape(re.sub(r"<[^>]+>", "", t)).replace("\u200b", "").replace("\xa0", " ").replace("\u2003", " ")
    return clean_lines(t)

def parse_wikisource(b):
    out = []
    for page, title in b["pages"]:
        final, h = ws_html(page)
        lines = ws_poem_lines(h)
        if len([l for l in lines if l.strip()]) < 4:
            print("  wikisource page without a poem block:", page); continue
        out.append(poem(title, lines, b["author"], b, {"ws_page": final}))
    return out

PARSERS = {"wikisource": parse_wikisource, "blocks": parse_blocks, "dickinson": parse_dickinson, "golden": parse_golden, "titled": parse_titled, "hopkins": parse_hopkins}

# ---------------- anchors in the HTML edition ----------------
BAD_ID = re.compile(r"linknote|noteref|FNanchor|Footnote|^fn|^note|^pg-header|^pg-footer|^pg-start|^pg-machine|^pg-end")
class HtmlIndex:
    def __init__(self, i):
        s = open(os.path.join(SRC, f"pg{i}-images.html"), encoding="utf-8", errors="replace").read()
        st = s.find('id="pg-start-separator"')
        s = s[st if st > 0 else 0:]
        en = s.find('id="pg-end-separator"')
        s = s[:en] if en > 0 else s
        self.ids, norm_, self.anchors, n = set(), [], [], 0
        for m in re.finditer(r"<[^>]+>|[^<]+", s):
            tok = m.group(0)
            if tok.startswith("<"):
                for a in re.findall(r'\b(?:id|name)="([^"]+)"', tok):
                    self.ids.add(a)
                    if not BAD_ID.search(a): self.anchors.append((n, a))
            else:
                x = norm(html.unescape(tok)); norm_.append(x); n += len(x)
        self.norm = "".join(norm_)
    def locate(self, lines):
        txt = norm(" ".join(l for l in lines if l.strip()))
        for off in (0, 10, 30, 60):
            key = txt[off:off + 50]
            if len(key) < 12: break
            p = self.norm.find(key)
            if p >= 0:
                p -= off
                best = None
                for pos, aid in self.anchors:
                    if pos <= max(p, 0): best = (pos, aid)
                    else: break
                return p, best
        return None, None

# ---------------- selection ----------------
def matches(p, key):
    k = norm(key)
    return k and (norm(p["title"]).startswith(k) or norm(p["first_line"]).startswith(k) or norm(p.get("raw_title", "")).startswith(k)
                  or (len(k) > 8 and k in norm(p["title"])))

MISSED = []
JUNK = re.compile(r"\b(preface|contents|introduction|notes?|bibliography|index|transcriber|chronolog|edited|dedication|glossary|appendix|errata|advertisement|acknowledg|life of|footnotes?|copyright|illustrations|biographical|scene)\b", re.I)
def select(b, poems):
    chosen, used = [], set()
    maxf = b.get("maxl_featured", max(b.get("maxl", 60), 120))
    skip = [norm(s) for s in b.get("skip", [])]
    def ok(p, lim):
        if p["author"] in ("SHAKESPEARE", "WORDSWORTH"): return False
        if JUNK.search(p["title"]) or JUNK.search(p.get("raw_title", "")): return False
        ls = [len(l.strip()) for l in p["lines_text"] if l.strip()]
        if not ls or sorted(ls)[len(ls) // 2] > 68 or max(ls) > 115: return False   # prose, not verse
        if any(s and (s in norm(p["title"]) or s in norm(p.get("raw_title", "")) or s in norm(p["author"])) for s in skip): return False
        return 4 <= p["n"] <= lim
    for key in b.get("featured", []) + [nice_title(x) for x in b.get("titles", [])] + [t for _, t in b.get("pages", [])]:
        for k, p in enumerate(poems):
            if k not in used and matches(p, key) and ok(p, maxf):
                q = dict(p, featured=True)
                if b["mode"] == "golden" and not norm(p["title"]).startswith(norm(key)):
                    q["title"] = first_line_title(p["lines_text"])   # anthology editor's title: use the first line
                chosen.append(q); used.add(k); break
        else:
            MISSED.append((b["id"], key))
    rest = [k for k, p in enumerate(poems) if k not in used and ok(p, b.get("maxl", 60)) and b["mode"] not in ("titled", "wikisource")]
    need = b["quota"] - len(chosen)
    if need > 0 and rest:
        step = len(rest) / need
        for j in range(min(need, len(rest))):
            k = rest[int(j * step)]
            q = dict(poems[k], featured=False)
            if b["mode"] == "golden": q["title"] = first_line_title(q["lines_text"])
            chosen.append(q); used.add(k)
    return chosen[:b["quota"]] if len(chosen) > b["quota"] else chosen

OPENERS = ["The Road Not Taken", "Hope is the thing with feathers", "Ode to a Nightingale", "The Tyger", "I wandered lonely as a cloud",
           "O Captain! My Captain", "Ozymandias", "Stopping by Woods on a Snowy Evening", "Kubla Khan", "Because I could not stop for Death",
           "Dover Beach", "Remember", "God's Grandeur", "Annabel Lee"]

def order(items):
    """Openers first, then interleave authors in proportion so each author's poems spread across the year."""
    first = []
    for o in OPENERS:
        for p in items:
            if p not in first and (norm(p["title"]).startswith(norm(o)) or norm(p["first_line"]).startswith(norm(o))):
                first.append(p); break
    rest = [p for p in items if p not in first]
    queues = {}
    for p in rest:
        queues.setdefault(p["author"], []).append(p)
    for a in queues:  # featured poems first within each author
        queues[a].sort(key=lambda p: not p.get("featured"))
    n = len(rest); idx = {a: 0 for a in queues}; seq, last = [], first[-1]["author"] if first else None
    for d in range(n):
        cand = sorted((a for a in queues if idx[a] < len(queues[a])),
                      key=lambda a: -(len(queues[a]) * (d + 1) / n - idx[a]))
        pick = next((a for a in cand if a != last), cand[0])
        seq.append(queues[pick][idx[pick]]); idx[pick] += 1; last = pick
    return first + seq

GENERIC = {"sonnet", "sonnets", "song", "songs", "poems", "lines", "stanzas", "ode", "fragment"}
TITLE_FIX = {"Lines Written A Few Miles Above Tintern Abbey, on Revisiting the Banks of the Wye During A Tour, July 13, 1798":
             "Lines Written a Few Miles above Tintern Abbey","Stopping by Woods on Snowy Evening": "Stopping by Woods on a Snowy Evening"}  # the 1923 contents page reads "on a Snowy Evening"

def build():
    allp, report = [], []
    seen = set()
    for b in BOOKS:
        poems = PARSERS[b["mode"]](b)
        chosen = select(b, poems)
        hidx = HtmlIndex(b["id"]) if b.get("id") else None
        kept = []
        for p in chosen:
            key = norm(p["first_line"])[:14]
            if key in seen or norm(p["title"]) in seen:
                continue
            if p["title"].lower() in GENERIC: p["title"] = first_line_title(p["lines_text"])
            p["title"] = TITLE_FIX.get(p["title"], p["title"])
            seen.add(norm(p["title"]))
            if b["mode"] == "wikisource":
                p.update(book_id=None, book=b["book"], published=f"{b['book']} ({b['year']})", text_found_in_html=len(p["lines_text"]) >= 4,
                         anchor=None, anchor_gap_letters=None, anchor_precise=True, link=ws_url(p["ws_page"]))
                seen.add(key); kept.append(p); continue
            p_pos, anc = hidx.locate(p["lines_text"])
            p["book_id"] = b["id"]; p["book"] = b["book"]; p["published"] = p.get("edition") or f"{b['book']} ({b['year']})"
            p["text_found_in_html"] = p_pos is not None
            p["anchor"] = anc[1] if anc else None
            p["anchor_gap_letters"] = (p_pos - anc[0]) if (anc and p_pos is not None) else None
            title_len = len(norm(p["title"])) + len(norm(p.get("raw_title", ""))) + 400
            p["anchor_precise"] = bool(anc and p_pos is not None and (p_pos - anc[0]) <= title_len + 400)
            seen.add(key); kept.append(p)
        report.append((b.get("id") or "wikisource", b["author"] or "Golden Treasury", len(poems), len(kept), b["quota"]))
        allp += kept
    # trim to 365: drop non-featured fill from the authors with the most poems first
    while len(allp) > TOTAL:
        counts = {}
        for p in allp: counts[p["author"]] = counts.get(p["author"], 0) + 1
        cands = [p for p in allp if not p.get("featured") and p.get("gt_number")]   # anthology fill goes first
        if not cands: cands = [p for p in allp if not p.get("featured")]
        if not cands: cands = allp
        victim = max(cands, key=lambda p: (counts[p["author"]], allp.index(p)))
        allp.remove(victim)
    days = order(allp)
    out = []
    for i, p in enumerate(days, 1):
        link = p.get("link") or (PGH.format(id=p["book_id"]) + ("#" + p["anchor"] if p["anchor_precise"] else ""))
        e = {"day": i, "title": p["title"], "author": p["author"], "first_line": p["first_line"], "published": p["published"],
             "lines": p["n"], "text": "\n".join(p["lines_text"]), "full_text_link": link,
             "link_lands_on_poem": p["anchor_precise"],
             "verified": p["text_found_in_html"] and len(p["lines_text"]) >= 4,
             "source_notes": (f"Text from the linked page ({p['book']}, {p['published']})." if p.get("ws_page") else
                              f"Text parsed from the linked edition ({p['book']}); opening lines found on the linked page"
                             + (f", link anchor #{p['anchor']} sits just before the poem." if p["anchor_precise"] else "; no anchor right before the poem, so the link opens the book (search for the first line)."))}
        if p.get("subtitle"): e["subtitle"] = p["subtitle"]
        if p.get("editors_title"): e["editors_title"] = p["editors_title"]
        out.append(e)
    meta = {"path": "poems", "title": "Poem a Day", "count": len(out), "generated": date.today().isoformat(),
            "plan": "365 public-domain poems, one a day. Openers first, then poets interleaved so each one's work spreads across the year.",
            "rules": "Every poem comes from an edition published before 1931. Emily Dickinson texts come only from the 1890, 1891 and 1896 editions.",
            "sources": sorted({PG.format(id=b['id']) for b in BOOKS if b.get('id')}) + sorted({ws_url(p) for b in BOOKS for p, _ in b.get('pages', [])})}
    os.makedirs(os.path.join(HERE, "plans"), exist_ok=True)
    json.dump({"meta": meta, "days": out}, open(os.path.join(HERE, "plans", "poems.json"), "w"), indent=1, ensure_ascii=False)
    for r in report: print(*r)
    print("total", len(out), "verified", sum(e["verified"] for e in out), "precise links", sum(e["link_lands_on_poem"] for e in out))
    if MISSED: print("featured not matched:", MISSED)
    if GT_AUTHORS: print("unmapped GT attributions:", sorted(GT_AUTHORS.items(), key=lambda x: -x[1])[:30])

if __name__ == "__main__":
    if "--fetch" in sys.argv: fetch()
    build()
