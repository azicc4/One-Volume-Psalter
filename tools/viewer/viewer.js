// Book preview viewer: two-page spreads, nine ribbons, the Ordinary card, page turning. Served by tools/viewer/serve.py ("preview main.bat").
import * as pdfjsLib from './vendor/pdfjs/pdf.min.mjs';

pdfjsLib.GlobalWorkerOptions.workerSrc = new URL('./vendor/pdfjs/pdf.worker.min.mjs', import.meta.url).href;

// The nine ribbons of the one-volume book, assigned by use (TODO B-16, reports/simulation.md; the book's
// "Finding the Office", lh/render/common.py RIBBONS). `home` finds the ribbon's starting place among the PDF's
// bookmarks (`deep`: any level).
const RIBBONS = [
  { id: 'S',  name: 'Saints',            color: '#b3261e', home: /saints/i },
  { id: 'C',  name: 'Commons',           color: '#d4a017', home: /^commons/i },
  { id: 'O',  name: 'Ordinary: Compline', color: '#efe6cf', home: /^compline$/i, deep: true },
  { id: 'T1', name: 'Time: the hour',    color: '#2e7d32', home: /propers? of time/i },
  { id: 'T3', name: 'Time: the week',    color: '#00897b', home: /proper to each week/i, deep: true },
  { id: 'H',  name: 'Hymns',             color: '#1e63b5', home: /^hymns/i },
  { id: 'P1', name: 'Psalter',           color: '#7b1fa2', home: /psalter/i },
  { id: 'P2', name: 'Psalter, Canticles', color: '#d81b60', home: /^canticles/i },
  { id: 'R',  name: 'Readings',          color: '#795548', home: /readings/i },
];
const R = Object.fromEntries(RIBBONS.map((r, i) => [r.id, i]));
// which ribbon a reference into a section belongs to (shift-click on an ordinary page reference)
const SECTION_RIBBON = [[/saints/i, R.S], [/^commons/i, R.C], [/ordinary/i, R.O], [/propers? of time/i, R.T1],
  [/^hymns/i, R.H], [/psalter/i, R.P1], [/canticles/i, R.P2], [/readings/i, R.R]];

const $ = (s) => document.querySelector(s);
const el = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)');

const S = {
  file: new URLSearchParams(location.search).get('file') || 'book',
  pdf: null, n: 0, labels: [], outline: [], flat: [], sections: [],
  spread: 0, ribbons: RIBBONS.map(() => null), pw: 0, ph: 0, scale: 1, size: null,
};

// ------------------------------------------------------------------------------------------ pages and spreads
// Page 1 (index 0) is a recto standing alone; spread s shows pages 2s-1 (left) and 2s (right), 0-based.
const spreadOf = (i) => Math.floor((i + 1) / 2);
const pagesOf = (s) => [2 * s - 1 >= 0 ? 2 * s - 1 : null, 2 * s < S.n ? 2 * s : null];
const lastSpread = () => spreadOf(S.n - 1);
const label = (i) => (i == null ? '–' : S.labels[i] || String(i + 1));
const spreadLabel = (s) => { const [l, r] = pagesOf(s); return `${label(l)} | ${label(r)}`; };

// ------------------------------------------------------------------------------------------ persistence
const storeKey = () => `ovp-viewer:v3:${S.file}`;          // v3: nine ribbons by use (B-16)
function save() {
  try { localStorage.setItem(storeKey(), JSON.stringify({ ribbons: S.ribbons, spread: S.spread, n: S.n })); } catch {}
}
function load() {
  try { return JSON.parse(localStorage.getItem(storeKey()) || 'null'); } catch { return null; }
}
function prefs(k, v) {
  try { if (v === undefined) return localStorage.getItem('ovp-viewer:' + k); localStorage.setItem('ovp-viewer:' + k, v); } catch {}
  return null;
}

// ------------------------------------------------------------------------------------------ rendering
// Kept light after SumatraPDF's render cache:
// - the PDF arrives in byte ranges as pages are needed, and pdf.js parses lazily;
// - one render at a time, from a priority queue: visible pages, then the sharp zoom layer, then neighbours, then
//   page-edge thumbnails; requests for pages you have turned past are dropped;
// - a small fixed cache of rendered pages, freed eagerly;
// - zoom stretches the page already drawn and re-renders only the part on screen.
const CACHE_PAGES = 10;                  // rendered pages kept: the spread on show, both neighbours, a few behind
const THUMBS = 16;
const PRIO = { visible: 0, detail: 1, neighbour: 2, thumb: 3 };

const jobs = [];
let active = null;

function schedule(key, prio, start) {
  if (active && active.key === key && !active.cancelled) return active.promise;
  let j = jobs.find((x) => x.key === key);
  if (j) { j.prio = Math.min(j.prio, prio); return j.promise; }
  j = { key, prio, start, cancelled: false, task: null };
  j.promise = new Promise((res, rej) => { j.resolve = res; j.reject = rej; });
  j.promise.catch(() => {});
  jobs.push(j);
  queueMicrotask(pump);
  return j.promise;
}

function unschedule(key) {
  const at = jobs.findIndex((x) => x.key === key);
  if (at >= 0) jobs.splice(at, 1)[0].reject(new Error('dropped'));
  if (active && active.key === key) { active.cancelled = true; active.task?.cancel(); }
}

function unscheduleAll(prefix, keep = () => false) {
  for (const j of [...jobs]) if (j.key.startsWith(prefix) && !keep(j.key)) unschedule(j.key);
}

async function pump() {
  if (active || !jobs.length) return;
  jobs.sort((a, b) => a.prio - b.prio);
  const j = active = jobs.shift();
  try {
    j.task = await j.start();
    if (j.cancelled) j.task?.cancel();
    if (j.task) await j.task.promise;
    if (j.cancelled) j.reject(new Error('cancelled')); else j.resolve();
  } catch (err) {
    j.reject(err);
  } finally {
    active = null;
    pump();
  }
}

const cache = new Map();               // page index → { el, canvas, links, detail, done } at the current scale
const inUse = new Set();               // pages on show (or about to be, during a turn)

