#!/usr/bin/env python3
"""Nibble & Sip weekly scraper (multi-source).

Reads data/sources.json and pulls real posts/recipes from every enabled source:

  instagram_reel     one public reel/post (yt-dlp metadata, no login)
  instagram_profile  a creator's whole profile: needs an Instagram login, so it
                     is skipped (kept for a future logged-in browser option)
  tiktok_profile     a creator's public TikTok profile (yt-dlp, no login)
  youtube_channel    a creator's public YouTube channel / Shorts tab (yt-dlp)
  website_category   a recipe blog category listing (paged), Recipe JSON-LD
  website_sitemap    a recipe blog post sitemap filtered by keywords, Recipe JSON-LD

Websites: robots.txt is respected, requests are spaced out, nothing behind a
login or paywall is read. Every item keeps its own source URL and credit.

State lives in data/store.json (everything the scraper knows). The app reads
data/feed.json (slim card index) and data/items/<id>.json (detail on open).
Static Recipe pages for Umami go to r/<id>.html. Idempotent: known items are
not fetched again (use --refresh to rebuild items from source).

Run from the repo root (the venv has faster-whisper for video recipes):
    /workspace/.nvenv/bin/python docs/nibble/scripts/scrape.py
"""
import argparse
import datetime as dt
import difflib
import html as htmllib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import time as _time
import urllib.parse
import urllib.request
import urllib.robotparser

APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
SOURCES = os.path.join(APP, "data", "sources.json")
STORE = os.path.join(APP, "data", "store.json")
FEED = os.path.join(APP, "data", "feed.json")
ITEMS_DIR = os.path.join(APP, "data", "items")
THUMBS = os.path.join(APP, "thumbs")
BOT = "NibbleSip/1.0 (personal recipe reader; +https://chanelluuhai.github.io/personal-apps/nibble/)"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36 " + BOT
THUMB_W = 400

try:
    from PIL import Image
except ImportError:
    Image = None


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def now_iso():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def canonical(url):
    """Strip tracking params; normalise Instagram to https://www.instagram.com/reel|p/<code>/"""
    m = re.search(r"instagram\.com/(?:[^/]+/)?(reel|reels|p|tv)/([A-Za-z0-9_-]+)", url)
    if not m:
        return url.split("?")[0].split("#")[0]
    kind = "reel" if m.group(1) in ("reel", "reels", "tv") else "p"
    return f"https://www.instagram.com/{kind}/{m.group(2)}/"


def shortcode(url):
    return canonical(url).rstrip("/").rsplit("/", 1)[-1]


def ytdlp_bin():
    return shutil.which("yt-dlp") or os.path.expanduser("~/.local/bin/yt-dlp")


