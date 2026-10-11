#!/usr/bin/env python3
"""Nibble & Sip weekly scraper.

Reads data/sources.json, fetches public metadata for each Instagram post/reel
(via yt-dlp, no login, no cookies), downloads a web-sized thumbnail into
thumbs/, and merges everything into data/feed.json.

Idempotent: posts already in feed.json are kept as they are (dedupe by post
URL). Only new posts, and posts that failed last time, are fetched again.
Use --refresh to re-fetch everything.

Run from the repo root:
    python3 docs/nibble/scripts/scrape.py
"""
import argparse
import datetime as dt
import io
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request

APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCES = os.path.join(APP, "data", "sources.json")
FEED = os.path.join(APP, "data", "feed.json")
THUMBS = os.path.join(APP, "thumbs")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"

try:
    from PIL import Image
except ImportError:  # thumbnails are saved as-is without Pillow
    Image = None


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def canonical(url):
    """Strip tracking params; normalise to https://www.instagram.com/reel|p/<code>/"""
    m = re.search(r"instagram\.com/(?:[^/]+/)?(reel|reels|p|tv)/([A-Za-z0-9_-]+)", url)
    if not m:
        return url.split("?")[0]
    kind = "reel" if m.group(1) in ("reel", "reels", "tv") else "p"
    return f"https://www.instagram.com/{kind}/{m.group(2)}/"


def shortcode(url):
    return canonical(url).rstrip("/").rsplit("/", 1)[-1]


def ytdlp_bin():
    return shutil.which("yt-dlp") or os.path.expanduser("~/.local/bin/yt-dlp")


def fetch_meta(url):
    cmd = [ytdlp_bin(), "--skip-download", "--dump-json", "--no-warnings", "--no-playlist", url]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if r.returncode != 0 or not r.stdout.strip():
        raise RuntimeError((r.stderr or "no output").strip().splitlines()[-1][:300])
    return json.loads(r.stdout.strip().splitlines()[-1])