function sheet(i, prio = PRIO.visible) {
  if (i == null) return null;
  let c = cache.get(i);
  if (c) {
    cache.delete(i); cache.set(i, c);                              // LRU touch
  } else {
    const e = el('div', 'sheet');
    e.dataset.page = i;
    c = { el: e, canvas: el('canvas'), links: el('div', 'links'), detail: null, done: false };
    e.append(c.canvas, c.links);
    cache.set(i, c);
    addLinks(i, c.links);
    evict();
  }
  if (!c.done) {
    c.ready = schedule(`p${i}`, prio, () => startBase(i, c)).then(() => { c.done = true; }, () => {});
  }
  return c;
}

async function startBase(i, c) {
  const page = await S.pdf.getPage(i + 1);
  const vp = page.getViewport({ scale: S.scale });
  const dpr = window.devicePixelRatio || 1;
  c.canvas.width = Math.floor(vp.width * dpr);
  c.canvas.height = Math.floor(vp.height * dpr);
  return page.render({ canvasContext: c.canvas.getContext('2d'), viewport: vp,
    transform: dpr !== 1 ? [dpr, 0, 0, dpr, 0, 0] : null });
}

function free(canvas) {
  if (canvas) canvas.width = canvas.height = 0;                  // give the bitmap memory back now, not at GC
}

function drop(i) {
  const c = cache.get(i);
  if (!c) return;
  unschedule(`p${i}`);
  unschedule(`d${i}`);
  free(c.canvas);
  free(c.detail);
  c.el.remove();
  cache.delete(i);
  S.pdf.getPage(i + 1).then((p) => p.cleanup()).catch(() => {});
}

function evict() {
  for (const k of [...cache.keys()]) {
    if (cache.size <= CACHE_PAGES) break;
    if (!inUse.has(k)) drop(k);
  }
}

async function addLinks(i, links) {
  const page = await S.pdf.getPage(i + 1);
  const vp = page.getViewport({ scale: S.scale });
  const annots = await page.getAnnotations({ intent: 'display' });
  for (const a of annots) {
    if (a.subtype !== 'Link' || (!a.dest && !a.url)) continue;
    const [x1, y1, x2, y2] = vp.convertToViewportRectangle(a.rect);
    const link = el('a');
    Object.assign(link.style, { left: `${Math.min(x1, x2)}px`, top: `${Math.min(y1, y2)}px`,
      width: `${Math.abs(x2 - x1)}px`, height: `${Math.abs(y2 - y1)}px` });
    link.title = a.url || 'Click: turn there · Shift-click: lay the matching ribbon there';
    link.addEventListener('click', (ev) => { ev.preventDefault(); onLink(ev, i, a, annots); });
    links.append(link);
  }
}

// render scale: two pages side by side fill the stage at zoom 1, leaving room for a few ribbons in the gutter
const GAP_RESERVE = 33;
function measure() {
  const st = $('#stage');
  if (st.clientWidth < 100 || st.clientHeight < 100) { if (S.pw) return; }   // a hidden tab: keep the last size
  const w = Math.max(200, st.clientWidth - 24 - GAP_RESERVE), h = Math.max(200, st.clientHeight - 48);   // margin + ribbon tails
  const scale = Math.max(0.2, Math.min(w / (2 * S.size.w), h / S.size.h));
  S.scale = scale; S.pw = Math.floor(S.size.w * scale); S.ph = Math.floor(S.size.h * scale);
  const book = $('#book');
  book.style.setProperty('--pw', `${S.pw}px`);
  book.style.setProperty('--ph', `${S.ph}px`);
}

function place(slot, c) {
  slot.replaceChildren();
  if (c) slot.append(c.el);
}

function showSpread(s) {
  const [l, r] = pagesOf(s);
  inUse.clear(); [l, r].forEach((i) => i != null && inUse.add(i));
  place($('#slotL'), sheet(l));
  place($('#slotR'), sheet(r));
  // unrendered pages of spreads turned past (riffling, a held arrow key) are no longer wanted
  for (const [k, c] of [...cache]) if (!inUse.has(k) && !c.done && Math.abs(spreadOf(k) - s) > 1) drop(k);
}

function prefetch(s) {
  const run = () => {
    if (s !== S.spread) return;
    [s + 1, s - 1].forEach((t) => t >= 0 && t <= lastSpread() && pagesOf(t).forEach((i) => sheet(i, PRIO.neighbour)));
  };
  (window.requestIdleCallback || ((f) => setTimeout(f, 120)))(run);
}

// ------------------------------------------------------------------------------------------ zoom and pan
// Wheel (or pinch) zooms about the pointer; drag pans; double-click or F fits the spread again. The pages already
// drawn are stretched at once; after a pause the visible part of each page is drawn sharp at the new size.
const MAX_ZOOM = 5;
const Z = { z: 1, fit: 1, tx: 0, ty: 0 };
let fitted = true;                       // follow the fit size (window resize, ribbons widening the gutter)

function viewBox() {
  const v = $('#view');
  return { x: v.offsetLeft, y: v.offsetTop, w: v.offsetWidth, h: v.offsetHeight };
}

function computeFit() {
  const st = $('#stage'), b = viewBox();
  if (!b.w || !b.h || st.clientWidth < 100 || st.clientHeight < 100) return;   // hidden: keep the last fit
  Z.fit = Math.max(0.1, Math.min(1, (st.clientWidth - 24) / b.w, (st.clientHeight - 12) / b.h));
}

