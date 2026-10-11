#!/usr/bin/env python3
"""Build self-contained map HTML from data/places.json (file:// + GitHub Pages friendly)."""
from __future__ import annotations
import json
import pathlib
import html
import shutil

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "places.json"
EVENTS_DATA = ROOT / "data" / "events.json"
OUT_DIR = ROOT / "output" / "spots"
DOCS_DIR = ROOT / "docs" / "spots"
OUT_HTML = OUT_DIR / "index.html"
OUT_JSON = OUT_DIR / "places.json"
OUT_EVENTS = OUT_DIR / "events.json"
OUT_MD = OUT_DIR / "INDEX.md"

TEMPLATE = r'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover"/>
<meta name="theme-color" content="#E8E6E4"/>
<link rel="icon" type="image/png" href="favicon.png"/>
<link rel="apple-touch-icon" href="apple-touch-icon.png"/>
<link rel="manifest" href="site.webmanifest"/>
<meta name="apple-mobile-web-app-capable" content="yes"/>
<meta name="apple-mobile-web-app-title" content="Toddler Spots"/>
<meta name="apple-mobile-web-app-status-bar-style" content="default"/>
<meta name="description" content="Toddler outing map near Arvada/Denver — parks, museums, indoor play, farms from local parent guides."/>
<title>Toddler Spots · Denver / Arvada</title>
<link rel="preconnect" href="https://fonts.googleapis.com"/>
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin/>
<link href="https://fonts.googleapis.com/css2?family=Alice&family=Nunito:wght@400;500;600;700&display=swap" rel="stylesheet"/>
<link href="https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.css" rel="stylesheet"/>
<style>
  :root {
    --accent: #B57A88;
    --accent-soft: #F6EBEE;
    --accent-dark: #8E5A68;
    --blush: #E5B8C2;
    --blush-deep: #C98998;
    --mauve: #C4A8B4;
    --ink: #2F2A27;
    --ink-2: #5A524C;
    --muted: #9A9088;
    --line: rgba(80, 60, 58, 0.08);
    --bg: #E8E6E4;
    --bg-mid: #EDE8E6;
    --card: #FFFEFC;
    --far: #4F6F86;
    --far-soft: #E6EEF2;
    --near: #C4536E;
    --near-soft: #F8E7EB;
    --free: #B57A88;
    --free-soft: #F6EBEE;
    --indoor: #A08B8E;
    --indoor-soft: #F0EAEA;
    --hike: #7A8C6E;
    --hike-soft: #EBEFE6;
    --shadow: 0 10px 32px rgba(70, 50, 48, 0.06);
    --shadow-lg: 0 18px 48px rgba(60, 40, 42, 0.10);
    --radius: 34px;
    --radius-sm: 26px;
    --tap: 48px;
    --tab-h: calc(80px + env(safe-area-inset-bottom, 0px));
    --top-h: 56px;
    --safe-top: env(safe-area-inset-top, 0px);
    --safe-bottom: env(safe-area-inset-bottom, 0px);
    --font: "Nunito", system-ui, -apple-system, BlinkMacSystemFont, sans-serif;
    --display: "Alice", "Iowan Old Style", "Palatino Linotype", Palatino, Georgia, serif;
  }
  * { box-sizing: border-box; -webkit-tap-highlight-color: transparent; }
  html, body { height: 100%; margin: 0; overflow: hidden; }
  body {
    font-family: var(--font);
    color: var(--ink);
    background:
      linear-gradient(180deg,
        #E8E6E4 0%,
        #EBE7E5 38%,
        #F0E6E6 68%,
        #E9D5D8 100%);
    -webkit-font-smoothing: antialiased;
  }
  button, input { font-family: inherit; }

  #app {
    position: relative;
    height: 100%;
    height: 100dvh;
    width: 100%;
    overflow: hidden;
  }

  /* —— Top chrome —— */
  .topbar {
    position: absolute;
    top: 0; left: 0; right: 0;
    z-index: 20;
    display: flex;
    align-items: center;
    gap: 10px;
    padding: calc(8px + var(--safe-top)) 14px 8px;
    pointer-events: none;
  }
  .topbar > * { pointer-events: auto; }
  /* The map-only chrome must not reserve or cover space in other views. */
  .topbar[hidden] { display: none; }
  .topbar { transition: gap 460ms cubic-bezier(0.4, 0, 0.2, 1); }
  .topbar.search-focused { gap: 0; }
  .topbar.search-focused .brand {
    max-width: 0;
    margin-right: 0;
    opacity: 0;
    padding-left: 0;
    padding-right: 0;
    pointer-events: none;
  }
  .topbar.search-focused .search-pill {
    width: calc(100% - 28px);
  }
  .topbar::before {
    content: "";
    position: absolute;
    left: 0; right: 0; top: 0;
    height: calc(120px + var(--safe-top));
    pointer-events: none;
    background: linear-gradient(to bottom, rgba(232, 230, 228, 0.82) 0%, rgba(232, 230, 228, 0.35) 55%, transparent 100%);
    backdrop-filter: blur(16px) saturate(1.1);
    -webkit-backdrop-filter: blur(16px) saturate(1.1);
    -webkit-mask-image: linear-gradient(to bottom, #000 25%, transparent 100%);
    mask-image: linear-gradient(to bottom, #000 25%, transparent 100%);
  }
  .brand {
    display: flex;
    align-items: center;
    gap: 8px;
    height: 48px;
    background: rgba(255, 254, 252, 0.78);
    backdrop-filter: blur(24px) saturate(1.2);
    -webkit-backdrop-filter: blur(24px) saturate(1.2);
    border: none;
    border-radius: 999px;
    padding: 0 18px 0 12px;
    box-shadow: 0 8px 24px rgba(70, 50, 48, 0.07);
    flex-shrink: 0;
    max-width: 320px;
    margin-right: 58px;
    overflow: hidden;
    transition:
      max-width 460ms cubic-bezier(0.4, 0, 0.2, 1),
      padding 460ms cubic-bezier(0.4, 0, 0.2, 1),
      margin 460ms cubic-bezier(0.4, 0, 0.2, 1),
      opacity 280ms ease,
      width 320ms cubic-bezier(0.4, 0, 0.2, 1);
  }
  .brand.showing-hint { max-width: calc(100% - 70px); }
  .brand-mark {
    width: 38px; height: 38px;
    border-radius: 0;
    background: transparent;
    color: inherit;
    display: grid; place-items: center;
    flex-shrink: 0;
  }
  .brand-logo {
    width: 38px; height: 38px;
    object-fit: contain;
    display: block;
  }
  .brand-text {
    font-family: var(--display);
    font-weight: 600;
    font-size: 1.08rem;
    letter-spacing: -0.015em;
    line-height: 1;
    white-space: nowrap;
    transition: opacity 180ms ease;
  }
  .brand-text.is-hint {
    font-family: var(--font);
    font-weight: 500;
    font-size: 0.84rem;
    letter-spacing: -0.012em;
  }

  .search-pill {
    position: absolute;
    z-index: 3;
    right: 14px;
    top: calc(8px + var(--safe-top));
    flex: none;
    margin: 0;
    width: 48px;
    height: 48px;
    border-radius: 999px;
    background: rgba(255, 254, 252, 0.82);
    backdrop-filter: blur(24px) saturate(1.2);
    -webkit-backdrop-filter: blur(24px) saturate(1.2);
    box-shadow: 0 8px 24px rgba(70, 50, 48, 0.07);
    overflow: hidden;
    transition:
      width 460ms cubic-bezier(0.4, 0, 0.2, 1),
      background 220ms ease,
      box-shadow 220ms ease;
  }
  .search-pill input {
    display: block;
    position: absolute;
    z-index: 0;
    left: 0; right: 0; top: 0;
    width: 100%;
    height: 48px;
    min-height: 48px;
    border: none;
    border-radius: 999px;
    padding: 12px 16px 12px 42px;
    /* 16px prevents iOS Safari from auto-zooming on focus. */
    font-size: 16px;
    line-height: 1.25;
    -webkit-appearance: none;
    appearance: none;
    background: transparent;
    box-shadow: none;
    outline: none;
    color: transparent;
    caret-color: transparent;
    opacity: 1;
    pointer-events: none;
  }
  .topbar.search-focused .search-pill input {
    color: var(--ink);
    caret-color: var(--ink);
    pointer-events: auto;
  }
  .search-pill input::placeholder { color: transparent; }
  .topbar.search-focused .search-pill input::placeholder { color: #A89E96; }
  .search-pill input:focus { box-shadow: none; }
  .topbar.search-focused .search-pill:focus-within {
    box-shadow: 0 8px 24px rgba(70, 50, 48, 0.09), 0 0 0 3px rgba(181, 122, 136, 0.22);
  }
  .search-pill .ico {
    position: absolute; left: 50%; top: 50%; z-index: 1;
    display: block;
    transform: translate(-50%, -50%);
    color: var(--muted); pointer-events: none; width: 20px; height: 20px;
    stroke: currentColor; stroke-width: 2; overflow: visible;
    transition: left 460ms cubic-bezier(0.4, 0, 0.2, 1), color 180ms ease;
  }
  .topbar.search-focused .search-pill .ico { left: 26px; }
  .search-toggle {
    position: absolute;
    inset: 0;
    z-index: 2;
    display: grid;
    place-items: center;
    width: 100%;
    height: 100%;
    border: none;
    border-radius: 999px;
    color: var(--muted);
    background: transparent;
    box-shadow: none;
    cursor: pointer;
  }
  .search-toggle svg { width: 20px; height: 20px; stroke: currentColor; stroke-width: 2; opacity: 0; }
  .topbar.search-focused .search-toggle { pointer-events: none; }
  .search-toggle.is-active { color: var(--accent-dark); }
  .search-pill:has(.search-toggle.is-active) {
    background: rgba(255, 254, 252, 0.82);
    box-shadow: 0 8px 20px rgba(142, 90, 104, 0.16);
  }
  .search-pill:has(.search-toggle.is-active) .ico { color: var(--accent-dark); }
  .search-toggle:focus-visible { outline: 2px solid var(--accent-dark); outline-offset: 2px; }

  /* —— Map (full-bleed) —— */
  #map {
    position: absolute;
    inset: 0;
    bottom: 0;
    z-index: 1;
  }
  .maplibregl-ctrl-bottom-left,
  .maplibregl-ctrl-bottom-right {
    margin-bottom: calc(var(--tab-h) + 8px) !important;
  }
  .maplibregl-ctrl-attrib {
    font-size: 10px !important;
    background: rgba(255,255,255,0.75) !important;
  }
  .maplibregl-popup { display: none !important; }

  /* Marker dots */
  .pin {
    width: 18px; height: 18px;
    border-radius: 50%;
    border: 2.5px solid #fff;
    box-shadow: 0 2px 8px rgba(70,45,48,0.18);
    cursor: pointer;
    transition: transform .15s;
  }
  .pin.near { background: var(--near); }
  .pin.far { background: var(--far); }
  .pin.active { transform: scale(1.35); box-shadow: 0 0 0 4px rgba(196,137,152,0.35), 0 2px 10px rgba(60,40,45,0.22); }
  .home-pin {
    background: var(--free);
    color: #fff;
    font-size: 10px;
    font-weight: 800;
    letter-spacing: 0.04em;
    padding: 4px 8px;
    border-radius: 8px;
    border: 2px solid #fff;
    box-shadow: 0 2px 8px rgba(0,0,0,0.28);
    white-space: nowrap;
  }

  /* —— Views (List / Filters / About overlay panels) —— */
  .panel {
    position: absolute;
    inset: 0;
    z-index: 10;
    background:
      linear-gradient(180deg,
        #E8E6E4 0%,
        #EBE7E5 40%,
        #F0E6E6 72%,
        #E9D5D8 100%);
    display: none;
    overflow: auto;
    -webkit-overflow-scrolling: touch;
  }
  .panel.active { display: block; }
  .panel-header {
    position: sticky;
    top: 0;
    z-index: 4;
    padding: calc(22px + var(--safe-top)) 24px 10px;
  }
  /* Frosted fade: content scrolls under the title and blurs out, no hard edge. */
  .panel-header::before {
    content: "";
    position: absolute;
    left: 0; right: 0; top: 0;
    height: calc(100% + 18px);
    pointer-events: none;
    z-index: -1;
    background: linear-gradient(to bottom,
      rgba(232, 230, 228, 0.55) 0%,
      rgba(235, 231, 229, 0.28) 46%,
      rgba(235, 231, 229, 0.08) 72%,
      transparent 100%);
    backdrop-filter: blur(18px) saturate(1.25);
    -webkit-backdrop-filter: blur(18px) saturate(1.25);
    -webkit-mask-image: linear-gradient(to bottom, #000 0%, #000 48%, transparent 100%);
    mask-image: linear-gradient(to bottom, #000 0%, #000 48%, transparent 100%);
  }
  .panel-header h1 {
    position: relative;
    font-family: var(--display);
    font-size: 1.95rem;
    font-weight: 600;
    font-optical-sizing: auto;
    margin: 0;
    letter-spacing: -0.02em;
    line-height: 1.2;
    color: var(--ink);
  }
  .panel-header h1 {
    display: flex;
    align-items: center;
    min-height: 42px;
  }
  .panel-wordmark {
    display: block;
    width: auto;
    height: 42px;
    max-width: 100%;
    object-fit: contain;
    object-position: left center;
  }
  /* The All spots lettering is optically smaller than Events at the same image height. */
  .panel-wordmark-all-spots { height: 46px; }
  /* The Events asset has transparent padding on the left; align its visible
     lettering with the day heading below it. */
  .panel-wordmark-events { height: 37.8px; margin-left: -5px; }
  .panel-body {
    /* Leave the frosted sticky heading room to fade before content begins. */
    padding: 12px 18px calc(var(--tab-h) + 22px);
  }

  /* List cards */
  .place-card {
    background: var(--card);
    border: none;
    border-radius: var(--radius);
    padding: 18px 22px;
    margin-bottom: 12px;
    cursor: pointer;
    box-shadow: var(--shadow);
    transition: transform .12s, box-shadow .15s;
  }
  .place-card:active { transform: scale(0.985); }
  .place-card:hover, .place-card.active {
    box-shadow: var(--shadow-lg);
  }
  .place-card.active { outline: 2px solid rgba(181,122,136,0.40); outline-offset: 2px; }
  .card-top {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 6px;
    margin-bottom: 8px;
  }
  .badge {
    display: inline-flex;
    align-items: center;
    font-size: 0.68rem;
    font-weight: 600;
    padding: 4px 10px;
    border-radius: 999px;
    letter-spacing: 0.02em;
  }
  .badge.near { background: var(--near-soft); color: var(--near); }
  .badge.far { background: var(--far-soft); color: var(--far); }
  .badge.free { background: var(--free-soft); color: var(--free); }
  .badge.indoor { background: var(--indoor-soft); color: var(--indoor); }
  .badge.hike { background: var(--hike-soft); color: var(--hike); }
  .place-card h3 {
    margin: 0;
    font-family: var(--display);
    font-size: 1.22rem;
    font-weight: 600;
    letter-spacing: -0.015em;
    line-height: 1.3;
    color: var(--ink);
  }
  .card-line {
    margin: 4px 0 0;
    font-size: 0.84rem;
    color: var(--muted);
    line-height: 1.35;
  }
  .empty {
    text-align: center;
    color: var(--muted);
    padding: 48px 20px;
    font-size: 0.95rem;
    line-height: 1.5;
  }

  /* Events panel */
  .event-day { margin: 0 0 22px; }
  .event-day-heading {
    display: flex; align-items: baseline; justify-content: space-between;
    gap: 10px; margin: 6px 8px 12px;
    font-family: var(--display); font-size: 1.2rem; font-weight: 600;
    color: var(--ink); line-height: 1.3;
  }
  .event-day-heading span { color: var(--muted); font-family: var(--font); font-size: .7rem; font-weight: 500; text-transform: uppercase; letter-spacing: .08em; }
  .event-card {
    background: var(--card); border: none; border-radius: var(--radius);
    padding: 18px 22px; margin-bottom: 12px; box-shadow: var(--shadow);
  }
  .event-card { cursor: pointer; }
  .event-card.linked { transition: transform .12s, box-shadow .15s, border-color .15s; }
  .event-card.linked:hover, .event-card.linked:focus { box-shadow: var(--shadow-lg); outline: none; }
  .event-card.linked:active { transform: scale(.985); }
  .event-date-label { color: var(--muted); font-size: .72rem; font-weight: 500; margin-bottom: 6px; letter-spacing: 0.01em; }
  .event-card-top { display: flex; align-items: flex-start; justify-content: space-between; gap: 10px; margin: 0 0 6px; }
  .event-card h3 { margin: 0; flex: 1 1 auto; font-family: var(--display); font-size: 1.18rem; line-height: 1.3; font-weight: 600; color: var(--ink); }
  .cal-add {
    flex: 0 0 auto; align-self: flex-start;
    font-size: 0.75rem; font-weight: 600; line-height: 1.2;
    color: var(--accent-dark); text-decoration: none;
    background: var(--accent-soft); border-radius: 999px;
    padding: 7px 10px; white-space: nowrap;
  }
  .cal-add:hover { text-decoration: underline; }
  .event-meta { display: flex; flex-wrap: wrap; gap: 5px 12px; color: var(--muted); font-size: .78rem; margin: 0; }
  .event-time { color: var(--accent-dark); font-weight: 600; }
  .event-note {
    margin: 0 0 10px; color: var(--ink-2); font-size: .86rem; line-height: 1.4;
    display: -webkit-box; -webkit-box-orient: vertical; -webkit-line-clamp: 1;
    overflow: hidden; text-overflow: ellipsis;
  }
  .event-place {
    margin: 0 0 7px; color: var(--muted); font-size: .8rem; line-height: 1.3;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  }
  .event-link { color: var(--accent-dark); font-size: .82rem; font-weight: 600; text-decoration: none; }
  .event-link:hover { text-decoration: underline; }

  /* Filters panel */
  .filter-grid {
    display: grid;
    gap: 10px;
  }
  .filter-chip {
    display: flex;
    align-items: center;
    gap: 14px;
    width: 100%;
    text-align: left;
    background: var(--card);
    border: none;
    border-radius: var(--radius);
    box-shadow: var(--shadow);
    padding: 18px 20px;
    min-height: var(--tap);
    cursor: pointer;
    transition: border-color .15s, background .15s, transform .1s;
  }
  .filter-chip:active { transform: scale(0.98); }
  .filter-chip.active {
    background: var(--accent-soft);
    box-shadow: 0 0 0 1.5px var(--accent), var(--shadow);
  }
  .filter-chip .dot {
    width: 12px; height: 12px;
    border-radius: 50%;
    flex-shrink: 0;
    background: var(--muted);
  }
  .filter-chip[data-filter="near"] .dot { background: var(--near); }
  .filter-chip[data-filter="far"] .dot { background: var(--far); }
  .filter-chip[data-filter="free"] .dot { background: var(--free); }
  .filter-chip[data-filter="indoor"] .dot { background: var(--indoor); }
  .filter-chip[data-filter="hike"] .dot { background: var(--hike); }
  .filter-chip[data-filter="all"] .dot { background: var(--accent); }
  .filter-chip .label {
    flex: 1;
    font-weight: 500;
    font-size: 1rem;
  }
  .filter-chip .hint {
    font-size: 0.8rem;
    color: var(--muted);
    font-weight: 400;
  }
  .filter-chip .check {
    width: 22px; height: 22px;
    border-radius: 50%;
    border: 2px solid var(--line);
    flex-shrink: 0;
    display: grid; place-items: center;
  }
  .filter-chip.active .check {
    background: var(--accent);
    border-color: var(--accent);
    color: #fff;
  }
  .filter-chip.active .check::after { content: "✓"; font-size: 12px; font-weight: 700; }


  /* About */
  .about-card {
    background: var(--card);
    border: none;
    border-radius: var(--radius);
    padding: 24px 24px 20px;
    margin-bottom: 16px;
    box-shadow: var(--shadow);
  }
  .about-card h2 {
    font-family: var(--display);
    font-size: 1.18rem;
    margin: 0 0 12px;
    font-weight: 600;
    line-height: 1.3;
    color: var(--ink);
  }
  .about-card p, .about-card li {
    font-size: 0.92rem;
    color: var(--ink-2);
    line-height: 1.6;
    margin: 0 0 8px;
  }
  .about-card ul { padding-left: 1.1em; margin: 0 0 8px; }
  .about-card a { color: var(--accent-dark); font-weight: 600; text-decoration: none; }
  .about-card a:hover { text-decoration: underline; }
  .legend-row {
    display: flex; align-items: center; gap: 10px;
    font-size: 0.88rem; margin-bottom: 8px; color: var(--ink-2);
  }
  .legend-row i {
    width: 12px; height: 12px; border-radius: 50%;
    border: 2px solid #fff; box-shadow: 0 1px 3px rgba(0,0,0,.2);
    display: inline-block;
  }

  /* —— Split glass navigation —— */
  .dock {
    position: absolute;
    left: 12px; right: 12px;
    bottom: calc(10px + var(--safe-bottom));
    z-index: 45;
    display: flex;
    align-items: flex-end;
    justify-content: space-between;
    gap: 12px;
    pointer-events: none;
  }
  /* A quiet frosted fade keeps scrolling content from competing with the dock. */
  .dock::before {
    content: "";
    position: absolute;
    z-index: -1;
    left: -12px; right: -12px;
    bottom: calc(-10px - var(--safe-bottom));
    height: 148px;
    pointer-events: none;
    background: linear-gradient(to bottom, transparent 0%, rgba(232, 230, 228, 0.10) 25%, rgba(232, 230, 228, 0.74) 100%);
    backdrop-filter: blur(16px) saturate(1.08);
    -webkit-backdrop-filter: blur(16px) saturate(1.08);
    -webkit-mask-image: linear-gradient(to bottom, transparent 0%, #000 48%, #000 100%);
    mask-image: linear-gradient(to bottom, transparent 0%, #000 48%, #000 100%);
  }
  .dock-left, .dock-btn, .seg, .events-shell, .filter-shell { pointer-events: auto; }
  .dock-left {
    display: flex;
    align-items: flex-end;
    gap: 10px;
    min-width: 0;
  }
  .glass {
    background: rgba(255, 254, 252, 0.28);
    backdrop-filter: blur(22px) saturate(1.45);
    -webkit-backdrop-filter: blur(22px) saturate(1.45);
    border: 1px solid rgba(255, 254, 252, 0.5);
    box-shadow: 0 10px 28px rgba(70, 45, 50, 0.10);
  }
  .seg {
    --tab-pad: 6px;
    --tab-left: 0px;
    --tab-width: 0px;
    position: relative;
    display: flex;
    align-items: stretch;
    height: 68px;
    padding: var(--tab-pad);
    border-radius: 999px;
  }
  .tab-indicator {
    position: absolute;
    z-index: 0;
    top: var(--tab-pad);
    bottom: var(--tab-pad);
    left: 0;
    width: var(--tab-width);
    border: 1px solid rgba(255, 254, 252, 0.52);
    border-radius: 999px;
    background: linear-gradient(135deg, rgba(229, 184, 194, 0.88), rgba(196, 168, 180, 0.78));
    box-shadow: 0 5px 14px rgba(142, 90, 104, 0.18), inset 0 1px 0 rgba(255, 255, 255, 0.28);
    pointer-events: none;
    transform: translateX(var(--tab-left));
    transition: transform 480ms cubic-bezier(.22, 1, .36, 1), width 220ms ease, opacity 200ms ease;
    will-change: transform;
  }
  .seg.idle .tab-indicator { opacity: 0; }
  .tab, .dock-btn {
    position: relative;
    z-index: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 3px;
    border: none;
    background: transparent;
    color: var(--muted);
    font-size: 0;
    font-weight: 600;
    letter-spacing: 0.01em;
    cursor: pointer;
    border-radius: 999px;
    transition: color 220ms ease, background 220ms ease, opacity 160ms ease, transform 180ms ease;
  }
  .tab {
    min-width: 62px;
    padding: 8px 14px;
    font-size: 0;
  }
  .dock-btn {
    height: 68px;
    min-width: 68px;
    padding: 8px 14px;
    border-radius: 24px;
    font-size: 0;
  }
  /* Standalone actions use the same button-within-glass treatment. */
  @keyframes filterShellIn {
    from {
      opacity: 0;
      transform: scale(0.82);
      max-width: 0px;
      width: 0px;
      padding-left: 0px;
      padding-right: 0px;
      margin-left: -10px;
    }
    to {
      opacity: 1;
      transform: scale(1);
      max-width: 68px;
      width: 68px;
      padding-left: 6px;
      padding-right: 6px;
      margin-left: 0px;
    }
  }
  .filter-shell, .events-shell {
    display: grid;
    place-items: center;
    width: 68px;
    height: 68px;
    max-width: 68px;
    padding: 6px;
    border-radius: 999px;
    overflow: hidden;
    transform-origin: center;
  }
  /* The same animation runs in both directions; JS resets the class so it
     can replay whenever the button changes tabs. */
  .filter-shell.is-shown {
    animation: filterShellIn 420ms cubic-bezier(.22, 1, .36, 1) both;
  }
  .filter-shell.is-away {
    animation: filterShellIn 420ms cubic-bezier(.22, 1, .36, 1) reverse both;
    pointer-events: none;
  }
  .filter-shell .dock-btn, .events-shell .dock-btn {
    display: grid;
    place-items: center;
    width: 100%;
    height: 100%;
    min-width: 0;
    padding: 0;
    gap: 0;
    line-height: 0;
    border-radius: 999px;
  }
  .tab svg, .dock-btn svg { width: 30px; height: 30px; stroke-width: 1.75; display: block; }
  .filter-shell .dock-btn svg, .events-shell .dock-btn svg {
    width: 28px;
    height: 28px;
    margin: 0;
  }
  .tab.active { color: var(--accent-dark); }
  .dock-btn.on {
    color: var(--accent-dark);
    background: linear-gradient(135deg, rgba(229, 184, 194, 0.88), rgba(196, 168, 180, 0.78));
    border-color: rgba(255, 254, 252, 0.55);
    box-shadow: 0 8px 18px rgba(142, 90, 104, 0.16), inset 0 1px 0 rgba(255, 255, 255, 0.28);
  }
  .tab:focus-visible, .dock-btn:focus-visible, .brand:focus-visible { outline: 2px solid var(--accent-dark); outline-offset: 2px; }
  .tab:active, .dock-btn:active { opacity: 0.72; transform: scale(0.97); }
  @media (prefers-reduced-motion: reduce) {
    .tab-indicator, .tab, .dock-btn, .filter-shell, .filter-sheet, .about-drawer, .drawer-backdrop, .filter-backdrop, .welcome, .welcome-emoji, .welcome-emoji img, .welcome-wordmark, .welcome h1, .welcome-line, .welcome-credit, .welcome-enter, .loc-secondary, .loc-note, .search-pill, .search-pill .ico, .search-pill input, .brand, .brand-text, .topbar { transition: none !important; animation: none !important; }
    .filter-shell.is-away {
      opacity: 0;
      transform: scale(0.82);
      max-width: 0;
      width: 0;
      padding-left: 0;
      padding-right: 0;
      margin-left: -10px;
      pointer-events: none;
    }
  }

  /* Filter sheet and its backdrop sit above the map and nav. */
  .filter-backdrop, .drawer-backdrop {
    position: absolute;
    inset: 0;
    background: rgba(55, 42, 40, 0.18);
    opacity: 0;
    pointer-events: none;
    transition: opacity .25s;
  }
  .filter-backdrop { z-index: 52; }
  .drawer-backdrop { z-index: 60; }
  .filter-backdrop.open, .drawer-backdrop.open { opacity: 1; pointer-events: auto; }
  .filter-sheet {
    position: absolute;
    left: 0; right: 0;
    bottom: 0;
    z-index: 56;
    max-height: min(64dvh, 520px);
    overflow: auto;
    -webkit-overflow-scrolling: touch;
    background: rgba(255, 254, 252, 0.94);
    backdrop-filter: blur(26px) saturate(1.2);
    -webkit-backdrop-filter: blur(26px) saturate(1.2);
    border-radius: 28px 28px 0 0;
    box-shadow: var(--shadow-lg);
    padding: 8px 12px 14px;
    transform: translateY(18px);
    opacity: 0;
    pointer-events: none;
    transition: transform .36s cubic-bezier(.22, 1, .36, 1), opacity .24s;
  }
  .filter-sheet.open { transform: translateY(0); opacity: 1; pointer-events: auto; }
  .filter-sheet-head {
    display: flex; align-items: center; justify-content: space-between;
    gap: 10px; padding: 8px 8px 6px;
  }
  .filter-sheet-head h2 {
    margin: 0; font-family: var(--display); font-size: 1.35rem; font-weight: 600; color: var(--ink);
  }
  .icon-x {
    width: 40px; height: 40px; border: none; border-radius: 999px;
    background: rgba(232, 230, 228, 0.9); color: var(--ink);
    font-size: 1.35rem; line-height: 1; cursor: pointer; flex-shrink: 0;
  }
  .filter-sheet .filter-chip { border-radius: 22px; padding: 14px 16px; box-shadow: none; background: rgba(255,254,252,0.7); }
  .filter-sheet .filter-chip.active { background: var(--accent-soft); }

  .about-drawer {
    position: absolute;
    top: 0; right: 0; bottom: 0;
    width: min(440px, 100%);
    z-index: 70;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    transform: translateX(104%);
    visibility: hidden;
    pointer-events: none;
    transition:
      transform 480ms cubic-bezier(0.4, 0, 0.2, 1),
      visibility 0s linear 480ms;
    background: linear-gradient(180deg, #E8E6E4 0%, #EBE7E5 42%, #F0E6E6 74%, #E9D5D8 100%);
    box-shadow: -18px 0 48px rgba(60, 40, 42, 0.14);
    padding: 0;
    border-radius: 0;
  }
  .about-drawer.open {
    transform: translateX(0);
    visibility: visible;
    pointer-events: auto;
    transition:
      transform 480ms cubic-bezier(0.4, 0, 0.2, 1),
      visibility 0s linear 0s;
  }
  .drawer-scroll {
    flex: 1 1 auto;
    min-height: 0;
    overflow-x: hidden;
    overflow-y: auto;
    -webkit-overflow-scrolling: touch;
    padding: 0 18px calc(24px + var(--safe-bottom));
  }
  .drawer-top {
    display: flex; align-items: flex-start; justify-content: space-between;
    gap: 12px;
    position: sticky; top: 0; z-index: 2;
    margin: 0 -18px 12px;
    padding: calc(14px + var(--safe-top)) 18px 20px;
    /* Solid cap so scrolled cards cannot show through or above the top edge. */
    background: #E8E6E4;
    isolation: isolate;
  }
  /* Frosted fade only below the solid cap. The scrollport clips anything above it. */
  .drawer-top::before {
    content: "";
    position: absolute;
    left: 0; right: 0; top: 0;
    height: calc(100% + 32px);
    pointer-events: none;
    z-index: 0;
    background: linear-gradient(to bottom,
      #E8E6E4 0%,
      #E8E6E4 68%,
      rgba(235, 231, 229, 0.82) 84%,
      transparent 100%);
    backdrop-filter: blur(18px) saturate(1.25);
    -webkit-backdrop-filter: blur(18px) saturate(1.25);
    -webkit-mask-image: linear-gradient(to bottom, #000 0%, #000 68%, transparent 100%);
    mask-image: linear-gradient(to bottom, #000 0%, #000 68%, transparent 100%);
  }
  .drawer-top h1, .drawer-top .icon-x {
    position: relative;
    z-index: 1;
  }
  .drawer-top h1 {
    margin: 6px 0 0; font-family: var(--display); font-size: 1.8rem; font-weight: 600; color: var(--ink);
  }
  button.brand { cursor: pointer; color: inherit; text-align: left; font: inherit; }

  /* First-visit welcome */
  @keyframes welcomeButtonGradient {
    0%, 100% { background-position: 0% 50%; }
    50% { background-position: 100% 50%; }
  }
  @keyframes welcomeIconBounce {
    0% { opacity: 0; transform: translateY(12px) scale(.88); }
    55% { opacity: 1; transform: translateY(-5px) scale(1.03); }
    78% { transform: translateY(2px) scale(.98); }
    100% { opacity: 1; transform: translateY(0) scale(1); }
  }
  .welcome {
    position: absolute;
    inset: 0;
    z-index: 90;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: flex-start;
    text-align: center;
    padding: calc(28px + var(--safe-top)) 28px calc(28px + var(--safe-bottom));
    background: #E8E6E4;
    opacity: 0;
    transition: opacity .36s ease;
  }
  .welcome[hidden] { display: none; animation: none; }
  .welcome.open { opacity: 1; }
  .welcome-main {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    width: min(420px, 100%);
  }
  .welcome-emoji,
  .welcome-wordmark,
  .welcome h1,
  .welcome-line,
  .welcome-credit,
  .welcome-enter,
  .loc-secondary {
    opacity: 0;
    transform: translateY(14px);
    transition: opacity 560ms cubic-bezier(.22, 1, .36, 1), transform 560ms cubic-bezier(.22, 1, .36, 1);
  }
  .welcome.open .welcome-emoji { opacity: 1; transform: none; transition-delay: 90ms; }
  .welcome.open .welcome-wordmark { opacity: 1; transform: none; transition-delay: 220ms; }
  .welcome.open h1 { opacity: 1; transform: none; transition-delay: 220ms; }
  .welcome.open .welcome-line { opacity: 1; transform: none; transition-delay: 350ms; }
  .welcome.open .welcome-enter { opacity: 1; transform: none; transition-delay: 480ms; }
  .welcome.open .loc-secondary { opacity: 1; transform: none; transition-delay: 560ms; }
  .welcome.open .welcome-credit { opacity: 1; transform: none; transition-delay: 620ms; }
  .welcome-emoji {
    display: flex;
    align-items: flex-end;
    justify-content: center;
    gap: 4px;
    line-height: 1;
    margin: 0 0 40px;
  }
  .welcome-emoji img {
    width: 92px;
    height: 92px;
    object-fit: contain;
    display: block;
    opacity: 0;
    transform: translateY(12px) scale(.88);
  }
  .welcome.open .welcome-emoji img {
    animation: welcomeIconBounce 500ms cubic-bezier(.22, 1, .36, 1) both;
  }
  .welcome.open .welcome-emoji img:nth-child(2) { animation-delay: 110ms; }
  .welcome.open .welcome-emoji img:nth-child(3) { animation-delay: 220ms; }
  @media (max-width: 380px) {
    .welcome-emoji img { width: 76px; height: 76px; }
  }
  .welcome-wordmark {
    width: min(350px, 92vw);
    height: auto;
    display: block;
    object-fit: contain;
    margin: 0 0 28px;
    opacity: 0;
    transform: translateY(14px) scale(.96);
  }
  @media (max-width: 600px) {
    .welcome-wordmark { width: min(245px, 64.4vw); }
  }
  .welcome h1 {
    font-family: var(--display);
    font-weight: 600;
    font-size: clamp(1.85rem, 6vw, 2.35rem);
    letter-spacing: -0.025em;
    line-height: 1.15;
    margin: 0 0 14px;
    color: var(--ink);
  }
  .welcome-line {
    margin: 0 0 22px;
    max-width: 32ch;
    color: var(--ink-2);
    font-size: 1.02rem;
    line-height: 1.55;
  }
  .welcome-credit {
    margin-top: auto;
    margin-bottom: 0;
    color: var(--ink-2);
    font-size: 1.02rem;
    line-height: 1.55;
    font-style: normal;
    font-weight: 400;
    letter-spacing: 0.01em;
  }
  .welcome-enter, .about-replay {
    width: 100%;
    min-height: 52px;
    border: none;
    outline: none;
    border-radius: 999px;
    cursor: pointer;
    font-family: var(--font);
    font-weight: 600;
    font-size: 1rem;
    letter-spacing: 0.01em;
  }
  .welcome-enter {
    width: min(184px, 100%);
    min-height: 50px;
    margin: 18px 0 0;
    color: #fff;
    background: linear-gradient(120deg, #C98998 0%, #DFA9B5 44%, #B57A88 100%);
    background-size: 220% 100%;
    border: 0;
    outline: none;
    -webkit-appearance: none;
    appearance: none;
    -webkit-backdrop-filter: blur(14px) saturate(1.2);
    backdrop-filter: blur(14px) saturate(1.2);
    box-shadow: none;
    animation: welcomeButtonGradient 8s ease-in-out infinite;
  }
  .welcome-enter:active { transform: scale(0.98); }
  .welcome-enter:focus,
  .welcome-enter:focus-visible,
  .welcome-enter:hover,
  .welcome-enter:active {
    border: 0;
    outline: none;
    box-shadow: none;
  }
  .about-replay:focus-visible {
    outline: 2px solid var(--accent-dark);
    outline-offset: 3px;
  }
  .about-replay {
    margin: 4px 0 8px;
    color: var(--accent-dark);
    background: rgba(255, 254, 252, 0.72);
    box-shadow: var(--shadow);
  }
  .about-replay:active { transform: scale(0.985); }
  a.about-replay {
    display: flex; align-items: center; justify-content: center;
    text-decoration: none; box-sizing: border-box;
  }
  .loc-actions {
    display: flex;
    flex-direction: column;
    align-items: center;
    width: min(240px, 100%);
    margin-top: 22px;
    gap: 4px;
  }
  .loc-screen .welcome-line { margin-bottom: 0; }
  .loc-actions .welcome-enter { margin: 0; width: 100%; }
  .welcome-enter[disabled] { opacity: 0.72; cursor: progress; }
  .loc-secondary {
    width: 100%;
    min-height: 44px;
    border: none;
    background: transparent;
    color: var(--ink-2);
    font-family: var(--font);
    font-size: 1.02rem;
    font-weight: 500;
    line-height: 1.55;
    cursor: pointer;
    border-radius: 999px;
  }
  .loc-secondary:active { opacity: 0.7; }
  .loc-secondary:focus-visible {
    outline: 2px solid var(--accent-dark);
    outline-offset: 3px;
  }
  .loc-note {
    margin: 6px 0 0;
    max-width: 32ch;
    color: var(--accent-dark);
    font-size: 0.92rem;
    line-height: 1.45;
  }


  /* —— Bottom sheet (place detail) —— */
  .sheet-backdrop {
    position: absolute;
    inset: 0;
    z-index: 40;
    background: rgba(55, 42, 40, 0.22);
    opacity: 0;
    pointer-events: none;
    transition: opacity .25s;
  }
  .sheet-backdrop.open { opacity: 1; pointer-events: auto; }
  .sheet {
    position: absolute;
    left: 0; right: 0; bottom: 0;
    z-index: 50;
    height: 90dvh;
    max-height: 90dvh;
    background: rgba(255, 254, 252, 0.96);
    backdrop-filter: blur(28px) saturate(1.15);
    -webkit-backdrop-filter: blur(28px) saturate(1.15);
    border-radius: 36px 36px 0 0;
    box-shadow: var(--shadow-lg);
    transform: translateY(110%);
    transition: transform .32s cubic-bezier(.32,.72,0,1);
    display: flex;
    flex-direction: column;
    padding-bottom: var(--safe-bottom);
  }
  .sheet.open { transform: translateY(0); }
  .sheet-handle {
    width: 40px; height: 4px;
    background: rgba(181, 122, 136, 0.35);
    border-radius: 999px;
    margin: 12px auto 8px;
    flex-shrink: 0;
  }
  .sheet-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    padding: 2px 14px 0;
    flex-shrink: 0;
  }
  .sheet-nav {
    width: 40px;
    height: 40px;
    border: none;
    border-radius: 999px;
    background: rgba(232, 230, 228, 0.9);
    color: var(--ink);
    display: grid;
    place-items: center;
    cursor: pointer;
    padding: 0;
    font-size: 1.45rem;
    line-height: 1;
  }
  .sheet-nav svg { width: 22px; height: 22px; stroke: currentColor; stroke-width: 1.75; display: block; }
  .sheet-cal { display: inline-flex; margin: 0 0 16px; }
  .sheet-scroll {
    overflow: auto;
    -webkit-overflow-scrolling: touch;
    padding: 4px 24px 32px;
    flex: 1;
  }
  .sheet-scroll h2 {
    font-family: var(--display);
    font-size: 1.7rem;
    font-weight: 600;
    letter-spacing: -0.02em;
    margin: 4px 0 12px;
    line-height: 1.25;
    color: var(--ink);
  }
  .sheet-badges { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 14px; }
  .sheet-section {
    margin-bottom: 14px;
    font-size: 0.92rem;
    line-height: 1.5;
    color: var(--ink-2);
  }
  .sheet-section strong {
    display: block;
    font-size: 0.7rem;
    text-transform: uppercase;
    letter-spacing: 0.07em;
    color: var(--muted);
    margin-bottom: 4px;
    font-weight: 500;
  }
  .sheet-actions {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-top: 8px;
    padding-top: 4px;
  }
  .sheet-actions a, .sheet-actions button.primary, .sheet-close-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-height: 44px;
    padding: 10px 16px;
    border-radius: 999px;
    font-weight: 600;
    font-size: 0.88rem;
    text-decoration: none;
    border: none;
    cursor: pointer;
  }
  .sheet-actions a.primary, .sheet-actions button.primary {
    background: var(--accent-dark);
    color: #fff;
  }
  .sheet-close-btn { display: none; }
  .sheet-actions a.ghost {
    background: var(--bg);
    color: var(--ink);
    border: 1px solid var(--line);
  }
  .sheet-close-btn {
    background: transparent;
    color: var(--muted);
    margin-left: auto;
  }

  /* Desktop: a real two-pane layout. Phone styles under 768px are unchanged. */
  @media (min-width: 768px) {
    #app {
      --side: clamp(340px, 32vw, 440px);
      display: grid;
      grid-template-columns: var(--side) minmax(0, 1fr);
      grid-template-rows: minmax(0, 1fr);
      width: 100%;
      height: 100%;
      height: 100dvh;
      background:
        linear-gradient(180deg, #E8E6E4 0%, #EBE7E5 42%, #F3E4E6 100%);
    }
    #app::after {
      content: "";
      position: absolute;
      z-index: 25;
      top: 0; bottom: 0;
      left: var(--side);
      width: 1px;
      pointer-events: none;
      background: rgba(80, 60, 58, 0.10);
      box-shadow: 8px 0 28px rgba(70, 50, 48, 0.06);
    }
    #map {
      position: relative;
      inset: auto;
      grid-column: 2;
      grid-row: 1;
      width: auto;
      height: auto;
      min-width: 0;
      min-height: 0;
      z-index: 1;
    }
    .maplibregl-ctrl-top-right {
      margin-top: 78px !important;
    }
    .maplibregl-ctrl-bottom-left,
    .maplibregl-ctrl-bottom-right {
      margin-bottom: 14px !important;
    }

    /* Header sits on the map. Search stays an icon beside the wordmark. */
    #app .topbar,
    #app .topbar[hidden] {
      position: absolute;
      top: 0; left: 0; right: 0; bottom: auto;
      display: flex;
      flex-direction: row;
      align-items: center;
      justify-content: flex-start;
      gap: 10px;
      grid-column: 2;
      grid-row: 1;
      z-index: 30;
      width: auto;
      padding: calc(14px + var(--safe-top)) 18px 10px;
      pointer-events: none;
    }
    #app .topbar > * { pointer-events: auto; }
    .topbar::before { display: block; }
    .topbar.search-focused { gap: 10px; }
    .brand,
    .topbar.search-focused .brand {
      display: flex;
      align-self: center;
      flex-shrink: 0;
      max-width: none;
      margin-right: 0;
      opacity: 1;
      overflow: hidden;
      padding: 0 18px 0 12px;
      pointer-events: auto;
    }
    .search-pill,
    .topbar.search-focused .search-pill {
      position: relative;
      top: auto;
      right: auto;
      left: auto;
      z-index: 3;
      flex: 0 1 auto;
      margin: 0;
      width: 48px;
      height: 48px;
      max-width: none;
      border-radius: 999px;
      background: rgba(255, 254, 252, 0.82);
      box-shadow: 0 8px 24px rgba(70, 50, 48, 0.07);
      backdrop-filter: blur(24px) saturate(1.2);
      -webkit-backdrop-filter: blur(24px) saturate(1.2);
      overflow: hidden;
    }
    .topbar.search-focused .search-pill {
      width: min(300px, calc(100% - 240px));
      min-width: 148px;
    }
    .search-pill input,
    .topbar.search-focused .search-pill input {
      position: absolute;
      display: block;
      left: 0; right: 0; top: 0;
      width: 100%;
      height: 48px;
      min-height: 48px;
      opacity: 1;
      background: transparent;
      box-shadow: none;
      backdrop-filter: none;
      -webkit-backdrop-filter: none;
    }
    .search-pill input {
      color: transparent;
      caret-color: transparent;
      pointer-events: none;
    }
    .topbar.search-focused .search-pill input {
      color: var(--ink);
      caret-color: var(--ink);
      pointer-events: auto;
    }
    .search-pill input::placeholder { color: transparent; }
    .topbar.search-focused .search-pill input::placeholder { color: #A89E96; }
    .search-pill input:focus { box-shadow: none; }
    .topbar.search-focused .search-pill:focus-within {
      box-shadow: 0 8px 24px rgba(70, 50, 48, 0.09), 0 0 0 3px rgba(181, 122, 136, 0.22);
    }
    .search-pill .ico {
      display: block;
      left: 50%;
      top: 50%;
      width: 20px;
      height: 20px;
      transform: translate(-50%, -50%);
    }
    .topbar.search-focused .search-pill .ico { left: 26px; }
    .search-toggle { display: grid; }

    .panel {
      position: relative;
      inset: auto;
      grid-column: 1;
      grid-row: 1;
      min-height: 0;
      height: 100%;
      background: transparent;
      flex-direction: column;
      overflow: auto;
    }
    #app:not([data-view="events"]) #panel-list,
    #app[data-view="events"] #panel-events {
      display: flex;
    }
    .panel-header {
      position: sticky;
      top: 0;
      flex: 0 0 auto;
      padding: calc(18px + var(--safe-top)) 22px 2px;
    }
    .panel-header h1 { min-height: 36px; }
    .panel-wordmark { height: 36px; }
    .panel-wordmark-all-spots { height: 40px; }
    .panel-wordmark-events { height: 32.4px; margin-left: -4px; }
    .panel-body {
      flex: 0 0 auto;
      min-height: auto;
      overflow: visible;
      padding: 12px 16px calc(136px + var(--safe-bottom));
    }

    .dock {
      position: absolute;
      top: auto;
      left: 0;
      right: auto;
      bottom: 0;
      width: var(--side);
      grid-column: 1;
      grid-row: 1;
      z-index: 45;
      padding: 0 14px calc(16px + var(--safe-bottom));
    }
    .dock::before {
      display: block;
      left: 0;
      right: 0;
      bottom: 0;
    }
    /* Map and list are both on screen, so the switch is phone-only. */
    .seg { display: none; }

    .filter-sheet {
      left: 14px;
      right: auto;
      width: calc(var(--side) - 28px);
      bottom: 92px;
      border-radius: 28px;
      max-height: min(56vh, 460px);
    }
    .about-drawer { width: min(420px, 36vw); }

    .sheet-handle { display: none; }
    .sheet-bar { display: none; }
    .sheet-close-btn { display: inline-flex; }
    .sheet {
      left: auto;
      right: 24px;
      bottom: 24px;
      width: min(400px, calc(100% - var(--side) - 48px));
      height: auto;
      max-height: min(72vh, 640px);
      border-radius: 32px;
      padding-bottom: 0;
      transform: translateY(110%);
    }
    .sheet.open { transform: translateY(0); }
    .sheet-backdrop { background: rgba(55, 42, 40, 0.08); }
  }
</style>
</head>
<body>
<div id="app">
  <div id="map" role="application" aria-label="Map of toddler outing spots"></div>

  <header class="topbar">
    <button type="button" class="brand" id="open-about" aria-haspopup="dialog" aria-controls="about-drawer" aria-expanded="false">
      <span class="brand-mark">
        <img class="brand-logo" src="icons/header-baby.png" alt=""/>
      </span>
      <span class="brand-text">Toddler Spots</span>
    </button>
    <div class="search-pill">
      <button type="button" class="search-toggle" id="search-toggle" aria-label="Search" aria-expanded="false" aria-pressed="false">
        <svg viewBox="0 0 24 24" fill="none" aria-hidden="true" focusable="false"><circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5" stroke-linecap="round"/></svg>
      </button>
      <svg class="ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true" focusable="false"><circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5" stroke-linecap="round"/></svg>
      <input type="search" id="search" placeholder="Search" autocomplete="off" enterkeyhint="search" aria-label="Search places"/>
    </div>
  </header>

  <section class="panel" id="panel-list" aria-label="Place list">
    <div class="panel-header">
      <h1><img class="panel-wordmark panel-wordmark-all-spots" src="icons/clay-all-spots.png" alt="All spots" width="1050" height="270"/></h1>
    </div>
    <div class="panel-body" id="list"></div>
  </section>

  <section class="panel" id="panel-events" aria-label="Upcoming events">
    <div class="panel-header">
      <h1><img class="panel-wordmark panel-wordmark-events" src="icons/clay-events.png" alt="Events" width="930" height="222"/></h1>
    </div>
    <div class="panel-body" id="events"></div>
  </section>

  <div class="filter-backdrop" id="filter-backdrop" hidden></div>
  <aside class="filter-sheet" id="filter-sheet" role="dialog" aria-modal="true" aria-labelledby="filter-title" hidden>
    <div class="filter-sheet-head">
      <h2 id="filter-title">Filters</h2>
      <button type="button" class="icon-x" id="filter-close" aria-label="Close filters">&times;</button>
    </div>
    <div class="filter-grid" role="listbox" aria-label="Filter options">
      <button type="button" class="filter-chip active" data-filter="all" role="option" aria-selected="true">
        <span class="dot"></span>
        <span class="label">All spots<span class="hint"><br>Show everything</span></span>
        <span class="check"></span>
      </button>
      <button type="button" class="filter-chip" data-filter="near" role="option" aria-selected="false">
        <span class="dot"></span>
        <span class="label">Near (~30 min)<span class="hint" id="near-from"><br>From __BASE_LABEL__</span></span>
        <span class="check"></span>
      </button>
      <button type="button" class="filter-chip" data-filter="far" role="option" aria-selected="false">
        <span class="dot"></span>
        <span class="label">Farther<span class="hint"><br>Worth the drive</span></span>
        <span class="check"></span>
      </button>
      <button type="button" class="filter-chip" data-filter="free" role="option" aria-selected="false">
        <span class="dot"></span>
        <span class="label">Free<span class="hint"><br>Parks & free-entry spots</span></span>
        <span class="check"></span>
      </button>
      <button type="button" class="filter-chip" data-filter="indoor" role="option" aria-selected="false">
        <span class="dot"></span>
        <span class="label">Indoor<span class="hint"><br>Museums, play, libraries</span></span>
        <span class="check"></span>
      </button>
      <button type="button" class="filter-chip" data-filter="hike" role="option" aria-selected="false">
        <span class="dot"></span>
        <span class="label">Toddler hikes<span class="hint"><br>Short trails & creek walks</span></span>
        <span class="check"></span>
      </button>
    </div>
  </aside>

  <div class="drawer-backdrop" id="about-backdrop" hidden></div>
  <aside class="about-drawer" id="about-drawer" role="dialog" aria-modal="true" aria-labelledby="about-title" hidden>
    <div class="drawer-scroll">
    <div class="drawer-top">
      <h1 id="about-title">About</h1>
      <button type="button" class="icon-x" id="about-close" aria-label="Close">&times;</button>
    </div>
    <div class="about-card">
      <h2>Base & audience</h2>
      <p id="about-home-line">Home base: <strong>__BASE_LABEL__</strong>. Aimed at a toddler ~20 months; prefer spots within ~30 minutes.</p>
      <p>Updated __UPDATED__ · __COUNT__ places · __EVENT_COUNT__ upcoming events</p>
    </div>
    <div class="about-card">
      <h2>Map legend</h2>
      <div class="legend-row"><i style="background:#C4536E"></i> Within ~30 min</div>
      <div class="legend-row"><i style="background:#4F6F86"></i> Farther</div>
      <div class="legend-row"><i style="background:#B57A88"></i> <span id="legend-home">Home (80004)</span></div>
    </div>
    <div class="about-card">
      <h2>Sources</h2>
      <ul>
__SOURCES_HTML__
      </ul>
      <p>Why-notes paraphrased from those guides. Drive times are rough estimates — confirm in Maps.</p>
    </div>
    <button type="button" class="about-replay" id="welcome-replay">What is this</button>
    <button type="button" class="about-replay" id="loc-edit">Edit location sharing</button>
    <a class="about-replay" href="https://chanelluuhai.github.io/personal-apps/">More apps</a>
    </div>
  </aside>

  <nav class="dock" aria-label="Main">
    <div class="dock-left">
      <div class="seg glass" id="view-seg" role="tablist" aria-label="Map or list">
        <span class="tab-indicator" aria-hidden="true"></span>
        <button type="button" class="tab active" data-tab="map" role="tab" aria-label="Map" aria-selected="true">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true"><path d="M9 4l-5 2v14l5-2 6 2 5-2V4l-5 2-6-2z"/><path d="M9 4v14M15 6v14"/></svg>
        </button>
        <button type="button" class="tab" data-tab="list" role="tab" aria-label="List" aria-selected="false">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true"><path d="M8 6h12M8 12h12M8 18h12" stroke-linecap="round"/><circle cx="4" cy="6" r="1.2" fill="currentColor" stroke="none"/><circle cx="4" cy="12" r="1.2" fill="currentColor" stroke="none"/><circle cx="4" cy="18" r="1.2" fill="currentColor" stroke="none"/></svg>
        </button>
      </div>
      <div class="filter-shell glass" id="filter-shell">
        <button type="button" class="dock-btn" id="filter-btn" aria-label="Filter" aria-pressed="false" aria-expanded="false" aria-controls="filter-sheet">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true"><path d="M5 7h14M8 12h8M10.5 17h3" stroke-linecap="round"/></svg>
        </button>
      </div>
    </div>
    <div class="events-shell glass">
      <button type="button" class="dock-btn" id="events-btn" aria-label="Events" aria-pressed="false">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true"><rect x="4" y="5.5" width="16" height="14.5" rx="2"/><path d="M8 3.5v3.5M16 3.5v3.5M4 10h16M8.5 14h.01M12 14h.01M15.5 14h.01M8.5 17.5h.01M12 17.5h.01" stroke-linecap="round" stroke-linejoin="round"/></svg>
      </button>
    </div>
  </nav>

  <div class="sheet-backdrop" id="sheet-backdrop"></div>
  <aside class="sheet" id="sheet" role="dialog" aria-modal="true" aria-labelledby="sheet-title" hidden>
    <div class="sheet-handle" aria-hidden="true"></div>
    <div class="sheet-bar">
      <button type="button" class="sheet-nav" id="sheet-back" aria-label="Back">
        <svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M15 5l-7 7 7 7" stroke-linecap="round" stroke-linejoin="round"/></svg>
      </button>
      <button type="button" class="sheet-nav sheet-nav-close" id="sheet-dismiss" aria-label="Close">&times;</button>
    </div>
    <div class="sheet-scroll" id="sheet-body"></div>
  </aside>

  <div class="welcome" id="welcome" role="dialog" aria-modal="true" aria-labelledby="welcome-title" hidden>
    <div class="welcome-main">
      <div class="welcome-emoji" aria-hidden="true"><img src="icons/clay-baby.png" alt="" width="92" height="92"/><img src="icons/clay-slide.png" alt="" width="92" height="92"/><img src="icons/clay-book.png" alt="" width="92" height="92"/></div>
      <img class="welcome-wordmark" id="welcome-title" src="icons/clay-wordmark.png" alt="Toddler Spots" width="770" height="354"/>
      <p class="welcome-line">Locations and events for toddlers, sourced from local guides.</p>
      <button type="button" class="welcome-enter" id="welcome-enter">Enter</button>
    </div>
    <p class="welcome-credit">Created by Chanel and her bot</p>
  </div>

  <div class="welcome loc-screen" id="loc-screen" role="dialog" aria-modal="true" aria-labelledby="loc-title" hidden>
    <div class="welcome-main">
      <h1 id="loc-title">Share your location</h1>
      <p class="welcome-line">The map can mark spots as near or far depending on your location.</p>
      <div class="loc-actions">
        <button type="button" class="welcome-enter" id="loc-enable">Enable location</button>
        <button type="button" class="loc-secondary" id="loc-default">Use Chanel's default</button>
        <p class="loc-note" id="loc-note" hidden></p>
      </div>
    </div>
  </div>
</div>

<script src="https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.js"></script>
<script>
const PLACES_DOC = __PLACES_JSON__;
const EVENTS_DOC = __EVENTS_JSON__;
</script>
<script>
(function(){
  const places = PLACES_DOC.places || [];
  const events = EVENTS_DOC.events || [];
  const placesById = Object.fromEntries(places.map(p => [p.id, p]));
  const base = PLACES_DOC.meta && PLACES_DOC.meta.base;
  const app = document.getElementById('app');
  const topbar = document.querySelector('.topbar');
  const listEl = document.getElementById('list');
  const eventsEl = document.getElementById('events');
  const searchEl = document.getElementById('search');
  const searchToggle = document.getElementById('search-toggle');
  const sheet = document.getElementById('sheet');
  const sheetBody = document.getElementById('sheet-body');
  const sheetBackdrop = document.getElementById('sheet-backdrop');
  const seg = document.getElementById('view-seg');
  const tabIndicator = document.querySelector('.tab-indicator');
  const tabs = Array.from(document.querySelectorAll('.seg .tab'));
  const eventsBtn = document.getElementById('events-btn');
  const filterBtn = document.getElementById('filter-btn');
  const filterShell = document.getElementById('filter-shell');
  const filterSheet = document.getElementById('filter-sheet');
  const filterBackdrop = document.getElementById('filter-backdrop');
  const aboutDrawer = document.getElementById('about-drawer');
  const aboutBackdrop = document.getElementById('about-backdrop');
  const openAboutBtn = document.getElementById('open-about');
  let filterOpen = false;
  let aboutOpen = false;
  const welcome = document.getElementById('welcome');
  const welcomeEnter = document.getElementById('welcome-enter');
  const WELCOME_KEY = 'toddler-spots-welcome';
  function openWelcome(){
    clearTimeout(hintWait);
    if (hintBusy) cancelHeaderHint();
    const bits = welcome.querySelectorAll('.welcome-emoji, .welcome-wordmark, .welcome-line, .welcome-enter, .welcome-credit');
    welcome.classList.remove('open');
    welcome.hidden = false;
    welcome.style.transition = 'none';
    bits.forEach((el) => { el.style.transition = 'none'; });
    void welcome.offsetWidth;
    welcome.style.removeProperty('transition');
    bits.forEach((el) => { el.style.removeProperty('transition'); });
    requestAnimationFrame(() => {
      welcome.classList.add('open');
      setTimeout(() => { if (welcome.classList.contains('open')) welcomeEnter.focus({ preventScroll: true }); }, 820);
    });
  }
  function closeWelcome(persist){
    if (persist) {
      try { localStorage.setItem(WELCOME_KEY, '1'); } catch (err) {}
    }
    const needsLoc = persist && !readLocChoice();
    welcome.classList.remove('open');
    setTimeout(() => {
      if (!welcome.classList.contains('open')) welcome.hidden = true;
      if (needsLoc) openLoc();
      else noteMapReadyForHint();
    }, 320);
  }

  const locScreen = document.getElementById('loc-screen');
  const locEnable = document.getElementById('loc-enable');
  const locNote = document.getElementById('loc-note');
  const LOC_KEY = 'toddler-spots-location';
  let home = { mode: 'default', lat: base ? base.lat : 39.812596, lng: base ? base.lng : -105.139898 };
  let homeMarker = null;

  function readLocChoice(){
    try {
      const raw = localStorage.getItem(LOC_KEY);
      if (!raw) return null;
      const v = JSON.parse(raw);
      if (v && v.mode === 'default') return v;
      if (v && v.mode === 'geo' && Number.isFinite(+v.lat) && Number.isFinite(+v.lng)) return v;
    } catch (err) {}
    return null;
  }
  function haversineMiles(lat1, lng1, lat2, lng2){
    const R = 3958.8;
    const dLat = (lat2 - lat1) * Math.PI / 180;
    const dLng = (lng2 - lng1) * Math.PI / 180;
    const a = Math.sin(dLat / 2) ** 2 + Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) * Math.sin(dLng / 2) ** 2;
    return 2 * R * Math.asin(Math.min(1, Math.sqrt(a)));
  }
  function estimateMinutes(miles){
    if (miles < 0.35) return 3;
    return Math.max(4, Math.round(miles * 2.15 + 1.5));
  }
  function isFar(p){
    return home.mode === 'geo' ? !!p._liveFar : !!p.farther_than_30min;
  }
  function driveMinutes(p){
    return home.mode === 'geo' ? (p._liveMinutes || 999) : (p.approx_drive_minutes || 999);
  }
  function effectiveDrive(p){
    if (home.mode === 'geo') return p._liveDrive || '';
    return p.drive_note || '';
  }
  function currentHomeLngLat(){
    if (home.mode === 'geo') return [home.lng, home.lat];
    return base ? [base.lng, base.lat] : null;
  }
  function moveHomePin(){
    const ll = currentHomeLngLat();
    if (!homeMarker || !ll) return;
    homeMarker.setLngLat(ll);
    const el = homeMarker.getElement();
    if (el) el.textContent = home.mode === 'geo' ? 'YOU' : 'HOME';
  }
  function computeLive(lat, lng){
    places.forEach(p => {
      const mi = haversineMiles(lat, lng, p.lat, p.lng);
      const mins = estimateMinutes(mi);
      const miles = Math.round(mi * 10) / 10;
      const far = mins > 30;
      p._liveMiles = miles;
      p._liveMinutes = mins;
      p._liveFar = far;
      p._liveDrive = '~' + mins + ' min from your location (~' + miles.toFixed(1) + ' mi straight-line)' + (far ? ' — FARTHER (>30 min)' : '');
    });
  }
  function syncLocationCopy(){
    const line = document.getElementById('about-home-line');
    const hint = document.getElementById('near-from');
    const legend = document.getElementById('legend-home');
    const label = base && base.label ? base.label : 'W 64th Ave & Ward Rd, Arvada';
    if (home.mode === 'geo') {
      if (line) line.innerHTML = 'Home base: <strong>your location</strong>. Spots are marked near or far from where you are. Aimed at a toddler ~20 months; prefer spots within ~30 minutes.';
      if (hint) hint.innerHTML = '<br>From your location';
      if (legend) legend.textContent = 'You';
    } else {
      if (line) line.innerHTML = 'Home base: <strong>' + escapeHtml(label) + '</strong>. Aimed at a toddler ~20 months; prefer spots within ~30 minutes.';
      if (hint) hint.innerHTML = '<br>From ' + escapeHtml(label);
      if (legend) legend.textContent = 'Home (80004)';
    }
  }
  function refreshNearFar(){
    places.forEach(p => {
      const m = markers[p.id];
      if (!m) return;
      const far = isFar(p);
      m.el.classList.toggle('far', far);
      m.el.classList.toggle('near', !far);
    });
    moveHomePin();
    syncLocationCopy();
    renderList();
    if (activeId && sheet.classList.contains('open')) {
      const p = places.find(x => x.id === activeId);
      if (p) openSheet(p);
    }
  }
  function setGeoHome(lat, lng){
    home = { mode: 'geo', lat: lat, lng: lng };
    computeLive(lat, lng);
    refreshNearFar();
  }
  function setDefaultHome(){
    home = { mode: 'default', lat: base ? base.lat : 39.812596, lng: base ? base.lng : -105.139898 };
    refreshNearFar();
  }
  function openLoc(){
    clearTimeout(hintWait);
    if (hintBusy) cancelHeaderHint();
    const bits = locScreen.querySelectorAll('h1, .welcome-line, .welcome-enter, .loc-secondary');
    locScreen.classList.remove('open');
    locScreen.hidden = false;
    locNote.hidden = true;
    locEnable.disabled = false;
    locEnable.textContent = 'Enable location';
    locScreen.style.transition = 'none';
    bits.forEach((el) => { el.style.transition = 'none'; });
    void locScreen.offsetWidth;
    locScreen.style.removeProperty('transition');
    bits.forEach((el) => { el.style.removeProperty('transition'); });
    requestAnimationFrame(() => {
      locScreen.classList.add('open');
      setTimeout(() => { if (locScreen.classList.contains('open')) locEnable.focus({ preventScroll: true }); }, 700);
    });
  }
  function closeLoc(){
    locScreen.classList.remove('open');
    setTimeout(() => {
      if (!locScreen.classList.contains('open')) locScreen.hidden = true;
      noteMapReadyForHint();
    }, 320);
  }
  function enableLocation(){
    if (!navigator.geolocation) {
      locNote.hidden = false;
      locNote.textContent = 'This browser can’t share location. You can use Chanel’s default.';
      return;
    }
    locEnable.disabled = true;
    locEnable.textContent = 'Finding you…';
    locNote.hidden = true;
    navigator.geolocation.getCurrentPosition(function(pos){
      const lat = pos.coords.latitude;
      const lng = pos.coords.longitude;
      try { localStorage.setItem(LOC_KEY, JSON.stringify({ mode: 'geo', lat: lat, lng: lng })); } catch (err) {}
      setGeoHome(lat, lng);
      locEnable.disabled = false;
      locEnable.textContent = 'Enable location';
      closeLoc();
    }, function(){
      locEnable.disabled = false;
      locEnable.textContent = 'Enable location';
      locNote.hidden = false;
      locNote.textContent = 'Location was blocked. Try again, or use Chanel’s default.';
    }, { enableHighAccuracy: false, timeout: 12000, maximumAge: 600000 });
  }
  function useChanelDefault(){
    try { localStorage.setItem(LOC_KEY, JSON.stringify({ mode: 'default' })); } catch (err) {}
    setDefaultHome();
    closeLoc();
  }


  let filter = 'all';
  let query = '';
  let currentTab = 'map';
  app.dataset.view = currentTab;
  let activeId = null;
  const markers = {};

  // Soft light basemap: OpenFreeMap Positron (MapLibre, no token)
  const map = new maplibregl.Map({
    container: 'map',
    style: 'https://tiles.openfreemap.org/styles/positron',
    center: base ? [base.lng, base.lat] : [-105.0, 39.74],
    zoom: 10.2,
    attributionControl: true
  });
  function escapeHtml(s){
    return String(s==null?'':s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  }
  function isFree(p){
    const c = (p.cost||'').toLowerCase();
    const tags = (p.tags||[]).map(t => String(t).toLowerCase());
    return tags.includes('free') || tags.includes('free-playground') || tags.includes('free-entry') ||
      /^free\b/.test(c) || c.includes('park free') || c === 'free';
  }
  function isIndoor(p){
    const tags = (p.tags||[]).map(t => String(t).toLowerCase());
    return tags.includes('indoor') || tags.includes('museum') || tags.includes('library') || tags.includes('bookstore');
  }
  function isHike(p){
    const tags = (p.tags||[]).map(t => String(t).toLowerCase());
    return tags.includes('toddler-hike');
  }
  function snippet(text, n){
    const t = String(text||'').trim();
    if (t.length <= n) return t;
    return t.slice(0, n).replace(/\s+\S*$/, '') + '…';
  }
  function mapsUrl(p){
    const q = encodeURIComponent(p.address || (p.name + ' Denver CO'));
    return 'https://www.google.com/maps/search/?api=1&query=' + q;
  }

  function badgesHtml(p){
    const badges = [];
    badges.push(isFar(p) ? '<span class="badge far">Farther</span>' : '<span class="badge near">Near</span>');
    if (isFree(p)) badges.push('<span class="badge free">Free</span>');
    if (isIndoor(p)) badges.push('<span class="badge indoor">Indoor</span>');
    if (isHike(p)) badges.push('<span class="badge hike">Hike</span>');
    return badges.join('');
  }

  let sheetReturn = 'map';
  function showSheet(){
    sheet.hidden = false;
    requestAnimationFrame(() => {
      sheet.classList.add('open');
      sheetBackdrop.classList.add('open');
    });
  }
  function openSheet(p, returnTo){
    sheetReturn = returnTo || 'map';
    activeId = p.id;
    Object.keys(markers).forEach(id => {
      markers[id].el.classList.toggle('active', id === p.id);
    });
    const links = (p.links||[]).slice(0, 4).map(l =>
      `<a class="ghost" href="${escapeHtml(l.url)}" target="_blank" rel="noopener">${escapeHtml(l.label||'Link')}</a>`
    ).join('');
    sheetBody.innerHTML = `
      <div class="sheet-badges">${badgesHtml(p)}</div>
      <h2 id="sheet-title">${escapeHtml(p.name)}</h2>
      <div class="sheet-section"><strong>Address</strong>${escapeHtml(p.address||'—')}</div>
      <div class="sheet-section"><strong>Why go</strong>${escapeHtml(p.why||'')}</div>
      <div class="sheet-section"><strong>Source</strong>${escapeHtml(p.source||'')}</div>
      ${effectiveDrive(p) ? `<div class="sheet-section"><strong>Drive</strong>${escapeHtml(effectiveDrive(p))}</div>` : ''}
      ${p.hours ? `<div class="sheet-section"><strong>Hours</strong>${escapeHtml(p.hours)}</div>` : ''}
      ${p.cost ? `<div class="sheet-section"><strong>Cost</strong>${escapeHtml(p.cost)}</div>` : ''}
      ${p.hike ? `<div class="sheet-section"><strong>Trail</strong>${escapeHtml(p.hike)}</div>` : ''}
      ${p.toddler_notes ? `<div class="sheet-section"><strong>Toddler tip</strong>${escapeHtml(p.toddler_notes)}</div>` : ''}
      <div class="sheet-actions">
        <a class="primary" href="${mapsUrl(p)}" target="_blank" rel="noopener">Directions</a>
        ${links}
        <button type="button" class="sheet-close-btn" id="sheet-close">Close</button>
      </div>`;
    showSheet();
    const closeBtn = document.getElementById('sheet-close');
    if (closeBtn) closeBtn.onclick = closeSheet;
    listEl.querySelectorAll('.place-card').forEach(el => el.classList.toggle('active', el.dataset.id === p.id));
  }

  function openEventSheet(ev){
    sheetReturn = currentTab;
    activeId = null;
    Object.keys(markers).forEach(id => markers[id].el.classList.remove('active'));
    const place = ev.place_id && placesById[ev.place_id];
    const venue = ev.place || (place && place.name) || 'Location to be confirmed';
    const when = eventDateLabel(ev) + ' · ' + eventTimeLabel(ev);
    const page = ev.link
      ? `<a class="ghost" href="${escapeHtml(ev.link)}" target="_blank" rel="noopener">Event page</a>`
      : '';
    sheetBody.innerHTML = `
      <h2 id="sheet-title">${escapeHtml(ev.title)}</h2>
      <a class="cal-add sheet-cal" href="${calendarUrl(ev)}" target="_blank" rel="noopener">Add to calendar</a>
      <div class="sheet-section"><strong>When</strong>${escapeHtml(when)}</div>
      <div class="sheet-section"><strong>Where</strong>${escapeHtml(venue)}</div>
      ${ev.drive_note ? `<div class="sheet-section"><strong>Drive</strong>${escapeHtml(ev.drive_note)}</div>` : ''}
      <div class="sheet-section"><strong>Details</strong>${escapeHtml(ev.note || 'Family-friendly event details coming soon.')}</div>
      ${ev.source ? `<div class="sheet-section"><strong>Source</strong>${escapeHtml(ev.source)}</div>` : ''}
      <div class="sheet-actions">
        ${place ? '<button type="button" class="primary" id="event-show-map">Show on map</button>' : ''}
        ${page}
      </div>`;
    const show = document.getElementById('event-show-map');
    if (show && place) show.onclick = () => {
      const origin = sheetReturn;
      closeSheet();
      setTab('map');
      openSheet(place, origin);
      flyTo(place);
    };
    showSheet();
  }

  function closeSheet(){
    sheet.classList.remove('open');
    sheetBackdrop.classList.remove('open');
    activeId = null;
    Object.keys(markers).forEach(id => markers[id].el.classList.remove('active'));
    setTimeout(() => { if (!sheet.classList.contains('open')) sheet.hidden = true; }, 320);
  }
  sheetBackdrop.addEventListener('click', closeSheet);
  document.getElementById('sheet-back').addEventListener('click', () => {
    const dest = sheetReturn;
    closeSheet();
    if (dest && dest !== 'map') setTab(dest);
  });
  document.getElementById('sheet-dismiss').addEventListener('click', closeSheet);

  function flyTo(p){
    const pad = window.matchMedia('(min-width: 768px)').matches
      ? { top: 96, bottom: 48, left: 40, right: 40 }
      : { top: 80, bottom: 200, left: 40, right: 40 };
    map.flyTo({ center: [p.lng, p.lat], zoom: Math.max(map.getZoom(), 13), essential: true, padding: pad });
  }

  // Markers after style loads
  map.on('load', () => {
    const bounds = new maplibregl.LngLatBounds();

    places.forEach(p => {
      const el = document.createElement('div');
      el.className = 'pin ' + (isFar(p) ? 'far' : 'near');
      el.title = p.name;
      el.setAttribute('role', 'button');
      el.setAttribute('aria-label', p.name);
      el.addEventListener('click', (e) => {
        e.stopPropagation();
        openSheet(p, 'map');
        flyTo(p);
      });
      const marker = new maplibregl.Marker({ element: el, anchor: 'center' })
        .setLngLat([p.lng, p.lat])
        .addTo(map);
      markers[p.id] = { marker, el, place: p };
      bounds.extend([p.lng, p.lat]);
    });

    const homeLL = currentHomeLngLat();
    if (homeLL) {
      const homeEl = document.createElement('div');
      homeEl.className = 'home-pin';
      homeEl.textContent = home.mode === 'geo' ? 'YOU' : 'HOME';
      homeMarker = new maplibregl.Marker({ element: homeEl, anchor: 'center' })
        .setLngLat(homeLL)
        .addTo(map);
      bounds.extend(homeLL);
    }

    if (!bounds.isEmpty()) {
      const pad = window.matchMedia('(min-width: 768px)').matches
        ? { top: 96, bottom: 48, left: 40, right: 40 }
        : { top: 100, bottom: 100, left: 40, right: 40 };
      map.fitBounds(bounds, { padding: pad, maxZoom: 11.5 });
    }
    setTimeout(() => map.resize(), 200);
  });

  function matchesQuery(p, q){
    if (!q) return true;
    const blob = [p.name, p.address, p.why, p.source, p.toddler_notes, p.hike, ...(p.tags||[])].join(' ').toLowerCase();
    return blob.includes(q);
  }
  function passesFilter(p){
    if (filter === 'near') return !isFar(p);
    if (filter === 'far') return isFar(p);
    if (filter === 'free') return isFree(p);
    if (filter === 'indoor') return isIndoor(p);
    if (filter === 'hike') return isHike(p);
    return true;
  }



  function renderList(){
    const sorted = places.slice().sort((a,b)=> driveMinutes(a)-driveMinutes(b));
    const filtered = sorted.filter(p => passesFilter(p) && matchesQuery(p, query));
    if (!filtered.length) {
      listEl.innerHTML = '<div class="empty">No spots match.<br>Try another filter or clear search.</div>';
    } else {
      listEl.innerHTML = filtered.map(p => `
        <article class="place-card${activeId===p.id?' active':''}" data-id="${escapeHtml(p.id)}" role="button" tabindex="0">
          <h3>${escapeHtml(p.name)}</h3>
          <p class="card-line">${escapeHtml(placeKeyLine(p))}</p>
        </article>`).join('');
    }

    listEl.querySelectorAll('.place-card').forEach(el => {
      const go = () => {
        const p = places.find(x => x.id === el.dataset.id);
        if (!p) return;
        const origin = currentTab;
        setTab('map');
        openSheet(p, origin);
        flyTo(p);
      };
      el.addEventListener('click', go);
      el.addEventListener('keydown', e => {
        if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); go(); }
      });
    });

    // Toggle markers
    places.forEach(p => {
      const show = passesFilter(p) && matchesQuery(p, query);
      const m = markers[p.id];
      if (!m) return;
      m.el.style.display = show ? '' : 'none';
    });
  }

  function shortDate(key){
    const d = new Date(key + 'T12:00:00Z');
    return new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric', timeZone: 'UTC' }).format(d);
  }
  function longDate(key){
    const d = new Date(key + 'T12:00:00Z');
    const parts = new Intl.DateTimeFormat('en-US', { weekday: 'short', month: 'short', day: 'numeric', timeZone: 'UTC' }).formatToParts(d);
    const values = Object.fromEntries(parts.filter(part => part.type !== 'literal').map(part => [part.type, part.value]));
    return `${values.weekday} ${values.month} ${values.day}`;
  }
  function eventDateLabel(e){
    return e.end_date && e.end_date !== e.date ? shortDate(e.date) + '–' + shortDate(e.end_date) : shortDate(e.date);
  }
  function eventKeyLine(e){
    const date = eventDateLabel(e);
    const time = String(e.time || '').trim();
    if (time && !/confirm/i.test(time)) return date + ' · ' + time;
    return date;
  }
  function eventTimeLabel(e){
    const time = String(e.time || '').trim();
    return time && !/confirm/i.test(time) ? time : 'Time to be confirmed';
  }
  function placeKeyLine(p){
    const note = effectiveDrive(p);
    if (note) return note;
    const mins = driveMinutes(p);
    if (mins && mins < 900) return '~' + mins + ' min';
    return '';
  }
  function eventDateKeys(e){
    const keys = [];
    const end = e.end_date || e.date;
    let d = new Date(e.date + 'T12:00:00Z');
    const last = new Date(end + 'T12:00:00Z');
    while (d <= last) {
      keys.push(d.toISOString().slice(0,10));
      d.setUTCDate(d.getUTCDate() + 1);
    }
    return keys;
  }
  function pad2(n){ return String(n).padStart(2, '0'); }
  function addDays(iso, n){
    const d = new Date(iso + 'T12:00:00Z');
    d.setUTCDate(d.getUTCDate() + n);
    return d.toISOString().slice(0, 10);
  }
  function readClock(text, inherit){
    const m = String(text || '').trim().match(/^(\d{1,2})(?::(\d{2}))?\s*(a\.?m\.?|p\.?m\.?)?$/i);
    if (!m) return null;
    let h = parseInt(m[1], 10);
    const min = m[2] ? parseInt(m[2], 10) : 0;
    if (h > 23 || min > 59) return null;
    let mer = m[3] ? m[3].replace(/\./g, '').toUpperCase() : (inherit || '');
    if (!mer) return { h: h, min: min, mer: '', minutes: null };
    if (h > 12) mer = '';
    if (mer === 'PM' && h < 12) h += 12;
    if (mer === 'AM' && h === 12) h = 0;
    return { h: h, min: min, mer: mer, minutes: h * 60 + min };
  }
  function withMer(text, mer){
    const c = readClock(text, mer);
    return c && c.minutes != null ? c : null;
  }
  function resolvePair(aRaw, bRaw){
    let a = readClock(aRaw, '');
    let b = readClock(bRaw, '');
    if (!a || !b) return null;
    if (!a.mer && b.mer) {
      const same = withMer(aRaw, b.mer);
      const other = withMer(aRaw, b.mer === 'PM' ? 'AM' : 'PM');
      a = (same && b.minutes != null && same.minutes < b.minutes) ? same : (other || same);
    }
    if (a && !b.mer && a.mer) {
      const same = withMer(bRaw, a.mer);
      const other = withMer(bRaw, a.mer === 'AM' ? 'PM' : 'AM');
      b = (same && a.minutes != null && same.minutes > a.minutes) ? same : (other || same);
    }
    if (a && a.minutes == null) a = withMer(aRaw, 'PM');
    if (b && b.minutes == null) b = withMer(bRaw, 'PM');
    if (!a || !b || a.minutes == null || b.minutes == null) return null;
    return [a, b];
  }
  function stamp(date, clock){
    return date.replace(/-/g, '') + 'T' + pad2(clock.h) + pad2(clock.min) + '00';
  }
  function calendarUrl(e){
    const startDate = e.date;
    const endDate = e.end_date || e.date;
    const time = String(e.time || '');
    const rangeRe = /(\d{1,2}(?::\d{2})?\s*(?:a\.?m\.?|p\.?m\.?)?)\s*[–—-]\s*(\d{1,2}(?::\d{2})?\s*(?:a\.?m\.?|p\.?m\.?)?)/gi;
    const ranges = [];
    let rm;
    while ((rm = rangeRe.exec(time))) ranges.push(rm);
    let dates = '';
    if (ranges.length) {
      const first = resolvePair(ranges[0][1], ranges[0][2]);
      if (first) {
        let endClock = first[1];
        let endD = startDate;
        if (endDate !== startDate && ranges.length > 1) {
          const last = resolvePair(ranges[ranges.length - 1][1], ranges[ranges.length - 1][2]);
          if (last) { endClock = last[1]; endD = endDate; }
        }
        const start = stamp(startDate, first[0]);
        let end = stamp(endD, endClock);
        if (end <= start) end = stamp(addDays(endD, 1), endClock);
        dates = start + '/' + end;
      }
    }
    if (!dates) {
      const clocks = [];
      const clockRe = /\b(\d{1,2}:\d{2}\s*(?:a\.?m\.?|p\.?m\.?)?)\b/gi;
      let cm;
      while ((cm = clockRe.exec(time))) clocks.push(cm[1]);
      if (clocks.length) {
        const a = readClock(clocks[0], /[ap]\.?m/i.test(clocks[0]) ? '' : 'PM');
        let b = clocks.length > 1 ? readClock(clocks[clocks.length - 1], /[ap]\.?m/i.test(clocks[clocks.length - 1]) ? '' : 'PM') : null;
        if (a && a.minutes != null) {
          if (!b || b.minutes == null || b.minutes <= a.minutes) {
            const mins = a.minutes + 120;
            b = { h: Math.floor(mins / 60) % 24, min: mins % 60 };
            dates = stamp(startDate, a) + '/' + stamp(addDays(startDate, Math.floor(mins / 1440)), b);
          } else {
            dates = stamp(startDate, a) + '/' + stamp(endDate !== startDate ? endDate : startDate, b);
          }
        }
      }
    }
    if (!dates) dates = startDate.replace(/-/g, '') + '/' + addDays(endDate, 1).replace(/-/g, '');
    const details = [e.note, e.time, e.source].filter(Boolean).join('\n');
    return 'https://calendar.google.com/calendar/render?action=TEMPLATE'
      + '&text=' + encodeURIComponent(e.title || 'Event')
      + '&dates=' + dates
      + '&details=' + encodeURIComponent(details)
      + '&location=' + encodeURIComponent(e.place || '')
      + '&ctz=America%2FDenver';
  }
  function eventStartMinutes(e){
    const time = String(e.time || '');
    const first = time.match(/(\d{1,2}(?::\d{2})?\s*(?:a\.?m\.?|p\.?m\.?)?)/i);
    if (!first) return Number.MAX_SAFE_INTEGER;
    const hasAm = /a\.?m\.?/i.test(time);
    const hasPm = /p\.?m\.?/i.test(time);
    const inherit = hasAm && !hasPm ? 'AM' : 'PM';
    const clock = readClock(first[1], inherit);
    return clock && clock.minutes != null ? clock.minutes : Number.MAX_SAFE_INTEGER;
  }
  function renderEvents(){
    const today = new Intl.DateTimeFormat('en-CA', { year: 'numeric', month: '2-digit', day: '2-digit', timeZone: 'America/Denver' }).format(new Date());
    // Keep an event visible while any part of its date range is still upcoming,
    // but do not render already-past day groups.
    const upcoming = events.filter(e => String(e.end_date || e.date) >= today);
    const groups = {};
    upcoming.forEach(e => eventDateKeys(e).filter(day => day >= today).forEach(day => {
      (groups[day] ||= []).push(e);
    }));
    const days = Object.keys(groups).sort();
    if (!days.length) { eventsEl.innerHTML = '<div class="empty">No upcoming events listed yet.</div>'; return; }
    eventsEl.innerHTML = days.map(day => `
      <section class="event-day" data-day="${day}" aria-labelledby="event-day-${day}">
        <h2 class="event-day-heading" id="event-day-${day}">${escapeHtml(longDate(day))}<span>${groups[day].length} event${groups[day].length === 1 ? '' : 's'}</span></h2>
        ${groups[day].sort((a, b) => eventStartMinutes(a) - eventStartMinutes(b) || String(a.date).localeCompare(String(b.date)) || String(a.title).localeCompare(String(b.title))).map(e => {
          const linked = e.place_id && placesById[e.place_id];
          const venue = e.place || (linked && linked.name) || 'Location to be confirmed';
          return `<article class="event-card${linked?' linked':''}" data-event-id="${escapeHtml(e.id)}"${linked?` data-place-id="${escapeHtml(e.place_id)}"`:''} role="button" tabindex="0">
            <div class="event-card-top">
              <h3>${escapeHtml(e.title)}</h3>
              <a class="cal-add" href="${calendarUrl(e)}" target="_blank" rel="noopener">Add to calendar</a>
            </div>
            <p class="event-place">${escapeHtml(venue)}</p>
            <p class="event-note">${escapeHtml(snippet(e.note || 'Family-friendly event details coming soon.', 120))}</p>
            <div class="event-meta"><span>${escapeHtml(eventDateLabel(e))}</span><span class="event-time">${escapeHtml(eventTimeLabel(e))}</span></div>
          </article>`;
        }).join('')}
      </section>`).join('');
    eventsEl.querySelectorAll('.event-card[data-event-id]').forEach(el => {
      const go = () => {
        const ev = events.find(item => item.id === el.dataset.eventId);
        if (!ev) return;
        const place = ev.place_id && placesById[ev.place_id];
        const desktop = window.matchMedia('(min-width: 768px)').matches;
        if (desktop && place) {
          const origin = currentTab;
          setTab('map');
          openSheet(place, origin);
          flyTo(place);
          return;
        }
        openEventSheet(ev);
      };
      el.addEventListener('click', e => { if (!e.target.closest('a')) go(); });
      el.addEventListener('keydown', e => { if ((e.key === 'Enter' || e.key === ' ') && !e.target.closest('a')) { e.preventDefault(); go(); } });
    });
  }

  function moveTabIndicator(name, immediate = false){
    const selected = tabs.find(t => t.dataset.tab === name);
    if (!selected || !tabIndicator || !seg || name === 'events') return;
    if (immediate) tabIndicator.style.transition = 'none';
    seg.style.setProperty('--tab-left', `${selected.offsetLeft}px`);
    seg.style.setProperty('--tab-width', `${selected.offsetWidth}px`);
    if (immediate) {
      requestAnimationFrame(() => { tabIndicator.style.removeProperty('transition'); });
    }
  }

  function paintFilterButton(){
    const on = filterOpen || filter !== 'all';
    filterBtn.classList.toggle('on', on);
    filterBtn.setAttribute('aria-pressed', on ? 'true' : 'false');
    filterBtn.setAttribute('aria-expanded', filterOpen ? 'true' : 'false');
  }
  function openFilterSheet(){
    filterOpen = true;
    filterSheet.hidden = false;
    filterBackdrop.hidden = false;
    requestAnimationFrame(() => {
      filterSheet.classList.add('open');
      filterBackdrop.classList.add('open');
    });
    paintFilterButton();
  }
  function closeFilterSheet(){
    filterOpen = false;
    filterSheet.classList.remove('open');
    filterBackdrop.classList.remove('open');
    paintFilterButton();
    setTimeout(() => {
      if (!filterOpen) { filterSheet.hidden = true; filterBackdrop.hidden = true; }
    }, 320);
  }
  let aboutTimer = 0;
  function openAbout(){
    aboutOpen = true;
    clearTimeout(aboutTimer);
    aboutDrawer.hidden = false;
    aboutBackdrop.hidden = false;
    aboutDrawer.classList.remove('open');
    aboutBackdrop.classList.remove('open');
    openAboutBtn.setAttribute('aria-expanded', 'true');
    void aboutDrawer.offsetWidth;
    aboutDrawer.classList.add('open');
    aboutBackdrop.classList.add('open');
  }
  function closeAbout(){
    if (!aboutOpen && !aboutDrawer.classList.contains('open')) return;
    aboutOpen = false;
    aboutDrawer.classList.remove('open');
    aboutBackdrop.classList.remove('open');
    openAboutBtn.setAttribute('aria-expanded', 'false');
    clearTimeout(aboutTimer);
    aboutTimer = setTimeout(() => {
      if (!aboutOpen) { aboutDrawer.hidden = true; aboutBackdrop.hidden = true; }
    }, 520);
  }

  function replayFilterShellAnimation(show){
    filterShell.classList.remove('is-shown', 'is-away');
    // Flush the collapsed/expanded state before adding the same animation
    // class again, otherwise the browser may keep the one-shot animation at
    // its finished state and skip the next transition.
    void filterShell.offsetWidth;
    filterShell.classList.add(show ? 'is-shown' : 'is-away');
  }

  function setTab(name){
    const wasEvents = currentTab === 'events';
    currentTab = name;
    app.dataset.view = name;
    const mapActive = name === 'map';
    const eventsActive = name === 'events';
    if (eventsActive && filterOpen) closeFilterSheet();
    if (eventsActive !== wasEvents) replayFilterShellAnimation(!eventsActive);
    filterShell.setAttribute('aria-hidden', eventsActive ? 'true' : 'false');
    filterBtn.tabIndex = eventsActive ? -1 : 0;
    const desktopLayout = window.matchMedia('(min-width: 768px)').matches;
    const showTopbar = mapActive || desktopLayout;
    topbar.hidden = !showTopbar;
    topbar.setAttribute('aria-hidden', showTopbar ? 'false' : 'true');
    if (mapActive) noteMapReadyForHint();
    else {
      clearTimeout(hintWait);
      if (hintBusy) cancelHeaderHint();
    }
    const viewOn = name === 'map' || name === 'list';
    tabs.forEach(t => {
      const on = viewOn && t.dataset.tab === name;
      t.classList.toggle('active', on);
      t.setAttribute('aria-selected', on ? 'true' : 'false');
    });
    seg.classList.toggle('idle', !viewOn);
    eventsBtn.classList.toggle('on', name === 'events');
    eventsBtn.setAttribute('aria-pressed', name === 'events' ? 'true' : 'false');
    if (viewOn) moveTabIndicator(name);
    document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
    if (name === 'list') document.getElementById('panel-list').classList.add('active');
    if (name === 'events') document.getElementById('panel-events').classList.add('active');
    setTimeout(() => map.resize(), 50);
  }

  tabs.forEach(btn => {
    btn.addEventListener('click', () => setTab(btn.dataset.tab));
  });
  eventsBtn.addEventListener('click', () => {
    const desktop = window.matchMedia('(min-width: 768px)').matches;
    if (desktop && currentTab === 'events') setTab('list');
    else setTab('events');
  });
  filterBtn.addEventListener('click', () => {
    if (currentTab === 'events' || filterShell.classList.contains('is-away')) return;
    filterOpen ? closeFilterSheet() : openFilterSheet();
  });
  document.getElementById('filter-close').addEventListener('click', closeFilterSheet);
  filterBackdrop.addEventListener('click', closeFilterSheet);
  openAboutBtn.addEventListener('click', openAbout);
  document.getElementById('about-close').addEventListener('click', closeAbout);
  aboutBackdrop.addEventListener('click', closeAbout);
  document.addEventListener('keydown', (e) => {
    if (e.key !== 'Escape') return;
    if (!welcome.hidden) closeWelcome(false);
    else if (locScreen && !locScreen.hidden) { if (readLocChoice()) closeLoc(); }
    else if (aboutOpen) closeAbout();
    else if (filterOpen) closeFilterSheet();
  });

  const HINT_KEY = 'toddler-spots-header-hint';
  const HINT_LABEL = 'Click here for more info';
  const BRAND_LABEL = 'Toddler Spots';
  let hintWait = 0;
  let hintPhase = 0;
  let hintBusy = false;
  let hintGen = 0;
  function brandTextEl(){ return openAboutBtn.querySelector('.brand-text'); }
  function hintSeen(){
    try { return localStorage.getItem(HINT_KEY) === '1'; } catch (err) { return true; }
  }
  function markHintSeen(){
    try { localStorage.setItem(HINT_KEY, '1'); } catch (err) {}
  }
  function mapReadyForHint(){
    return !!(welcome.hidden && locScreen.hidden && !topbar.hidden && currentTab === 'map' && !topbar.classList.contains('search-focused'));
  }
  function restoreBrandTitle(){
    const text = brandTextEl();
    const pill = openAboutBtn;
    text.classList.remove('is-hint');
    text.textContent = BRAND_LABEL;
    text.style.opacity = '';
    pill.classList.remove('showing-hint');
    pill.style.width = '';
    pill.style.overflow = '';
    pill.style.transition = '';
  }
  function cancelHeaderHint(){
    hintGen++;
    hintBusy = false;
    clearTimeout(hintPhase);
    restoreBrandTitle();
  }
  function noteMapReadyForHint(){
    if (hintSeen() || hintBusy) return;
    clearTimeout(hintWait);
    hintWait = setTimeout(runHeaderHint, 300);
  }
  function measureBrandWidth(mutate){
    const pill = openAboutBtn;
    const locked = pill.style.width;
    const prevTransition = pill.style.transition;
    pill.style.transition = 'none';
    mutate();
    const w = Math.ceil(pill.getBoundingClientRect().width);
    pill.style.width = locked;
    void pill.offsetWidth;
    pill.style.transition = prevTransition;
    return w;
  }
  function collapsedBrandWidth(){
    const text = brandTextEl();
    const pill = openAboutBtn;
    const locked = pill.style.width;
    const prevTransition = pill.style.transition;
    pill.style.transition = 'none';
    text.style.display = 'none';
    pill.style.width = 'max-content';
    const w = Math.ceil(pill.getBoundingClientRect().width);
    text.style.display = '';
    pill.style.width = locked;
    void pill.offsetWidth;
    pill.style.transition = prevTransition;
    return w;
  }
  function naturalBrandWidth(){
    return measureBrandWidth(() => {
      openAboutBtn.style.width = 'max-content';
    });
  }
  function runHeaderHint(){
    if (hintSeen() || hintBusy) return;
    if (!mapReadyForHint()) return;
    const text = brandTextEl();
    const pill = openAboutBtn;
    const gen = ++hintGen;
    hintBusy = true;
    function alive(){ return gen === hintGen && mapReadyForHint(); }
    function stop(){
      if (gen !== hintGen) return;
      cancelHeaderHint();
      if (!hintSeen()) noteMapReadyForHint();
    }
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      text.textContent = HINT_LABEL;
      text.classList.add('is-hint');
      markHintSeen();
      hintPhase = setTimeout(() => {
        if (!alive()) { stop(); return; }
        hintBusy = false;
        restoreBrandTitle();
      }, 3000);
      return;
    }
    const startW = Math.ceil(pill.getBoundingClientRect().width);
    const small = collapsedBrandWidth();
    pill.style.overflow = 'hidden';
    pill.style.transition = 'none';
    pill.style.width = startW + 'px';
    text.style.opacity = '1';
    void pill.offsetWidth;
    pill.style.transition = '';
    text.style.opacity = '0';
    pill.style.width = small + 'px';
    hintPhase = setTimeout(() => {
      if (!alive()) { stop(); return; }
      text.textContent = HINT_LABEL;
      text.classList.add('is-hint');
      pill.classList.add('showing-hint');
      const target = naturalBrandWidth();
      pill.style.transition = 'none';
      pill.style.width = small + 'px';
      void pill.offsetWidth;
      pill.style.transition = '';
      text.style.opacity = '1';
      pill.style.width = target + 'px';
      markHintSeen();
      hintPhase = setTimeout(() => {
        if (!alive()) { stop(); return; }
        text.style.opacity = '0';
        pill.style.width = small + 'px';
        hintPhase = setTimeout(() => {
          if (!alive()) { stop(); return; }
          text.classList.remove('is-hint');
          text.textContent = BRAND_LABEL;
          pill.classList.remove('showing-hint');
          const back = naturalBrandWidth();
          pill.style.transition = 'none';
          pill.style.width = small + 'px';
          void pill.offsetWidth;
          pill.style.transition = '';
          text.style.opacity = '1';
          pill.style.width = back + 'px';
          hintPhase = setTimeout(() => {
            if (gen !== hintGen) return;
            hintBusy = false;
            pill.style.width = '';
            pill.style.overflow = '';
            text.style.opacity = '';
          }, 360);
        }, 340);
      }, 3320);
    }, 340);
  }

  welcomeEnter.addEventListener('click', () => closeWelcome(true));
  document.getElementById('welcome-replay').addEventListener('click', openWelcome);
  document.getElementById('loc-edit').addEventListener('click', () => {
    closeAbout();
    setTimeout(openLoc, 180);
  });
  locEnable.addEventListener('click', enableLocation);
  document.getElementById('loc-default').addEventListener('click', useChanelDefault);
  moveTabIndicator(currentTab, true);
  try {
    if (localStorage.getItem(WELCOME_KEY) !== '1') openWelcome();
    else if (!readLocChoice()) openLoc();
    else noteMapReadyForHint();
  } catch (err) {
    openWelcome();
  }
  (function restoreLocation(){
    const stored = readLocChoice();
    if (stored && stored.mode === 'geo') setGeoHome(+stored.lat, +stored.lng);
    else syncLocationCopy();
  })();

  function setFilter(f){
    filter = f;
    document.querySelectorAll('.filter-chip').forEach(b => {
      const on = b.dataset.filter === f;
      b.classList.toggle('active', on);
      b.setAttribute('aria-selected', on ? 'true' : 'false');
    });
    renderList();
    paintFilterButton();
    if (filterOpen) closeFilterSheet();
  }

  document.querySelectorAll('.filter-chip').forEach(btn => {
    btn.addEventListener('click', () => setFilter(btn.dataset.filter));
  });

  let searchTimer;
  function openSearch(){
    clearTimeout(hintWait);
    if (hintBusy) cancelHeaderHint();
    searchToggle.classList.add('is-active');
    searchToggle.setAttribute('aria-expanded', 'true');
    searchToggle.setAttribute('aria-pressed', 'true');
    /* Focus in the tap, before the bar grows, so iOS opens the keyboard. */
    searchEl.focus({ preventScroll: true });
    topbar.classList.add('search-focused');
  }
  function closeSearchIfEmpty(){
    if (!searchEl.value.trim()) {
      topbar.classList.remove('search-focused');
      searchToggle.classList.remove('is-active');
      searchToggle.setAttribute('aria-expanded', 'false');
      searchToggle.setAttribute('aria-pressed', 'false');
      noteMapReadyForHint();
    }
  }
  searchToggle.addEventListener('pointerdown', () => {
    searchToggle.classList.add('is-active');
  });
  searchToggle.addEventListener('click', openSearch);
  searchEl.addEventListener('focus', () => {
    topbar.classList.add('search-focused');
    searchToggle.setAttribute('aria-expanded', 'true');
  });
  searchEl.addEventListener('blur', closeSearchIfEmpty);
  searchEl.addEventListener('input', () => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => {
      query = searchEl.value.trim().toLowerCase();
      renderList();
    }, 100);
  });

  renderEvents();

  // Wait for markers then first render
  map.on('load', () => renderList());
  // Also render list HTML immediately (markers toggle later)
  renderList();

  window.addEventListener('resize', () => {
    map.resize();
    if (currentTab === 'map' || currentTab === 'list') moveTabIndicator(currentTab, true);
  });
})();
</script>
</body>
</html>
'''

def source_link(label, url):
    """Return a safe external link for a source metadata field."""
    if not isinstance(url, str) or not url.startswith(("https://", "http://")):
        return ""
    return (f'<a href="{html.escape(url, quote=True)}" target="_blank" '
            f'rel="noopener">{html.escape(label)}</a>')


def sources_html(meta):
    """Render the About source list directly from meta.sources_scrubbed."""
    fields = (("instagram", "Instagram"), ("facebook", "Facebook"),
              ("newsletter", "newsletter"), ("tiktok", "TikTok"))
    rows = []
    for source in meta.get("sources_scrubbed", []):
        name = str(source.get("name", "")).strip()
        if not name:
            continue
        available = [(field, label, source.get(field)) for field, label in fields
                     if source_link(label, source.get(field))]
        if available:
            # Make the account name itself the primary social link, then expose
            # additional accounts/newsletters without hard-coding the list.
            primary_field, _, primary_url = next(
                (item for item in available if item[0] == "instagram"), available[0]
            )
            primary = source_link(name, primary_url)
            extras = [source_link(label, url) for field, label, url in available
                      if field != primary_field]
            rendered = primary + (" (" + " · ".join(extras) + ")" if extras else "")
        else:
            rendered = html.escape(name)
        rows.append(f"          <li>{rendered}</li>")
    return "\n".join(rows)

def build():
    doc = json.loads(DATA.read_text())
    events_doc = json.loads(EVENTS_DATA.read_text())
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
    OUT_EVENTS.write_text(json.dumps(events_doc, indent=2, ensure_ascii=False) + "\n")
    places_json = json.dumps(doc, ensure_ascii=False)
    html_out = (TEMPLATE
        .replace("__SOURCES_HTML__", sources_html(doc.get("meta", {})))
        .replace("__PLACES_JSON__", places_json)
        .replace("__EVENTS_JSON__", json.dumps(events_doc, ensure_ascii=False))
        .replace("__UPDATED__", str(doc.get("meta", {}).get("updated", "")))
        .replace("__COUNT__", str(len(doc.get("places", []))))
        .replace("__EVENT_COUNT__", str(len(events_doc.get("events", []))))
        .replace("__BASE_LABEL__", str(doc.get("meta", {}).get("base", {}).get("label", "home")))
    )
    OUT_HTML.write_text(html_out)

    lines = [
        f"# {doc['meta'].get('title', 'Toddler outing map')}",
        "",
        f"Updated: {doc['meta'].get('updated')}  ",
        f"Base: {doc['meta']['base'].get('label')}  ",
        f"Audience: {doc['meta'].get('audience')}  ",
        f"Places: {len(doc.get('places', []))}",
        "",
        "Each pin has a why-note from a named social/newsletter source. Drive times are rough estimates.",
        "",
    ]
    for p in sorted(doc["places"], key=lambda x: x.get("approx_drive_minutes", 999)):
        flag = "FARTHER" if p.get("farther_than_30min") else "near"
        lines += [
            f"## {p['name']} ({flag})",
            "",
            f"- **Address:** {p.get('address','')}",
            f"- **Drive:** {p.get('drive_note','')}",
            f"- **Why:** {p.get('why','')}",
            f"- **Source:** {p.get('source','')}",
            f"- **Hours:** {p.get('hours','')}",
            f"- **Cost:** {p.get('cost','')}",
            f"- **Toddler tip:** {p.get('toddler_notes','')}",
        ]
        if p.get("hike"):
            lines.append(f"- **Trail:** {p['hike']}")
        for l in p.get("links") or []:
            lines.append(f"- [{l.get('label', l.get('url'))}]({l.get('url')})")
        lines.append("")
    OUT_MD.write_text("\n".join(lines) + "\n")

    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    sources = DOCS_DIR / "SOURCES.md"
    sources_backup = sources.read_text() if sources.exists() else None
    for name in ("index.html", "places.json", "events.json", "INDEX.md"):
        src = OUT_DIR / name
        if src.exists():
            shutil.copy2(src, DOCS_DIR / name)
    icons_src = DOCS_DIR / "icons"
    if icons_src.exists():
        shutil.copytree(icons_src, OUT_DIR / "icons", dirs_exist_ok=True)
    for name in ("favicon.png", "apple-touch-icon.png", "site.webmanifest"):
        src = DOCS_DIR / name
        if src.exists():
            shutil.copy2(src, OUT_DIR / name)
    if sources_backup is not None:
        sources.write_text(sources_backup)
        (OUT_DIR / "SOURCES.md").write_text(sources_backup)

    print(f"Wrote {OUT_HTML}")
    print(f"Wrote {OUT_JSON}")
    print(f"Wrote {OUT_MD}")
    print(f"Events: {len(events_doc.get('events', []))}")
    print(f"Synced docs/spots/ for GitHub Pages")
    print(f"Places: {len(doc['places'])}")

if __name__ == "__main__":
    build()
