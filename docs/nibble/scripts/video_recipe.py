"""Pull a recipe out of a reel's own video: narration (faster-whisper, CPU) and
on-screen text (ffmpeg frames + tesseract). Only words actually said or shown are
used; nothing is inferred. Videos are downloaded to a temp folder and deleted.

Optional dependencies: faster-whisper (pip), tesseract (apt), ffmpeg, yt-dlp.
Missing tools are reported and skipped, never faked.
"""
import csv
import difflib
import io
import os
import re
import shutil
import subprocess
import tempfile

WORDNUM = {w: i for i, w in enumerate("zero one two three four five six seven eight nine ten eleven twelve thirteen "
                                       "fourteen fifteen sixteen seventeen eighteen nineteen twenty".split())}
WORDNUM.update({"thirty": 30, "forty": 40, "forty-five": 45, "fifty": 50, "sixty": 60, "a couple": 2, "half an": 0.5})

# Foods we recognise in narration / on-screen text (longest phrases first when matching).
FOODS = """
rice flour|almond flour|oat flour|coconut flour|flour|baking powder|baking soda|rolled oats|oats|oatmeal|chia seeds|flax seeds|hemp seeds
olive oil|avocado oil|coconut oil|butter|ghee|lemon juice|lime juice|lemon|lime|garlic powder|garlic|onion|ginger|cinnamon|vanilla|salt|pepper
egg|eggs|egg yolk|milk|whole milk|breast milk|formula|yogurt|greek yogurt|cream cheese|heavy cream|cream|cheese|cheddar|parmesan|mozzarella|ricotta|cottage cheese
banana|bananas|apple|apples|pear|pears|tangerine|tangerines|orange|oranges|mandarin|blueberries|strawberries|raspberries|blackberries|berries|mango|peach|peaches|dates|raisins|applesauce|pumpkin|pumpkin puree
avocado|broccoli|spinach|kale|zucchini|carrot|carrots|sweet potato|sweet potatoes|potato|potatoes|peas|corn|cauliflower|bell pepper|tomato|tomatoes|tomato paste|tomato sauce|beets|butternut squash|squash|cucumber|green beans|mushrooms
chickpeas|lentils|black beans|beans|tofu|peanut butter|almond butter|nut butter|tahini|sardines|sardine|salmon|tuna|cod|shrimp|fish|chicken|turkey|beef|ground beef|ground turkey|pork|meatballs
pasta|macaroni|noodles|udon|spaghetti|rotini|orzo|rice|quinoa|couscous|bread|tortilla|tortillas|pita|crackers|honey|maple syrup|cocoa|chocolate|seaweed|soy sauce|sesame oil|broth|stock|water
""".replace("\n", "|").split("|")
FOODS = sorted({f.strip() for f in FOODS if f.strip()}, key=len, reverse=True)
CUES = re.compile(r"\b(you('ll| will)? need|all you need|ingredients?|i (add|use|used|mix|mixed|blend|blended)|add|combine|mix|blend|made with|using|use)\b", re.I)
COOK_VERBS = r"mix|stir|blend|whisk|mash|microwave|bake|cook|boil|steam|simmer|roast|fry|saute|sauté|toast|grill|heat|freeze|chill|pour|fold|knead|roll|spread|slice|cut|chop|dice|grate|puree|purée|scoop|shape|flatten|cool|serve|add|combine|top|sprinkle|dip"
STEP_RE = re.compile(rf"\b({COOK_VERBS})\b", re.I)
REAL_COOK = re.compile(r"\b(mix|stir|blend|whisk|mash|microwave|bake|cook|boil|steam|simmer|roast|fry|saute|sauté|toast|grill|heat|freeze|pour|fold|knead|puree|purée|shape|flatten|spread)\b", re.I)
UNITS = r"(?:cups?|tbsp|tablespoons?|tsp|teaspoons?|g|grams?|ml|oz|ounces?|pieces?|slices?|cans?|handful)"


def tools():
    have = {"ffmpeg": bool(shutil.which("ffmpeg")), "tesseract": bool(shutil.which("tesseract"))}
    try:
        import faster_whisper  # noqa: F401
        have["whisper"] = True
    except Exception:  # noqa: BLE001
        have["whisper"] = False
    return have


def words_to_digits(t):
    for w, n in sorted(WORDNUM.items(), key=lambda x: -len(x[0])):
        t = re.sub(rf"\b{w}\b(?=\s+(?:minutes?|mins?|hours?|ingredients?|{UNITS})\b)", str(n), t, flags=re.I)
    return t


def download(url, ytdlp, tmp):
    out = os.path.join(tmp, "v.%(ext)s")
    r = subprocess.run([ytdlp, "-q", "--no-warnings", "--no-playlist", "-f", "best[height<=720]/bv*[height<=720]+ba/b", "--merge-output-format", "mp4", "-o", out, url],
                       capture_output=True, text=True, timeout=300)
    files = [f for f in os.listdir(tmp) if f.startswith("v.")]
    if r.returncode or not files:
        raise RuntimeError((r.stderr or "download failed").strip().splitlines()[-1][:200])
    return os.path.join(tmp, files[0])


_model = None


def transcribe(path, model_size="small"):
    global _model
    import numpy as np
    from faster_whisper import WhisperModel
    if _model is None:
        _model = WhisperModel(model_size, device="cpu", compute_type="int8")
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", path, "-ac", "1", "-ar", "16000", "-f", "s16le", "-"],
                         capture_output=True).stdout
    if not raw:
        return ""
    audio = np.frombuffer(raw, np.int16).astype(np.float32) / 32768.0
    segs, info = _model.transcribe(audio, vad_filter=True, beam_size=5)
    segs = [s for s in segs if s.no_speech_prob < 0.5]
    if info.language_probability < 0.5 and not segs:
        return ""
    return " ".join(s.text.strip() for s in segs).strip()