function applyView() {
  const st = $('#stage'), b = viewBox();
  if (fitted || Z.z <= Z.fit + 1e-3) {
    fitted = true;
    Z.z = Z.fit; Z.tx = ((1 - Z.z) * b.w) / 2; Z.ty = ((1 - Z.z) * b.h) / 2;
  } else {                                                          // keep the book under the middle of the stage
    const cx = st.clientWidth / 2, cy = st.clientHeight / 2;
    Z.tx = Math.min(cx - b.x, Math.max(cx - b.x - b.w * Z.z, Z.tx));
    Z.ty = Math.min(cy - b.y, Math.max(cy - b.y - b.h * Z.z, Z.ty));
  }
  $('#view').style.transform = `translate(${Z.tx}px, ${Z.ty}px) scale(${Z.z})`;
  document.body.classList.toggle('zoomed', !fitted);
  // percentage of the printed size (96 CSS px to the inch)
  $('#zoomBtn').textContent = `${Math.round(((S.scale * Z.z) / (96 / 72)) * 100)}%`;
  scheduleDetail();
  placeCard();
}

function zoomAt(px, py, z) {
  const b = viewBox();
  const nz = Math.max(Z.fit, Math.min(MAX_ZOOM, z));
  const qx = (px - b.x - Z.tx) / Z.z, qy = (py - b.y - Z.ty) / Z.z;
  Z.tx = px - b.x - nz * qx; Z.ty = py - b.y - nz * qy; Z.z = nz;
  fitted = nz <= Z.fit + 1e-3;
  applyView();
}

function zoomCentre(f) {
  const st = $('#stage');
  zoomAt(st.clientWidth / 2, st.clientHeight / 2, Z.z * f);
}

function fit() { fitted = true; applyView(); }

function setupZoom() {
  const st = $('#stage');
  const local = (e) => { const r = st.getBoundingClientRect(); return [e.clientX - r.left - st.clientLeft, e.clientY - r.top - st.clientTop]; };
  st.addEventListener('wheel', (e) => {
    e.preventDefault();
    const d = e.deltaMode === 1 ? e.deltaY * 33 : e.deltaMode === 2 ? e.deltaY * 400 : e.deltaY;
    zoomAt(...local(e), Z.z * Math.exp(-d * (e.ctrlKey ? 0.01 : 0.0015)));   // ctrlKey: a trackpad pinch
  }, { passive: false });
  let drag = null, eatClick = false;
  st.addEventListener('pointerdown', (e) => {
    if (e.button !== 0 || fitted) return;
    drag = { x: e.clientX, y: e.clientY, tx: Z.tx, ty: Z.ty, id: e.pointerId, moved: false };
  });
  st.addEventListener('pointermove', (e) => {
    if (!drag) return;
    const dx = e.clientX - drag.x, dy = e.clientY - drag.y;
    if (!drag.moved) {
      if (Math.hypot(dx, dy) < 4) return;
      drag.moved = true;
      st.setPointerCapture(drag.id);
      document.body.classList.add('panning');
    }
    Z.tx = drag.tx + dx; Z.ty = drag.ty + dy;
    applyView();
  });
  const end = () => {
    if (drag?.moved) { eatClick = true; setTimeout(() => { eatClick = false; }, 0); }
    drag = null;
    document.body.classList.remove('panning');
  };
  st.addEventListener('pointerup', end);
  st.addEventListener('pointercancel', end);
  st.addEventListener('click', (e) => { if (eatClick) { e.stopPropagation(); e.preventDefault(); } }, true);
  st.addEventListener('dblclick', (e) => { if (!e.target.closest('.links a')) fit(); });
  $('#zoomBtn').addEventListener('click', fit);
}

let detailTimer;
function scheduleDetail() {
  clearTimeout(detailTimer);
  detailTimer = setTimeout(renderDetail, 140);
}

function renderDetail() {
  unscheduleAll('d');
  for (const [i, c] of cache) {
    if (!inUse.has(i) || Z.z <= 1.05) { free(c.detail); c.detail?.remove(); c.detail = null; }
  }
  if (Z.z <= 1.05 || busy) return;
  for (const i of inUse) {
    const c = cache.get(i);
    if (c) schedule(`d${i}`, PRIO.detail, () => startDetail(i, c));
  }
}

// draw the part of page i that is on screen at full screen resolution, over the stretched page
async function startDetail(i, c) {
  if (!c.el.isConnected || busy) return null;
  const st = $('#stage').getBoundingClientRect(), r = c.el.getBoundingClientRect();
  const x0 = Math.max(st.left, r.left), x1 = Math.min(st.right, r.right);
  const y0 = Math.max(st.top, r.top), y1 = Math.min(st.bottom, r.bottom);
  if (x1 <= x0 || y1 <= y0) return null;
  const k = r.width / S.pw;                                          // screen px per page px
  const lx = (x0 - r.left) / k, ly = (y0 - r.top) / k, lw = (x1 - x0) / k, lh = (y1 - y0) / k;
  const dev = k * (window.devicePixelRatio || 1);
  const page = await S.pdf.getPage(i + 1);
  const canvas = el('canvas', 'detail');
  canvas.width = Math.ceil(lw * dev); canvas.height = Math.ceil(lh * dev);
  Object.assign(canvas.style, { left: `${lx}px`, top: `${ly}px`, width: `${lw}px`, height: `${lh}px` });
  const vp = page.getViewport({ scale: S.scale * dev, offsetX: -lx * dev, offsetY: -ly * dev });
  const task = page.render({ canvasContext: canvas.getContext('2d'), viewport: vp });
  task.promise.then(() => {
    if (!c.el.isConnected || !inUse.has(i)) { free(canvas); return; }
    const old = c.detail;
    c.detail = canvas;
    c.el.insertBefore(canvas, c.links);
    if (old) { old.remove(); free(old); }
  }, () => free(canvas));
  return task;
}

// ------------------------------------------------------------------------------------------ turning
let busy = false, pending = null;

