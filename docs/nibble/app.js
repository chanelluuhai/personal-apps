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
    { id: 'all', label: 'All ideas', hint: 'Show everything', dot: '#B5654D' },
    { id: 'pasta', label: 'Pasta & noodles', hint: 'Shapes he can hold', icon: 'icons/clay-pizza.webp', dot: '#C8735A' },
    { id: 'finger', label: 'Finger food', hint: 'Bites, pancakes, dips', icon: 'icons/clay-bread.webp', dot: '#B98A5E' },
    { id: 'sweet', label: 'Sweets & snacks', hint: 'Treats and small bites', icon: 'icons/clay-sweet.webp', dot: '#C98998' },
    { id: 'meal', label: 'Meals', hint: 'Plates and bowls', icon: 'icons/clay-plate.webp', dot: '#7D8FAE' },
  ];
  const TIMES = [
    { id: 'quick', label: 'Quick', hint: 'About 15 min or less, no-bake or no-cook', dot: '#B5654D' },
    { id: 'long', label: 'Longer cook', hint: 'Says it takes longer', dot: '#8A4430' },
    { id: 'prep', label: 'Meal prep', hint: 'Make-ahead, batch or freezer-friendly', dot: '#9AA383' },
  ];
  const CAT_ICON = Object.fromEntries(CATS.filter(c => c.icon).map(c => [c.id, c.icon]));
  const CAT_LABEL = Object.fromEntries(CATS.map(c => [c.id, c.label]));
  const ARS = ['4 / 5', '3 / 4', '4 / 5', '5 / 7', '1 / 1.2', '3 / 4'];

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
  const state = { view: 'feed', cat: 'all', time: new Set(), q: '' };

  /* ---------- filtering ---------- */
  function passes(it, useCat = true) {
    if (useCat && state.cat !== 'all' && it.category !== state.cat) return false;
    const t = state.time;
    if (t.size) {
      if (it.status !== 'ok') return false;
      const speed = [...t].filter(x => x === 'quick' || x === 'long');
      if (speed.length && !speed.includes(it.time)) return false;
      if (t.has('prep') && !it.mealPrep) return false;
    }
    if (state.q) {
      const hay = [it.title, it.summary, it.caption, it.account, it.account_name, (it.tags || []).join(' '), (it.ingredients || []).join(' ')].join(' ').toLowerCase();
      if (!state.q.split(/\s+/).every(w => hay.includes(w))) return false;
    }
    return true;
  }

  /* ---------- picks: score against his favorites ---------- */
  const wordRe = (k) => new RegExp('(^|[^a-z])' + k.toLowerCase().replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '($|[^a-z])', 'i');
  function scoreItem(it) {
    if (!profile || it.status !== 'ok') return null;
    const text = [it.title, it.caption, (it.tags || []).join(' ')].join('\n').toLowerCase();
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
    if (!score) return null;
    hits.sort((a, b) => b.pts - a.pts);
    const favWords = new Set((profile.favorites || []).flatMap(f => f.keywords.map(k => k.toLowerCase())));
    const fresh = (profile.new_foods || []).filter(k => !favWords.has(k) && wordRe(k).test(text));
    const freshUnique = [...new Set(fresh.map(k => k.replace(/s$/, '')))].slice(0, 2);
    return { score, strong, reasons: hits.slice(0, 2).map(h => h.f.reason), fresh: freshUnique };
  }

  /* ---------- cards: photo, title, one quiet line ---------- */
  function timeText(it) {
    if (it.status !== 'ok') return '';
    if (it.minutes) return `${it.minutes} min`;
    if (it.time === 'quick') return 'Quick';
    if (it.time === 'long') return 'Longer cook';
    return '';
  }
  function photoHtml(it, ar, eager) {
    if (it.thumb) {
      return `<div class="photo" style="--ar:${ar}">
        ${it.thumb_lqip ? `<img class="lqip" src="${it.thumb_lqip}" alt="" aria-hidden="true"/>` : ''}
        <img class="real" src="${esc(it.thumb)}" alt="${esc(it.title)}" loading="${eager ? 'eager' : 'lazy'}" decoding="async" ${it.thumb_w ? `width="${it.thumb_w}" height="${it.thumb_h}"` : ''}/>
      </div>`;
    }
    return `<div class="photo loaded" style="--ar:${ar}"><div class="placeholder">
      <img src="${CAT_ICON[it.category] || CAT_ICON.meal}" alt=""/>
      <small>${it.status === 'ok' ? 'No photo' : 'Not fetched'}</small></div></div>`;
  }
  function card(it, i, why) {
    const ar = ARS[i % ARS.length];
    const title = it.status === 'ok' ? it.title : 'Instagram post';
    const line = [it.account ? '@' + it.account : 'Open on Instagram', timeText(it)].filter(Boolean).join(' · ');
    return `<article class="card" role="button" tabindex="0" data-id="${esc(it.id)}" style="--i:${Math.min(i, 12)}" aria-label="${esc(title)}">
      ${photoHtml(it, ar, i < 4)}
      ${saved.has(it.id) ? `<span class="saved-dot" aria-label="Saved">${ICON.heart}</span>` : ''}
      <div class="card-body">
        <h3>${esc(title)}</h3>
        <p class="card-line">${esc(line)}</p>
        ${why ? `<p class="card-why">${esc(why)}</p>` : ''}
      </div>
    </article>`;
  }
  function wireImages(root) {
    $$('.photo img.real', root).forEach(img => {
      const done = () => img.closest('.photo').classList.add('loaded');
      if (img.complete && img.naturalWidth) done(); else { img.addEventListener('load', done, { once: true }); img.addEventListener('error', done, { once: true }); }
    });
  }
  function emptyHtml(icon, title, body, reset) {
    return `<div class="empty"><img src="${icon}" alt=""/><strong>${esc(title)}</strong>${esc(body)}${reset ? '<br><button type="button" data-reset>Clear filters</button>' : ''}</div>`;
  }
  const filtersActive = () => state.cat !== 'all' || state.time.size || state.q;

  /* ---------- renders ---------- */
  function renderFeed() {
    const list = items.filter(it => passes(it));
    const g = $('#feed-grid');
    g.innerHTML = list.length ? list.map((it, i) => card(it, i)).join('')
      : emptyHtml('icons/clay-plate.webp', 'Nothing here yet', state.time.size ? 'Only ideas that state a time or a make-ahead tip show with time filters.' : 'Try another filter or search.', filtersActive());
    wireImages(g);
  }
  function renderPicks() {
    const body = $('#picks-body');
    const scored = items.map(it => ({ it, s: scoreItem(it) })).filter(x => x.s && passes(x.it));
    scored.sort((a, b) => b.s.score - a.s.score);
    const close = scored.filter(x => x.s.strong);
    const next = scored.filter(x => !x.s.strong);
    $('#picks-sub').textContent = profile && profile.headline ? `Matched to what he loves: ${profile.headline}.` : '';
    if (!scored.length) {
      body.innerHTML = emptyHtml('icons/clay-sweet.webp', 'No close matches yet', 'Nothing lines up with his favorites' + (filtersActive() ? ' with these filters.' : ' this week. New ideas arrive weekly.'), filtersActive());
      return;
    }
    let i = 0;
    const why = (s) => s.reasons[0] + (s.fresh.length ? ` · new: ${s.fresh[0]}` : '');
    const sec = (title, note, arr) => arr.length ? `<section class="pick-section">
      <div class="section-head"><h2>${title}</h2><p>${note}</p></div>
      <div class="grid">${arr.map(x => card(x.it, i++, why(x.s))).join('')}</div></section>` : '';
    body.innerHTML = sec('Close to his favorites', 'Textures he already says yes to.', close)
      + sec('Gentle next steps', 'A familiar format with one new food.', next);
    wireImages(body);
  }
  function renderSaved() {
    const list = items.filter(it => saved.has(it.id));
    const g = $('#saved-grid');
    g.innerHTML = list.length ? list.map((it, i) => card(it, i)).join('') : emptyHtml('icons/clay-bread.webp', 'Nothing saved yet', 'Open an idea and tap Save to keep it here.');
    wireImages(g);
  }
  function activeCount() { return (state.cat !== 'all' ? 1 : 0) + state.time.size; }
  function renderActive() {
    const box = $('#active-filters');
    const pills = [];
    if (state.cat !== 'all') pills.push(`<button type="button" class="pill" data-clear-cat aria-label="Remove ${esc(CAT_LABEL[state.cat])}">${esc(CAT_LABEL[state.cat])}<span aria-hidden="true">&times;</span></button>`);
    TIMES.filter(t => state.time.has(t.id)).forEach(t => pills.push(`<button type="button" class="pill" data-clear-time="${t.id}" aria-label="Remove ${t.label}">${t.label}<span aria-hidden="true">&times;</span></button>`));
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
    seg.style.setProperty('--tab-left', `${sel.offsetLeft - 6}px`);
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
  function countWith(cat, time) {
    const keep = { cat: state.cat, time: state.time };
    state.cat = cat; state.time = time;
    const n = baseList().filter(it => passes(it)).length;
    state.cat = keep.cat; state.time = keep.time;
    return n;
  }
  function renderSheet() {
    $('#cat-options').innerHTML = CATS.map(c => {
      const on = draft.cat === c.id;
      return `<button type="button" class="filter-chip" role="radio" aria-checked="${on}" data-cat="${c.id}">
        <span class="dot" style="background:${c.dot}"></span>
        <span class="label">${c.label}<span class="hint">${c.hint}</span></span>
        <span class="n">${countWith(c.id, draft.time)}</span><span class="check"></span></button>`;
    }).join('');
    $('#time-options').innerHTML = TIMES.map(t => {
      const on = draft.time.has(t.id);
      return `<button type="button" class="filter-chip" aria-pressed="${on}" data-time="${t.id}">
        <span class="dot" style="background:${t.dot}"></span>
        <span class="label">${t.label}<span class="hint">${t.hint}</span></span><span class="check"></span></button>`;
    }).join('');
    const n = countWith(draft.cat, draft.time);
    $('#filter-apply').textContent = `Show ${n} result${n === 1 ? '' : 's'}`;
  }
  function openFilters() {
    draft = { cat: state.cat, time: new Set(state.time) };
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
    const t = e.target.closest('[data-time]');
    if (t) {
      const id = t.dataset.time;
      if (draft.time.has(id)) draft.time.delete(id);
      else { draft.time.add(id); if (id === 'quick') draft.time.delete('long'); if (id === 'long') draft.time.delete('quick'); }
      renderSheet(); return;
    }
    if (e.target.closest('#filter-clear')) { draft = { cat: 'all', time: new Set() }; renderSheet(); return; }
    if (e.target.closest('#filter-apply')) { state.cat = draft.cat; state.time = new Set(draft.time); render(); closeFilters(); }
  });
  $('#active-filters').addEventListener('click', e => {
    if (e.target.closest('[data-clear-cat]')) state.cat = 'all';
    const t = e.target.closest('[data-clear-time]'); if (t) state.time.delete(t.dataset.clearTime);
    render();
  });

  /* ---------- card clicks (delegated) ---------- */
  document.addEventListener('click', e => {
    if (e.target.closest('[data-reset]')) { state.cat = 'all'; state.time.clear(); state.q = ''; $('#search').value = ''; closeSearchIfEmpty(); render(); return; }
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
  function openSheet(id) {
    const it = items.find(x => x.id === id); if (!it) return;
    lastFocus = document.activeElement;
    const ok = it.status === 'ok';
    const done = new Set(checked[id] || []);
    const badges = [];
    if (it.category) badges.push(`<span class="badge soft">${esc(CAT_LABEL[it.category] || it.category)}</span>`);
    const tt = timeText(it); if (tt) badges.push(`<span class="badge">${ICON.clock}${esc(tt)}</span>`);
    if (it.mealPrep) badges.push(`<span class="badge">${ICON.box}Meal prep</span>`);
    if (it.yield) badges.push(`<span class="badge soft">Makes ${esc(it.yield)}</span>`);
    const partial = it.extraction === 'video-partial';
    const ing = (it.ingredients || []).map((x, n) => `<li><label><input type="checkbox" data-ing="${n}" ${done.has(n) ? 'checked' : ''}/><span class="box"></span><span class="txt">${esc(x)}</span></label></li>`).join('');
    const steps = (it.steps || []).map(x => `<li><span>${esc(x)}</span></li>`).join('');
    const notes = (it.notes || []).map(x => `<li>${esc(x)}</li>`).join('');
    const s = scoreItem(it);
    const srcName = it.account_name ? `${esc(it.account_name)} (@${esc(it.account)})` : (it.account ? '@' + esc(it.account) : 'Instagram');
    const credit = it.extraction === 'video' ? `From the video’s narration and on-screen text, by @${esc(it.account)}. Amounts aren’t given unless said.`
      : partial ? `Mentioned in the video’s narration. The video doesn’t give a full method or amounts.`
      : it.extraction === 'recipe-page' ? `Recipe text as written on the creator’s recipe page.`
      : (ing || steps) ? `Recipe text as written in @${esc(it.account)}’s caption.` : '';
    $('#sheet-body').innerHTML = `
      <div class="sheet-hero">${photoHtml(it, '4 / 5', true)}</div>
      <h2 id="sheet-title">${esc(ok ? it.title : 'Instagram post (not fetched)')}</h2>
      <p class="sheet-by">By ${it.account_url ? `<a href="${esc(it.account_url)}" target="_blank" rel="noopener">${srcName}</a>` : srcName}${it.date ? ' · ' + esc(new Date(it.date + 'T12:00:00').toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })) : ''}</p>
      ${badges.length ? `<div class="sheet-badges">${badges.join('')}</div>` : ''}
      ${s ? `<div class="sheet-section"><strong>For him</strong>${esc(s.reasons.join(' · '))}${s.fresh.length ? esc(' · new to him: ' + s.fresh.join(', ')) : ''}</div>` : ''}
      ${ok && it.summary ? `<div class="sheet-section">${esc(it.summary)}</div>` : ''}
      ${ing ? `<div class="sheet-section"><strong>${partial ? 'Mentioned in the video' : 'Ingredients'}</strong><ul class="ing-list">${ing}</ul></div>` : ''}
      ${steps ? `<div class="sheet-section"><strong>Steps</strong><ol class="step-list">${steps}</ol></div>` : ''}
      ${!steps && !partial ? `<div class="recipe-missing"><img src="${CAT_ICON[it.category] || CAT_ICON.meal}" alt=""/><span>${ing ? 'Steps are in the video, open original.' : 'Recipe in the video, open original.'}</span></div>` : ''}
      ${credit ? `<p class="credit">${credit}</p>` : ''}
      ${notes ? `<div class="sheet-section"><strong>Why it works (from the post)</strong><ul class="note-list">${notes}</ul></div>` : ''}
      ${ok && it.caption ? `<details class="caption"><summary>Full caption</summary><p>${esc(it.caption)}</p></details>` : ''}
      <div class="sheet-actions">
        <a class="primary" href="${esc(it.recipeSourceUrl || it.url)}" target="_blank" rel="noopener">${ICON.out}Open original</a>
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
    const id = $('#sheet-save').dataset.id;
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
    const up = feed.updated_at ? new Date(feed.updated_at) : null;
    $('#about-updated').textContent = `Updated ${up ? up.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' }) : '—'} · ${items.length} ideas`;
    if (profile) $('#about-profile').textContent = `Each idea is matched against his favorites (${profile.favorites.map(f => f.label).join(', ')}). “Close to his favorites” share a main favorite; “Gentle next steps” share a texture or format and may add one new food.`;
    const accs = (sources && sources.accounts) || [];
    $('#about-sources').innerHTML = accs.map(a => `<li><a href="https://www.instagram.com/${esc(a.handle)}/" target="_blank" rel="noopener">@${esc(a.handle)}</a>${a.name ? ` · ${esc(a.name)}` : ''}</li>`).join('');
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

  window.addEventListener('resize', moveIndicator);

  /* ---------- boot ---------- */
  const get = (u) => fetch(u, { cache: 'no-cache' }).then(r => { if (!r.ok) throw new Error(u + ' ' + r.status); return r.json(); });
  Promise.all([get('data/feed.json'), get('data/profile.json').catch(() => null), get('data/sources.json').catch(() => null)])
    .then(([f, p, s]) => {
      feed = f; profile = p; sources = s;
      items = (f.items || []).slice();
      fillAbout();
      setView('feed');
      const m = location.hash.match(/item=([^&]+)/);
      if (m) openSheet(decodeURIComponent(m[1]));
    })
    .catch(err => {
      console.warn(err);
      $('#feed-grid').innerHTML = emptyHtml('icons/clay-plate.webp', 'Couldn’t load ideas', 'Check the connection and try again.');
    });
  requestAnimationFrame(moveIndicator);
})();
