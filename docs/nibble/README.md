# Nibble & Sip

Toddler food ideas gathered weekly from a few creators (Instagram, TikTok, YouTube, their blogs) plus a few toddler recipe sites, shown as a Pinterest-style feed, with a **For him** tab that ranks ideas against his favorite foods.

Live: https://chanelluuhai.github.io/personal-apps/nibble/

Static site (GitHub Pages serves `docs/` on `main`). No build step. Design follows [`design.md`](../../design.md) with a terra cotta theme.

## Weekly update (the one command)

```bash
cd /workspace/personal-apps && /workspace/.nvenv/bin/python docs/nibble/scripts/scrape.py && git add docs/nibble && git -c user.name=chanelluuhai -c user.email=chanelluuhai@users.noreply.github.com commit -m "Nibble & Sip: weekly scrape" && git push
```

A full run takes about 15-20 minutes: recipe sites are read politely (robots.txt checked, ~1.2 s between requests) and up to 30 videos are transcribed. Needs `yt-dlp` (on the PATH or `~/.local/bin/yt-dlp`), plus `ffmpeg`, `tesseract`, Pillow and `faster-whisper` from the venv at `/workspace/.nvenv`, so use that python.

### Sources (`data/sources.json`)

Creators get top billing in the feed (round-robin across creators, newest first); recipe sites are filler after them. The reels Chanel sent (`instagram_reel`) lead their creator's queue, so they all land in the first round of the feed.

| `type` | What it does |
|--------|--------------|
| `instagram_reel` | One public reel/post link (metadata via `yt-dlp`, no login) |
| `instagram_profile` | A creator's whole Instagram profile. **Disabled** (`enabled: false`): Instagram only lists a profile's posts to logged-in users. Ready for a future run where Chanel logs into Instagram in the box browser |
| `tiktok_profile` | Every public video on a TikTok profile (`yt-dlp --flat-playlist`) |
| `youtube_channel` | A channel tab such as `/shorts`. YouTube asks per-video requests to "sign in to confirm you're not a bot", so only the flat title and thumbnail are kept (no date or description) |
| `website_category` | Recipe links from a blog category page (`/page/N/` paging) |
| `website_sitemap` | Recipe URLs from a sitemap, filtered by `include` / `exclude` keywords, newest first |

Each source can set `creator` (links it to a creator in `creators`), `site`, `id_prefix`, `limit`, `enabled`, `since` (YYYY-MM-DD: posts older than this, or undated, are never fetched or queued; used for newer creators, e.g. @toddler.snack.therapy from 2025-01-01) and `strict_food` (keep only posts whose title names something to make; used for accounts with lots of nutrition talk or product reviews. YouTube Shorts always use this, since they often only have a title). Website pages are read from their schema.org Recipe JSON-LD (name, ingredients, steps, totalTime, yield, category, keywords). Sites that block bots or need a login/paywall are skipped, never bypassed.

### What a run does

- Lists each enabled source and fetches only items it hasn't seen (`--refresh` re-fetches all).
- Downloads a ~400px WebP thumbnail into `thumbs/` and stores its average colour as the loading placeholder.
- Social posts: parses the caption (line-based for Instagram, inline for TikTok's one-line captions) for title, ingredients and steps. Non-food posts (vlogs, toys, etc.) are excluded.
- Re-posts on one platform with the same title and caption are merged into one card (preferring the one with a written recipe).
- The same video posted on Instagram and TikTok/YouTube is merged into one card ("Also posted on"). Instagram is preferred, and the other caption's recipe is used if it has one.
- Video-only posts: `scripts/video_recipe.py` transcribes the narration (Whisper) and OCRs on-screen text, building a recipe **only from what is said or shown**. It handles the newest 30 per run (`--video-max`); the rest wait for later runs (`video_pending` in `store.json`). Videos go to a temp folder that is deleted right away.
- Derives tags, category, time (`quick` / `long`, `minutes` only when stated or from `totalTime`) and `mealPrep`.
- Writes `data/feed.json` (slim card index), `data/items/<id>.json` (detail loaded on open) and `r/<id>.html` recipe pages (`noindex`, canonical to the original) for every item with ingredients and steps.

`extraction` is one of `caption`, `recipe-page`, `video`, `video-partial` (ingredients mentioned, no method) or `none` (shown as "Recipe in the video").

Flags: `--only <text>` runs only sources whose type or URL contains the text; `--no-fetch` re-derives and rewrites outputs offline; `--no-video` skips video reading; `--video-max N`; `--video-retry`; `--refresh`.

## His favorites

`data/profile.json` holds his favorites as keyword groups with a weight and a short reason (shown as a chip). The For him tab scores in the browser, so editing that file changes the picks on the next load. "Close to his favorites" = matches a main favorite (weight 5); "Gentle next steps" = shares a format/sauce/snack signal, with any `new_foods` it contains shown as a "New: …" chip.

## Files

| Path | Role |
|------|------|
| `index.html`, `styles.css`, `app.js` | The app |
| `data/store.json` | Full scraper state (do not hand-edit except `title_locked`/`summary_locked: true` on an item to keep a manual title/summary) |
| `data/feed.json`, `data/items/` | Generated card index and per-item details |
| `data/sources.json` | Creators and sources to scrape |
| `data/profile.json` | His favorites for the For him tab |
| `scripts/scrape.py` | Weekly scraper |
| `scripts/video_recipe.py` | Narration + on-screen text recipe extraction for video-only posts |
| `thumbs/` | Downloaded post thumbnails |
| `r/` | Generated recipe pages with schema.org JSON-LD |
| `icons/` | Clay art cut out to transparent WebP, app icons |