async function go(target, { animate = true, flash = null } = {}) {
  target = Math.max(0, Math.min(lastSpread(), target));
  if (target === S.spread && !busy) { if (flash != null) flashPage(flash); return; }
  if (busy) { pending = { target, flash }; return; }
  busy = true;
  const from = S.spread, fwd = target > from;
  const [oL, oR] = pagesOf(from).map((i) => (i == null ? null : cache.get(i) || sheet(i)));
  const [nLi, nRi] = pagesOf(target);
  [nLi, nRi].forEach((i) => i != null && inUse.add(i));
  const nL = sheet(nLi), nR = sheet(nRi);
  await Promise.race([Promise.all([nL?.ready, nR?.ready]), sleep(450)]);   // don't turn onto a blank page

  if (!animate || reducedMotion.matches || document.hidden || target === from) {
    showSpread(target);
  } else {
    $('#gutter').replaceChildren();
    const leaf = el('div', `leaf ${fwd ? 'fwd' : 'back'}`);
    const front = el('div', 'face f'), back = el('div', 'face b');
    leaf.append(front, back);
    if (fwd) { place($('#slotR'), nR); if (oR) front.append(oR.el); if (nL) back.append(nL.el); }
    else { place($('#slotL'), nL); if (oL) front.append(oL.el); if (nR) back.append(nR.el); }
    $('#book').append(leaf);
    const dur = Math.abs(target - from) > 1 ? 420 : 340;
    const anim = leaf.animate([{ transform: 'rotateY(0deg)' }, { transform: `rotateY(${fwd ? -180 : 180}deg)` }],
      { duration: dur, easing: 'cubic-bezier(.45,.05,.35,1)' });
    // a hidden tab stops the animation clock: never wait on it longer than the turn itself
    await Promise.race([anim.finished.catch(() => {}), sleep(dur + 200)]);
    anim.cancel();
    showSpread(target);
    leaf.remove();
  }
  S.spread = target;
  busy = false;
  afterMove();
  if (flash != null) flashPage(flash);
  prefetch(target);
  if (pending) { const p = pending; pending = null; go(p.target, { flash: p.flash }); }
}

function flashPage(i) {
  const c = cache.get(i);
  if (!c) return;
  c.el.classList.remove('flash'); void c.el.offsetWidth; c.el.classList.add('flash');
}

function afterMove() {
  save();
  drawRibbons();
  drawGutter();
  drawEdge();
  markOutline();
  $('#where').textContent = spreadLabel(S.spread);
  $('#prev').disabled = S.spread === 0;
  $('#next').disabled = S.spread === lastSpread();
}

// ------------------------------------------------------------------------------------------ ribbons
function clickRibbon(k) {
  const pos = S.ribbons[k];
  if (pos == null) { S.ribbons[k] = S.spread; toast(`${RIBBONS[k].name} laid in ${spreadLabel(S.spread)}`); }
  else if (pos === S.spread) { S.ribbons[k] = null; toast(`${RIBBONS[k].name} taken out (loose)`); }
  else { go(pos); return; }
  save(); drawRibbons(); drawGutter(); drawEdge();
}

function layRibbon(k, s) {
  S.ribbons[k] = s;
  save(); drawRibbons(); drawGutter(); drawEdge();
  toast(`${RIBBONS[k].name} laid in ${spreadLabel(s)}`);
}

function drawRibbons() {
  const bar = $('#ribbons');
  if (!bar.children.length) {
    RIBBONS.forEach((r, k) => {
      const b = el('button', 'rib');
      b.style.setProperty('--c', r.color);
      const txt = el('span', 'txt');
      const name = el('span', 'name');
      name.append(el('kbd', null, String((k + 1) % 10)), r.name);
      txt.append(name, el('span', 'pos'));
      b.append(el('span', 'tail'), txt);
      b.addEventListener('click', () => clickRibbon(k));
      bar.append(b);
    });
  }
  [...bar.children].forEach((b, k) => {
    const pos = S.ribbons[k];
    b.classList.toggle('loose', pos == null);
    b.classList.toggle('here', pos === S.spread);
    b.querySelector('.pos').textContent = pos == null ? 'loose' : spreadLabel(pos);
    b.title = pos == null ? `${RIBBONS[k].name}: loose — click to lay it in these pages`
      : pos === S.spread ? `${RIBBONS[k].name}: here — click to take it out`
      : `${RIBBONS[k].name}: between ${spreadLabel(pos)} — click to turn there`;
  });
}

// The ribbons in the open spread lie side by side in the gutter, which widens to hold them, so they never cover text.
const RIB_W = 7, RIB_STEP = 9;
function drawGutter() {
  const g = $('#gutter');
  g.replaceChildren();
  const here = RIBBONS.map((r, k) => k).filter((k) => S.ribbons[k] === S.spread);
  here.forEach((k, j) => {
    const r = el('div', 'grib');
    r.style.setProperty('--c', RIBBONS[k].color);
    r.style.left = `${(j - (here.length - 1) / 2) * RIB_STEP - RIB_W / 2}px`;
    r.title = RIBBONS[k].name;
    g.append(r);
  });
  const gap = here.length ? here.length * RIB_STEP + 6 : 0;
  if ($('#book').style.getPropertyValue('--gap') !== `${gap}px`) {
    $('#book').style.setProperty('--gap', `${gap}px`);
    computeFit();
    applyView();
  }
}

function defaults() {
  return RIBBONS.map((r) => {
    const sec = (r.deep ? S.flat : S.sections).find((x) => r.home.test(x.title));
    return sec ? spreadOf(sec.index) : null;
  });
}

// ------------------------------------------------------------------------------------------ links in the book
async function onLink(ev, pageIdx, a, annots) {
  if (a.url) { window.open(a.url, '_blank', 'noopener'); return; }
  const dest = await destIndex(a.dest);
  if (dest == null) return;
  if (!ev.shiftKey) { go(spreadOf(dest), { flash: dest }); return; }
  const k = await ribbonForLink(pageIdx, a, annots, dest);
  if (k == null) { toast('No ribbon for that part of the book'); return; }
  layRibbon(k, spreadOf(dest));
}