def og_image(page_url):
    """Fallback: the public og:image of the post page (no login)."""
    req = urllib.request.Request(page_url, headers={"User-Agent": UA, "Accept-Language": "en"})
    html = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")
    m = re.search(r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"', html)
    return m.group(1).replace("&amp;", "&") if m else None


def lqip(path):
    """Tiny blurred preview as a data URI, for the blur-up while the photo loads."""
    if Image is None:
        return None
    import base64
    im = Image.open(os.path.join(APP, path)).convert("RGB")
    im.thumbnail((16, 28))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=50)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def download_thumb(url, code):
    os.makedirs(THUMBS, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    data = urllib.request.urlopen(req, timeout=60).read()
    path = os.path.join(THUMBS, f"{code}.jpg")
    if Image is None:
        open(path, "wb").write(data)
        return f"thumbs/{code}.jpg", None, None
    im = Image.open(io.BytesIO(data)).convert("RGB")
    if im.width > 540:
        im = im.resize((540, round(im.height * 540 / im.width)), Image.LANCZOS)
    im.save(path, "JPEG", quality=80, optimize=True, progressive=True)
    return f"thumbs/{code}.jpg", im.width, im.height


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


def build_item(url, meta, thumb, w, h):
    caption = meta.get("description") or ""
    handle = meta.get("channel") or meta.get("uploader_id") or ""
    title = title_from(caption, meta.get("title") or "Instagram post")
    ing, steps, notes = sections(caption)
    ts = meta.get("timestamp")
    date = dt.datetime.fromtimestamp(ts, dt.timezone.utc).date().isoformat() if ts else None
    tags = auto_tags(title + "\n" + caption)
    extraction, recipe_url, rec_yield, page_minutes = ("caption" if (ing or steps) else "none"), None, None, None
    if not (ing and steps):
        for link in links_in(caption):
            try:
                rec = fetch_recipe_page(link)
            except Exception as e:  # noqa: BLE001
                log(f"  recipe page failed {link}: {e}")
                continue
            if rec and (rec["ingredients"] or rec["steps"]):
                ing, steps = ing or rec["ingredients"], steps or rec["steps"]
                extraction, recipe_url, rec_yield, page_minutes = "recipe-page", link, rec["yield"], rec["minutes"]
                break
    return {
        "id": shortcode(url),
        "url": url,
        "status": "ok",
        "title": title,
        "summary": summary(caption, title),
        "caption": caption,
        "ingredients": ing,
        "steps": steps,
        "notes": notes,
        "account": handle,
        "account_name": meta.get("uploader") or "",
        "account_url": f"https://www.instagram.com/{handle}/" if handle else "",
        "date": date,
        "thumb": thumb,
        "thumb_w": w,
        "thumb_h": h,
        "thumb_lqip": lqip(thumb) if thumb else None,
        "links": links_in(caption),
        "extraction": extraction,
        "recipeSourceUrl": recipe_url,
        "yield": rec_yield,
        "page_minutes": page_minutes,
        "tags": tags,
        "category": category(tags),
        **prep_signals(title + "\n" + caption),
        "fetched_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
    }


def try_account(handle):
    """Public listing of an account's recent posts. Instagram currently requires
    login for this, so it usually fails; we never log in or use cookies."""
    try:
        r = subprocess.run([ytdlp_bin(), "--flat-playlist", "--dump-json", "--playlist-end", "12",
                            "--no-warnings", f"https://www.instagram.com/{handle}/"],
                           capture_output=True, text=True, timeout=90)
        urls = []
        for line in r.stdout.splitlines():
            try:
                u = json.loads(line).get("url") or ""
            except ValueError:
                continue
            if "instagram.com" in u:
                urls.append(canonical(u))
        if urls:
            return urls, "ok"
        return [], (r.stderr.strip().splitlines() or ["no posts returned"])[-1][:200]
    except Exception as e:  # noqa: BLE001
        return [], str(e)[:200]


# ---------- static per-recipe pages (server-rendered JSON-LD, e.g. for Umami import) ----------
SITE = "https://chanelluuhai.github.io/personal-apps/nibble/"
PAGE_CSS = """:root{--accent:#B5654D;--accent-soft:#F6E9E2;--accent-dark:#8A4430;--ink:#2F2A27;--ink-2:#5A524C;--muted:#8F857D;
--card:#FFFEFC;--radius:34px;--shadow:0 10px 32px rgba(70,50,48,.06);--font:"Nunito",system-ui,sans-serif;--display:"Alice",Georgia,serif}
*{box-sizing:border-box}body{margin:0;font-family:var(--font);color:var(--ink);-webkit-font-smoothing:antialiased;
background:linear-gradient(180deg,#ECE6E1 0%,#EEE5DF 38%,#F1E2D9 68%,#EBD3C6 100%);min-height:100vh}
main{max-width:640px;margin:0 auto;padding:28px 18px 48px}a{color:var(--accent-dark);font-weight:600}
.back{display:inline-flex;align-items:center;height:48px;padding:0 18px;border-radius:999px;background:rgba(255,254,252,.78);
backdrop-filter:blur(24px) saturate(1.2);-webkit-backdrop-filter:blur(24px) saturate(1.2);box-shadow:0 8px 24px rgba(70,50,48,.07);text-decoration:none;color:var(--ink)}
.card{background:var(--card);border-radius:var(--radius);box-shadow:var(--shadow);padding:22px 24px;margin:16px 0}
img.hero{width:100%;aspect-ratio:4/5;object-fit:cover;border-radius:28px;display:block}
h1{font-family:var(--display);font-weight:600;font-size:1.9rem;letter-spacing:-.02em;line-height:1.2;margin:18px 0 6px}
h2{font-family:var(--display);font-weight:600;font-size:1.2rem;margin:0 0 10px}.meta{color:var(--muted);font-size:.9rem}
li{line-height:1.55;margin:0 0 6px;color:var(--ink-2)}.btn{display:inline-flex;align-items:center;min-height:48px;padding:10px 20px;
border-radius:999px;background:var(--accent-dark);color:#fff;text-decoration:none}"""


def esc(s):
    return (str(s or "")).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def write_recipe_pages(items):
    out_dir = os.path.join(APP, "r")
    os.makedirs(out_dir, exist_ok=True)
    keep = set()
    for it in items:
        if it.get("status") != "ok" or not (it.get("ingredients") or it.get("steps")):
            continue
        keep.add(f"{it['id']}.html")
        ld = {
            "@context": "https://schema.org", "@type": "Recipe", "name": it["title"],
            "description": it.get("summary") or "",
            "image": [SITE + it["thumb"]] if it.get("thumb") else [],
            "author": {"@type": "Person", "name": it.get("account_name") or it.get("account"),
                       "url": it.get("account_url") or None},
            "datePublished": it.get("date"),
            "isBasedOn": it["url"], "url": SITE + f"r/{it['id']}.html",
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
        html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover"/>
<title>{esc(it['title'])} · Nibble &amp; Sip</title>
<meta name="description" content="{esc(it.get('summary'))}"/>
<meta property="og:title" content="{esc(it['title'])}"/>
{f'<meta property="og:image" content="{SITE + it["thumb"]}"/>' if it.get('thumb') else ''}
<link rel="icon" href="../favicon.png"/>
<link rel="canonical" href="{SITE}r/{it['id']}.html"/>
<link href="https://fonts.googleapis.com/css2?family=Alice&family=Nunito:wght@400;500;600;700&display=swap" rel="stylesheet"/>
<script type="application/ld+json">{json.dumps(ld, ensure_ascii=False).replace("</", "<\\/")}</script>
<style>{PAGE_CSS}</style></head>
<body><main>
<a class="back" href="../#item={esc(it['id'])}">&larr; Nibble &amp; Sip</a>
<h1>{esc(it['title'])}</h1>
<p class="meta">From <a href="{esc(it.get('account_url'))}" rel="noopener">@{esc(it.get('account'))}</a>{(' · ' + esc(it['date'])) if it.get('date') else ''}{(' · ' + str(it['minutes']) + ' min') if it.get('minutes') else ''}</p>
{f'<img class="hero" src="../{esc(it["thumb"])}" alt="{esc(it["title"])}"/>' if it.get('thumb') else ''}
{f'<section class="card"><h2>Ingredients</h2><ul>{ing}</ul></section>' if ing else ''}
{f'<section class="card"><h2>Steps</h2><ol>{st}</ol></section>' if st else ''}
<p>Recipe text as written by @{esc(it.get('account'))}. <a class="btn" href="{esc(src)}" rel="noopener">Open original</a></p>
</main></body></html>
"""
        open(os.path.join(out_dir, f"{it['id']}.html"), "w", encoding="utf-8").write(html)
        it["recipePage"] = f"r/{it['id']}.html"
    for f in os.listdir(out_dir):
        if f.endswith(".html") and f not in keep:
            os.remove(os.path.join(out_dir, f))
    for it in items:
        if f"{it['id']}.html" not in keep:
            it.pop("recipePage", None)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--refresh", action="store_true", help="re-fetch posts already in the feed")
    ap.add_argument("--no-accounts", action="store_true", help="skip trying to list each account's recent posts")
    args = ap.parse_args()

    sources = json.load(open(SOURCES, encoding="utf-8"))
    feed = json.load(open(FEED, encoding="utf-8")) if os.path.exists(FEED) else {"items": []}
    by_url = {canonical(i["url"]): i for i in feed.get("items", [])}

    want = [canonical(u) for u in sources.get("posts", [])]
    account_status = {}
    if not args.no_accounts:
        for acc in sources.get("accounts", []):
            urls, status = try_account(acc["handle"])
            account_status[acc["handle"]] = {"recent_posts_listing": status, "found": len(urls)}
            log(f"account @{acc['handle']}: {status} ({len(urls)} posts)")
            want += urls
    seen, ordered = set(), []
    for u in want:
        if u not in seen:
            seen.add(u); ordered.append(u)

    new, failed = 0, 0
    for url in ordered:
        old = by_url.get(url)
        if old and old.get("status") == "ok" and not args.refresh:
            continue
        code = shortcode(url)
        try:
            meta = fetch_meta(url)
            thumb, w, h = (None, None, None)
            candidates = [meta.get("thumbnail")] + [t.get("url") for t in reversed(meta.get("thumbnails") or [])]
            for cand in [c for c in candidates if c] + ["og:image"]:
                try:
                    if cand == "og:image":
                        cand = og_image(url)
                        if not cand:
                            break
                    thumb, w, h = download_thumb(cand, code)
                    break
                except Exception as e:  # noqa: BLE001
                    log(f"  thumbnail failed for {code}: {e}")
            item = build_item(url, meta, thumb, w, h)
            if old:  # keep anything hand-edited before
                for k in ("title", "summary"):
                    if old.get(k + "_locked"):
                        item[k] = old[k]
            by_url[url] = item
            new += 1
            log(f"ok   {code}  @{item['account']}  {item['title']}")
        except Exception as e:  # noqa: BLE001
            failed += 1
            log(f"FAIL {code}: {e}")
            if not old:
                by_url[url] = {"id": code, "url": url, "status": "failed", "title": "Instagram post",
                               "error": str(e)[:200], "tags": [], "category": "meal",
                               "fetched_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}

    for it in by_url.values():  # rules may change; re-derive from the stored caption
        if it.get("status") == "ok" and it.get("caption") is not None:
            if not it.get("title_locked"):
                it["title"] = title_from(it["caption"], it.get("title") or "Instagram post")
            if not it.get("summary_locked"):
                it["summary"] = summary(it["caption"], it["title"])
            ci, cs, it["notes"] = sections(it["caption"])
            if it.get("extraction") == "recipe-page":
                it["ingredients"], it["steps"] = it["ingredients"] or ci, it["steps"] or cs
            else:
                it["ingredients"], it["steps"] = ci, cs
                it["extraction"] = "caption" if (ci or cs) else "none"
                it.setdefault("recipeSourceUrl", None)
                it.setdefault("yield", None)
            it["links"] = links_in(it["caption"])
            if it.get("thumb") and not it.get("thumb_lqip") and os.path.exists(os.path.join(APP, it["thumb"])):
                it["thumb_lqip"] = lqip(it["thumb"])
            text = it["title"] + "\n" + it["caption"]
            it["tags"] = auto_tags(text)
            it["category"] = category(it["tags"])
            sig = prep_signals(text)
            if sig["minutes"] is None and it.get("page_minutes"):
                sig.update(minutes=it["page_minutes"], time="quick" if it["page_minutes"] <= 20 else "long",
                           time_basis=f"recipe page says {it['page_minutes']} min")
            it.update(sig)
        elif it.get("status") != "ok":
            it.update({"time": "unknown", "minutes": None, "mealPrep": False})
    items = sorted(by_url.values(), key=lambda i: (i.get("status") == "ok", i.get("date") or ""), reverse=True)
    write_recipe_pages(items)
    out = {
        "updated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "count": len(items),
        "accounts": account_status or feed.get("accounts", {}),
        "items": items,
    }
    with open(FEED, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
        f.write("\n")
    log(f"done: {len(items)} items ({new} fetched, {failed} failed) -> {os.path.relpath(FEED)}")


if __name__ == "__main__":
    main()
