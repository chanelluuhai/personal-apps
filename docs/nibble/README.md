# Nibble & Sip

Toddler food ideas gathered weekly from a few Instagram creators, shown as a Pinterest-style feed, with a **For him** tab that ranks ideas against his favorite foods.

Live: https://chanelluuhai.github.io/personal-apps/nibble/

Static site (GitHub Pages serves `docs/` on `main`). No build step. Design follows [`design.md`](../../design.md) with a terra cotta theme.

## Weekly update (the one command)

From the repo root (`personal-apps/`):

```bash
/workspace/.nvenv/bin/python docs/nibble/scripts/scrape.py && git add docs/nibble && git commit -m "Nibble & Sip: weekly scrape" && git push
```

Needs `yt-dlp` on the PATH (or at `~/.local/bin/yt-dlp`), Pillow, and for video recipes `ffmpeg`, `tesseract` and `faster-whisper` (installed in the venv at `/workspace/.nvenv`, so run with that python). The script:

- reads `data/sources.json` (`posts` = Instagram post/reel links, `accounts` = creator handles),
- fetches public metadata for each post with `yt-dlp --skip-download` (no login, no cookies),
- downloads a 540px JPEG thumbnail into `thumbs/` (plus a tiny blur-up preview),
- parses the caption for a title, summary, ingredients, steps and "why it works" notes; if the caption links a recipe page, reads its schema.org Recipe JSON-LD,
- derives tags, a category, a time signal (`time`: quick / long / unknown, `minutes` only when a time is written) and `mealPrep`,
- for posts whose caption has no recipe, runs `scripts/video_recipe.py` once: downloads the reel to a temp folder (deleted right after, never committed), transcribes the narration with Whisper (`small`, CPU) and OCRs one frame per second with tesseract, then builds ingredients/steps **only from what is said or shown** (amounts only when stated). The raw narration/on-screen text is cached in `feed.json → video`, so it is not re-downloaded next week,
- writes `data/feed.json` and static recipe pages with Recipe JSON-LD in `r/<id>.html` (only for items with both ingredients and steps).

`extraction` on each item is one of `caption`, `recipe-page`, `video` (ingredients + method from the video), `video-partial` (ingredients mentioned, no method), or `none` (shown as "Recipe in the video").

It is idempotent: posts already in the feed are kept (dedupe by post URL); only new or previously failed posts are fetched. Derived fields are recomputed from the stored caption each run. `--refresh` re-fetches everything; `--no-accounts` skips the account listing attempt; `--no-video` skips video extraction; `--video-retry` re-runs it for items already checked.

**Adding sources:** paste new reel/post links into `posts` in `data/sources.json` (tracking `?...` params are stripped automatically). Listing an account's other recent posts needs an Instagram login today, so the script tries it publicly, logs the result in `feed.json → accounts`, and moves on.

## His favorites

`data/profile.json` holds his favorites as keyword groups with a weight and a short reason (shown as a chip). The For him tab scores in the browser, so editing that file changes the picks on the next load. "Close to his favorites" = matches a main favorite (weight 5); "Gentle next steps" = shares a format/sauce/snack signal, with any `new_foods` it contains shown as a "New: …" chip.

## Files

| Path | Role |
|------|------|
| `index.html`, `styles.css`, `app.js` | The app |
| `data/feed.json` | Generated feed (do not hand-edit; set `title_locked`/`summary_locked: true` on an item to keep a manual title/summary) |
| `data/sources.json` | Accounts and post links to scrape |
| `data/profile.json` | His favorites for the For him tab |
| `scripts/scrape.py` | Weekly scraper |
| `scripts/video_recipe.py` | Narration + on-screen text recipe extraction for video-only posts |
| `thumbs/` | Downloaded post thumbnails |
| `r/` | Generated recipe pages with schema.org JSON-LD |
| `icons/` | Clay art cut out to transparent WebP, app icons |
