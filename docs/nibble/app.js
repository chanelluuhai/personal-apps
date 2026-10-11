/* Nibble & Sip: static feed of toddler food ideas (data/feed.json),
   picks scored in the browser against data/profile.json. */
(function () {
  'use strict';
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
  const app = $('#app');
  const SAVED_KEY = 'nibble-sip-saved';
  const CHECK_KEY = 'nibble-sip-checked';
  const WELCOME_KEY = 'nibble-sip-welcome';

  const CATS = [
    { id: 'all', label: 'All ideas', hint: 'Show everything', dot: '#9E6656' },
    { id: 'pasta', label: 'Pasta & noodles', hint: 'Shapes he can hold', icon: 'icons/clay-pizza.webp', dot: '#B78272' },
    { id: 'finger', label: 'Finger food', hint: 'Bites, pancakes, dips', icon: 'icons/clay-bread.webp', dot: '#A8906F' },
    { id: 'sweet', label: 'Sweets & snacks', hint: 'Treats and small bites', icon: 'icons/clay-sweet.webp', dot: '#B9939A' },
    { id: 'meal', label: 'Meals', hint: 'Plates and bowls', icon: 'icons/clay-plate.webp', dot: '#8794A8' },
  ];
  const TIMES = [
    { id: 'quick', label: 'Quick', hint: '20 min or less, no-bake or no-cook', dot: '#9E6656' },
    { id: 'long', label: 'Longer cook', hint: 'Says it takes more than 20 min', dot: '#87534A' },
    { id: 'prep', label: 'Meal prep', hint: 'Make-ahead, batch or freezer-friendly', dot: '#9AA383' },
  ];
  const SRCS = [
    { id: 'all', label: 'All sources', hint: 'Creators and recipe sites', dot: '#9E6656' },
    { id: 'creators', label: 'Creators', hint: 'Their Instagram, TikTok, YouTube and blog posts', dot: '#B78272' },
    { id: 'sites', label: 'Recipe sites', hint: 'Toddler recipe websites', dot: '#8794A8' },
  ];
  const SRC_LABEL = Object.fromEntries(SRCS.map(c => [c.id, c.label]));
  const PLAT = { instagram: 'Instagram', tiktok: 'TikTok', youtube: 'YouTube', web: 'their site' };
  const CAT_ICON = Object.fromEntries(CATS.filter(c => c.icon).map(c => [c.id, c.icon]));
  const CAT_LABEL = Object.fromEntries(CATS.map(c => [c.id, c.label]));
  const ARS = ['4 / 5', '3 / 4', '4 / 5', '5 / 7', '1 / 1.2', '3 / 4'];
  const BATCH = 24;

  const ICON = {
    clock: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true"><circle cx="12" cy="13" r="7.5"/><path d="M12 9.5V13l2.5 1.5M10 3h4" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    pot: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true"><path d="M4 11h16v3a6 6 0 0 1-6 6h-4a6 6 0 0 1-6-6v-3zM2.5 11h19" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    box: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true"><rect x="3.5" y="8" width="17" height="11" rx="3"/><path d="M3.5 12h17M8 5h8" stroke-linecap="round"/></svg>',
    out: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true"><path d="M14 4h6v6M20 4l-9 9M18 14v4a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    heart: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 20s-7-4.4-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.6-7 10-7 10z" stroke-linejoin="round"/></svg>',
    page: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true"><path d="M7 3.5h7l4 4V20a.5.5 0 0 1-.5.5h-10A.5.5 0 0 1 7 20z" stroke-linejoin="round"/><path d="M10 12h5M10 16h5" stroke-linecap="round"/></svg>',
  };

  const esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const load = (k, d) => { try { return JSON.parse(localStorage.getItem(k)) || d; } catch (e) { return d; } };
  const store = (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} };

  let feed = { items: [] }, profile = null, sources = null;
  let items = [];
  let saved = new Set(load(SAVED_KEY, []));
  let checked = load(CHECK_KEY, {});
  const state = { view: 'feed', cat: 'all', time: new Set(), src: 'all', q: '' };
  const details = new Map();

  /* ---------- filtering ---------- */
  function passes(it, useCat = true) {
    if (useCat && state.cat !== 'all' && it.category !== state.cat) return false;
    if (state.src === 'creators' && it.kind !== 'creator') return false;
    if (state.src === 'sites' && it.kind === 'creator') return false;
    const t = state.time;
    if (t.size) {
      const speed = [...t].filter(x => x === 'quick' || x === 'long');
      if (speed.length && !speed.includes(it.time)) return false;
      if (t.has('prep') && !it.mealPrep) return false;
    }
    if (state.q) {
      const hay = it._hay || (it._hay = [it.title, it.by, it.site, it.kw].join(' ').toLowerCase());
      if (!state.q.split(/\s+/).every(w => hay.includes(w))) return false;
    }
    return true;
  }

  /* ---------- picks: score against his favorites ---------- */
  const wordRe = (k) => new RegExp('(^|[^a-z])' + k.toLowerCase().replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '($|[^a-z])', 'i');
  function scoreItem(it) {
    if (!profile) return null;
    if (it._score !== undefined) return it._score;
    const text = [it.title, it.kw, (it.tags || []).join(' ')].join('\n').toLowerCase();
    let score = 0, strong = false;
    const hits = [];
    for (const f of profile.favorites || []) {
      const m = (f.keywords || []).filter(k => wordRe(k).test(text));
      if (!m.length) continue;
      const pts = f.weight * (1 + Math.min(m.length - 1, 3) * 0.2);
      score += pts;
      if (f.kind === 'favorite' && f.weight >= 5) strong = true;
      hits.push({ f, pts, m });
    }
    if (!score) return (it._score = null);
    hits.sort((a, b) => b.pts - a.pts);
    const favWords = new Set((profile.favorites || []).flatMap(f => f.keywords.map(k => k.toLowerCase())));
    const fresh = (profile.new_foods || []).filter(k => !favWords.has(k) && wordRe(k).test(text));
    const freshUnique = [...new Set(fresh.map(k => k.replace(/s$/, '')))].slice(0, 2);
    return (it._score = { score, strong, reasons: hits.slice(0, 2).map(h => h.f.reason), fresh: freshUnique });
  }

  /* ---------- cards: photo, title, one quiet line ---------- */
  function timeText(it) {
    if (it.minutes) return `${it.minutes} min`;
    if (it.time === 'quick') return 'Quick';
    if (it.time === 'long') return 'Longer cook';
    return '';
  }
  function arOf(it, i) {
    if (it.thumb_w && it.thumb_h) { const r = Math.min(1.45, Math.max(1, it.thumb_h / it.thumb_w)); return `1 / ${r.toFixed(3)}`; }
    return ARS[i % ARS.length];
  }
  function photoHtml(it, ar, eager) {
    if (it.thumb) {
      return `<div class="photo" style="--ar:${ar}${it.color ? `;--ph:${esc(it.color)}` : ''}">
        <img class="real" src="${esc(it.thumb)}" alt="${esc(it.title)}" loading="${eager ? 'eager' : 'lazy'}" decoding="async" ${it.thumb_w ? `width="${it.thumb_w}" height="${it.thumb_h}"` : ''}/>
      </div>`;
    }
    return `<div class="photo loaded" style="--ar:${ar}"><div class="placeholder">
      <img src="${CAT_ICON[it.category] || CAT_ICON.meal}" alt=""/>
      <small>No photo</small></div></div>`;
  }
  function card(it, i, why) {
    const ar = arOf(it, i);
    const title = it.title || 'Post';
    const line = [it.by, timeText(it)].filter(Boolean).join(' · ');
    return `<article class="card" role="button" tabindex="0" data-id="${esc(it.id)}" style="--i:${Math.min(i % BATCH, 12)}" aria-label="${esc(title)}">
      ${photoHtml(it, ar, i < 6)}
      ${saved.has(it.id) ? `<span class="saved-dot" aria-label="Saved">${ICON.heart}</span>` : ''}
      <div class="card-body">
        <h3>${esc(title)}</h3>
        <p class="card-line">${esc(line)}</p>
        ${why ? `<p class="card-why">${esc(why)}</p>` : ''}
      </div>
    </article>`;
  }
  function wireImages(root) {
    $$('.photo img.real:not([data-w])', root).forEach(img => {
      img.dataset.w = 1;
      const done = () => img.closest('.photo').classList.add('loaded');
      if (img.complete && img.naturalWidth) done(); else { img.addEventListener('load', done, { once: true }); img.addEventListener('error', done, { once: true }); }
    });
  }
  function emptyHtml(icon, title, body, reset) {
    return `<div class="empty"><img src="${icon}" alt=""/><strong>${esc(title)}</strong><span>${esc(body)}</span>${reset ? '<button type="button" data-reset>Clear filters</button>' : ''}</div>`;
  }
  const filtersActive = () => state.cat !== 'all' || state.time.size || state.src !== 'all' || state.q;

  /* ---------- masonry: row-wise order, shortest column first, appended in batches ---------- */
  const colCount = () => window.innerWidth >= 1100 ? 4 : window.innerWidth >= 768 ? 3 : 2;
  function mount(g, list, why, upto) {
    g.classList.remove('is-empty');
    const n = colCount();
    g.innerHTML = Array.from({ length: n }, () => '<div class="col"></div>').join('');
    g._m = { list, why, shown: 0, h: new Array(n).fill(0), cols: $$('.col', g), n };
    do { appendBatch(g); } while (upto && g._m.shown < Math.min(upto, list.length));
  }
  function appendBatch(g) {
    const m = g._m; if (!m || m.shown >= m.list.length) return false;
    const end = Math.min(m.list.length, m.shown + BATCH);
    const parts = m.cols.map(() => []);
    for (let i = m.shown; i < end; i++) {
      const it = m.list[i];
      const k = m.h.indexOf(Math.min(...m.h));
      const r = +arOf(it, i).split('/')[1] || 1.25;
      m.h[k] += r + 0.34 + ((it.title || '').length > 24 ? 0.1 : 0) + (m.why ? 0.1 : 0);
      parts[k].push(card(it, i, m.why ? m.why(it) : ''));
    }
    m.cols.forEach((c, k) => { if (parts[k].length) c.insertAdjacentHTML('beforeend', parts[k].join('')); });
    m.shown = end;
    wireImages(g);
    const btn = g.parentElement && g.parentElement.querySelector(`[data-more-for="${g.id || g.dataset.sec}"]`);
    if (btn) btn.hidden = m.shown >= m.list.length;
    return true;
  }
  function relayout() {
    $$('.grid').forEach(g => { if (g._m && g._m.n !== colCount()) mount(g, g._m.list, g._m.why, g._m.shown); });
  }
  const io = 'IntersectionObserver' in window ? new IntersectionObserver(es => {
    es.forEach(e => { if (e.isIntersecting && state.view === 'feed') appendBatch($('#feed-grid')); });
  }, { rootMargin: '900px 0px' }) : null;

  /* ---------- renders ---------- */
  function setEmpty(g, html) { g._m = null; g.classList.add('is-empty'); g.innerHTML = html; }
  function renderFeed() {
    const list = items.filter(it => passes(it));
    const g = $('#feed-grid');
    if (!list.length) setEmpty(g, emptyHtml('icons/clay-plate.webp', 'Nothing here yet', state.time.size ? 'Only ideas that state a time or a make-ahead tip show with time filters.' : 'Try another filter or search.', filtersActive()));
    else mount(g, list);
    $('#feed-sub').textContent = list.length ? `${list.length} idea${list.length === 1 ? '' : 's'}` : '';
  }
  const whyText = (s) => s.reasons[0] + (s.fresh.length ? ` · new: ${s.fresh[0]}` : '');
  function renderPicks() {
    const body = $('#picks-body');
    const scored = items.map(it => ({ it, s: scoreItem(it) })).filter(x => x.s && passes(x.it));
    scored.sort((a, b) => b.s.score - a.s.score || (b.it.full ? 1 : 0) - (a.it.full ? 1 : 0));
    const close = scored.filter(x => x.s.strong).map(x => x.it);
    const next = scored.filter(x => !x.s.strong).map(x => x.it);
    $('#picks-sub').textContent = profile && profile.headline ? `Matched to what he loves: ${profile.headline}.` : '';
    if (!scored.length) {
      body.innerHTML = emptyHtml('icons/clay-bread.webp', 'No close matches yet', 'Nothing lines up with his favorites' + (filtersActive() ? ' with these filters.' : ' this week. New ideas arrive weekly.'), filtersActive());
      return;
    }
    const sec = (id, title, note, arr) => arr.length ? `<section class="pick-section">
      <div class="section-head"><h2>${title}</h2><p>${note} · ${arr.length}</p></div>
      <div class="grid" data-sec="${id}"></div><button type="button" class="more-btn" data-more-for="${id}" hidden>Show more</button></section>` : '';
    body.innerHTML = sec('close', 'Close to his favorites', 'Textures he already says yes to', close)
      + sec('next', 'Gentle next steps', 'A familiar format with one new food', next);
    const why = it => whyText(scoreItem(it));
    if (close.length) mount($('[data-sec="close"]', body), close, why);
    if (next.length) mount($('[data-sec="next"]', body), next, why);
  }
  function renderSaved() {
    const list = items.filter(it => saved.has(it.id));
    const g = $('#saved-grid');
    if (!list.length) setEmpty(g, emptyHtml('icons/clay-bread.webp', 'Nothing saved yet', 'Open an idea and tap Save to keep it here.'));
    else mount(g, list, null, list.length);
  }
  function activeCount() { return (state.cat !== 'all' ? 1 : 0) + state.time.size + (state.src !== 'all' ? 1 : 0); }
  function renderActive() {
    const box = $('#active-filters');
    const pills = [];
    if (state.cat !== 'all') pills.push(`<button type="button" class="pill" data-clear-cat aria-label="Remove ${esc(CAT_LABEL[state.cat])}">${esc(CAT_LABEL[state.cat])}<span aria-hidden="true">&times;</span></button>`);
    TIMES.filter(t => state.time.has(t.id)).forEach(t => pills.push(`<button type="button" class="pill" data-clear-time="${t.id}" aria-label="Remove ${t.label}">${t.label}<span aria-hidden="true">&times;</span></button>`));
    if (state.src !== 'all') pills.push(`<button type="button" class="pill" data-clear-src aria-label="Remove ${esc(SRC_LABEL[state.src])}">${esc(SRC_LABEL[state.src])}<span aria-hidden="true">&times;</span></button>`);
    box.innerHTML = pills.join('');
    box.hidden = !pills.length || state.view === 'saved';
    const n = activeCount(), badge = $('#filter-count'), fb = $('#filter-btn');
    badge.hidden = !n; badge.textContent = n;
    fb.setAttribute('aria-label', n ? `Filter, ${n} active` : 'Filter');
  }
  function render() {
    renderActive();
    if (state.view === 'feed') renderFeed();
    else if (state.view === 'picks') renderPicks();
    else renderSaved();
  }
  /* ---------- views + dock ---------- */
  const seg = $('#view-seg');
  function moveIndicator() {
    const sel = $(`.tab[data-tab="${state.view}"]`, seg);
    seg.classList.toggle('idle', !sel);
    if (!sel) return;
    seg.style.setProperty('--tab-left', `${sel.offsetLeft}px`);
    seg.style.setProperty('--tab-width', `${sel.offsetWidth}px`);
  }
  function setView(v) {
    state.view = v;
    app.dataset.view = v;
    $$('.panel').forEach(p => p.classList.toggle('active', p.id === 'panel-' + v));
    $$('.tab', seg).forEach(t => { const on = t.dataset.tab === v; t.classList.toggle('active', on); t.setAttribute('aria-selected', on); });
    const sb = $('#saved-btn'); sb.classList.toggle('on', v === 'saved'); sb.setAttribute('aria-pressed', v === 'saved');
    $(`#panel-${v} .panel-header`).appendChild($('#active-filters'));
    $('#filter-shell').style.visibility = v === 'saved' ? 'hidden' : '';
    moveIndicator();
    render();
  }
  $$('.tab', seg).forEach(t => t.addEventListener('click', () => setView(t.dataset.tab)));
  $('#saved-btn').addEventListener('click', () => setView(state.view === 'saved' ? 'feed' : 'saved'));

  /* ---------- filter sheet (Spots pattern) ---------- */
  const fSheet = $('#filter-sheet'), fBack = $('#filter-backdrop'), fBtn = $('#filter-btn');
  let draft = null;
  const baseList = () => state.view === 'picks' ? items.filter(it => scoreItem(it)) : items;
  function countWith(cat, time, src) {
    const keep = { cat: state.cat, time: state.time, src: state.src };
    state.cat = cat; state.time = time; state.src = src;
    const n = baseList().filter(it => passes(it)).length;
    state.cat = keep.cat; state.time = keep.time; state.src = keep.src;
    return n;
  }
  function renderSheet() {
    $('#cat-options').innerHTML = CATS.map(c => {
      const on = draft.cat === c.id;
      return `<button type="button" class="filter-chip" role="radio" aria-checked="${on}" data-cat="${c.id}">
        <span class="dot" style="background:${c.dot}"></span>
        <span class="label">${c.label}<span class="hint">${c.hint}</span></span>
        <span class="n">${countWith(c.id, draft.time, draft.src)}</span><span class="check"></span></button>`;
    }).join('');
    $('#time-options').innerHTML = TIMES.map(t => {
      const on = draft.time.has(t.id);
      const next = new Set(draft.time); next.add(t.id); if (t.id === 'quick') next.delete('long'); if (t.id === 'long') next.delete('quick');
      return `<button type="button" class="filter-chip" aria-pressed="${on}" data-time="${t.id}">
        <span class="dot" style="background:${t.dot}"></span>
        <span class="label">${t.label}<span class="hint">${t.hint}</span></span>
        <span class="n">${countWith(draft.cat, on ? draft.time : next, draft.src)}</span><span class="check"></span></button>`;
    }).join('');
    $('#src-options').innerHTML = SRCS.map(c => {
      const on = draft.src === c.id;
      return `<button type="button" class="filter-chip" role="radio" aria-checked="${on}" data-src="${c.id}">
        <span class="dot" style="background:${c.dot}"></span>
        <span class="label">${c.label}<span class="hint">${c.hint}</span></span>
        <span class="n">${countWith(draft.cat, draft.time, c.id)}</span><span class="check"></span></button>`;
    }).join('');
    const n = countWith(draft.cat, draft.time, draft.src);
    $('#filter-apply').textContent = `Show ${n} result${n === 1 ? '' : 's'}`;
  }
  function openFilters() {
    draft = { cat: state.cat, time: new Set(state.time), src: state.src };
    renderSheet();
    fSheet.hidden = false; fBack.hidden = false;
    requestAnimationFrame(() => { fSheet.classList.add('open'); fBack.classList.add('open'); });
    fBtn.classList.add('on'); fBtn.setAttribute('aria-expanded', 'true'); fBtn.setAttribute('aria-pressed', 'true');
    setTimeout(() => $('#filter-close').focus({ preventScroll: true }), 60);
  }
  function closeFilters() {
    fSheet.classList.remove('open'); fBack.classList.remove('open');
    fBtn.classList.remove('on'); fBtn.setAttribute('aria-expanded', 'false'); fBtn.setAttribute('aria-pressed', 'false');
    setTimeout(() => { if (!fSheet.classList.contains('open')) { fSheet.hidden = true; fBack.hidden = true; } }, 360);
    fBtn.focus({ preventScroll: true });
  }
  fBtn.addEventListener('click', () => fSheet.classList.contains('open') ? closeFilters() : openFilters());
  $('#filter-close').addEventListener('click', closeFilters);
  fBack.addEventListener('click', closeFilters);
  fSheet.addEventListener('click', e => {
    const c = e.target.closest('[data-cat]');
    if (c) { draft.cat = c.dataset.cat; renderSheet(); return; }
    const sr = e.target.closest('[data-src]');
    if (sr) { draft.src = sr.dataset.src; renderSheet(); return; }
    const t = e.target.closest('[data-time]');
    if (t) {
      const id = t.dataset.time;
      if (draft.time.has(id)) draft.time.delete(id);
      else { draft.time.add(id); if (id === 'quick') draft.time.delete('long'); if (id === 'long') draft.time.delete('quick'); }
      renderSheet(); return;
    }
    if (e.target.closest('#filter-clear')) { draft = { cat: 'all', time: new Set(), src: 'all' }; renderSheet(); return; }
    if (e.target.closest('#filter-apply')) { state.cat = draft.cat; state.time = new Set(draft.time); state.src = draft.src; render(); closeFilters(); scrollTopActive(); }
  });
  $('#active-filters').addEventListener('click', e => {
    if (e.target.closest('[data-clear-cat]')) state.cat = 'all';
    if (e.target.closest('[data-clear-src]')) state.src = 'all';
    const t = e.target.closest('[data-clear-time]'); if (t) state.time.delete(t.dataset.clearTime);
    render();
  });

  /* ---------- card clicks (delegated) ---------- */
  document.addEventListener('click', e => {
    const mb = e.target.closest('[data-more-for]');
    if (mb) { const g = $(`[data-sec="${mb.dataset.moreFor}"]`); if (g) appendBatch(g); return; }
    if (e.target.closest('[data-reset]')) { state.cat = 'all'; state.time.clear(); state.src = 'all'; state.q = ''; $('#search').value = ''; closeSearchIfEmpty(); render(); return; }
    const c = e.target.closest('.card');
    if (c) openSheet(c.dataset.id);
  });
  document.addEventListener('keydown', e => {
    if ((e.key === 'Enter' || e.key === ' ') && e.target.classList && e.target.classList.contains('card')) { e.preventDefault(); openSheet(e.target.dataset.id); }
    if (e.key === 'Escape') { if (!$('#sheet').hidden) closeSheet(); else if (fSheet.classList.contains('open')) closeFilters(); else if ($('#about-drawer').classList.contains('open')) closeAbout(); }
  });
  function toggleSave(id) {
    if (saved.has(id)) saved.delete(id); else saved.add(id);
    store(SAVED_KEY, [...saved]);
    const sb = $('#sheet-save'); if (sb && sb.dataset.id === id) { sb.setAttribute('aria-pressed', saved.has(id)); sb.lastChild.textContent = saved.has(id) ? 'Saved' : 'Save'; }
    render();
  }

  /* ---------- detail sheet ---------- */
  const sheet = $('#sheet'), backdrop = $('#sheet-backdrop');
  let lastFocus = null;
  function getDetail(id) {
    if (details.has(id)) return Promise.resolve(details.get(id));
    return fetch(`data/items/${encodeURIComponent(id)}.json`).then(r => r.ok ? r.json() : {}).catch(() => ({}))
      .then(d => { details.set(id, d); return d; });
  }
  let sheetId = null;
  function openSheet(id) {
    const it = items.find(x => x.id === id); if (!it) return;
    lastFocus = document.activeElement;
    sheetId = id;
    const badges = [];
    if (it.category) badges.push(`<span class="badge soft">${esc(CAT_LABEL[it.category] || it.category)}</span>`);
    const tt = timeText(it); if (tt) badges.push(`<span class="badge">${ICON.clock}${esc(tt)}</span>`);
    if (it.mealPrep) badges.push(`<span class="badge">${ICON.box}Meal prep</span>`);
    const s = scoreItem(it);
    $('#sheet-body').innerHTML = `
      <div class="sheet-hero">${photoHtml(it, '4 / 5', true)}</div>
      <h2 id="sheet-title">${esc(it.title)}</h2>
      <p class="sheet-by" id="sheet-by">${esc(it.by)}</p>
      ${badges.length ? `<div class="sheet-badges" id="sheet-badges">${badges.join('')}</div>` : ''}
      ${s ? `<div class="sheet-section"><strong>For him</strong>${esc(s.reasons.join(' · '))}${s.fresh.length ? esc(' · new to him: ' + s.fresh.join(', ')) : ''}</div>` : ''}
      <div id="sheet-detail" class="sheet-loading" aria-busy="true"><span></span><span></span><span></span></div>
      <div class="sheet-actions">
        <a class="primary" id="sheet-open" href="${esc(it.url)}" target="_blank" rel="noopener">${ICON.out}Open original</a>
        ${it.recipePage ? `<a class="ghost" href="${esc(it.recipePage)}" target="_blank" rel="noopener">${ICON.page}Recipe page</a>` : ''}
        <button type="button" class="ghost" id="sheet-save" data-id="${esc(id)}" aria-pressed="${saved.has(id)}">${ICON.heart.replace('<svg', '<svg fill="none" stroke="currentColor"')}<span>${saved.has(id) ? 'Saved' : 'Save'}</span></button>
        <button type="button" class="close-btn" id="sheet-close">Close</button>
      </div>`;
    wireImages($('#sheet-body'));
    $('#sheet-body').scrollTop = 0;
    sheet.hidden = false;
    requestAnimationFrame(() => { sheet.classList.add('open'); backdrop.classList.add('open'); });
    setTimeout(() => $('#sheet-dismiss').offsetParent ? $('#sheet-dismiss').focus({ preventScroll: true }) : $('#sheet-close').focus({ preventScroll: true }), 60);
    history.replaceState(null, '', '#item=' + encodeURIComponent(id));
    getDetail(id).then(d => { if (sheetId === id) fillDetail(it, d); });
  }
  function fillDetail(it, d) {
    const id = it.id, web = it.platform === 'web';
    const done = new Set(checked[id] || []);
    const partial = d.extraction === 'video-partial';
    const ing = (d.ingredients || []).map((x, n) => `<li><label><input type="checkbox" data-ing="${n}" ${done.has(n) ? 'checked' : ''}/><span class="box"></span><span class="txt">${esc(x)}</span></label></li>`).join('');
    const steps = (d.steps || []).map(x => `<li><span>${esc(x)}</span></li>`).join('');
    const notes = (d.notes || []).map(x => `<li>${esc(x)}</li>`).join('');
    const handle = d.account ? '@' + esc(d.account) : '';
    const on = PLAT[it.platform] || '';
    let by;
    if (web) by = `${d.author ? 'By ' + esc(d.author) + ' · ' : ''}<a href="${esc(d.site_url || d.account_url)}" target="_blank" rel="noopener">${esc(d.site || it.by)}</a>`;
    else by = `By <a href="${esc(d.account_url || '#')}" target="_blank" rel="noopener">${d.account_name ? esc(d.account_name) + ' (' + handle + ')' : handle}</a> on ${on}`;
    if (d.date) by += ' · ' + esc(new Date(d.date + 'T12:00:00').toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' }));
    $('#sheet-by').innerHTML = by;
    if (d.yield && $('#sheet-badges')) $('#sheet-badges').insertAdjacentHTML('beforeend', `<span class="badge soft">Makes ${esc(d.yield)}</span>`);
    const credit = web ? `Recipe from ${esc(d.site)}${d.author ? ' by ' + esc(d.author) : ''}, saved for personal use. The original has the full notes, tips and photos.`
      : d.extraction === 'video' ? `From the video’s narration and on-screen text, by ${handle}. Amounts aren’t given unless said.`
      : partial ? `Mentioned in the video (narration or on-screen text). The video doesn’t give a full method or amounts.`
      : d.extraction === 'recipe-page' ? `Recipe text from the page ${handle} linked in the caption.`
      : (ing || steps) ? `Recipe text as written by ${handle}${d.recipe_from && d.recipe_from !== 'caption' ? ' in their ' + esc(d.recipe_from) : ' in the caption'}.` : '';
    const box = $('#sheet-detail');
    box.classList.remove('sheet-loading'); box.removeAttribute('aria-busy');
    box.innerHTML = `
      ${d.summary ? `<div class="sheet-section">${esc(d.summary)}</div>` : ''}
      ${ing ? `<div class="sheet-section"><strong>${partial ? 'Mentioned in the video' : 'Ingredients'}</strong><ul class="ing-list">${ing}</ul></div>` : ''}
      ${steps ? `<div class="sheet-section"><strong>Steps</strong><ol class="step-list">${steps}</ol></div>` : ''}
      ${!steps && !partial ? `<div class="recipe-missing"><img src="${CAT_ICON[it.category] || CAT_ICON.meal}" alt=""/><span>${ing ? 'Steps are in the video, open original.' : 'Recipe in the video, open original.'}</span></div>` : ''}
      ${credit ? `<p class="credit">${credit}</p>` : ''}
      ${notes ? `<div class="sheet-section"><strong>Why it works (from the post)</strong><ul class="note-list">${notes}</ul></div>` : ''}
      ${d.mirror ? `<p class="credit">Also posted on <a href="${esc(d.mirror.url)}" target="_blank" rel="noopener">${esc(PLAT[d.mirror.platform] || d.mirror.platform)}</a>.</p>` : ''}
      ${!web && d.caption ? `<details class="caption"><summary>Full caption</summary><p>${esc(d.caption)}</p></details>` : ''}`;
    if (d.recipeSourceUrl && d.recipeSourceUrl !== it.url) $('#sheet-open').href = d.recipeSourceUrl;
  }
  function closeSheet() {
    sheet.classList.remove('open'); backdrop.classList.remove('open');
    setTimeout(() => { if (!sheet.classList.contains('open')) sheet.hidden = true; }, 380);
    history.replaceState(null, '', location.pathname + location.search);
    if (lastFocus && lastFocus.focus) lastFocus.focus({ preventScroll: true });
  }
  backdrop.addEventListener('click', closeSheet);
  $('#sheet-dismiss').addEventListener('click', closeSheet);
  $('#sheet-body').addEventListener('click', e => {
    if (e.target.closest('#sheet-close')) closeSheet();
    const sv = e.target.closest('#sheet-save'); if (sv) toggleSave(sv.dataset.id);
  });
  $('#sheet-body').addEventListener('change', e => {
    const cb = e.target.closest('[data-ing]'); if (!cb) return;
    const id = sheetId;
    const set = new Set(checked[id] || []);
    cb.checked ? set.add(+cb.dataset.ing) : set.delete(+cb.dataset.ing);
    checked[id] = [...set]; store(CHECK_KEY, checked);
  });
  // Swipe the sheet down to close (phone)
  (function () {
    let y0 = null;
    sheet.addEventListener('touchstart', e => { if ($('#sheet-body').scrollTop <= 0) y0 = e.touches[0].clientY; }, { passive: true });
    sheet.addEventListener('touchmove', e => { if (y0 == null) return; const dy = e.touches[0].clientY - y0; if (dy > 0) { sheet.style.transition = 'none'; sheet.style.transform = `translateY(${dy}px)`; } }, { passive: true });
    sheet.addEventListener('touchend', e => {
      if (y0 == null) return; const dy = e.changedTouches[0].clientY - y0; y0 = null;
      sheet.style.removeProperty('transition'); sheet.style.removeProperty('transform');
      if (dy > 110) closeSheet();
    });
  })();

  /* ---------- search (shared pattern) ---------- */
  const topbar = $('#topbar'), searchEl = $('#search'), searchToggle = $('#search-toggle');
  function openSearch() {
    searchToggle.classList.add('is-active'); searchToggle.setAttribute('aria-expanded', 'true'); searchToggle.setAttribute('aria-pressed', 'true');
    searchEl.focus({ preventScroll: true }); topbar.classList.add('search-focused');
  }
  function closeSearchIfEmpty() {
    if (!searchEl.value.trim()) {
      topbar.classList.remove('search-focused'); searchToggle.classList.remove('is-active');
      searchToggle.setAttribute('aria-expanded', 'false'); searchToggle.setAttribute('aria-pressed', 'false');
    }
  }
  searchToggle.addEventListener('click', openSearch);
  searchEl.addEventListener('focus', () => topbar.classList.add('search-focused'));
  searchEl.addEventListener('blur', closeSearchIfEmpty);
  let st;
  searchEl.addEventListener('input', () => { clearTimeout(st); st = setTimeout(() => { state.q = searchEl.value.trim().toLowerCase(); render(); }, 120); });

  /* ---------- about drawer ---------- */
  const drawer = $('#about-drawer'), dback = $('#about-backdrop'), openAbout = $('#open-about');
  function showAbout() { drawer.hidden = false; dback.hidden = false; requestAnimationFrame(() => { drawer.classList.add('open'); dback.classList.add('open'); }); openAbout.setAttribute('aria-expanded', 'true'); setTimeout(() => $('#about-close').focus({ preventScroll: true }), 80); }
  function closeAbout() { drawer.classList.remove('open'); dback.classList.remove('open'); openAbout.setAttribute('aria-expanded', 'false'); setTimeout(() => { if (!drawer.classList.contains('open')) { drawer.hidden = true; dback.hidden = true; } }, 480); openAbout.focus({ preventScroll: true }); }
  openAbout.addEventListener('click', showAbout);
  $('#about-close').addEventListener('click', closeAbout);
  dback.addEventListener('click', closeAbout);
  function fillAbout() {
    const creators = (sources && sources.creators) || [];
    const srcs = (sources && sources.sources) || [];
    const link = (u, t) => `<a href="${esc(u)}" target="_blank" rel="noopener">${esc(t)}</a>`;
    const others = (h) => srcs.filter(x => x.creator === h && /^(tiktok|youtube|website)/.test(x.type) && x.enabled !== false).map(x => {
      if (x.type.startsWith('tiktok')) return link(x.url, 'TikTok');
      if (x.type.startsWith('youtube')) return link(x.url.replace(/\/(shorts|videos)\/?$/, ''), 'YouTube');
      return link(x.site_url || new URL(x.url).origin, 'blog');
    });
    const sites = srcs.filter(x => x.type.startsWith('website') && !x.creator && x.enabled !== false);
    $('#about-sources').innerHTML = creators.map(a => { const o = others(a.handle); return `<li>${link(a.instagram, '@' + a.handle)}${o.length ? ` (${o.join(' · ')})` : ''}</li>`; }).join('')
      + sites.map(x => `<li>${link(x.site_url || new URL(x.url).origin, x.site)}</li>`).join('');
  }

  /* ---------- welcome (shared shape) ---------- */
  const welcome = $('#welcome'), welcomeEnter = $('#welcome-enter');
  function openWelcome() {
    const bits = $$('.welcome-emoji, .welcome-wordmark, .welcome-line, .welcome-enter, .welcome-credit', welcome);
    welcome.classList.remove('open'); welcome.hidden = false;
    welcome.style.transition = 'none'; bits.forEach(el => { el.style.transition = 'none'; });
    void welcome.offsetWidth;
    welcome.style.removeProperty('transition'); bits.forEach(el => el.style.removeProperty('transition'));
    requestAnimationFrame(() => { welcome.classList.add('open'); setTimeout(() => { if (welcome.classList.contains('open')) welcomeEnter.focus({ preventScroll: true }); }, 820); });
  }
  function closeWelcome() {
    store(WELCOME_KEY, 1);
    welcome.classList.remove('open');
    setTimeout(() => { if (!welcome.classList.contains('open')) welcome.hidden = true; }, 360);
  }
  welcomeEnter.addEventListener('click', closeWelcome);
  $('#welcome-replay').addEventListener('click', () => { closeAbout(); setTimeout(openWelcome, 200); });
  if (!load(WELCOME_KEY, 0) && !/[?&]nowelcome/.test(location.search)) openWelcome();

  let rz;
  window.addEventListener('resize', () => { moveIndicator(); clearTimeout(rz); rz = setTimeout(relayout, 150); });
  function scrollTopActive() { const p = $(`#panel-${state.view}`); if (p) p.scrollTop = 0; }

  /* ---------- boot ---------- */
  const get = (u) => fetch(u, { cache: 'no-cache' }).then(r => { if (!r.ok) throw new Error(u + ' ' + r.status); return r.json(); });
  Promise.all([get('data/feed.json'), get('data/profile.json').catch(() => null), get('data/sources.json').catch(() => null)])
    .then(([f, p, s]) => {
      feed = f; profile = p; sources = s;
      items = (f.items || []).slice();
      fillAbout();
      setView('feed');
      if (io) io.observe($('#feed-more'));
      const m = location.hash.match(/item=([^&]+)/);
      if (m) openSheet(decodeURIComponent(m[1]));
    })
    .catch(err => {
      console.warn(err);
      $('#feed-grid').innerHTML = emptyHtml('icons/clay-plate.webp', 'Couldn’t load ideas', 'Check the connection and try again.');
    });
  requestAnimationFrame(moveIndicator);
})();