// Hour headings print "Lauds   O 672 P 1582, 1702, 1681" (R … for the readings): O → Ordinary ribbon, the n-th P →
// Psalter n (the Invitatory psalm → P4), R → Readings. Any other reference → the ribbon of the section it points into.
async function ribbonForLink(pageIdx, a, annots, dest) {
  const mid = (a.rect[1] + a.rect[3]) / 2;
  const sameLine = (r) => Math.abs((r[1] + r[3]) / 2 - mid) < 3;
  const lineLinks = annots.filter((x) => x.subtype === 'Link' && x.dest && sameLine(x.rect)).sort((p, q) => p.rect[0] - q.rect[0]);
  const page = await S.pdf.getPage(pageIdx + 1);
  const tc = await page.getTextContent();
  const words = tc.items.filter((it) => it.str.trim() && it.transform[5] >= a.rect[1] - 2 && it.transform[5] <= a.rect[3])
    .sort((p, q) => p.transform[4] - q.transform[4]).map((it) => it.str).join(' ');
  const kinds = [];
  let kind = null;
  for (const tok of words.split(/[\s,·]+/)) {
    if (/^[OPR]$/.test(tok)) kind = tok;
    else if (kind && /^\d+$/.test(tok)) kinds.push(kind);
  }
  const at = lineLinks.indexOf(a);
  if (kinds.length && kinds.length === lineLinks.length && at >= 0) {
    const k = kinds[at];
    if (k === 'O') return R.O;
    if (k === 'R') return R.R;
    // psalms: the first on ribbon 8; a canticle, or the next psalm, on ribbon 9
    if (/canticles/i.test(sectionOf(dest)?.title || '')) return R.P2;
    return kinds.slice(0, at).filter((x) => x === 'P').length ? R.P2 : R.P1;
  }
  const sec = sectionOf(dest);
  const hit = sec && SECTION_RIBBON.find(([re]) => re.test(sec.title));
  return hit ? hit[1] : null;
}

// ------------------------------------------------------------------------------------------ outline (left nav)
async function destIndex(dest) {
  try {
    const d = typeof dest === 'string' ? await S.pdf.getDestination(dest) : dest;
    if (!d) return null;
    return typeof d[0] === 'number' ? d[0] : await S.pdf.getPageIndex(d[0]);
  } catch { return null; }
}

async function loadOutline() {
  if (await loadServerOutline()) return;
  const raw = (await S.pdf.getOutline()) || [];
  const walk = async (items, lvl, parent) => {
    const out = [];
    for (const it of items) {
      const node = { title: it.title, lvl, index: await destIndex(it.dest), parent, kids: [] };
      node.kids = await walk(it.items || [], lvl + 1, node);
      out.push(node);
    }
    return out;
  };
  finishOutline(await walk(raw, 0, null));
}

// The server reads the bookmarks with PyMuPDF ([level, title, page index] rows); resolving them here instead walks
// the PDF's whole named-destination tree, which is most of the file.
async function loadServerOutline() {
  let rows;
  try {
    const res = await fetch(`outline/${encodeURIComponent(S.file)}.json`, { cache: 'no-store' });
    if (!res.ok) return false;
    rows = await res.json();
  } catch { return false; }
  const root = { kids: [], lvl: -1 }, stack = [root];
  for (const [lvl, title, index] of rows) {
    while (stack.length > 1 && stack[stack.length - 1].lvl >= lvl) stack.pop();
    const parent = stack[stack.length - 1];
    const node = { title, lvl, index, parent: parent === root ? null : parent, kids: [] };
    parent.kids.push(node);
    stack.push(node);
  }
  finishOutline(root.kids);
  return true;
}

function finishOutline(outline) {
  S.outline = outline;
  const flat = [];
  const visit = (ns) => ns.forEach((n) => { if (n.index != null) flat.push(n); visit(n.kids); });
  visit(S.outline);
  S.flat = flat;
  S.sections = S.outline.filter((n) => n.index != null).sort((p, q) => p.index - q.index);
}

function sectionOf(i) {
  let hit = null;
  for (const s of S.sections) if (s.index <= i) hit = s;
  return hit;
}

// the bookmark in force on page i: the last one starting at or before it; of several on the same page the first,
// unless a later one is nested inside it ("The Ordinary" → "Finding the Office", both on one page)
function bookmarkAt(i) {
  let cur = null;
  const inside = (n, a) => { for (let p = n.parent; p; p = p.parent) if (p === a) return true; return false; };
  for (const n of S.flat) {
    if (n.index > i) continue;
    if (!cur || n.index > cur.index || (n.index === cur.index && inside(n, cur))) cur = n;
  }
  return cur;
}

function ribbonDot(node) {
  if (node.lvl) return null;
  const r = RIBBONS.find((x) => x.home.test(node.title));
  if (!r) return null;
  const d = el('span', 'dot');
  d.style.setProperty('--c', r.color);
  return d;
}

function drawOutline() {
  const root = $('#outlineTree');
  root.replaceChildren();
  const row = (n, top) => {
    const r = el('div', `oitem${top ? ' top' : ''}`);
    r.style.setProperty('--lvl', n.lvl);
    r.append(el('span', 'caret', n.kids.length ? '▸' : ''));
    const dot = ribbonDot(n);
    if (dot) r.append(dot);
    r.append(el('span', 't', n.title), el('span', 'p', n.index != null ? label(n.index) : ''));
    r.title = n.title;
    r.addEventListener('click', (ev) => {
      if (n.kids.length && ev.target.classList.contains('caret')) return;   // caret only folds
      if (n.index != null) go(spreadOf(n.index), { flash: n.index });
    });
    n.row = r;
    return r;
  };
  const build = (nodes, into) => nodes.forEach((n) => {
    if (n.kids.length) {
      const d = el('details');
      const sm = el('summary');
      sm.append(row(n, n.lvl === 0));
      d.append(sm);
      build(n.kids, d);
      into.append(d);
      n.details = d;
    } else into.append(row(n, n.lvl === 0));
  });
  build(S.outline, root);
}

function markOutline() {
  const [l, r] = pagesOf(S.spread);
  const top = r ?? l;
  const cur = bookmarkAt(top);
  S.flat.forEach((n) => n.row?.classList.toggle('current', n === cur));
  if (cur) {
    for (let p = cur.parent; p; p = p.parent) if (p.details && !p.details.open) p.details.open = true;
    const box = $('#outline'), rr = cur.row.getBoundingClientRect(), bb = box.getBoundingClientRect();
    if (rr.top < bb.top || rr.bottom > bb.bottom) cur.row.scrollIntoView({ block: 'center' });
    const trail = [];
    for (let p = cur; p; p = p.parent) trail.unshift(p.title);
    $('#crumb').textContent = trail.join(' › ');
  } else $('#crumb').textContent = '';
}

