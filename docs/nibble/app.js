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
    { id: 'all', label: 'All' },
    { id: 'pasta', label: 'Pasta & noodles', icon: 'icons/clay-pizza.webp' },
    { id: 'finger', label: 'Finger food', icon: 'icons/clay-bread.webp' },
    { id: 'sweet', label: 'Sweets & snacks', icon: 'icons/clay-sweet.webp' },
    { id: 'meal', label: 'Meals', icon: 'icons/clay-plate.webp' },
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

  /* ---------- cards ---------- */
  function timeBadge(it) {
    if (it.status !== 'ok') return '';
    let b = '';
    if (it.minutes) b += `<span class="pbadge">${ICON.clock}${it.minutes} min</span>`;
    else if (it.time === 'quick') b += `<span class="pbadge">${ICON.clock}Quick</span>`;
    else if (it.time === 'long') b += `<span class="pbadge">${ICON.pot}Longer cook</span>`;
    if (it.mealPrep) b += `<span class="pbadge">${ICON.box}Meal prep</span>`;
    return b;
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
      <small>${it.status === 'ok' ? 'No photo' : 'Couldn’t fetch'}</small></div></div>`;
  }
  function card(it, i, extra = '') {
    const ar = ARS[i % ARS.length];
    const isSaved = saved.has(it.id);
    const title = it.status === 'ok' ? it.title : 'Instagram post (not fetched)';
    const src = it.account ? '@' + it.account : 'Instagram';
    return `<article class="card" role="button" tabindex="0" data-id="${esc(it.id)}" style="--i:${Math.min(i, 12)}" aria-label="${esc(title)}">
      ${photoHtml(it, ar, i < 4)}
      <div class="photo-badges">${timeBadge(it)}</div>
      <button type="button" class="heart" data-heart="${esc(it.id)}" aria-pressed="${isSaved}" aria-label="${isSaved ? 'Unsave' : 'Save'} ${esc(title)}"><span>${ICON.heart}</span></button>
      <div class="card-body">
        <span class="card-src">${esc(src)}</span>
        <h3>${esc(title)}</h3>
        ${it.status === 'ok' && it.summary ? `<p class="card-sum">${esc(it.summary)}</p>` : ''}
        ${it.status !== 'ok' ? `<p class="card-sum">This post couldn’t be read from here. Open it on Instagram.</p>` : ''}
        ${extra}
        <div class="card-foot">
          <a class="open-link" href="${esc(it.url)}" target="_blank" rel="noopener" data-stop>Open original ${ICON.out}</a>
        </div>
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
      : emptyHtml('icons/clay-plate.webp', 'Nothing here yet', state.time.size ? 'Only ideas whose caption states a time or meal-prep tip show with these filters.' : 'Try another filter or search.', filtersActive());
    wireImages(g);
    const ok = items.filter(i => i.status === 'ok').length;
    $('#feed-sub').textContent = `${list.length} of ${items.length} ideas · from ${new Set(items.map(i => i.account).filter(Boolean)).size} creators${ok < items.length ? ` · ${items.length - ok} not fetched` : ''}`;
  }
  function renderPicks() {
    const body = $('#picks-body');
    const scored = items.map(it => ({ it, s: scoreItem(it) })).filter(x => x.s && passes(x.it));
    scored.sort((a, b) => b.s.score - a.s.score);
    const close = scored.filter(x => x.s.strong);
    const next = scored.filter(x => !x.s.strong);
    const favs = profile ? profile.favorites.filter(f => f.kind === 'favorite').map(f => f.label) : [];
    $('#picks-sub').textContent = profile && profile.headline ? `Ranked by what he already loves: ${profile.headline}.` : (favs.length ? `Ranked by what he already loves: ${favs.join(', ')}.` : '');
    const reasons = (s) => `<div class="reasons">${s.reasons.map(r => `<span class="reason">${esc(r)}</span>`).join('')}${s.fresh.map(f => `<span class="reason new">New: ${esc(f)}</span>`).join('')}</div>`;
    if (!scored.length) {
      body.innerHTML = emptyHtml('icons/clay-sweet.webp', 'No close matches yet', 'Nothing in the feed lines up with his favorites' + (filtersActive() ? ' with these filters.' : ' this week. New ideas arrive weekly.'), filtersActive());
      return;
    }
    let i = 0;
    const sec = (title, note, arr) => arr.length ? `<section class="pick-section">
      <div class="section-head"><h2>${title}</h2><span>${arr.length}</span></div>
      <p class="section-note">${note}</p>
      <div class="grid">${arr.map(x => card(x.it, i++, reasons(x.s))).join('')}</div></section>` : '';
    body.innerHTML = sec('Close to his favorites', 'Pasta, mac and cheese, muffins: the textures he already says yes to.', close)
      + sec('Gentle next steps', 'Same holdable, saucy or snacky format, with one new food to meet.', next);
    wireImages(body);
  }
  function renderSaved() {
    const list = items.filter(it => saved.has(it.id));
    const g = $('#saved-grid');
    g.innerHTML = list.length ? list.map((it, i) => card(it, i)).join('') : emptyHtml('icons/clay-bread.webp', 'Nothing saved yet', 'Tap the heart on any idea to keep it here.');
    wireImages(g);
  }
  function renderChips() {
    const counts = {};
    items.forEach(it => { if (passes(it, false)) counts[it.category] = (counts[it.category] || 0) + 1; });
    const total = items.filter(it => passes(it, false)).length;
    $('#cat-chips').innerHTML = CATS.map(c => `<button type="button" class="chip${c.icon ? '' : ' no-icon'}${c.id !== 'all' && !counts[c.id] ? ' is-empty' : ''}" data-cat="${c.id}" aria-pressed="${state.cat === c.id}">
      ${c.icon ? `<img src="${c.icon}" alt="" width="34" height="34"/>` : ''}${c.label} <span class="count">${c.id === 'all' ? total : (counts[c.id] || 0)}</span></button>`).join('');
    $$('#time-chips .chip').forEach(b => b.setAttribute('aria-pressed', state.time.has(b.dataset.time)));
  }
  function render() {
    renderChips();
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
    const filters = $('#filters');
    if (v === 'saved') filters.hidden = true;
    else { filters.hidden = false; $(`#panel-${v} .panel-header`).appendChild(filters); }
    moveIndicator();
    render();
  }
  $$('.tab', seg).forEach(t => t.addEventListener('click', () => setView(t.dataset.tab)));
  $('#saved-btn').addEventListener('click', () => setView(state.view === 'saved' ? 'feed' : 'saved'));

  /* ---------- chips ---------- */
  $('#cat-chips').addEventListener('click', e => {
    const b = e.target.closest('[data-cat]'); if (!b) return;
    state.cat = (state.cat === b.dataset.cat && b.dataset.cat !== 'all') ? 'all' : b.dataset.cat;
    render();
  });
  $('#time-chips').addEventListener('click', e => {
    const b = e.target.closest('[data-time]'); if (!b) return;
    const t = b.dataset.time;
    if (state.time.has(t)) state.time.delete(t);
    else { state.time.add(t); if (t === 'quick') state.time.delete('long'); if (t === 'long') state.time.delete('quick'); }
    render();
  });

  /* ---------- card clicks (delegated) ---------- */
  document.addEventListener('click', e => {
    if (e.target.closest('[data-reset]')) { state.cat = 'all'; state.time.clear(); state.q = ''; $('#search').value = ''; closeSearchIfEmpty(); render(); return; }
    const h = e.target.closest('[data-heart]');
    if (h) { e.stopPropagation(); toggleSave(h.dataset.heart); return; }
    if (e.target.closest('[data-stop]')) return;
    const c = e.target.closest('.card');
    if (c) openSheet(c.dataset.id);
  });
  document.addEventListener('keydown', e => {
    if ((e.key === 'Enter' || e.key === ' ') && e.target.classList && e.target.classList.contains('card')) { e.preventDefault(); openSheet(e.target.dataset.id); }
    if (e.key === 'Escape') { if (!$('#sheet').hidden) closeSheet(); else if ($('#about-drawer').classList.contains('open')) closeAbout(); }
  });
  function toggleSave(id) {
    if (saved.has(id)) saved.delete(id); else saved.add(id);
    store(SAVED_KEY, [...saved]);
    $$(`[data-heart="${CSS.escape(id)}"]`).forEach(b => b.setAttribute('aria-pressed', saved.has(id)));
    const sb = $('#sheet-save'); if (sb && sb.dataset.id === id) { sb.setAttribute('aria-pressed', saved.has(id)); sb.lastChild.textContent = saved.has(id) ? 'Saved' : 'Save'; }
    if (state.view === 'saved') renderSaved();
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
    if (it.category) badges.push(`<span class="badge">${esc(CAT_LABEL[it.category] || it.category)}</span>`);
    if (it.minutes) badges.push(`<span class="badge">${ICON.clock}${it.minutes} min</span>`);
    else if (it.time === 'quick') badges.push(`<span class="badge">${ICON.clock}Quick</span>`);
    else if (it.time === 'long') badges.push(`<span class="badge">${ICON.pot}Longer cook</span>`);
    if (it.mealPrep) badges.push(`<span class="badge">${ICON.box}Meal prep</span>`);
    if (it.yield) badges.push(`<span class="badge soft">Makes ${esc(it.yield)}</span>`);
    const ing = (it.ingredients || []).map((x, n) => `<li><label><input type="checkbox" data-ing="${n}" ${done.has(n) ? 'checked' : ''}/><span class="box"></span><span class="txt">${esc(x)}</span></label></li>`).join('');
    const steps = (it.steps || []).map(x => `<li><span>${esc(x)}</span></li>`).join('');
    const notes = (it.notes || []).map(x => `<li>${esc(x)}</li>`).join('');
    const s = scoreItem(it);
    const srcName = it.account_name ? `${esc(it.account_name)} (@${esc(it.account)})` : (it.account ? '@' + esc(it.account) : 'Instagram');
    const fromWhere = it.extraction === 'recipe-page' ? `the creator’s recipe page` : `@${esc(it.account)}’s caption`;
    $('#sheet-body').innerHTML = `
      <div class="sheet-hero">${photoHtml(it, '4 / 5', true)}</div>
      <h2 id="sheet-title">${esc(ok ? it.title : 'Instagram post (not fetched)')}</h2>
      <p class="sheet-by">By ${it.account_url ? `<a href="${esc(it.account_url)}" target="_blank" rel="noopener">${srcName}</a>` : srcName}${it.date ? ' · ' + esc(new Date(it.date + 'T12:00:00').toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })) : ''}</p>
      <div class="sheet-badges">${badges.join('')}</div>
      ${s ? `<div class="sheet-section"><strong>Why it’s a pick for him</strong><div class="reasons">${s.reasons.map(r => `<span class="reason">${esc(r)}</span>`).join('')}${s.fresh.map(f => `<span class="reason new">New: ${esc(f)}</span>`).join('')}</div></div>` : ''}
      ${ok && it.summary ? `<div class="sheet-section">${esc(it.summary)}</div>` : ''}
      ${ing ? `<div class="sheet-section"><strong>Ingredients</strong><ul class="ing-list">${ing}</ul></div>` : ''}
      ${steps ? `<div class="sheet-section"><strong>Steps</strong><ol class="step-list">${steps}</ol></div>` : ''}
      ${!ing && !steps ? `<div class="recipe-missing"><img src="${CAT_ICON[it.category] || CAT_ICON.meal}" alt=""/><span>Recipe in the video, open original.</span></div>` : ''}
      ${notes ? `<div class="sheet-section"><strong>Why it works (from the post)</strong><ul class="note-list">${notes}</ul></div>` : ''}
      ${ok && it.caption ? `<details class="caption"><summary>Full caption</summary><p>${esc(it.caption)}</p></details>` : ''}
      ${ing || steps ? `<p class="credit">Recipe text as written in ${fromWhere}.</p>` : ''}
      <div class="sheet-actions">
        <a class="primary" href="${esc(it.recipeSourceUrl || it.url)}" target="_blank" rel="noopener">${ICON.out}Open original</a>
        ${it.recipeSourceUrl ? `<a class="ghost" href="${esc(it.url)}" target="_blank" rel="noopener">${ICON.out}Instagram post</a>` : ''}
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