def ytdlp_json(args, timeout=300):
    r = subprocess.run([ytdlp_bin(), "--no-warnings", *args], capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0 or not r.stdout.strip():
        raise RuntimeError(((r.stderr or "no output").strip().splitlines() or ["no output"])[-1][:300])
    return json.loads(r.stdout.strip().splitlines()[-1])


def fetch_meta(url):
    return ytdlp_json(["--skip-download", "--dump-json", "--no-playlist", url], timeout=120)


# ---------- polite web fetching ----------
_robots, _last = {}, {}


def allowed(url):
    p = urllib.parse.urlparse(url)
    base = f"{p.scheme}://{p.netloc}"
    if base not in _robots:
        rp = urllib.robotparser.RobotFileParser()
        try:
            req = urllib.request.Request(base + "/robots.txt", headers={"User-Agent": UA})
            rp.parse(urllib.request.urlopen(req, timeout=20).read().decode("utf-8", "replace").splitlines())
        except Exception:  # noqa: BLE001  (no robots.txt = allowed)
            rp.parse([])
        _robots[base] = rp
    return _robots[base].can_fetch("NibbleSip", url) and _robots[base].can_fetch("*", url)


def get_url(url, delay=1.2):
    if not allowed(url):
        raise PermissionError(f"robots.txt disallows {url}")
    host = urllib.parse.urlparse(url).netloc
    wait = delay - (_time.time() - _last.get(host, 0))
    if wait > 0:
        _time.sleep(wait)
    _last[host] = _time.time()
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en"})
    return urllib.request.urlopen(req, timeout=40).read().decode("utf-8", "replace")


def og_image(page_url):
    html = get_url(page_url)
    m = re.search(r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"', html)
    return m.group(1).replace("&amp;", "&") if m else None


# ---------- thumbnails ----------
def download_thumb(url, iid):
    """Web-sized photo in the repo (WebP, 400px wide) + its average colour for the placeholder."""
    os.makedirs(THUMBS, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Referer": "https://www.tiktok.com/" if "tiktok" in url else url})
    data = urllib.request.urlopen(req, timeout=60).read()
    if Image is None:
        path = f"thumbs/{iid}.jpg"
        open(os.path.join(APP, path), "wb").write(data)
        return path, None, None, None
    im = Image.open(io.BytesIO(data)).convert("RGB")
    if im.width > THUMB_W:
        im = im.resize((THUMB_W, round(im.height * THUMB_W / im.width)), Image.LANCZOS)
    if im.height > im.width * 1.8:  # very tall covers: keep a 9:16-ish crop
        h = round(im.width * 1.78)
        top = (im.height - h) // 2
        im = im.crop((0, top, im.width, top + h))
    path = f"thumbs/{iid}.webp"
    im.save(os.path.join(APP, path), "WEBP", quality=72, method=6)
    return path, im.width, im.height, avg_color(im)


def avg_color(im):
    c = im.resize((1, 1), Image.BILINEAR).getpixel((0, 0))
    return "#%02x%02x%02x" % c[:3]


def thumb_color(path):
    if Image is None or not path or not os.path.exists(os.path.join(APP, path)):
        return None
    return avg_color(Image.open(os.path.join(APP, path)).convert("RGB"))


# ---------- caption parsing (only ever reads the real caption) ----------
EMOJI = re.compile("[\U0001F000-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF\uFE0F\u200D\u2190-\u21FF\u2300-\u23FF]+")
BULLET = re.compile("^\\s*(?:[*\u2022\\-\u2013\u00b7\u25aa\u25cf\u2705\u2714]|\\d+[.)]|[\U0001F300-\U0001FAFF]\uFE0F?)\\s*")
HEAD_ING = re.compile(r"^\s*(ingredients?|you'?ll need|what you need)\s*:?\s*$", re.I)
HEAD_STEP = re.compile(r"^\s*(how to make|directions|instructions|method|steps|how to)\s*:?\s*$", re.I)
HEAD_WHY = re.compile(r"^\s*why (this|it) (meal )?works\s*:?\s*$", re.I)


def clean(s):
    s = EMOJI.sub("", s)
    s = re.sub(r"#\w+", "", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip(" -–—:•*·")


GENERIC = re.compile(r"^(baby|toddler|kid|easy|quick)?\s*(dessert|snack|lunch|dinner|breakfast|meal|food)?\s*(idea|ideas|recipe|recipes)$", re.I)
STARTS_EMOJI = re.compile("^\\s*[\U0001F000-\U0001FAFF\u2600-\u27BF]")


def nice(s):
    s = s.strip()
    return s[:1].upper() + s[1:]


def title_from(caption, fallback):
    lines = [l for l in caption.splitlines() if l.strip()]
    for l in lines:  # "Today's lunch: carrot mac & cheese + ..."
        m = re.search(r"today[’']?s (?:lunch|dinner|breakfast|snack|meal)\s*:\s*(.+)", l, re.I)
        if m:
            return nice(clean(m.group(1)))[:90]
    for l in lines[:12]:  # a short line that opens with an emoji is the recipe name
        c = clean(l)
        if STARTS_EMOJI.match(l) and c and len(c.split()) <= 8 and not re.search(r"[.!?]$", c):
            return nice(c)[:90]
    for i, l in enumerate(lines[:3]):  # "Baby dessert idea" + "Korean rice cake — no added sugar"
        if GENERIC.match(clean(l)) and i + 1 < len(lines):
            nxt = re.split(r"\s[—–-]\s|[.!:]", clean(lines[i + 1]))[0]
            if 1 <= len(nxt.split()) <= 8:
                return nice(nxt)[:90]
    for l in lines[:4]:  # "Hi I'm Min..." then "This creamy sardine hummus is perfect ..."
        m = re.search(r"\bthis ([a-z][\w\s&’'-]{3,60}?) (?:is|are)\b", l, re.I)
        if m and re.match(r"\s*\W*\s*(hi|hey|hello)\b", lines[0], re.I):
            return nice(clean(m.group(1)))[:90]
    for l in lines:
        c = clean(l)
        if not c or re.match(r"(hi|hey|hello)\b", c, re.I) or re.match(r"day \d+ of", c, re.I):
            continue
        return nice(re.split(r"(?<=[.!?])\s", c)[0].rstrip(".!"))[:90]
    return fallback


def sections(caption):
    ing, steps, notes, cur = [], [], [], None
    for raw in caption.splitlines():
        l = raw.strip()
        if not l:
            continue
        if HEAD_ING.match(clean(l) or l):
            cur = ing; continue
        if HEAD_STEP.match(clean(l) or l):
            cur = steps; continue
        if HEAD_WHY.match(clean(l) or l):
            cur = notes; continue
        if cur is None:
            continue
        if BULLET.match(l) or (cur is steps and len(steps) < 15 and not l.startswith("#")):
            item = clean(BULLET.sub("", l))
            if item and not item.lower().startswith(("that", "save this", "follow", "want ")):
                cur.append(item)
            elif not item:
                continue
            else:
                cur = None
        else:
            cur = None
    return ing, steps, notes


def summary(caption, title):
    skip = re.compile(r"^(hi|hey|hello)\b|^day \d+ of|^if you|^today[’']?s (lunch|dinner|breakfast|snack|meal)", re.I)
    paras = []
    for p in re.split(r"\n\s*\n", caption):
        keep = [clean(l) for l in p.splitlines()]
        keep = [l for l in keep if l and not skip.match(l) and not GENERIC.match(l)
                and l.lower().rstrip(".!") != title.lower()]
        if keep:
            paras.append(" ".join(keep))
    for p in paras:
        if p.lower().startswith(title.lower()):  # "Korean rice cake — no added sugar" -> "No added sugar"
            p = nice(p[len(title):].lstrip(" —–-:,"))
        if len(p) > 25:
            s = " ".join(re.split(r"(?<=[.!?])\s", p)[:2])
            return s[:220] + ("…" if len(s) > 220 else "")
    return ""


# ---------- linked recipe pages (schema.org Recipe JSON-LD) ----------
def iso_minutes(v):
    if not v or not isinstance(v, str):
        return None
    m = re.match(r"P(?:\d+D)?T?(?:(\d+)H)?(?:(\d+)M)?", v.strip(), re.I)
    if not m or not (m.group(1) or m.group(2)):
        return None
    return int(m.group(1) or 0) * 60 + int(m.group(2) or 0)


def _find_recipe(node):
    if isinstance(node, list):
        for n in node:
            r = _find_recipe(n)
            if r:
                return r
    elif isinstance(node, dict):
        t = node.get("@type")
        if t == "Recipe" or (isinstance(t, list) and "Recipe" in t):
            return node
        for k in ("@graph", "mainEntity", "itemListElement"):
            if k in node:
                r = _find_recipe(node[k])
                if r:
                    return r
    return None


def _steps(ins):
    out = []
    if isinstance(ins, str):
        return [clean(x) for x in re.split(r"\n+", ins) if clean(x)]
    for x in ins or []:
        if isinstance(x, str):
            out.append(clean(x))
        elif isinstance(x, dict):
            if x.get("@type") == "HowToSection":
                out += _steps(x.get("itemListElement"))
            elif x.get("text"):
                out.append(clean(re.sub(r"<[^>]+>", " ", x["text"])))
    return [o for o in out if o]


def fetch_recipe_page(url):
    """Return structured recipe data from a linked page, or None. Only reads what the page says."""
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en"})
    html = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")
    for block in re.findall(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', html, re.S | re.I):
        try:
            data = json.loads(block.strip())
        except ValueError:
            continue
        r = _find_recipe(data)
        if not r:
            continue
        img = r.get("image")
        if isinstance(img, list):
            img = img[0] if img else None
        if isinstance(img, dict):
            img = img.get("url")
        y = r.get("recipeYield")
        if isinstance(y, list):
            y = y[0] if y else None
        return {
            "ingredients": [clean(i) for i in r.get("recipeIngredient") or [] if clean(i)],
            "steps": _steps(r.get("recipeInstructions")),
            "minutes": iso_minutes(r.get("totalTime")) or iso_minutes(r.get("cookTime")) or iso_minutes(r.get("prepTime")),
            "yield": str(y) if y else None,
            "image": img,
        }
    return None


# ---------- time / prep signals (only from words actually in the caption) ----------
MIN_RE = re.compile(r"(?<![\w.])(\d{1,3})(?:\s*(?:-|–|to)\s*(\d{1,3}))?\s*(?:min|mins|minute|minutes)\b", re.I)
HR_RE = re.compile(r"(?<![\w.])(\d{1,2}(?:\.\d)?)\s*(?:hr|hrs|hour|hours)\b", re.I)
QUICK_KW = ["quick", "5 minute", "5-minute", "10 minute", "10-minute", "no bake", "no-bake", "no baking",
            "no cook", "no-cook", "5 ingredient", "5-ingredient", "3 ingredient", "3-ingredient"]
LONG_KW = ["slow cooker", "crockpot", "crock pot", "overnight", "roast for", "simmer for an hour"]
PREP_KW = ["meal prep", "mealprep", "meal-prep", "batch", "freeze", "freezer", "frozen portions", "make ahead",
           "make-ahead", "prep ahead", "lunchbox", "lunch box", "for the week", "all week", "keeps for",
           "lasts for", "store in the fridge", "storage"]


def has_kw(t, kws):
    return [k for k in kws if re.search(r"(?<![a-z])" + re.escape(k) + r"(?![a-z])", t)]


def prep_signals(text):
    t = text.lower()
    mins = []
    for a, b in MIN_RE.findall(t):
        mins.append(int(b or a))
    for h in HR_RE.findall(t):
        mins.append(round(float(h) * 60))
    minutes = max(mins) if mins else None
    q, l, p = has_kw(t, QUICK_KW), has_kw(t, LONG_KW), has_kw(t, PREP_KW)
    if minutes is not None:
        time = "quick" if minutes <= 20 else "long"
        why = f"says {minutes} min"
    elif l:
        time, why = "long", l[0]
    elif q:
        time, why = "quick", q[0]
    else:
        time, why = "unknown", ""
    return {"time": time, "minutes": minutes, "time_basis": why, "mealPrep": bool(p), "mealPrep_basis": p[:3]}


TAGS = {
    "breakfast": ["breakfast", "oatmeal", "oats", "waffle"],
    "lunch": ["lunch"],
    "dinner": ["dinner", "supper"],
    "snack": ["snack", "snacks", "dessert", "rice cake", "bites"],
    "sweet": ["dessert", "sweet", "cake", "muffin", "cookie"],
    "finger food": ["finger food", "hold", "pancake", "jeon", "bites", "nugget", "fritter", "dip"],
    "pasta & noodles": ["pasta", "noodle", "udon", "mac", "macaroni", "spaghetti", "rotini", "orzo"],
    "seafood": ["shrimp", "fish", "salmon", "sardine", "tuna", "cod"],
    "veggies": ["broccoli", "spinach", "zucchini", "carrot", "veggie", "vegetable", "pea", "avocado"],
    "one pot": ["rice cooker", "one pot", "one-pot", "sheet pan"],
    "dip & spread": ["hummus", "spread", "dip for"],
}


def auto_tags(text):
    t = text.lower()
    out = []
    for tag, kws in TAGS.items():
        if any(re.search(r"(?<![a-z])" + re.escape(k) + r"(?![a-z])", t) for k in kws):
            out.append(tag)
    return out


CATEGORY_ORDER = [("pasta & noodles", "pasta"), ("finger food", "finger"), ("sweet", "sweet"), ("snack", "sweet")]


def category(tags):
    for tag, cat in CATEGORY_ORDER:
        if tag in tags:
            return cat
    return "meal"


def links_in(caption):
    """Recipe/blog links the creator put in the caption (real URLs only)."""
    return sorted(set(u.rstrip(".,)") for u in re.findall(r"https?://[^\s\"'<>]+", caption)))



# ---------- captions without line breaks (TikTok flattens them) ----------
EMO_RUN = re.compile("[\U0001F000-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF\u2300-\u23FF]"
                     "[\uFE0F\u200D\U0001F3FB-\U0001F3FF\U0001F000-\U0001FAFF\u2600-\u27BF]*")
ING_MARK = re.compile(r"\b(ingredients?|you(?:'|’)?ll need|what you need)\b\s*(?::|(?=(?:\s*[A-Z][\w ]{0,24})?\s*[•*▪●◦]))", re.I)
STEP_MARK = re.compile(r"\b(how to make(?: it| them| this)?|directions|instructions|method|steps|to make)\b\s*:", re.I)
STEP_MARK_SOFT = re.compile(r"\b(how to make(?: it| them| this)?|directions|instructions|method|how to(?=\s+(?-i:[A-Z])))\b\s*:?", re.I)
VERB_START = re.compile(r"\s(?=(?:Mash|Mix|Whisk|Add|Combine|Cook|Bake|Preheat|Blend|Stir|Heat|Place|Pour|In a|Steam|Boil|Melt|Cut|Slice|Spread|Roll|Shape|Fold|Grate|Microwave|Simmer|Saut[eé]|Season|Toss|Beat|Spoon|Scoop|Line|Grease|Freeze)\b)")
BUL_CH = "•*▪●◦"
PROMO = re.compile(r"\b(bio|follow|save (this|it)|link|code|munchmind|comment|dm me|subscribe|giveaway|tag a|shop|discount|ebook|e-book|guide)\b", re.I)


def pseudo_lines(caption):
    """Turn a one-line caption into lines at emoji breaks so title/summary rules can work."""
    c = caption or ""
    if "\n" in c.strip() or len(c) < 40:
        return c
    return EMO_RUN.sub(lambda m: m.group(0) + "\n", c)


def strip_tags_tail(t):
    return re.sub(r"(?:\s*#[\w\u00C0-\uFFFF]+)+\s*$", "", t)


def _first_clause(s):
    s = EMO_RUN.split(s)[0]
    return s


def inline_sections(caption):
    """Ingredients/steps from a caption that has no line breaks. Only the caption's own words."""
    t = strip_tags_tail(re.sub(r"\s+", " ", caption or ""))
    mi = ING_MARK.search(t)
    bullets = [i for i, ch in enumerate(t) if ch in BUL_CH]
    if mi:
        start = mi.end()
    elif len(bullets) >= 3:
        start = bullets[0]
    else:
        return [], []
    ms = STEP_MARK.search(t, start) or STEP_MARK_SOFT.search(t, start)
    ing_text = t[start: ms.start() if ms else len(t)]
    ing_text = ing_text.replace("⸻", " ")
    tail = ""
    if not ms:  # steps may follow the list as plain sentences ("... 2 tbsp milk Mash the banana, ...")
        mv = VERB_START.search(ing_text)
        if mv:
            ing_text, tail = ing_text[:mv.start()], ing_text[mv.start():]
    if any(ch in ing_text for ch in BUL_CH):
        parts = re.split("[" + re.escape(BUL_CH) + "]", ing_text)
    elif mi and len(EMO_RUN.findall(ing_text)) >= 3:
        parts = EMO_RUN.split(ing_text)
    elif mi and ing_text.count(",") >= 2:
        parts = re.split(r"(?<=[.!?])\s", ing_text, maxsplit=1)[0].split(",")
    else:
        parts = []
    ing = []
    for i, p in enumerate(parts):
        p = _first_clause(p) if (i == len(parts) - 1 and not ms) else p
        c = clean(p)
        if not c or len(c) > 140 or PROMO.search(c):
            continue
        ing.append(c)
    steps = []
    if ms or tail:
        st = t[ms.end():] if ms else tail
        head = EMO_RUN.split(st)[0]
        if len(head) >= 15:
            st = head
        st = re.split(r"\s#\w", st)[0]
        if "→" in st or "->" in st:
            chunks = re.split(r"\s*(?:→|->)\s*", st)
        elif re.search(r"(?:^|\s)1[.)]\s", st):
            chunks = re.split(r"(?:^|\s)\d{1,2}[.)]\s", st)
        else:
            chunks = re.split(r"(?<=[.!?])\s+", st)
        for ch in chunks:
            c = clean(ch)
            if not c or PROMO.search(c) or len(c) < 4:
                continue
            steps.append(nice(c))
            if len(steps) >= 15:
                break
    return ing, steps


COOKY = re.compile(r"\b(mix|stir|blend|whisk|mash|microwave|bake|cook|boil|steam|simmer|roast|fry|saut[eé]|toast|grill|heat|freeze|pour|fold|knead|puree|purée|shape|flatten|spread|combine|add|brown|season|roll|wrap|fill|layer|top|cut|slice|grate|preheat|serve)\b", re.I)


def recipe_from_caption(caption):
    ing, steps, notes = sections(caption or "")
    if not (ing or steps) and caption and "\n" not in caption.strip():
        ing, steps = inline_sections(caption)
        if food_count(" ".join(ing)) < 2:  # a bullet list that isn't food (prices, toys, tips)
            ing = []
        if not any(COOKY.search(x) for x in steps):
            steps = []
        if not ing and steps and food_count(" ".join(steps)) < 2:
            steps = []
    return ing, steps, notes


DAY_RE = re.compile(r"^(day|week)\s*\d+\b", re.I)


SKIP_T = re.compile(r"^(full recipe|recipe (below|in)|no\s|just\s|comment|follow|save|tag|share|link|dm|pov|hi|hey|hello|if you|here[’']?s|ad\b|sponsored|part \d)", re.I)


ING_CUT = re.compile(r"\s+\b[Ii]ngredients?\s*(?=[:•*▪●]|\d)")


def _shorten(t):
    t = ING_CUT.split(t)[0].strip(" -–—:")
    if len(t) > 60:
        head = re.split(r"\s[—–-]\s|[:;]\s|…", t)[0].strip()
        if len(head.split()) >= 3:
            t = head
    if len(t) > 80:
        t = t[:78].rsplit(" ", 1)[0] + "…"
    return t


def social_title(caption, fallback):
    cap = caption or ""
    pl = pseudo_lines(cap)
    lines = []
    for l in (clean(x) for x in pl.splitlines()):
        if not l:
            continue
        if lines and not re.search(r"[.!?]$", lines[-1]) and (l[:1].islower() or re.search(r"\b(a|an|the|quick|easy|simple|super|just|with|and|of|for|my|your|made|\d+)$", lines[-1], re.I)):
            lines[-1] += " " + l  # an emoji in the middle of a sentence is not a line break
        else:
            lines.append(l)
    for i, l in enumerate(lines[:3]):  # "Day 16 of 20 toddler lunch ideas" + "cheesy broccoli bites"
        if DAY_RE.match(l) and i + 1 < len(lines):
            nxt = re.split(r"\s[—–-]\s|[.!:]|\b[Ii]ngredients?\b", lines[i + 1])[0].strip()
            if 1 <= len(nxt.split()) <= 9 and not any(ch in nxt for ch in BUL_CH):
                return nice(nxt)[:90]
    if "\n" in cap.strip():  # real line breaks (Instagram): the original rules work well
        return _shorten(title_from(pl, fallback)) or fallback
    cands, days = [], []
    for l in lines[:6]:
        l = ING_CUT.split(l)[0]
        for first in re.split(r"(?<=[.!?])\s", l)[:3]:
            first = first.strip(" -–—:").rstrip(".!")
            mc = re.match(r"^comment\s+[“\"']?([A-Za-z][\w &'-]{2,30}?)[”\"']?(?:\s+(?:for|and|to|below|if)\b|$)", first, re.I)
            if mc and not cands:  # "Comment “waffles” for the recipe" names the dish
                cands.append((nice(mc.group(1).strip()), True))
                continue
            if first and DAY_RE.match(first):
                days.append(first)
                continue
            if (not first or SKIP_T.match(first) or any(ch in first for ch in BUL_CH) or first.startswith(("@", "("))
                    or PROMO.search(first) or first.lower().strip(" :") in ("how to make", "how to", "recipe", "ingredients", "directions")):
                continue
            foodish = bool(food_count(first) or DISH.search(first))
            if len(first.split()) < 3 and not foodish:
                continue
            cands.append((first, foodish))
    pick = next((c for c, f in cands[:3] if f), None) or (cands[0][0] if cands else None) or (days[0] if days else None)
    if not pick:
        pick = title_from(pl, fallback)
    return nice(_shorten(pick)) or fallback


FOOD_RE = None
DISH = re.compile(r"\b(ate today|eats? in a day|what my .{1,20} eats?|purees?|purées?|risotto|solids|iron[- ]rich|recipes?|ingredients?|lunch(es)?|dinners?|breakfasts?|snacks?|meals?|muffins?|pancakes?|waffles?|bites|cakes?|cupcakes?|"
                  r"cookies?|soups?|bowls?|toast|puree|purée|smoothies?|fritters?|nuggets?|desserts?|sandwich(es)?|quesadillas?|"
                  r"oatmeal|porridge|pudding|pizza|tacos?|wraps?|sauce|dips?|salad|curry|stew|baby[- ]led weaning|blw|finger foods?|"
                  r"bake[ds]?|cook(ed|ing)?|tartlets?|bars|balls|patties|jeon|pancake|omelette?|frittata|dumplings?|bun|buns)\b", re.I)
LIFESTYLE = re.compile(r"\b(grwm|get ready with me|skincare|bath|routine|outfit|giveaway|day in (my|the) life|pacifier|potty|"
                       r"nursery|stroller|vlog|sleep training|weaned off|ivf|fertili[sz]ation|infertility|embryo|transfer day|work trip|"
                       r"park strolls?|museum|destination series|high ?chair|teething|bibs?|organi[sz]e|laundry|playroom|play ?kitchen|toys?|"
                       r"gift ideas?|costume|unbox\w*|cleaning ?tips|clean ?with ?me|bought in|what i bought|stocking|crayons?|weather was)\b", re.I)


def food_count(text):
    global FOOD_RE
    if FOOD_RE is None:
        import video_recipe as _vr
        FOOD_RE = re.compile(r"(?<![a-z])(" + "|".join(re.escape(f) for f in _vr.FOODS if f not in ("water", "salt", "pepper", "formula", "stock")) + r")(?![a-z])", re.I)
    return len({m.lower() for m in FOOD_RE.findall(text)})


def is_food_post(caption, has_recipe):
    if has_recipe:
        return True
    t = re.sub(r"#[\w]+", " ", caption or "")
    foods, dishes = food_count(t), len({d[0].lower() if isinstance(d, tuple) else d.lower() for d in DISH.findall(t)})
    if LIFESTYLE.search(caption or "") and foods < 3:
        return False
    if foods + dishes >= 1:
        return True
    tags = " ".join(re.findall(r"#(\w+)", caption or "")).lower()
    return len(t.strip()) < 60 and bool(re.search(r"food|meal|recipe|snack|lunch|dinner|breakfast|puree", tags))


# ---------- website recipes (schema.org Recipe JSON-LD) ----------
def _parens(s):
    s = re.sub(r"\(\(+", "(", s)
    s = re.sub(r"\)\)+", ")", s)
    return re.sub(r"\(\s*\)", "", s).strip()


def cleanh(s):
    return _parens(clean(htmllib.unescape(re.sub(r"<[^>]+>", " ", str(s or "")))))


def _steps_h(ins):
    out = []
    if isinstance(ins, str):
        return [cleanh(x) for x in re.split(r"\n+|<br\s*/?>|</p>", ins) if cleanh(x)]
    if isinstance(ins, dict):
        ins = [ins]
    for x in ins or []:
        if isinstance(x, str):
            out.append(cleanh(x))
        elif isinstance(x, dict):
            if x.get("@type") == "HowToSection" or "itemListElement" in x:
                out += _steps_h(x.get("itemListElement"))
            elif x.get("text") or x.get("name"):
                out.append(cleanh(x.get("text") or x.get("name")))
    return [o for o in out if o]


def _first(v):
    if isinstance(v, list):
        v = v[0] if v else None
    if isinstance(v, dict):
        v = v.get("url") or v.get("name") or v.get("@id")
    return v


def _listish(v):
    if not v:
        return []
    if isinstance(v, str):
        return [x.strip() for x in v.split(",") if x.strip()]
    return [str(_first(x) if isinstance(x, dict) else x).strip() for x in v if x]


def fetch_recipe(url):
    """Structured recipe from a public page's Recipe JSON-LD, or None. Reads only what the page states."""
    html = get_url(url)
    for block in re.findall(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', html, re.S | re.I):
        try:
            data = json.loads(block.strip())
        except ValueError:
            continue
        r = _find_recipe(data)
        if not r:
            continue
        img = _first(r.get("image"))
        if not img:
            m = re.search(r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"', html)
            img = m.group(1).replace("&amp;", "&") if m else None
        author = r.get("author")
        if isinstance(author, list):
            author = author[0] if author else None
        if isinstance(author, dict):
            author = author.get("name")
        mins = iso_minutes(r.get("totalTime"))
        if mins is None and (iso_minutes(r.get("prepTime")) or iso_minutes(r.get("cookTime"))):
            mins = (iso_minutes(r.get("prepTime")) or 0) + (iso_minutes(r.get("cookTime")) or 0)
        y = _first(r.get("recipeYield"))
        return {
            "name": cleanh(r.get("name")),
            "description": cleanh(r.get("description"))[:400],
            "author": cleanh(author) if author else None,
            "date": (str(r.get("datePublished") or "")[:10] or None),
            "image": img,
            "ingredients": [cleanh(i) for i in r.get("recipeIngredient") or [] if cleanh(i)],
            "steps": _steps_h(r.get("recipeInstructions")),
            "minutes": mins,
            "yield": cleanh(y) if y else None,
            "recipeCategory": _listish(r.get("recipeCategory")),
            "cuisine": _listish(r.get("recipeCuisine")),
            "keywords": _listish(r.get("keywords"))[:12],
        }
    return None


# ---------- sources ----------
def load_sources():
    s = json.load(open(SOURCES, encoding="utf-8"))
    creators = {c["handle"]: c for c in s.get("creators") or s.get("accounts") or []}
    srcs = [{"type": "instagram_reel", "url": u} for u in s.get("posts", [])]  # legacy shape
    srcs += s.get("sources", [])
    return creators, srcs


def skey(src):
    return src["type"] + " " + (src.get("url") or src.get("creator") or "")


def social_item(platform, pid, url, caption, ts, handle, name, creator, thumbs, account_url):
    iid = {"instagram": pid, "tiktok": "tt-" + pid, "youtube": "yt-" + pid}[platform]
    thumb = w = h = color = None
    for cand in [c for c in thumbs if c]:
        try:
            thumb, w, h, color = download_thumb(cand, iid)
            break
        except Exception as e:  # noqa: BLE001
            log(f"  thumbnail failed for {iid}: {e}")
    date = dt.datetime.fromtimestamp(int(ts), dt.timezone.utc).date().isoformat() if ts else None
    return {"id": iid, "url": url, "platform": platform, "kind": "creator", "creator": creator,
            "account": handle, "account_name": name or "", "account_url": account_url, "status": "ok",
            "caption": caption or "", "date": date, "thumb": thumb, "thumb_w": w, "thumb_h": h, "color": color,
            "fetched_at": now_iso()}


def want_social(store, iid, caption, refresh):
    if iid in store["items"] and not refresh and store["items"][iid].get("status") in ("ok", "merged"):
        return False
    if iid in store["skipped"] and not refresh:
        return False
    ing, steps, _ = recipe_from_caption(caption)
    if not is_food_post(caption, bool(ing or steps)):
        store["skipped"][iid] = "not a food post"
        return False
    return True


def run_instagram_reel(src, store, creators, args):
    url = canonical(src["url"])
    code = shortcode(url)
    old = store["items"].get(code)
    if old and old.get("status") == "ok" and not args.refresh:
        return "kept", 0
    meta = fetch_meta(url)
    handle = meta.get("channel") or meta.get("uploader_id") or ""
    cands = [meta.get("thumbnail")] + [t.get("url") for t in reversed(meta.get("thumbnails") or [])]
    it = social_item("instagram", code, url, meta.get("description") or "", meta.get("timestamp"), handle,
                     meta.get("uploader"), src.get("creator") or handle, cands,
                     f"https://www.instagram.com/{handle}/" if handle else "")
    if not it["thumb"]:
        try:
            og = og_image(url)
            if og:
                it["thumb"], it["thumb_w"], it["thumb_h"], it["color"] = download_thumb(og, code)
        except Exception as e:  # noqa: BLE001
            log(f"  og:image failed {code}: {e}")
    it["title"] = meta.get("title") or "Instagram post"
    if old:
        for k in ("title", "summary"):
            if old.get(k + "_locked"):
                it[k], it[k + "_locked"] = old[k], True
        for k in ("video", "linked"):
            if old.get(k):
                it[k] = old[k]
    attach_linked(it)
    store["items"][code] = it
    return "ok", 1


def attach_linked(it):
    """A recipe page the creator linked in the caption (only if the caption has no full recipe)."""
    ing, steps, _ = recipe_from_caption(it.get("caption") or "")
    if (ing and steps) or it.get("linked"):
        return
    for link in links_in(it.get("caption") or ""):
        try:
            rec = fetch_recipe(link)
        except Exception as e:  # noqa: BLE001
            log(f"  recipe page failed {link}: {e}")
            continue
        if rec and rec["ingredients"] and rec["steps"]:
            rec["url"] = link
            it["linked"] = rec
            return


def run_tiktok(src, store, creators, args):
    data = ytdlp_json(["--flat-playlist", "-J", src["url"]], timeout=600)
    entries = data.get("entries") or []
    added = 0
    for e in entries:
        pid = str(e.get("id"))
        cap = e.get("description") or e.get("title") or ""
        if not want_social(store, "tt-" + pid, cap, args.refresh):
            continue
        handle = e.get("uploader") or src["url"].rstrip("/").rsplit("@", 1)[-1]
        thumbs = [t.get("url") for t in sorted(e.get("thumbnails") or [], key=lambda t: (t.get("id") != "cover", -(t.get("width") or 0)))]
        url = e.get("url") or f"https://www.tiktok.com/@{handle}/video/{pid}"
        it = social_item("tiktok", pid, url, cap, e.get("timestamp"), handle, e.get("channel") or handle,
                         src.get("creator") or handle, thumbs, f"https://www.tiktok.com/@{handle}")
        if not it["thumb"]:
            store["skipped"]["tt-" + pid] = "no photo"
            continue
        store["items"][it["id"]] = it
        added += 1
        log(f"ok   {it['id']}  @{handle}  {social_title(cap, '')[:60]}")
    ts = [e.get("timestamp") for e in entries if e.get("timestamp")]
    oldest = dt.datetime.fromtimestamp(min(ts), dt.timezone.utc).date().isoformat() if ts else None
    return f"listed {len(entries)} posts (oldest {oldest})", added


def run_youtube(src, store, creators, args):
    data = ytdlp_json(["--flat-playlist", "-J", src["url"]], timeout=600)
    entries = data.get("entries") or []
    added = 0
    dates = []
    for e in entries:
        pid = str(e.get("id"))
        iid = "yt-" + pid
        if iid in store["items"] and not args.refresh and store["items"][iid].get("status") in ("ok", "merged"):
            continue
        if iid in store["skipped"] and not args.refresh:
            continue
        try:
            meta = fetch_meta(f"https://www.youtube.com/watch?v={pid}")
        except Exception as ex:  # noqa: BLE001
            # YouTube sometimes asks to sign in for the full page; we never pass cookies, so fall back to
            # the public channel listing (title + thumbnail) and the public oEmbed author name.
            log(f"  {iid}: full metadata blocked ({str(ex)[:60]}...), using the public listing")
            meta = {"title": e.get("title"), "description": "", "timestamp": None,
                    "thumbnail": f"https://i.ytimg.com/vi/{pid}/hq720.jpg",
                    "thumbnails": [{"url": f"https://i.ytimg.com/vi/{pid}/hqdefault.jpg"}] + list(reversed(e.get("thumbnails") or [])),
                    "channel": data.get("channel") or data.get("uploader"), "uploader_id": data.get("uploader_id"),
                    "channel_url": data.get("channel_url")}
        cap = (meta.get("title") or "") + "\n" + (meta.get("description") or "")
        if not want_social(store, iid, cap, args.refresh):
            continue
        url = f"https://www.youtube.com/shorts/{pid}" if "/shorts" in src["url"] else f"https://www.youtube.com/watch?v={pid}"
        handle = (meta.get("uploader_id") or "").lstrip("@") or meta.get("channel")
        thumbs = [meta.get("thumbnail")] + [t.get("url") for t in reversed(meta.get("thumbnails") or [])]
        it = social_item("youtube", pid, url, cap.strip(), meta.get("timestamp"), handle, meta.get("channel"),
                         src.get("creator") or handle, thumbs, meta.get("channel_url") or "")
        it["title"] = meta.get("title")
        if it["date"]:
            dates.append(it["date"])
        store["items"][iid] = it
        added += 1
        log(f"ok   {iid}  {meta.get('title', '')[:60]}")
    return f"listed {len(entries)} videos", added


def _site_id(src, url):
    slug = urllib.parse.urlparse(url).path.strip("/").split("/")[-1] or "home"
    return (src.get("id_prefix") or re.sub(r"[^a-z]", "", urllib.parse.urlparse(url).netloc.replace("www.", ""))[:4]) + "-" + slug[:70]


def list_category(src):
    urls, page = [], 1
    while page <= int(src.get("max_pages", 60)):
        u = src["url"] if page == 1 else src["url"].rstrip("/") + f"/page/{page}/"
        try:
            html = get_url(u)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                break
            raise
        arts = re.findall(r"<article\b.*?</article>", html, re.S)
        found = [m.group(1) for a in arts for m in [re.search(r'href="([^"]+)"', a)] if m]
        if not found:
            break
        urls += found
        if len(urls) >= int(src.get("limit", 150)) + 20:
            break
        page += 1
    seen, out = set(), []
    for u in urls:
        if u not in seen:
            seen.add(u); out.append(u)
    return out


def list_sitemap(src):
    xml = get_url(src["url"])
    rows = re.findall(r"<url>\s*<loc>([^<]+)</loc>(?:\s*<lastmod>([^<]+)</lastmod>)?", xml)
    inc = [k.lower() for k in src.get("include", [])]
    exc = [k.lower() for k in src.get("exclude", [])]
    picked = []
    for loc, mod in rows:
        slug = urllib.parse.urlparse(loc).path.lower()
        if inc and not any(k in slug for k in inc):
            continue
        if any(k in slug for k in exc):
            continue
        picked.append((mod or "", loc))
    picked.sort(reverse=True)
    return [loc for _, loc in picked]


def run_website(src, store, creators, args):
    urls = list_category(src) if src["type"] == "website_category" else list_sitemap(src)
    limit = int(src.get("limit", 20))
    added = 0
    for url in urls[:limit]:
        iid = _site_id(src, url)
        if iid in store["items"] and not args.refresh:
            continue
        if url in store["skipped"] and not args.refresh:
            continue
        try:
            rec = fetch_recipe(url)
        except Exception as e:  # noqa: BLE001
            log(f"FAIL {url}: {e}")
            store["skipped"][url] = f"fetch failed: {str(e)[:120]}"
            continue
        if not rec or not (rec["ingredients"] and rec["steps"]) or not rec["image"]:
            store["skipped"][url] = "no Recipe JSON-LD with ingredients, steps and a photo"
            continue
        try:
            thumb, w, h, color = download_thumb(urllib.parse.urljoin(url, rec["image"]), iid)
        except Exception as e:  # noqa: BLE001
            store["skipped"][url] = f"photo failed: {str(e)[:120]}"
            continue
        creator = src.get("creator")
        c = creators.get(creator) or {}
        store["items"][iid] = {
            "id": iid, "url": url, "platform": "web", "kind": "creator" if creator else "site", "creator": creator,
            "site": src.get("site"), "site_url": src.get("site_url") or f"https://{urllib.parse.urlparse(url).netloc}/",
            "account": creator or "", "account_name": c.get("name") or src.get("site"),
            "account_url": src.get("site_url") or f"https://{urllib.parse.urlparse(url).netloc}/",
            "status": "ok", "web": rec, "date": rec["date"], "thumb": thumb, "thumb_w": w, "thumb_h": h, "color": color,
            "fetched_at": now_iso(),
        }
        added += 1
        log(f"ok   {iid}  {rec['name'][:60]}")
    return f"listed {len(urls)} pages, considered newest {min(limit, len(urls))}", added


RUNNERS = {"instagram_reel": run_instagram_reel, "tiktok_profile": run_tiktok, "youtube_channel": run_youtube,
           "website_category": run_website, "website_sitemap": run_website}


# ---------- derive display fields (re-run every time, from stored text only) ----------
def video_text(it):
    v = it.get("video") or {}
    if not v:
        return ""
    import video_recipe as _vr
    return "\n" + _vr.words_to_digits(v.get("narration") or "") + "\n" + "\n".join(_vr.words_to_digits(l) for l in v.get("onscreen") or [])


def derive_social(it):
    cap = it.get("caption") or ""
    if not it.get("title_locked"):
        it["title"] = social_title(cap, it.get("title") or {"tiktok": "TikTok post", "youtube": "YouTube Short"}.get(it.get("platform"), "Instagram post"))
    ing, steps, notes = recipe_from_caption(cap)
    extraction, frm = ("caption" if (ing or steps) else "none"), "caption"
    m = it.get("mirror") or {}
    if not (ing or steps) and m.get("caption"):
        mi, ms, mn = recipe_from_caption(m["caption"])
        if mi or ms:
            ing, steps, notes, extraction, frm = mi, ms, notes or mn, "caption", m["platform"] + " caption"
    it["recipeSourceUrl"], it["yield"], it["page_minutes"] = None, None, None
    lk = it.get("linked")
    if lk and not (ing and steps):
        ing, steps, extraction, frm = ing or lk["ingredients"], steps or lk["steps"], "recipe-page", "recipe page"
        it["recipeSourceUrl"], it["yield"], it["page_minutes"] = lk.get("url"), lk.get("yield"), lk.get("minutes")
    v = it.get("video") or {}
    if v and (v.get("narration") or v.get("onscreen")):
        import video_recipe as _vr
        v["ingredients"], v["steps"], v["kind"] = _vr.extract(v.get("narration"), v.get("onscreen"), it["title"])
    if not (ing or steps) and v.get("kind") in ("video", "video-partial"):
        ing, steps, extraction, frm = v["ingredients"], v["steps"], v["kind"], "video"
    it["ingredients"], it["steps"], it["notes"], it["extraction"], it["recipe_from"] = ing, steps, notes, extraction, frm
    if not it.get("summary_locked"):
        it["summary"] = summary(pseudo_lines(cap), it["title"])
    it["links"] = links_in(cap)
    text = it["title"] + "\n" + cap + "\n" + (m.get("caption") or "") + video_text(it)
    it["tags"] = auto_tags(text)
    it["category"] = category(it["tags"])
    sig = prep_signals(text)
    if sig["minutes"] is None and it.get("page_minutes"):
        sig.update(minutes=it["page_minutes"], time="quick" if it["page_minutes"] <= 20 else "long",
                   time_basis=f"recipe page says {it['page_minutes']} min")
    it.update(sig)


def derive_web(it):
    w = it["web"]
    it["title"] = w["name"] or it.get("title") or "Recipe"
    it["ingredients"] = [_parens(x) for x in w["ingredients"]]
    it["steps"], it["notes"] = [_parens(x) for x in w["steps"]], []
    it["extraction"], it["recipe_from"] = "recipe-page", "recipe page"
    it["recipeSourceUrl"], it["yield"] = it["url"], w.get("yield")
    d = w.get("description") or ""
    s = " ".join(re.split(r"(?<=[.!?])\s", d)[:2])
    it["summary"] = s[:200] + ("…" if len(s) > 200 else "")  # short excerpt only; the rest stays on the site
    meta = " ".join([it["title"], d, " ".join(w.get("recipeCategory") or []), " ".join(w.get("keywords") or [])])
    it["tags"] = auto_tags(meta)
    it["category"] = category(it["tags"])
    sig = prep_signals(meta)
    if w.get("minutes"):
        sig.update(minutes=w["minutes"], time="quick" if w["minutes"] <= 20 else "long", time_basis=f"recipe says {w['minutes']} min total")
    elif sig["minutes"] is not None:
        sig["time_basis"] = "description " + sig["time_basis"]
    if not sig["mealPrep"] and re.search(r"\b(freez|make[- ]ahead|meal[- ]prep|batch)", " ".join(w["steps"]), re.I):
        sig["mealPrep"], sig["mealPrep_basis"] = True, ["steps mention freezing / make-ahead"]
    it.update(sig)


def derive(it):
    if it.get("status") not in ("ok", "excluded"):
        return
    if it.get("platform") == "web":
        derive_web(it)
    else:
        derive_social(it)
        cap = it.get("caption") or ""
        full = bool(it.get("ingredients") or it.get("steps"))
        it["status"] = "ok" if (is_food_post(cap, full) or it.get("extraction") in ("video", "video-partial")) else "excluded"
    if it.get("thumb") and not it.get("color"):
        it["color"] = thumb_color(it["thumb"])


# ---------- the same post on two platforms ----------
def _norm(s):
    return re.sub(r"[^a-z0-9 ]", "", clean(re.sub(r"#\w+", "", s or "")).lower())[:160]


def link_mirrors(items):
    rank = {"instagram": 0, "tiktok": 1, "youtube": 2}
    for it in items.values():
        if it.get("status") == "merged":
            it["status"] = "ok"
        it.pop("mirror", None)
        it.pop("merged_into", None)
    social = [i for i in items.values() if i.get("status") == "ok" and i.get("platform") in rank]
    social.sort(key=lambda i: rank[i["platform"]])
    for a in social:
        if a.get("status") != "ok":
            continue
        best, bs = None, 0
        na = ((a.get("video") or {}).get("narration") or "").lower()
        for b in social:
            if b is a or b.get("status") != "ok" or b.get("creator") != a.get("creator"):
                continue
            nb = ((b.get("video") or {}).get("narration") or "").lower()
            nr = difflib.SequenceMatcher(None, na[:400], nb[:400]).ratio() if len(na) > 40 and len(nb) > 40 else 0
            same = rank[b["platform"]] == rank[a["platform"]]
            if rank[b["platform"]] < rank[a["platform"]] or (same and not (nr >= 0.9 and (b.get("date") or "") <= (a.get("date") or ""))):
                continue
            r = max(difflib.SequenceMatcher(None, _norm(a.get("caption"))[:120], _norm(b.get("caption"))[:120]).ratio(),
                    difflib.SequenceMatcher(None, _norm(a.get("title")), _norm(b.get("title"))).ratio(), nr)
            close = a.get("date") and b.get("date") and abs((dt.date.fromisoformat(a["date"]) - dt.date.fromisoformat(b["date"])).days) <= 3
            if (r >= 0.8 or (r >= 0.55 and close)) and r > bs:
                best, bs = b, r
        if best and not a.get("mirror"):
            a["mirror"] = {"platform": best["platform"], "url": best["url"], "id": best["id"], "caption": best.get("caption")}
            best["status"], best["merged_into"] = "merged", a["id"]


# ---------- outputs ----------
def by_line(it, creators):
    if it.get("kind") == "creator" and it.get("creator"):
        return "@" + it["creator"]
    return it.get("site") or it.get("account_name") or ""


def kw_text(it):
    bits = [it.get("title") or "", " ".join(it.get("tags") or []), it.get("summary") or "",
            " ".join(it.get("ingredients") or [])[:400], " ".join(re.findall(r"#(\w+)", it.get("caption") or ""))[:200]]
    return re.sub(r"\s+", " ", " ".join(bits).lower()).strip()[:900]


def order_items(items):
    """Creators first (round-robin across creators, newest first within each), then recipe sites."""
    def rr(group_key, pool):
        groups = {}
        for it in sorted(pool, key=lambda i: i.get("date") or "", reverse=True):
            groups.setdefault(group_key(it), []).append(it)
        out, qs = [], list(groups.values())
        while any(qs):
            for q in qs:
                if q:
                    out.append(q.pop(0))
        return out
    creators = [i for i in items if i.get("kind") == "creator"]
    sites = [i for i in items if i.get("kind") != "creator"]
    return rr(lambda i: i.get("creator"), creators) + rr(lambda i: i.get("site"), sites)


CARD_KEYS = ("id", "url", "platform", "kind", "creator", "site", "title", "thumb", "thumb_w", "thumb_h", "color", "date",
             "tags", "category", "time", "minutes", "mealPrep", "extraction", "recipePage")
DETAIL_KEYS = ("id", "url", "platform", "kind", "creator", "site", "site_url", "title", "summary", "ingredients", "steps",
               "notes", "yield", "recipeSourceUrl", "account", "account_name", "account_url", "date", "time_basis",
               "mealPrep_basis", "extraction", "recipe_from", "links")


def write_outputs(store, creators, source_status):
    items = [i for i in store["items"].values() if i.get("status") == "ok"]
    items = order_items(items)
    write_recipe_pages(items)
    os.makedirs(ITEMS_DIR, exist_ok=True)
    keep = set()
    cards = []
    for it in items:
        c = {k: it.get(k) for k in CARD_KEYS if it.get(k) not in (None, "", [], False)}
        c["by"] = by_line(it, creators)
        c["kw"] = kw_text(it)
        if it.get("ingredients") and it.get("steps"):
            c["full"] = True
        if it.get("mirror"):
            c["also"] = it["mirror"]["platform"]
        cards.append(c)
        d = {k: it.get(k) for k in DETAIL_KEYS if it.get(k) not in (None, "", [])}
        if it.get("platform") != "web":
            d["caption"] = it.get("caption") or ""
        else:
            d["author"] = (it.get("web") or {}).get("author")
        if it.get("mirror"):
            d["mirror"] = {"platform": it["mirror"]["platform"], "url": it["mirror"]["url"]}
        keep.add(it["id"] + ".json")
        p = os.path.join(ITEMS_DIR, it["id"] + ".json")
        txt = json.dumps(d, ensure_ascii=False, separators=(",", ":"))
        if not os.path.exists(p) or open(p, encoding="utf-8").read() != txt:
            open(p, "w", encoding="utf-8").write(txt)
    for f in os.listdir(ITEMS_DIR):
        if f.endswith(".json") and f not in keep:
            os.remove(os.path.join(ITEMS_DIR, f))
    counts = {}
    for it in items:
        k = by_line(it, creators) + " · " + it["platform"]
        counts[k] = counts.get(k, 0) + 1
    feed = {"updated_at": now_iso(), "count": len(cards), "counts": counts, "sources": source_status,
            "creators": [{"handle": h, "name": c.get("name"), "instagram": c.get("instagram")} for h, c in creators.items()],
            "items": cards}
    with open(FEED, "w", encoding="utf-8") as f:
        json.dump(feed, f, ensure_ascii=False, separators=(",", ":"))
        f.write("\n")
    # thumbnails no longer used by any item (e.g. merged duplicates) are removed
    used = {i.get("thumb") for i in store["items"].values() if i.get("status") in ("ok", "merged")}
    for f in os.listdir(THUMBS):
        if f"thumbs/{f}" not in used:
            os.remove(os.path.join(THUMBS, f))
    return items


# ---------- static per-recipe pages (server-rendered JSON-LD, e.g. for Umami import) ----------
SITE = "https://chanelluuhai.github.io/personal-apps/nibble/"
PAGE_CSS = """:root{--accent:#9E6656;--accent-soft:#EFE3DD;--accent-dark:#86503F;--ink:#2F2A27;--ink-2:#5A524C;--muted:#857B74;
--card:#FFFEFC;--radius:34px;--shadow:0 10px 32px rgba(70,50,48,.06);--font:"Nunito",system-ui,sans-serif;--display:"Alice",Georgia,serif}
*{box-sizing:border-box}body{margin:0;font-family:var(--font);color:var(--ink);-webkit-font-smoothing:antialiased;
background:linear-gradient(180deg,#ECE7E4 0%,#EDE6E2 38%,#EFE4DF 68%,#E8DAD3 100%);min-height:100vh}
main{max-width:640px;margin:0 auto;padding:28px 18px 48px}a{color:var(--accent-dark);font-weight:600}
.back{display:inline-flex;align-items:center;height:48px;padding:0 18px;border-radius:999px;background:rgba(255,254,252,.78);
backdrop-filter:blur(24px) saturate(1.2);-webkit-backdrop-filter:blur(24px) saturate(1.2);box-shadow:0 8px 24px rgba(70,50,48,.07);text-decoration:none;color:var(--ink)}
.card{background:var(--card);border-radius:var(--radius);box-shadow:var(--shadow);padding:22px 24px;margin:16px 0}
img.hero{width:100%;aspect-ratio:4/5;object-fit:cover;border-radius:28px;display:block}
h1{font-family:var(--display);font-weight:600;font-size:1.9rem;letter-spacing:-.02em;line-height:1.2;margin:18px 0 6px}
h2{font-family:var(--display);font-weight:600;font-size:1.2rem;margin:0 0 10px}.meta{color:var(--muted);font-size:.9rem}
li{line-height:1.55;margin:0 0 6px;color:var(--ink-2)}.btn{display:inline-flex;align-items:center;min-height:48px;padding:10px 20px;
border-radius:999px;background:var(--accent-dark);color:#fff;text-decoration:none}.credit{color:var(--ink-2);line-height:1.6}"""


def esc(s):
    return (str(s or "")).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


PLAT = {"instagram": "Instagram", "tiktok": "TikTok", "youtube": "YouTube", "web": "the web"}


def credit_text(it):
    who = esc(it.get("account_name") or it.get("site") or it.get("account"))
    if it.get("platform") == "web":
        return (f"Recipe by {esc((it.get('web') or {}).get('author') or who)}, from {esc(it.get('site') or who)}. "
                "Saved here for personal use; the original has the full notes, tips and photos.")
    h = "@" + esc(it.get("account"))
    if it.get("extraction") == "video":
        return f"From the video's narration and on-screen text, by {h} on {PLAT[it['platform']]}."
    if it.get("extraction") == "recipe-page":
        return f"Recipe from the page {h} linked in the caption."
    if it.get("recipe_from", "caption") != "caption":
        return f"Recipe text as written by {h} in their {esc(it['recipe_from'])}."
    return f"Recipe text as written by {h} on {PLAT[it['platform']]}."


def write_recipe_pages(items):
    out_dir = os.path.join(APP, "r")
    os.makedirs(out_dir, exist_ok=True)
    keep = set()
    for it in items:
        it.pop("recipePage", None)
        if it.get("status") != "ok" or not (it.get("ingredients") and it.get("steps")):
            continue
        keep.add(f"{it['id']}.html")
        web = it.get("platform") == "web"
        author = ({"@type": "Person", "name": (it.get("web") or {}).get("author") or it.get("site")} if web else
                  {"@type": "Person", "name": it.get("account_name") or it.get("account"), "url": it.get("account_url") or None})
        ld = {
            "@context": "https://schema.org", "@type": "Recipe", "name": it["title"],
            "description": it.get("summary") or "",
            "image": [SITE + it["thumb"]] if it.get("thumb") else [],
            "author": {k: v for k, v in author.items() if v},
            "datePublished": it.get("date"),
            "isBasedOn": it.get("recipeSourceUrl") or it["url"], "url": SITE + f"r/{it['id']}.html",
            "recipeIngredient": it.get("ingredients") or [],
            "recipeInstructions": [{"@type": "HowToStep", "text": t} for t in it.get("steps") or []],
            "keywords": ", ".join(it.get("tags") or []),
        }
        if it.get("minutes"):
            ld["totalTime"] = f"PT{it['minutes']}M"
        if it.get("yield"):
            ld["recipeYield"] = it["yield"]
        ld = {k: v for k, v in ld.items() if v not in (None, "", [])}
        ing = "".join(f"<li>{esc(x)}</li>" for x in it.get("ingredients") or [])
        st = "".join(f"<li>{esc(x)}</li>" for x in it.get("steps") or [])
        src = it.get("recipeSourceUrl") or it["url"]
        who = (f'<a href="{esc(it.get("site_url"))}" rel="noopener">{esc(it.get("site"))}</a>' if web else
               f'<a href="{esc(it.get("account_url"))}" rel="noopener">@{esc(it.get("account"))}</a> on {PLAT[it["platform"]]}')
        html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover"/>
<meta name="robots" content="noindex"/>
<title>{esc(it['title'])} · Nibble &amp; Sip</title>
<meta name="description" content="{esc(it.get('summary'))}"/>
<meta property="og:title" content="{esc(it['title'])}"/>
{f'<meta property="og:image" content="{SITE + it["thumb"]}"/>' if it.get('thumb') else ''}
<link rel="icon" href="../favicon.png"/>
<link rel="canonical" href="{esc(src)}"/>
<link href="https://fonts.googleapis.com/css2?family=Alice&family=Nunito:wght@400;500;600;700&display=swap" rel="stylesheet"/>
<script type="application/ld+json">{json.dumps(ld, ensure_ascii=False).replace("</", "<\\/")}</script>
<style>{PAGE_CSS}</style></head>
<body><main>
<a class="back" href="../#item={esc(it['id'])}">&larr; Nibble &amp; Sip</a>
<h1>{esc(it['title'])}</h1>
<p class="meta">From {who}{(' · ' + esc(it['date'])) if it.get('date') else ''}{(' · ' + str(it['minutes']) + ' min') if it.get('minutes') else ''}</p>
{f'<img class="hero" src="../{esc(it["thumb"])}" alt="{esc(it["title"])}"/>' if it.get('thumb') else ''}
<section class="card"><h2>Ingredients</h2><ul>{ing}</ul></section>
<section class="card"><h2>Steps</h2><ol>{st}</ol></section>
<p class="credit">{credit_text(it)} <a class="btn" href="{esc(src)}" rel="noopener">Open original</a></p>
</main></body></html>
"""
        p = os.path.join(out_dir, f"{it['id']}.html")
        if not os.path.exists(p) or open(p, encoding="utf-8").read() != html:
            open(p, "w", encoding="utf-8").write(html)
        it["recipePage"] = f"r/{it['id']}.html"
    for f in os.listdir(out_dir):
        if f.endswith(".html") and f not in keep:
            os.remove(os.path.join(out_dir, f))


def load_store():
    if os.path.exists(STORE):
        s = json.load(open(STORE, encoding="utf-8"))
    else:  # first run after the multi-source upgrade: adopt the old feed.json items
        s = {"items": {}, "skipped": {}}
        if os.path.exists(FEED):
            for it in json.load(open(FEED, encoding="utf-8")).get("items", []):
                if "caption" in it or it.get("status") != "ok":
                    it.setdefault("platform", "instagram")
                    it.setdefault("kind", "creator")
                    it.setdefault("creator", it.get("account"))
                    it.pop("thumb_lqip", None)
                    s["items"][it["id"]] = it
    s.setdefault("skipped", {})
    s.setdefault("sources", {})
    return s


def run_video(store, args):
    try:
        import video_recipe
    except Exception as e:  # noqa: BLE001
        log(f"video extraction unavailable: {e}")
        return 0
    todo = [it for it in store["items"].values() if it.get("status") == "ok" and it.get("platform") != "web"
            and it.get("extraction") == "none" and (args.video_retry or not it.get("video"))]
    todo.sort(key=lambda i: i.get("date") or "", reverse=True)
    pending = max(0, len(todo) - args.video_max)
    done = 0
    for it in todo[:args.video_max]:
        try:
            res = video_recipe.from_reel(it["url"], ytdlp_bin(), it.get("title", ""), log)
            res["checked_at"] = now_iso()
            it["video"] = res
            done += 1
            log(f"video {it['id']}: {res['kind']} ({len(res['ingredients'])} ingredients, {len(res['steps'])} steps)")
        except Exception as e:  # noqa: BLE001
            it["video"] = {"kind": "none", "error": str(e)[:200], "checked_at": now_iso()}
            log(f"video {it['id']}: failed: {e}")
    store["video_pending"] = pending
    return done


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--refresh", action="store_true", help="re-fetch items already known")
    ap.add_argument("--only", help="run only sources whose type or URL contains this text")
    ap.add_argument("--no-fetch", action="store_true", help="don't contact any source; just re-derive and rewrite outputs")
    ap.add_argument("--no-video", action="store_true", help="skip reading recipes out of videos")
    ap.add_argument("--video-max", type=int, default=30, help="most videos to transcribe per run (newest first; default 30)")
    ap.add_argument("--video-retry", action="store_true", help="re-run video extraction on items already checked")
    args = ap.parse_args()

    creators, srcs = load_sources()
    store = load_store()
    status = store["sources"]
    if not args.no_fetch:
        for src in srcs:
            k = skey(src)
            if args.only and args.only not in k:
                continue
            if src.get("enabled") is False or src["type"] == "instagram_profile":
                status[k] = {"status": "skipped", "why": src.get("note") or "disabled", "checked_at": now_iso()}
                continue
            run = RUNNERS.get(src["type"])
            if not run:
                status[k] = {"status": "unknown source type"}
                continue
            try:
                msg, n = run(src, store, creators, args)
                status[k] = {"status": "ok", "detail": msg, "added": n, "checked_at": now_iso()}
                log(f"source {k}: {msg}, {n} new")
            except Exception as e:  # noqa: BLE001
                status[k] = {"status": "failed", "error": str(e)[:240], "checked_at": now_iso()}
                log(f"source {k}: FAILED {e}")
            json.dump(store, open(STORE, "w", encoding="utf-8"), ensure_ascii=False)  # checkpoint
    for it in store["items"].values():
        derive(it)
    if not args.no_video and not args.no_fetch:
        if run_video(store, args):
            for it in store["items"].values():
                derive(it)
    link_mirrors(store["items"])
    for it in store["items"].values():
        derive(it)
    store["updated_at"] = now_iso()
    items = write_outputs(store, creators, status)
    with open(STORE, "w", encoding="utf-8") as f:
        json.dump(store, f, ensure_ascii=False, indent=0, sort_keys=True)
        f.write("\n")
    full = sum(1 for i in items if i.get("ingredients") and i.get("steps"))
    log(f"done: {len(items)} items, {full} with a full recipe, {store.get('video_pending', 0)} videos left for later runs")


if __name__ == "__main__":
    main()