// ------------------------------------------------------------------------------------------ page edge + thumbnails
function drawEdge() {
  const t = $('#edgeTrack');
  if (!t.dataset.built) {
    t.dataset.built = '1';
    const secs = S.sections.length && S.sections[0].index > 0 ? [{ title: 'Front', index: 0 }, ...S.sections] : S.sections;
    secs.forEach((s, j) => {
      const end = j + 1 < secs.length ? secs[j + 1].index : S.n;
      const seg = el('div', 'eseg', s.title.replace(/^The /, ''));
      seg.style.left = `${(100 * s.index) / S.n}%`;
      seg.style.width = `${(100 * (end - s.index)) / S.n}%`;
      t.append(seg);
    });
    t.append(el('div', 'ecur'));
  }
  t.querySelectorAll('.erib').forEach((e) => e.remove());
  RIBBONS.forEach((r, k) => {
    const s = S.ribbons[k];
    if (s == null) return;
    const m = el('div', 'erib');
    m.style.setProperty('--c', r.color);
    m.style.left = `${(100 * 2 * s) / S.n}%`;
    t.append(m);
  });
  const cur = t.querySelector('.ecur');
  const [l, r] = pagesOf(S.spread);
  const a = l ?? r, b = r ?? l;
  cur.style.left = `${(100 * a) / S.n}%`;
  cur.style.width = `${(100 * (b - a + 1)) / S.n}%`;
}

const thumbs = new Map();               // page index → { canvas, promise }, a few only
function thumb(i) {
  let t = thumbs.get(i);
  if (t) { thumbs.delete(i); thumbs.set(i, t); return t.promise; }
  const canvas = el('canvas');
  t = { canvas };
  t.promise = schedule(`t${i}`, PRIO.thumb, async () => {
    const page = await S.pdf.getPage(i + 1);
    const vp = page.getViewport({ scale: 184 / S.size.w });
    canvas.width = Math.floor(vp.width); canvas.height = Math.floor(vp.height);
    return page.render({ canvasContext: canvas.getContext('2d'), viewport: vp });
  }).then(() => canvas);
  t.promise.catch(() => thumbs.delete(i));
  thumbs.set(i, t);
  for (const [k, old] of [...thumbs]) {
    if (thumbs.size <= THUMBS) break;
    unschedule(`t${k}`); free(old.canvas); thumbs.delete(k);
  }
  return t.promise;
}

function setupEdge() {
  const t = $('#edgeTrack'), tip = $('#edgeTip');
  let dragging = false, hoverToken = 0, ghost = null;
  const spreadAt = (x) => {
    const r = t.getBoundingClientRect();
    const f = Math.max(0, Math.min(0.9999, (x - r.left) / r.width));
    return spreadOf(Math.floor(f * S.n));
  };
  const show = (x) => {
    const s = spreadAt(x), r = t.getBoundingClientRect(), er = $('#edge').getBoundingClientRect();
    tip.hidden = false;
    tip.style.left = `${Math.max(110, Math.min(er.width - 110, x - er.left))}px`;
    const [l, rr] = pagesOf(s);
    const sec = sectionOf(rr ?? l);
    const sub = bookmarkAt(rr ?? l);
    $('#edgeTipText').innerHTML = '';
    $('#edgeTipText').append(el('b', null, spreadLabel(s)), el('small', null, [sec?.title, sub && sub !== sec ? sub.title : null].filter(Boolean).join(' › ')));
    if (!ghost) { ghost = el('div', 'eghost'); t.append(ghost); }
    ghost.style.left = `${x - r.left}px`;
    const token = ++hoverToken;
    setTimeout(async () => {
      if (token !== hoverToken) return;
      unscheduleAll('t', (key) => key === `t${l}` || key === `t${rr}`);   // only the spread under the pointer
      let cs;
      try { cs = await Promise.all([l, rr].map((i) => (i == null ? null : thumb(i)))); } catch { return; }
      if (token !== hoverToken) return;
      const box = $('#edgeThumbs');
      box.replaceChildren(...cs.map((c) => {
        if (!c) return el('div', 'blank');
        const copy = el('canvas'); copy.width = c.width; copy.height = c.height; copy.getContext('2d').drawImage(c, 0, 0);
        return copy;
      }));
    }, 70);
  };
  const hide = () => { tip.hidden = true; hoverToken++; ghost?.remove(); ghost = null; };
  t.addEventListener('pointerdown', (e) => { dragging = true; t.setPointerCapture(e.pointerId); show(e.clientX); });
  t.addEventListener('pointermove', (e) => show(e.clientX));
  t.addEventListener('pointerup', (e) => { if (dragging) { dragging = false; go(spreadAt(e.clientX)); } });
  t.addEventListener('pointerleave', () => { if (!dragging) hide(); });
  t.addEventListener('lostpointercapture', () => { dragging = false; hide(); });
}

// ------------------------------------------------------------------------------------------ the Ordinary card
// book/out/card.pdf (TODO B-14): one sheet, front and back. It rests at the right edge of the stage with its left
// edge showing; a click takes it out in front of the book, nearly as wide as the open book; a click on it turns it
// over; the faint outline where it rests (or C, Esc) puts it back.
const CARD = { pdf: null, out: false, aspect: 8.5 / 11, w: 0, h: 0, drawn: 0 };
const PEEK = 46;                                   // px of the card's left edge showing at rest