def ocr(path, tmp, every=1.0):
    from PIL import Image, ImageOps
    fdir = os.path.join(tmp, "frames")
    os.makedirs(fdir, exist_ok=True)
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", path, "-vf", f"fps=1/{every},scale=720:-1",
                    os.path.join(fdir, "%04d.png")], check=False)
    seen = []
    for f in sorted(os.listdir(fdir)):
        im = Image.open(os.path.join(fdir, f)).convert("L")
        for variant in (im, ImageOps.invert(im.point(lambda v: 255 if v > 215 else 0))):
            p = os.path.join(tmp, "o.png")
            variant.save(p)
            tsv = subprocess.run(["tesseract", p, "-", "--psm", "11", "tsv"], capture_output=True, text=True).stdout
            lines = {}
            for r in csv.DictReader(io.StringIO(tsv), delimiter="\t", quoting=csv.QUOTE_NONE):
                try:
                    conf = float(r["conf"])
                except (TypeError, ValueError):
                    continue
                w = (r.get("text") or "").strip()
                if conf < 80 or not re.fullmatch(r"[A-Za-z][A-Za-z'’-]+|\d+[a-z]*|&", w):
                    continue
                lines.setdefault((r["block_num"], r["par_num"], r["line_num"]), []).append(w)
            for words in lines.values():
                line = " ".join(words)
                if len(words) >= 2 and not any(difflib.SequenceMatcher(None, line.lower(), s.lower()).ratio() > 0.75 for s in seen):
                    seen.append(line)
    return seen


def sentences(text):
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


def food_hits(text):
    t, found = text.lower(), []
    pos = {}
    for f in FOODS:
        m = re.search(rf"(?<![a-z]){re.escape(f)}(?![a-z])", t)
        if m and not any(f in g for g in found):
            qty = re.search(rf"(\d+(?:[./]\d+)?\s*{UNITS}?\s*(?:of\s+)?)(?:some\s+|an?\s+)?{re.escape(f)}\b", t)
            item = (qty.group(1).strip() + " " + f) if qty and qty.group(1).strip() else f
            found.append(item)
            pos[item] = m.start()
            t = t[:m.start()] + " " * len(f) + t[m.end():]
    return sorted(found, key=lambda x: pos[x])


def tidy_step(s):
    s = re.sub(r"\b(and )?you'?re done\b\.?", "", s, flags=re.I)
    s = re.sub(r"\s+,", ",", s).strip(" ,")
    return s[:1].upper() + s[1:] if s else s


def extract(narration, onscreen, title=""):
    """Turn what was said/shown into ingredients + steps. Returns (ingredients, steps, kind)."""
    narration = words_to_digits(narration or "")
    shown = [words_to_digits(l) for l in (onscreen or [])]
    ing = []
    cue_text = " ".join(s for s in sentences(narration) if CUES.search(s))
    def list_like(line):  # "+ Rice flour", "2 eggs", "Ingredients: oats, banana"
        if CUES.search(line):
            return True
        rest = line.lower()
        for f in FOODS:
            rest = re.sub(rf"(?<![a-z]){re.escape(f)}(?![a-z])", " ", rest)
        rest = re.sub(rf"\b{UNITS}\b|[\d+&,./:-]|\b(and|of|a|an|some)\b", " ", rest)
        return len(rest.split()) <= 1 and rest != line.lower()
    shown_list = " . ".join(l for l in shown if list_like(l))
    for f in food_hits(cue_text) + food_hits(shown_list) + food_hits(title):
        base = re.sub(r"^[\d./]+\s*\S*\s*", "", f) if f[0].isdigit() else f
        if not any(base in g or g.endswith(base) for g in ing):
            ing.append(f)
    steps = []
    for s in sentences(narration):
        if STEP_RE.search(s) and len(s.split()) >= 3 and not re.match(r"(follow|comment|subscribe|save)\b", s, re.I):
            st = tidy_step(s)
            if st and st not in steps:
                steps.append(st)
    # on-screen instructions with a cooking verb and a number (e.g. "Microwave for 3 min") if not already said
    joined = []
    for l in shown:
        if joined and not re.search(r"[.!?]$", joined[-1]) and len(joined[-1].split()) < 4:
            joined[-1] += " " + l
        else:
            joined.append(l)
    for l in joined:
        if REAL_COOK.search(l) and re.search(r"\d", l):
            if not any(difflib.SequenceMatcher(None, l.lower(), s.lower()).find_longest_match(0, len(l), 0, len(s)).size > len(l) * 0.6 for s in steps):
                steps.append(tidy_step(l))
    has_cooking = any(REAL_COOK.search(s) for s in steps)
    if len(ing) >= 2 and has_cooking:
        return ing, steps, "video"
    if len(ing) >= 2:
        return ing, [], "video-partial"
    return [], [], "none"


def from_reel(url, ytdlp, title="", log=print):
    have = tools()
    if not have["ffmpeg"] or not (have["whisper"] or have["tesseract"]):
        raise RuntimeError(f"video tools missing: {have}")
    tmp = tempfile.mkdtemp(prefix="nibble-video-")
    try:
        path = download(url, ytdlp, tmp)
        narration = transcribe(path) if have["whisper"] else ""
        shown = ocr(path, tmp) if have["tesseract"] else []
        ing, steps, kind = extract(narration, shown, title)
        return {"narration": narration, "onscreen": shown[:30], "ingredients": ing, "steps": steps, "kind": kind,
                "tools": [k for k, v in have.items() if v]}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