async function setupCard() {
  try {
    // each version of the book has its own card (book → card, book-weekly → card-weekly), else the main card
    const own = S.file.replace(/^book/, 'card');
    const names = await fetch('pdfs.json', { cache: 'no-store' }).then((r) => r.json()).then((l) => l.map((f) => f.name)).catch(() => []);
    const card = names.includes(own) ? own : 'card';
    CARD.pdf = await pdfjsLib.getDocument({ url: `pdf/${card}.pdf`, disableAutoFetch: true, disableStream: true }).promise;
  } catch { return; }                              // no card built: nothing shown
  if (CARD.pdf.numPages < 2) return;
  const vp = (await CARD.pdf.getPage(1)).getViewport({ scale: 1 });
  CARD.aspect = vp.height / vp.width;
  const card = $('#card');
  card.hidden = false;
  card.addEventListener('click', (e) => { e.stopPropagation(); if (CARD.out) card.classList.toggle('flipped'); else takeCard(true); });
  card.addEventListener('pointerdown', (e) => e.stopPropagation());        // not a pan of the book
  $('#cardSlot').addEventListener('click', (e) => { e.stopPropagation(); takeCard(false); });
  placeCard();
}

function takeCard(out) {
  if (!CARD.pdf) return;
  CARD.out = out;
  const card = $('#card');
  card.classList.toggle('aside', !out);
  if (!out) card.classList.remove('flipped');
  card.title = out ? 'Ordinary card: click to turn it over' : 'Ordinary card: click to take it out (C)';
  $('#cardSlot').hidden = !out;
  placeCard();
}

function placeCard() {
  if (!CARD.pdf) return;
  const st = $('#stage'), card = $('#card'), slot = $('#cardSlot');
  const bookW = (2 * S.pw + (parseFloat($('#book').style.getPropertyValue('--gap')) || 0)) * (Z.fit || 1);
  const w = Math.max(240, Math.min(st.clientWidth - 40, bookW * 0.92));    // as wide as the open book, edges showing
  const h = Math.min(w * CARD.aspect, st.clientHeight - 24);
  const ww = h / CARD.aspect;
  CARD.w = ww; CARD.h = h;
  card.style.width = `${ww}px`;
  card.style.height = `${h}px`;
  const top = (st.clientHeight - h) / 2;
  card.style.transform = CARD.out
    ? `translate(${(st.clientWidth - ww) / 2}px, ${top}px)`
    : `translate(${st.clientWidth - PEEK}px, ${top + 10}px) rotate(-2deg)`;
  Object.assign(slot.style, { left: `${st.clientWidth - PEEK - 8}px`, top: `${top + 4}px`,
    width: `${PEEK + 2}px`, height: `${h - 8}px` });
  renderCard();
}

let cardTimer;
function renderCard() {
  clearTimeout(cardTimer);
  cardTimer = setTimeout(async () => {
    const w = Math.round(CARD.w);
    if (!w || CARD.drawn === w) return;
    CARD.drawn = w;
    const dpr = window.devicePixelRatio || 1;
    for (const [n, face] of [[1, '#card .front'], [2, '#card .back']]) {
      const page = await CARD.pdf.getPage(n);
      const vp = page.getViewport({ scale: (w / page.getViewport({ scale: 1 }).width) * dpr });
      const c = el('canvas');
      c.width = Math.floor(vp.width); c.height = Math.floor(vp.height);
      await page.render({ canvasContext: c.getContext('2d'), viewport: vp }).promise;
      const box = $(face);
      box.querySelectorAll('canvas').forEach(free);
      box.replaceChildren(c);
    }
  }, 120);
}

// ------------------------------------------------------------------------------------------ page-number box
function findPage(q) {
  q = q.trim();
  if (!q) return null;
  if (q.startsWith('#')) { const n = parseInt(q.slice(1), 10); return n >= 1 && n <= S.n ? n - 1 : null; }
  const low = q.toLowerCase().replace(/^p\.?\s*/, '');
  const i = S.labels.findIndex((x) => x && x.toLowerCase() === low);
  if (i >= 0) return i;
  if (!S.labels.length && /^\d+$/.test(low)) { const n = +low; return n >= 1 && n <= S.n ? n - 1 : null; }
  return null;
}

// ------------------------------------------------------------------------------------------ misc UI
let toastTimer;
function toast(msg) {
  const t = $('#toast');
  t.textContent = msg; t.classList.add('show');
  clearTimeout(toastTimer); toastTimer = setTimeout(() => t.classList.remove('show'), 1800);
}

function toggleNav() {
  if (matchMedia('(max-width: 900px)').matches) document.body.classList.toggle('nav-shown');
  else { document.body.classList.toggle('nav-hidden'); prefs('nav', document.body.classList.contains('nav-hidden') ? 'hidden' : 'shown'); }
}

function setupUI() {
  $('#prev').addEventListener('click', () => go(S.spread - 1));
  $('#next').addEventListener('click', () => go(S.spread + 1));
  $('#navToggle').addEventListener('click', () => { toggleNav(); });
  $('#helpBtn').addEventListener('click', () => { $('#help').hidden = false; });
  $('#helpClose').addEventListener('click', () => { $('#help').hidden = true; });
  $('#help').addEventListener('click', (e) => { if (e.target.id === 'help') $('#help').hidden = true; });
  $('#resetRibbons').addEventListener('click', () => {
    S.ribbons = defaults(); save(); drawRibbons(); drawGutter(); drawEdge(); toast('Ribbons back at their section starts');
  });
  $('#goForm').addEventListener('submit', (e) => {
    e.preventDefault();
    const inp = $('#pageInput');
    const i = findPage(inp.value);
    inp.classList.remove('bad');
    if (i == null) { void inp.offsetWidth; inp.classList.add('bad'); toast(`No page “${inp.value.trim()}” (printed page numbers; #N = N-th sheet)`); return; }
    inp.blur();
    go(spreadOf(i), { flash: i });
  });
  document.addEventListener('keydown', (e) => {
    if (!$('#help').hidden) { if (e.key === 'Escape' || e.key === '?') $('#help').hidden = true; return; }
    if (CARD.out && e.key === 'Escape') { takeCard(false); e.preventDefault(); return; }
    if (e.target.matches?.('input, select, textarea')) { if (e.key === 'Escape') e.target.blur(); return; }
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    const k = e.key;
    if (k === 'ArrowRight' || k === 'PageDown' || (k === ' ' && !e.shiftKey)) go(S.spread + 1);
    else if (k === 'ArrowLeft' || k === 'PageUp' || (k === ' ' && e.shiftKey)) go(S.spread - 1);
    else if (k === 'Home') go(0);
    else if (k === 'End') go(lastSpread());
    else if (/^[1-9]$/.test(k) && +k <= RIBBONS.length) clickRibbon(+k - 1);
    else if (k === 'g' || k === 'G' || k === '/') { $('#pageInput').focus(); $('#pageInput').select(); }
    else if (k === 'n' || k === 'N') toggleNav();
    else if (k === '+' || k === '=') zoomCentre(1.25);
    else if (k === '-' || k === '_') zoomCentre(0.8);
    else if (k === 'f' || k === 'F') fit();
    else if (k === 'c' || k === 'C') takeCard(!CARD.out);
    else if (k === '?') $('#help').hidden = false;
    else return;
    e.preventDefault();
  });
  let rt;
  new ResizeObserver(() => {
    clearTimeout(rt);
    rt = setTimeout(() => {
      if (!S.size || busy) return;
      const old = S.scale;
      measure();
      if (Math.abs(S.scale - old) / old >= 0.01) {                    // re-render at the new size
        inUse.clear();
        for (const k of [...cache.keys()]) drop(k);
        showSpread(S.spread);
      }
      computeFit();
      applyView();
    }, 150);
  }).observe($('#stage'));
}

async function setupFiles() {
  const sel = $('#fileSelect');
  let names = [];
  try {
    const list = await (await fetch('pdfs.json', { cache: 'no-store' })).json();
    names = list.map((f) => f.name);
    for (const f of list.filter((f) => !f.name.startsWith('card'))) {      // the Ordinary cards are not books
      const o = el('option', null, `${f.name}.pdf · ${new Date(f.mtime * 1000).toLocaleString()}`);
      o.value = f.name; o.selected = f.name === S.file;
      sel.append(o);
    }
  } catch {}
  sel.hidden = sel.options.length < 2;
  sel.addEventListener('change', () => switchTo(sel.value));
  // Main | Experiment: the versions of the book (lh/config.py VARIANTS) when both are built
  const tog = $('#variantToggle');
  const files = [...tog.querySelectorAll('button')].map((b) => b.dataset.file);
  tog.hidden = !files.every((f) => names.includes(f)) || !files.includes(S.file);
  tog.querySelectorAll('button').forEach((b) => {
    b.classList.toggle('on', b.dataset.file === S.file);
    b.addEventListener('click', () => { if (b.dataset.file !== S.file) switchTo(b.dataset.file); });
  });
}

// Switch to another PDF, keeping the place: the bookmark the reader is in (its titles from the top) and how far
// into it; the other version opens at the same bookmark (lh/config.py VARIANTS print the same parts).
function switchTo(file) {
  const [l, r] = pagesOf(S.spread);
  const at = r ?? l;
  const mark = S.flat.length ? bookmarkAt(at) : null;
  if (mark) {
    const trail = [];
    for (let p = mark; p; p = p.parent) trail.unshift(p.title);
    try { sessionStorage.setItem('ovp-viewer:jump', JSON.stringify({ trail, offset: at - mark.index })); } catch {}
  }
  location.search = `?file=${encodeURIComponent(file)}`;
}

function takeJump() {
  let jump = null;
  try { jump = JSON.parse(sessionStorage.getItem('ovp-viewer:jump') || 'null'); sessionStorage.removeItem('ovp-viewer:jump'); } catch {}
  if (!jump) return null;
  const trailOf = (n) => { const t = []; for (let p = n; p; p = p.parent) t.unshift(p.title); return t.join('\u0001'); };
  const want = jump.trail.join('\u0001');
  const i = S.flat.findIndex((n) => trailOf(n) === want);
  if (i < 0) return null;
  const node = S.flat[i];
  const next = S.flat.slice(i + 1).find((n) => n.index > node.index);
  const room = (next ? next.index : S.n) - node.index - 1;            // stay inside the same bookmark
  return spreadOf(node.index + Math.max(0, Math.min(jump.offset, room)));
}

// ------------------------------------------------------------------------------------------ start
async function main() {
  if (prefs('nav') === 'hidden') document.body.classList.add('nav-hidden');
  setupUI();
  setupZoom();
  setupEdge();
  setupFiles();
  try {
    // byte ranges on demand (serve.py answers Range requests): only the parts of the file for the pages shown are read
    S.pdf = await pdfjsLib.getDocument({ url: `pdf/${encodeURIComponent(S.file)}.pdf`, disableAutoFetch: true,
      disableStream: true, rangeChunkSize: 128 * 1024, isEvalSupported: false, enableXfa: false }).promise;
  } catch (err) {
    $('#loading').textContent = `Could not open book/out/${S.file}.pdf — ${err.message}`;
    return;
  }
  S.n = S.pdf.numPages;
  S.labels = (await S.pdf.getPageLabels()) || [];
  const first = await S.pdf.getPage(1);
  const vp = first.getViewport({ scale: 1 });
  S.size = { w: vp.width, h: vp.height };
  document.title = `${S.file}.pdf · Book Preview`;
  await loadOutline();
  drawOutline();

  const saved = load();
  if (saved && Array.isArray(saved.ribbons) && saved.ribbons.length === RIBBONS.length) {
    S.ribbons = saved.ribbons.map((s) => (s == null ? null : Math.min(s, lastSpread())));
    S.spread = Math.min(saved.spread || 0, lastSpread());
  } else {
    S.ribbons = defaults();
  }
  const jumped = takeJump();                       // switched from the other version: the same place
  if (jumped != null) S.spread = Math.min(jumped, lastSpread());
  measure();
  showSpread(S.spread);
  $('#loading').hidden = true;
  computeFit();
  applyView();
  afterMove();
  prefetch(S.spread);
  setupCard();
}

window.bookViewer = S;   // for debugging from the console
main();
