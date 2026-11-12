// Ciência #7 — "Você acha que está parado?"
// Imagens reais da NASA (domínio público): Terra vista da Estação Espacial em 4K, tour por dentro da Estação,
// luzes da Terra (Black Marble 2016), Sol (SDO), ilustração da Via Láctea (NASA/JPL-Caltech/R. Hurt) e
// o mapa da radiação cósmica de fundo (WMAP). Globo noturno gerado por src/globo.py.
// Odômetro ao vivo: quanto você já percorreu desde o início do vídeo (369,8 km/s em relação à radiação cósmica de fundo).
//   node src/render.js                   -> build/video.mp4
//   node src/render.js --preview 3,20    -> build/preview/*.png
//   node src/render.js --capa            -> output/capa.png
const { createCanvas, loadImage, GlobalFonts } = require('@napi-rs/canvas');
const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');

const ROOT = path.resolve(__dirname, '..');
const TL = JSON.parse(fs.readFileSync(path.join(ROOT, 'build/timeline.json'), 'utf8'));
const W = 1080, H = 1920, FPS = TL.fps, N = TL.frames;
GlobalFonts.registerFromPath(path.join(ROOT, 'fonts/IBMPlexMono-Light.ttf'), 'Plex Light');
GlobalFonts.registerFromPath(path.join(ROOT, 'fonts/IBMPlexMono-Regular.ttf'), 'Plex');
GlobalFonts.registerFromPath(path.join(ROOT, 'fonts/IBMPlexMono-Medium.ttf'), 'Plex Medium');
GlobalFonts.registerFromPath(path.join(ROOT, 'fonts/CormorantGaramond.ttf'), 'Cormorant');
GlobalFonts.registerFromPath(path.join(ROOT, 'fonts/CormorantGaramond-Italic.ttf'), 'Cormorant Italic');
const FONT = '"Inter Display"', MONO = '"Plex"', MONO_L = '"Plex Light"', MONO_M = '"Plex Medium"', SERIF = '"Cormorant"', SERIF_I = '"Cormorant Italic"';
const C = { yellow: '#FFD23F', cyan: '#4FD1FF', ink: '#070A14', accent: [255, 150, 70], red: [255, 70, 60] };
const L = TL.lines, M = TL.marks, REW = TL.rew;
const Wt = (line, i, k = 't0') => L[line].words[i][k];

// ---------------------------------------------------------------- utilidades
const clamp = (x, a = 0, b = 1) => Math.max(a, Math.min(b, x));
const lerp = (a, b, t) => a + (b - a) * t;
const sstep = (a, b, x) => { const t = clamp((x - a) / (b - a)); return t * t * (3 - 2 * t); };
const easeOutCubic = p => 1 - Math.pow(1 - clamp(p), 3);
const easeInCubic = p => Math.pow(clamp(p), 3);
const easeInOutCubic = p => (p = clamp(p), p < 0.5 ? 4 * p * p * p : 1 - Math.pow(-2 * p + 2, 3) / 2);
const easeOutBack = p => { p = clamp(p); const c1 = 1.70158, c3 = c1 + 1; return 1 + c3 * Math.pow(p - 1, 3) + c1 * Math.pow(p - 1, 2); };
const win = (t, a, b, fi = 0.25, fo = 0.25) => Math.min(sstep(a, a + fi, t), 1 - sstep(b - fo, b, t));
function rng(seed) { return () => { seed |= 0; seed = seed + 0x6D2B79F5 | 0; let t = Math.imul(seed ^ seed >>> 15, 1 | seed); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
const rgba = (c, a = 1) => `rgba(${c[0] | 0},${c[1] | 0},${c[2] | 0},${a})`;
const PERM = new Uint8Array(512);
{ const r = rng(1234), p = [...Array(256).keys()]; for (let i = 255; i > 0; i--) { const j = Math.floor(r() * (i + 1)); [p[i], p[j]] = [p[j], p[i]]; } for (let i = 0; i < 512; i++) PERM[i] = p[i & 255]; }
const fade = t => t * t * t * (t * (t * 6 - 15) + 10);
function grad(h, x, y, z) { h &= 15; const u = h < 8 ? x : y, v = h < 4 ? y : (h === 12 || h === 14 ? x : z); return ((h & 1) ? -u : u) + ((h & 2) ? -v : v); }
function noise3(x, y, z) {
  const X = Math.floor(x) & 255, Y = Math.floor(y) & 255, Z = Math.floor(z) & 255;
  x -= Math.floor(x); y -= Math.floor(y); z -= Math.floor(z);
  const u = fade(x), v = fade(y), w = fade(z);
  const A = PERM[X] + Y, AA = PERM[A] + Z, AB = PERM[A + 1] + Z, B = PERM[X + 1] + Y, BA = PERM[B] + Z, BB = PERM[B + 1] + Z;
  return lerp(lerp(lerp(grad(PERM[AA], x, y, z), grad(PERM[BA], x - 1, y, z), u), lerp(grad(PERM[AB], x, y - 1, z), grad(PERM[BB], x - 1, y - 1, z), u), v),
    lerp(lerp(grad(PERM[AA + 1], x, y, z - 1), grad(PERM[BA + 1], x - 1, y, z - 1), u), lerp(grad(PERM[AB + 1], x, y - 1, z - 1), grad(PERM[BB + 1], x - 1, y - 1, z - 1), u), v), w);
}
function rr(ctx, x, y, w, h, r) {
  ctx.beginPath(); ctx.moveTo(x + r, y); ctx.arcTo(x + w, y, x + w, y + h, r); ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r); ctx.arcTo(x, y, x + w, y, r); ctx.closePath();
}
function text(ctx, s, x, y, { font, color = '#fff', align = 'left', base = 'alphabetic', stroke = 0, strokeColor = 'rgba(0,0,0,0.9)', spacing = 0, alpha = 1, shadow = 0 } = {}) {
  if (alpha <= 0) return;
  ctx.save(); ctx.globalAlpha *= alpha; ctx.font = font; ctx.textAlign = align; ctx.textBaseline = base; ctx.letterSpacing = spacing + 'px';
  if (shadow) { ctx.shadowColor = 'rgba(0,0,0,0.75)'; ctx.shadowBlur = shadow; ctx.shadowOffsetY = shadow / 4; }
  if (stroke) { ctx.lineJoin = 'round'; ctx.lineWidth = stroke; ctx.strokeStyle = strokeColor; ctx.strokeText(s, x, y); ctx.shadowBlur = 0; }
  ctx.fillStyle = color; ctx.fillText(s, x, y); ctx.restore();
}
function glowAt(ctx, x, y, r, col, a) {
  if (a <= 0 || r <= 0) return;
  const g = ctx.createRadialGradient(x, y, 0, x, y, r);
  g.addColorStop(0, rgba(col, a)); g.addColorStop(1, rgba(col, 0));
  ctx.fillStyle = g; ctx.beginPath(); ctx.arc(x, y, r, 0, 6.283); ctx.fill();
}
const tracked = (s) => s.split('').join(' ');

// ---------------------------------------------------------------- tipografia e UI
function chip(ctx, s, x, y, a, { align = 'center', col = 'rgba(235,240,255,0.92)', size = 24, dot = null } = {}) {
  if (a <= 0) return;
  ctx.save(); ctx.globalAlpha *= a; ctx.font = `${size}px ${MONO}`; ctx.letterSpacing = '5px';
  const w = ctx.measureText(s).width + (dot ? 30 : 0), px = 22, h = size + 26;
  const x0 = align === 'center' ? x - w / 2 - px : align === 'right' ? x - w - 2 * px : x;
  ctx.fillStyle = 'rgba(6,8,16,0.55)'; rr(ctx, x0, y - h / 2, w + 2 * px, h, h / 2); ctx.fill();
  ctx.strokeStyle = 'rgba(255,255,255,0.16)'; ctx.lineWidth = 1.2; rr(ctx, x0, y - h / 2, w + 2 * px, h, h / 2); ctx.stroke();
  if (dot) { ctx.fillStyle = dot; ctx.beginPath(); ctx.arc(x0 + px + 7, y, 7, 0, 6.283); ctx.fill(); }
  ctx.fillStyle = col; ctx.textBaseline = 'middle'; ctx.fillText(s, x0 + px + (dot ? 30 : 0), y + 1); ctx.restore();
}
function leader(ctx, x0, y0, x1, y1, p, a) { // linha de anotação que se desenha
  if (a <= 0 || p <= 0) return;
  ctx.save(); ctx.globalAlpha *= a; ctx.strokeStyle = 'rgba(255,255,255,0.85)'; ctx.lineWidth = 2;
  const mx = lerp(x0, x1, 0.55);
  ctx.beginPath(); ctx.moveTo(x0, y0);
  const q = clamp(p * 2), q2 = clamp(p * 2 - 1);
  ctx.lineTo(lerp(x0, mx, q), y0); if (q2 > 0) ctx.lineTo(lerp(mx, x1, q2), lerp(y0, y1, q2)); ctx.stroke();
  if (p >= 1) { ctx.fillStyle = '#fff'; ctx.beginPath(); ctx.arc(x1, y1, 6, 0, 6.283); ctx.fill(); ctx.strokeStyle = 'rgba(255,255,255,0.5)'; ctx.beginPath(); ctx.arc(x1, y1, 14, 0, 6.283); ctx.stroke(); }
  ctx.restore();
}
function poem(ctx, lines, y, a, size = 84) {
  if (a <= 0) return;
  ctx.save(); ctx.globalAlpha *= a; ctx.shadowColor = 'rgba(0,0,0,0.9)'; ctx.shadowBlur = 40;
  lines.forEach((ln, k) => text(ctx, ln, 540, y + k * size * 1.12, { font: `italic 400 ${size}px ${SERIF_I}`, color: '#fff6ea', align: 'center' }));
  ctx.restore();
}
// ---------------------------------------------------------------- marca (padrão da série)
const STARS = Array.from({ length: 260 }, (_, i) => { const r = rng(900 + i); return { x: r() * W, y: r() * H, r: 0.4 + r() * r() * 2.2, a: 0.2 + r() * 0.7 }; });
function brandIcon(ctx, cx, cy, size, lt) {
  const ringRx = size * 0.62, ringRy = size * 0.17, tilt = -0.32 + Math.sin(lt * 1.2) * 0.05;
  const anel = (a0, a1) => { ctx.save(); ctx.translate(cx, cy); ctx.rotate(tilt); ctx.shadowColor = 'rgba(79,209,255,0.8)'; ctx.shadowBlur = size * 0.06;
    ctx.strokeStyle = C.cyan; ctx.lineWidth = size * 0.045; ctx.lineCap = 'round'; ctx.beginPath(); ctx.ellipse(0, 0, ringRx, ringRy, 0, a0, a1); ctx.stroke(); ctx.restore(); };
  glowAt(ctx, cx, cy, size * 0.8, [255, 210, 63], 0.3);
  anel(Math.PI, Math.PI * 2);
  ctx.save(); ctx.font = `900 ${size}px ${FONT}`; ctx.textAlign = 'center';
  const m = ctx.measureText('?'); const g = ctx.createLinearGradient(0, cy - size * 0.4, 0, cy + size * 0.4); g.addColorStop(0, '#FFE27A'); g.addColorStop(1, '#FFB81F');
  ctx.fillStyle = g; ctx.fillText('?', cx, cy + (m.actualBoundingBoxAscent - m.actualBoundingBoxDescent) / 2); ctx.restore();
  anel(0, Math.PI);
  const a = lt * 1.8; ctx.save(); ctx.translate(cx, cy); ctx.rotate(tilt); ctx.fillStyle = '#fff'; ctx.shadowColor = '#fff'; ctx.shadowBlur = size * 0.05;
  ctx.beginPath(); ctx.arc(ringRx * Math.cos(a), ringRy * Math.sin(a), size * 0.05, 0, 6.283); ctx.fill(); ctx.restore();
}
function ctaScene(ctx, t, lt) {
  const g = ctx.createRadialGradient(540, 860, 40, 540, 960, 1100); g.addColorStop(0, '#1d2d5c'); g.addColorStop(1, '#04060f');
  ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
  for (const s of STARS) { ctx.globalAlpha = s.a * 0.6; ctx.fillStyle = '#fff'; ctx.fillRect(s.x, s.y, s.r * 2, s.r * 2); }
  ctx.globalAlpha = 1;
  const p = easeOutBack(lt / 0.5);
  ctx.save(); ctx.translate(540, 900); ctx.scale(0.85 + 0.15 * p, 0.85 + 0.15 * p);
  brandIcon(ctx, 0, -270, 300, lt);
  text(ctx, 'CURIOSIDADES', 0, -20, { font: `900 104px ${FONT}`, color: '#fff', align: 'center', stroke: 12 });
  text(ctx, 'ALEATÓRIAS', 0, 90, { font: `900 104px ${FONT}`, color: C.yellow, align: 'center', stroke: 12 });
  const tap = Wt('cta', 0) + 0.6, pressed = t > tap;
  const bp = pressed ? 1 - 0.08 * Math.sin(clamp((t - tap) / 0.18) * Math.PI) : 1 + 0.04 * Math.sin(t * 9);
  ctx.save(); ctx.translate(0, 260); ctx.scale(bp, bp);
  ctx.fillStyle = pressed ? 'rgba(255,255,255,0.12)' : C.yellow; rr(ctx, -230, -60, 460, 120, 60); ctx.fill();
  if (pressed) { ctx.strokeStyle = 'rgba(255,255,255,0.5)'; ctx.lineWidth = 3; rr(ctx, -230, -60, 460, 120, 60); ctx.stroke(); }
  text(ctx, pressed ? '✓ SEGUINDO' : '+ SEGUIR', 0, 20, { font: `900 56px ${FONT}`, color: pressed ? '#fff' : C.ink, align: 'center' });
  ctx.restore();
  const hp = clamp((t - (tap - 0.45)) / 0.45);
  if (hp > 0 && t < tap + 0.6) {
    ctx.globalAlpha = t < tap ? hp : 1 - clamp((t - tap) / 0.6);
    ctx.fillStyle = 'rgba(255,255,255,0.9)'; ctx.beginPath(); ctx.arc(lerp(260, 120, easeOutCubic(hp)), lerp(430, 280, easeOutCubic(hp)), 30, 0, 6.283); ctx.fill();
    if (pressed) { ctx.strokeStyle = 'rgba(255,255,255,0.8)'; ctx.lineWidth = 4; ctx.beginPath(); ctx.arc(120, 280, 30 + (t - tap) * 160, 0, 6.283); ctx.stroke(); }
  }
  ctx.restore();
}
function drawCaptions(ctx, t) {
  const pg = TL.pages.find(p => t >= p.t0 && t < p.t1);
  if (!pg) return;
  let fs = 80; ctx.font = `900 ${fs}px ${FONT}`;
  const widths = () => pg.toks.map(k => ctx.measureText(k.txt).width);
  let ws = widths(), sp = fs * 0.3, total = ws.reduce((a, b) => a + b, 0) + sp * (ws.length - 1);
  while (total > 900 && fs > 50) { fs -= 4; ctx.font = `900 ${fs}px ${FONT}`; ws = widths(); sp = fs * 0.3; total = ws.reduce((a, b) => a + b, 0) + sp * (ws.length - 1); }
  const age = t - pg.t0, pin = easeOutBack(age / 0.2);
  const alpha = clamp(age / 0.08) * (1 - sstep(pg.t1 - 0.08, pg.t1, t));
  const cy = 1545;
  ctx.save(); ctx.globalAlpha = alpha; ctx.translate(W / 2, cy); ctx.scale(0.88 + 0.12 * pin, 0.88 + 0.12 * pin); ctx.translate(-W / 2, -cy);
  let x = W / 2 - total / 2;
  pg.toks.forEach((k, j) => {
    const active = t >= k.t0 - 0.03 && (j === pg.toks.length - 1 || t < pg.toks[j + 1].t0 - 0.03);
    const s = active ? 1 + 0.06 * (1 - easeOutCubic((t - k.t0) / 0.18)) + 0.02 : 1;
    ctx.save(); ctx.translate(x + ws[j] / 2, cy); ctx.scale(s, s);
    ctx.font = `900 ${fs}px ${FONT}`; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    ctx.lineJoin = 'round'; ctx.lineWidth = fs * 0.2; ctx.strokeStyle = 'rgba(0,0,0,0.92)';
    ctx.shadowColor = 'rgba(0,0,0,0.6)'; ctx.shadowBlur = 18; ctx.shadowOffsetY = 6;
    ctx.strokeText(k.txt, 0, 0); ctx.shadowBlur = 0; ctx.shadowOffsetY = 0;
    ctx.fillStyle = active ? C.yellow : '#fff'; ctx.fillText(k.txt, 0, 0);
    ctx.restore(); x += ws[j] + sp;
  });
  ctx.restore();
}


// ---------------------------------------------------------------- números
const KMS = 369.8; // km/s do Sol em relação à radiação cósmica de fundo (dipolo, Planck 2018)
const fmt = n => Math.round(n).toLocaleString('pt-BR');

// ---------------------------------------------------------------- imagens e tomadas
const IMG = {};
async function loadImages() { for (const k of ['via_lactea', 'cmb_wmap', 'sol_304']) IMG[k] = await loadImage(path.join(ROOT, 'assets', k + '.jpg')); }
const NOMES = ['limbo', 'nuvens', 'paineis', 'montanha', 'flutua', 'flutua2', 'cupula', 'estacao', 'gira', 'volta'];
const COUNT = {}, EXT = {};
for (const k of NOMES) {
  const d = path.join(ROOT, 'build/shots', k), fl = fs.existsSync(d) ? fs.readdirSync(d) : [];
  const j = fl.filter(f => f.endsWith('.jpg')).length, p = fl.filter(f => f.endsWith('.png')).length;
  COUNT[k] = Math.max(j, p); EXT[k] = p > j ? '.png' : '.jpg';
}
const GP = {}; for (const k of ['gira', 'volta']) { const f = path.join(ROOT, 'build/shots', k, 'params.json'); GP[k] = fs.existsSync(f) ? JSON.parse(fs.readFileSync(f, 'utf8')) : []; }
const CACHE = new Map();
async function frameOf(name, k) {
  k = clamp(Math.round(k), 1, Math.max(1, COUNT[name]));
  const key = name + k;
  if (!CACHE.has(key)) {
    CACHE.set(key, await loadImage(path.join(ROOT, 'build/shots', name, String(k).padStart(5, '0') + EXT[name])));
    if (CACHE.size > 16) CACHE.delete(CACHE.keys().next().value);
  }
  return CACHE.get(key);
}
const atS = (name, s) => frameOf(name, s * 30 + 1);                         // s segundos dentro da tomada
const atU = (name, u) => frameOf(name, 1 + clamp(u) * (COUNT[name] - 1));    // progresso 0..1
const idxU = (name, u) => clamp(Math.round(1 + clamp(u) * (COUNT[name] - 1)), 1, Math.max(1, COUNT[name]));
function cover(ctx, img, { z = 1, ox = 0, oy = 0, alpha = 1 } = {}) {
  const s = Math.max(W / img.width, H / img.height) * z;
  ctx.save(); ctx.globalAlpha *= alpha; ctx.translate(W / 2 + ox, H / 2 + oy); ctx.scale(s, s);
  ctx.drawImage(img, -img.width / 2, -img.height / 2); ctx.restore();
}

// ---------------------------------------------------------------- globo: projeção ortográfica (a mesma do globo.py)
const GX = 540, GY = 860, GS = 0.8; // centro do globo na tela e escala na cena da rotação
function proj(name, k, lat, lon, scale = 1) {
  const p = GP[name][k - 1] || GP[name][0]; if (!p) return null;
  const f = Math.PI / 180, phi = lat * f, lam = lon * f, phi0 = p.lat0 * f, lam0 = p.lon0 * f;
  const cosc = Math.sin(phi0) * Math.sin(phi) + Math.cos(phi0) * Math.cos(phi) * Math.cos(lam - lam0);
  const x = p.R * Math.cos(phi) * Math.sin(lam - lam0), y = p.R * (Math.cos(phi0) * Math.sin(phi) - Math.sin(phi0) * Math.cos(phi) * Math.cos(lam - lam0));
  return { x: GX + x * scale, y: GY - y * scale, vis: cosc > 0.02, cosc };
}
async function globe(ctx, name, u, scale = 1, alpha = 1) {
  const img = await atU(name, u), s = scale;
  ctx.save(); ctx.globalAlpha *= alpha; ctx.drawImage(img, GX - 540 * s, GY - 540 * s, 1080 * s, 1080 * s); ctx.restore();
  return idxU(name, u);
}
function equator(ctx, name, k, scale, a, { from = -180, to = 180, col = C.yellow, width = 4, dash = [14, 10], offset = 0 } = {}) {
  if (a <= 0) return;
  ctx.save(); ctx.globalAlpha *= a; ctx.strokeStyle = col; ctx.lineWidth = width; ctx.setLineDash(dash); ctx.lineDashOffset = offset; ctx.shadowColor = col; ctx.shadowBlur = 14;
  ctx.beginPath(); let pen = false;
  for (let lon = from; lon <= to; lon += 1.5) {
    const q = proj(name, k, 0, lon, scale);
    if (q && q.vis) { pen ? ctx.lineTo(q.x, q.y) : ctx.moveTo(q.x, q.y); pen = true; } else pen = false;
  }
  ctx.stroke(); ctx.restore();
}

// ---------------------------------------------------------------- céu estrelado
const SKY = (() => {
  const c = createCanvas(W, H), x = c.getContext('2d'), r = rng(42);
  x.fillStyle = '#010207'; x.fillRect(0, 0, W, H);
  for (let i = 0; i < 1400; i++) { const s = r() * r() * 1.8 + 0.3, a = 0.15 + r() * 0.75; x.globalAlpha = a; x.fillStyle = r() < 0.15 ? '#ffd9b0' : r() < 0.3 ? '#bcd4ff' : '#fff'; x.fillRect(r() * W, r() * H, s, s); }
  x.globalAlpha = 1; return c;
})();
function sky(ctx, drift = 0, tint = null) {
  ctx.drawImage(SKY, -((drift % W) + W) % W, 0); ctx.drawImage(SKY, W - ((drift % W) + W) % W, 0);
  if (tint) { const g = ctx.createRadialGradient(540, 860, 50, 540, 900, 1100); g.addColorStop(0, rgba(tint, 0.22)); g.addColorStop(1, rgba(tint, 0)); ctx.fillStyle = g; ctx.fillRect(0, 0, W, H); }
}

// ---------------------------------------------------------------- tipografia
function bigNumber(ctx, val, lab, y, a, { col = '#fff', size = 124 } = {}) {
  if (a <= 0) return;
  const p = easeOutCubic(a);
  ctx.save(); ctx.globalAlpha *= a; ctx.translate(0, (1 - p) * 24);
  let fs = size; ctx.font = `300 ${fs}px ${MONO_L}`; while (ctx.measureText(val).width > 980 && fs > 50) { fs -= 4; ctx.font = `300 ${fs}px ${MONO_L}`; }
  text(ctx, val, 540, y, { font: `300 ${fs}px ${MONO_L}`, color: col, align: 'center', shadow: 30 });
  if (lab) text(ctx, lab, 540, y + 56, { font: `22px ${MONO}`, color: 'rgba(225,232,255,0.85)', align: 'center', spacing: 5, shadow: 12 });
  ctx.restore();
}
// painel do topo: odômetro ao vivo + a camada de velocidade da cena
function panel(ctx, t, a, cells) {
  if (a <= 0) return;
  const x = 60, y = 186, w = 960, h = 178;
  ctx.save(); ctx.globalAlpha = a;
  ctx.fillStyle = 'rgba(4,6,14,0.5)'; rr(ctx, x, y, w, h, 22); ctx.fill();
  ctx.strokeStyle = 'rgba(255,255,255,0.14)'; ctx.lineWidth = 1.5; rr(ctx, x, y, w, h, 22); ctx.stroke();
  ctx.fillStyle = 'rgba(255,255,255,0.12)'; ctx.fillRect(x + w / 2, y + 30, 1.5, h - 60);
  cells.forEach(([lab, val, col], k) => {
    const cx = x + w / 4 + k * w / 2;
    let ls = 21; ctx.font = `${ls}px ${MONO}`; ctx.letterSpacing = '4px'; while (ctx.measureText(lab).width > w / 2 - 40 && ls > 14) { ls -= 1; ctx.font = `${ls}px ${MONO}`; } ctx.letterSpacing = '0px';
    text(ctx, lab, cx, y + 58, { font: `${ls}px ${MONO}`, color: 'rgba(205,215,240,0.8)', align: 'center', spacing: 4 });
    let fs = 56; ctx.font = `${fs}px ${MONO_L}`; while (ctx.measureText(val).width > w / 2 - 40) { fs -= 2; ctx.font = `${fs}px ${MONO_L}`; }
    text(ctx, val, cx, y + 132, { font: `${fs}px ${MONO_L}`, color: col || '#fff', align: 'center' });
  });
  ctx.fillStyle = 'rgb(90,200,255)'; ctx.beginPath(); ctx.arc(x + 12, y - 24, 6, 0, 6.283); ctx.fill();
  text(ctx, 'AO VIVO · CONTANDO DESDE O INÍCIO DO VÍDEO', x + 28, y - 18, { font: `18px ${MONO}`, color: 'rgba(160,215,255,0.9)', spacing: 3 });
  text(ctx, '*em relação à radiação cósmica de fundo (369,8 km/s)', x + w - 10, y + h + 32, { font: `17px ${MONO}`, color: 'rgba(210,220,245,0.6)', align: 'right' });
  ctx.restore();
}
function camada(t) { // rótulo e valor da velocidade em cada trecho
  if (t < M.boom - 0.05) return ['VELOCIDADE', '?'];
  if (t < M.rot) return ['EM RELAÇÃO AO UNIVERSO', '1.331.280 km/h'];
  if (t < M.orb) return ['ROTAÇÃO (NO EQUADOR)', '1.670 km/h'];
  if (t < M.gal) return ['EM VOLTA DO SOL', '107.000 km/h'];
  if (t < M.uni) return ['EM VOLTA DA GALÁXIA', '828.000 km/h'];
  if (t >= L.iss.start - 0.3 && t < L.odometro.start - 0.35) return ['ESTAÇÃO ESPACIAL', '27.600 km/h'];
  return ['EM RELAÇÃO AO UNIVERSO', '1.331.280 km/h'];
}

// ================================================================ cenas (bg recebe bloom; fg são os gráficos)
const S = {};
// ---- gancho: a Terra passando rápido; "na verdade você está viajando…"; depois rebobina
const hSrc = tt => tt <= REW[0] ? tt : lerp(REW[0], 0, easeInOutCubic((tt - REW[0]) / (REW[1] - REW[0])));
S.hook = {
  async bg(ctx, t, lt) {
    const s = hSrc(lt), cut = L.hook2.start - 0.15;
    if (s < cut) cover(ctx, await atS('limbo', 1.5 + s), { z: 1.06 });
    else cover(ctx, await atS('paineis', 2 + (s - cut)), { z: 1.04 });
    const fl = lt - M.boom; if (fl > 0 && fl < 0.35) { ctx.save(); ctx.globalCompositeOperation = 'screen'; ctx.fillStyle = `rgba(220,235,255,${0.5 * Math.pow(1 - fl / 0.35, 2)})`; ctx.fillRect(0, 0, W, H); ctx.restore(); }
  },
  fg(ctx, t, lt) {
    const a = win(lt, M.boom - 0.05, REW[0], 0.25, 0.2);
    bigNumber(ctx, '1.331.280 km/h', 'SUA VELOCIDADE AGORA', 1260, a);
  },
};
// ---- rotação: a Terra gira e o Brasil entra no centro
S.rotacao = {
  async bg(ctx, t, lt) {
    sky(ctx, lt * 6, [40, 90, 200]);
    const u = clamp((t - SCN.rotacao.t0) / (SCN.orbita.t0 - SCN.rotacao.t0));
    this.k = await globe(ctx, 'gira', u, GS);
  },
  fg(ctx, t, lt) {
    const k = this.k || 1;
    const ea = sstep(Wt('rotacao', 5) - 0.1, Wt('rotacao', 7), t);
    equator(ctx, 'gira', k, GS, ea, { offset: -lt * 40 }); // o tracejado anda para leste, como a rotação
    const q = proj('gira', k, 0, GP.gira[k - 1] ? GP.gira[k - 1].lon0 + 50 : 0, GS);
    if (q && q.vis) chip(ctx, 'LINHA DO EQUADOR  →', Math.min(q.x + 40, 1000), q.y - 44, ea, { align: 'right' });
    text(ctx, 'ACELERADO', 1020, 470, { font: `18px ${MONO}`, color: 'rgba(200,215,240,0.6)', align: 'right', spacing: 4, alpha: win(t, SCN.rotacao.t0 + 0.3, SCN.orbita.t0, 0.4, 0.3) });
    // São Paulo
    const sp = proj('gira', k, -23.55, -46.63, GS), sa = sstep(M.rot + 0.5, M.rot + 1.0, t);
    if (sp && sp.vis && sa > 0) {
      glowAt(ctx, sp.x, sp.y, 26, [255, 210, 120], 0.9 * sa); ctx.save(); ctx.fillStyle = '#fff'; ctx.globalAlpha = sa; ctx.beginPath(); ctx.arc(sp.x, sp.y, 5, 0, 6.283); ctx.fill(); ctx.restore();
      leader(ctx, 330, 520, sp.x, sp.y, easeOutCubic((t - M.rot - 0.5) / 0.5), sa);
      chip(ctx, 'SÃO PAULO: ≈1.530 km/h', 70, 520, sa, { align: 'left' });
    }
    bigNumber(ctx, '1.670 km/h', 'NA LINHA DO EQUADOR', 1340, sstep(M.rot - 0.1, M.rot + 0.3, t));
  },
};
// ---- órbita: a Terra em volta do Sol, 30 km a cada segundo
S.orbita = {
  async bg(ctx, t, lt) {
    sky(ctx, lt * 3, [255, 140, 40]);
    const cx = 540, cy = 860, rx = 420, ry = 150, ang = lt * 0.75 + 1.2; // anti-horário visto de cima
    const ex = cx + rx * Math.cos(ang), ey = cy + ry * Math.sin(ang), behind = Math.sin(ang) < 0;
    const drawEarth = async () => { const s = 0.075 + 0.02 * Math.sin(ang); await globeAt(ctx, 'volta', 0.2 + lt * 0.02, ex, ey, s); };
    ctx.save(); ctx.strokeStyle = 'rgba(160,200,255,0.35)'; ctx.lineWidth = 2; ctx.setLineDash([3, 8]); ctx.beginPath(); ctx.ellipse(cx, cy, rx, ry, 0, 0, 6.283); ctx.stroke(); ctx.restore();
    if (behind) await drawEarth();
    glowAt(ctx, cx, cy, 420, [255, 140, 40], 0.45); glowAt(ctx, cx, cy, 200, [255, 220, 150], 0.5);
    const s = 360 / IMG.sol_304.width * 1.12;
    ctx.save(); ctx.globalCompositeOperation = 'screen'; ctx.translate(cx, cy); ctx.rotate(lt * 0.02); ctx.scale(s, s);
    ctx.beginPath(); ctx.arc(0, 0, IMG.sol_304.width * 0.45, 0, 6.283); ctx.clip(); ctx.drawImage(IMG.sol_304, -IMG.sol_304.width / 2, -IMG.sol_304.height / 2); ctx.restore();
    if (!behind) await drawEarth();
    this.earth = [ex, ey];
  },
  fg(ctx, t, lt) {
    const [ex, ey] = this.earth || [540, 1010];
    chip(ctx, 'TERRA', ex, ey - 70, sstep(SCN.orbita.t0 + 0.3, SCN.orbita.t0 + 0.8, t));
    bigNumber(ctx, '107.000 km/h', 'EM VOLTA DO SOL', 1300, sstep(M.orb - 0.1, M.orb + 0.3, t) * (1 - sstep(Wt('orbita', 17) - 0.3, Wt('orbita', 17), t)));
    // 30 km a cada segundo: barra que enche em tempo real
    const t0 = Wt('orbita', 17), a = win(t, t0 - 0.1, SCN.galaxia.t0 + 0.2, 0.25, 0.3);
    if (a > 0) {
      const sec = Math.max(0, t - t0), frac = sec % 1, km = Math.min(30, frac * 29.78);
      ctx.save(); ctx.globalAlpha = a;
      text(ctx, `${km.toFixed(1).replace('.', ',')} km`, 540, 1290, { font: `300 110px ${MONO_L}`, color: '#fff', align: 'center', shadow: 30 });
      ctx.fillStyle = 'rgba(255,255,255,0.15)'; rr(ctx, 190, 1330, 700, 10, 5); ctx.fill();
      ctx.fillStyle = C.yellow; rr(ctx, 190, 1330, 700 * frac, 10, 5); ctx.fill();
      text(ctx, 'A CADA SEGUNDO (30 km/s)', 540, 1390, { font: `22px ${MONO}`, color: 'rgba(225,232,255,0.85)', align: 'center', spacing: 5 });
      ctx.restore();
    }
  },
};
async function globeAt(ctx, name, u, x, y, s) {
  const img = await atU(name, u);
  ctx.drawImage(img, x - 540 * s, y - 540 * s, 1080 * s, 1080 * s);
}
// ---- galáxia: o Sol dá a volta no centro da Via Láctea (e a última volta foi no tempo dos dinossauros)
const GAL = { cx: 540, cy: 860, size: 1500, sunU: 0.5, sunV: 0.746 };
S.galaxia = {
  async bg(ctx, t, lt) {
    sky(ctx, 0, [90, 110, 200]);
    const z = lerp(1.25, 0.95, easeInOutCubic(clamp(lt / 7))) * (t > SCN.universo.t0 - 0.6 ? 1 - 0.0 : 1);
    const rot = -lt * 0.035; // horário, como vista do polo norte galáctico
    const s = GAL.size * z / IMG.via_lactea.width;
    ctx.save(); ctx.globalCompositeOperation = 'screen'; ctx.translate(GAL.cx, GAL.cy); ctx.rotate(rot); ctx.scale(s, s); ctx.drawImage(IMG.via_lactea, -IMG.via_lactea.width / 2, -IMG.via_lactea.height / 2); ctx.restore();
    this.view = { z, rot };
  },
  fg(ctx, t, lt) {
    const { z, rot } = this.view || { z: 1, rot: 0 };
    const R = GAL.size * z * (GAL.sunV - 0.5), base = Math.PI / 2 + rot;
    // órbita do Sol (horária) e marcador
    const oa = sstep(SCN.galaxia.t0 + 0.4, SCN.galaxia.t0 + 1.0, t);
    const travel = -(t - SCN.galaxia.t0) * 0.05;
    const draw = 0.15 + 0.85 * sstep(Wt('ano', 0), Wt('ano', 8, 't1'), t);
    ctx.save(); ctx.globalAlpha = oa * 0.8; ctx.strokeStyle = C.yellow; ctx.lineWidth = 3; ctx.setLineDash([4, 10]); ctx.shadowColor = C.yellow; ctx.shadowBlur = 10;
    ctx.beginPath(); ctx.arc(GAL.cx, GAL.cy, R, base + travel, base + travel - draw * 2 * Math.PI, true); ctx.stroke(); ctx.restore();
    const sx = GAL.cx + R * Math.cos(base + travel), sy = GAL.cy + R * Math.sin(base + travel);
    glowAt(ctx, sx, sy, 40, [255, 220, 120], oa); ctx.save(); ctx.globalAlpha = oa; ctx.fillStyle = '#fff'; ctx.beginPath(); ctx.arc(sx, sy, 6, 0, 6.283); ctx.fill(); ctx.restore();
    chip(ctx, 'VOCÊ ESTÁ AQUI', sx, sy + 60, oa * (1 - sstep(M.gal - 0.2, M.gal, t)) + oa * sstep(Wt('ano', 9), Wt('ano', 10), t) * 0);
    bigNumber(ctx, '828.000 km/h', 'EM VOLTA DO CENTRO DA GALÁXIA', 1330, sstep(M.gal - 0.1, M.gal + 0.3, t) * (1 - sstep(Wt('ano', 0) - 0.2, Wt('ano', 0), t)));
    bigNumber(ctx, '230 milhões de anos', 'UMA VOLTA COMPLETA', 1330, win(t, Wt('ano', 3) - 0.1, Wt('ano', 9), 0.3, 0.3), { size: 96 });
    chip(ctx, 'HÁ 230 MILHÕES DE ANOS: SURGIAM OS DINOSSAUROS', 540, 1360, win(t, Wt('ano', 18) - 0.1, SCN.universo.t0 + 0.2, 0.3, 0.3), { size: 21 });
  },
};
// ---- universo: em relação à luz mais antiga (radiação cósmica de fundo)
// direção do movimento (dipolo): longitude galáctica 264°, latitude 48°, projetada no Mollweide do WMAP (l cresce para a esquerda)
const DIP = (() => { const lam = -(264 - 360) * 0, l = 264 > 180 ? 264 - 360 : 264, b = 48 * Math.PI / 180; let th = b;
  for (let i = 0; i < 20; i++) th -= (2 * th + Math.sin(2 * th) - Math.PI * Math.sin(b)) / (2 + 2 * Math.cos(2 * th));
  const nx = -(l / 180) * Math.cos(th), ny = Math.sin(th); return [540 + nx * 500, 860 - ny * 250]; })();
S.universo = {
  async bg(ctx, t, lt) {
    sky(ctx, 0, null);
    const p = easeInOutCubic(clamp(lt / 1.4));
    if (p < 1) { // a galáxia encolhe até virar um ponto
      const s = GAL.size * lerp(0.95, 0.04, p) / IMG.via_lactea.width;
      ctx.save(); ctx.globalAlpha = 1 - sstep(0.7, 1, p); ctx.globalCompositeOperation = 'screen'; ctx.translate(540, 860); ctx.rotate(-lt * 0.03); ctx.scale(s, s); ctx.drawImage(IMG.via_lactea, -IMG.via_lactea.width / 2, -IMG.via_lactea.height / 2); ctx.restore();
    }
    const m = sstep(0.6, 1.6, lt);
    if (m > 0) { // o mapa do WMAP: a luz mais antiga do universo
      const w = 1000 * (0.9 + 0.1 * easeOutCubic(m)) * (1 + 0.012 * lt), h = w / 2;
      ctx.save(); ctx.globalAlpha = m; ctx.beginPath(); ctx.ellipse(540, 860, w / 2, h / 2, 0, 0, 6.283); ctx.clip();
      ctx.drawImage(IMG.cmb_wmap, 540 - w / 2, 860 - h / 2, w, h); ctx.restore();
      glowAt(ctx, 540, 860, 600, [120, 170, 255], 0.18 * m);
    }
  },
  fg(ctx, t, lt) {
    const a = sstep(SCN.universo.t0 + 1.0, SCN.universo.t0 + 1.6, t);
    chip(ctx, 'A LUZ MAIS ANTIGA DO UNIVERSO', 540, 470, a);
    text(ctx, 'radiação cósmica de fundo · 380 mil anos após o Big Bang', 540, 1150, { font: `italic 400 36px ${SERIF_I}`, color: 'rgba(235,240,255,0.85)', align: 'center', alpha: a * (1 - sstep(M.uni - 0.4, M.uni, t)), shadow: 12 });
    // seta: a direção em que o Sistema Solar se move
    const ap = easeOutCubic((t - (M.uni - 0.6)) / 0.8), aa = sstep(M.uni - 0.6, M.uni - 0.3, t);
    if (aa > 0) {
      ctx.save(); ctx.globalAlpha = aa; ctx.strokeStyle = '#fff'; ctx.lineWidth = 5; ctx.lineCap = 'round'; ctx.shadowColor = '#9fd0ff'; ctx.shadowBlur = 16;
      const x0 = 540, y0 = 860, x1 = lerp(x0, DIP[0], ap), y1 = lerp(y0, DIP[1], ap);
      ctx.beginPath(); ctx.moveTo(x0, y0); ctx.lineTo(x1, y1); ctx.stroke();
      const an = Math.atan2(y1 - y0, x1 - x0); ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x1 - 26 * Math.cos(an - 0.45), y1 - 26 * Math.sin(an - 0.45)); ctx.moveTo(x1, y1); ctx.lineTo(x1 - 26 * Math.cos(an + 0.45), y1 - 26 * Math.sin(an + 0.45)); ctx.stroke(); ctx.restore();
      glowAt(ctx, x0, y0, 30, [255, 255, 255], aa); glowAt(ctx, DIP[0], DIP[1], 40, [255, 255, 255], aa * ap);
    }
    bigNumber(ctx, '1.331.280 km/h', 'O SISTEMA SOLAR, EM RELAÇÃO AO UNIVERSO', 1330, sstep(M.uni - 0.1, M.uni + 0.3, t));
  },
};
// ---- por que não sentimos: a tripulação flutuando, tranquila
S.sente = {
  async bg(ctx, t, lt) {
    const cut = Wt('sente', 7);
    if (t < cut) cover(ctx, await atS('flutua', 6 + lt), { z: 1.04 });
    else cover(ctx, await atS('flutua2', 2.5 + (t - cut)), { z: 1.04 });
  },
  fg(ctx, t, lt) {
    chip(ctx, 'O CORPO SENTE A MUDANÇA, NÃO A VELOCIDADE', 540, 470, win(t, Wt('sente', 13) - 0.1, SCN.iss.t0 + 0.2, 0.3, 0.3), { size: 21 });
  },
};
// ---- Estação Espacial: 28 mil km/h e ninguém sente
S.iss = {
  async bg(ctx, t, lt) {
    const cut = Wt('iss', 14);
    if (t < cut) cover(ctx, await atS('estacao', 0.3 + lt * 0.9), { z: 1.05 + 0.04 * clamp(lt / 6) });
    else cover(ctx, await atS('cupula', 4 + (t - cut)), { z: 1.04 });
  },
  fg(ctx, t, lt) {
    chip(ctx, '16 VOLTAS NA TERRA POR DIA', 540, 470, win(t, Wt('iss', 7) - 0.1, Wt('iss', 14), 0.3, 0.3));
  },
};
// ---- odômetro: mais de 20 mil km desde o início; metade da volta ao mundo
S.odometro = {
  async bg(ctx, t, lt) {
    const cut = Wt('odometro', 13) - 0.15;
    if (t < cut) { cover(ctx, await atS('montanha', 1 + lt), { z: 1.04 }); ctx.fillStyle = 'rgba(0,0,0,0.25)'; ctx.fillRect(0, 0, W, H); this.k = 0; }
    else { sky(ctx, 0, [40, 90, 200]); this.k = await globe(ctx, 'volta', clamp((t - cut) / 9), 1); }
  },
  fg(ctx, t, lt) {
    const cut = Wt('odometro', 13) - 0.15, km = KMS * t;
    if (t < cut) {
      const a = sstep(SCN.odometro.t0, SCN.odometro.t0 + 0.4, t);
      bigNumber(ctx, `${fmt(km)} km`, 'VOCÊ JÁ PERCORREU DESDE O INÍCIO DO VÍDEO', 960, a, { size: 150, col: '#fff' });
    } else {
      const k = this.k || 1, p = GP.volta[k - 1]; if (!p) return;
      const prog = easeInOutCubic((t - cut) / 1.2);
      equator(ctx, 'volta', k, 1, 1, { from: p.lon0 - 90, to: p.lon0 - 90 + 180 * prog, col: C.yellow, width: 6, dash: [] });
      const a = sstep(cut + 0.6, cut + 1.0, t);
      bigNumber(ctx, '20.037 km', 'METADE DA VOLTA AO MUNDO', 1330, a);
      text(ctx, `você: ${fmt(km)} km`, 540, 470, { font: `28px ${MONO}`, color: C.yellow, align: 'center', alpha: a, spacing: 2, shadow: 12 });
    }
  },
};
// ---- fecho
S.fecho = {
  async bg(ctx, t, lt) { cover(ctx, await atS('nuvens', 2 + lt), { z: 1.05 }); ctx.fillStyle = 'rgba(0,0,0,0.3)'; ctx.fillRect(0, 0, W, H); },
  fg(ctx, t, lt) {
    poem(ctx, ['Você nunca esteve', 'duas vezes no mesmo', 'lugar do universo.'], 760, win(t, Wt('fecho', 0) - 0.1, SCN.cta.t0 + 0.2, 0.6, 0.4), 88);
  },
};
S.cta = { async bg(ctx, t, lt) { ctaScene(ctx, t, lt); }, fg() {} };

// ---------------------------------------------------------------- composição
const SCENES = [
  { name: 'hook', t0: -1, local0: 0 },
  { name: 'rotacao', t0: REW[1] - 0.02, tr: 'cut' },
  { name: 'orbita', t0: L.orbita.start - 0.35, tr: 'push' },
  { name: 'galaxia', t0: L.galaxia.start - 0.3, tr: 'push' },
  { name: 'universo', t0: L.universo.start - 0.4, tr: 'cut' },
  { name: 'sente', t0: M.drop, tr: 'dissolve' },
  { name: 'iss', t0: L.iss.start - 0.3, tr: 'cut' },
  { name: 'odometro', t0: L.odometro.start - 0.35, tr: 'push' },
  { name: 'fecho', t0: L.fecho.start - 0.5, tr: 'dissolve' },
  { name: 'cta', t0: L.cta.start - 0.45, tr: 'dissolve' },
  { name: 'hook', t0: TL.total - 0.5, local0: TL.total, tr: 'dissolve' },
];
const SCN = {}; SCENES.forEach(s => { if (!SCN[s.name]) SCN[s.name] = s; });
const TR = { cut: 0, push: 0.5, dissolve: 0.6 };
const CRED = {
  hook: 'Imagens: NASA (4K Earth Views, Estação Espacial)',
  rotacao: 'Luzes da Terra: NASA Black Marble 2016',
  orbita: 'Sol: NASA/SDO · Terra: NASA Black Marble',
  galaxia: 'Ilustração: NASA/JPL-Caltech/R. Hurt (SSC-Caltech)',
  universo: t => t < SCN.universo.t0 + 0.9 ? 'Ilustração: NASA/JPL-Caltech/R. Hurt (SSC-Caltech)' : 'Mapa: NASA/WMAP Science Team',
  sente: 'Imagens: NASA (Step Inside the Station)',
  iss: 'Imagens: NASA (Step Inside the Station)',
  odometro: t => t < Wt('odometro', 13) - 0.15 ? 'Imagens: NASA (4K Earth Views, Estação Espacial)' : 'Luzes da Terra: NASA Black Marble 2016',
  fecho: 'Imagens: NASA (4K Earth Views, Estação Espacial)',
};
function credit(ctx, name, t) {
  let s = CRED[name]; if (typeof s === 'function') s = s(t); if (!s) return;
  text(ctx, s, W - 60, 1452, { font: `500 19px ${FONT}`, color: 'rgba(220,228,255,0.6)', align: 'right', shadow: 8 });
}
const vignette = (() => { const c = createCanvas(W, H), x = c.getContext('2d'); const g = x.createRadialGradient(W / 2, H * 0.47, H * 0.25, W / 2, H * 0.5, H * 0.78); g.addColorStop(0, 'rgba(0,0,0,0)'); g.addColorStop(1, 'rgba(0,0,0,0.6)'); x.fillStyle = g; x.fillRect(0, 0, W, H); return c; })();
const topVeil = (() => { const c = createCanvas(W, 700), x = c.getContext('2d'); const g = x.createLinearGradient(0, 0, 0, 700); g.addColorStop(0, 'rgba(0,0,0,0.55)'); g.addColorStop(1, 'rgba(0,0,0,0)'); x.fillStyle = g; x.fillRect(0, 0, W, 700); return c; })();
const botVeil = (() => { const c = createCanvas(W, 700), x = c.getContext('2d'); const g = x.createLinearGradient(0, 0, 0, 700); g.addColorStop(0, 'rgba(0,0,0,0)'); g.addColorStop(1, 'rgba(0,0,0,0.6)'); x.fillStyle = g; x.fillRect(0, 0, W, 700); return c; })();
const GRAIN = Array.from({ length: 4 }, (_, k) => { const c = createCanvas(540, 960), x = c.getContext('2d'), im = x.createImageData(540, 960), r = rng(60 + k); for (let q = 0; q < im.data.length; q += 4) { const v = r() * 255; im.data[q] = im.data[q + 1] = im.data[q + 2] = v; im.data[q + 3] = 14; } x.putImageData(im, 0, 0); return c; });
const canvas = createCanvas(W, H), ctx = canvas.getContext('2d');
const bufA = createCanvas(W, H), ctxA = bufA.getContext('2d');
const bufB = createCanvas(W, H), ctxB = bufB.getContext('2d');
const scratch = createCanvas(W, H), sctx = scratch.getContext('2d');
const small = createCanvas(270, 480), smx = small.getContext('2d');
const lt = (sc, t) => t - (sc.local0 !== undefined ? sc.local0 : sc.t0);
async function renderBg(target, sc, t) {
  target.save(); target.setTransform(1, 0, 0, 1, 0, 0); target.globalAlpha = 1; target.globalCompositeOperation = 'source-over';
  target.fillStyle = '#000'; target.fillRect(0, 0, W, H);
  await S[sc.name].bg(target, t, lt(sc, t)); target.restore();
}
function bloom(amount) {
  smx.globalCompositeOperation = 'source-over'; smx.filter = 'none'; smx.drawImage(canvas, 0, 0, 270, 480);
  smx.globalCompositeOperation = 'multiply'; smx.drawImage(small, 0, 0); smx.globalCompositeOperation = 'source-over';
  smx.filter = 'blur(7px)'; smx.drawImage(small, 0, 0); smx.filter = 'none';
  ctx.save(); ctx.globalCompositeOperation = 'screen'; ctx.globalAlpha = amount; ctx.drawImage(small, 0, 0, W, H); ctx.restore();
}
const BLOOM = { hook: 0.2, rotacao: 0.35, orbita: 0.45, galaxia: 0.35, universo: 0.25, sente: 0.15, iss: 0.2, odometro: 0.25, fecho: 0.2, cta: 0 };
const SHAKES = [[M.boom, 12], [M.rot, 6], [M.orb, 8], [M.gal, 10], [M.uni, 14]];
function shakeAt(t) {
  let dx = 0, dy = 0;
  for (const [t0, A] of SHAKES) { if (t < t0 || t > t0 + 1.4) continue; const e = A * Math.exp(-(t - t0) * 3.5); dx += e * noise3(t * 14, 1.3, t0); dy += e * noise3(4.1, t * 14, t0); }
  return [dx, dy];
}
async function frame(i, opts = {}) {
  const t = i / FPS;
  let cur = 0; for (let k = 0; k < SCENES.length; k++) if (t >= SCENES[k].t0) cur = k;
  const sc = SCENES[cur], into = t - sc.t0, trd = TR[sc.tr || 'cut'] || 0, inTr = cur > 0 && into < trd;
  ctx.save(); ctx.fillStyle = '#000'; ctx.fillRect(0, 0, W, H);
  const [sx, sy] = shakeAt(t);
  if (sx || sy) { ctx.translate(sx, sy); ctx.translate(W / 2, H / 2); ctx.scale(1.03, 1.03); ctx.translate(-W / 2, -H / 2); }
  if (inTr) {
    const p = easeInOutCubic(into / trd), prev = SCENES[cur - 1];
    await renderBg(ctxA, prev, t); await renderBg(ctxB, sc, t);
    if (sc.tr === 'push') {
      ctx.save(); ctx.globalAlpha = 1 - p; ctx.translate(W / 2, H / 2); ctx.scale(1 + 0.5 * p, 1 + 0.5 * p); ctx.translate(-W / 2, -H / 2); ctx.drawImage(bufA, 0, 0); ctx.restore();
      ctx.save(); ctx.globalAlpha = p; ctx.translate(W / 2, H / 2); ctx.scale(0.8 + 0.2 * p, 0.8 + 0.2 * p); ctx.translate(-W / 2, -H / 2); ctx.drawImage(bufB, 0, 0); ctx.restore();
    } else { ctx.drawImage(bufA, 0, 0); ctx.globalAlpha = p; ctx.drawImage(bufB, 0, 0); ctx.globalAlpha = 1; }
  } else { await renderBg(ctxA, sc, t); ctx.drawImage(bufA, 0, 0); }
  ctx.restore();
  const bl = inTr ? lerp(BLOOM[SCENES[cur - 1].name], BLOOM[sc.name], clamp(into / trd)) : BLOOM[sc.name];
  if (bl > 0) bloom(bl);
  // rebobinar (assinatura da série): o próprio vídeo volta ao começo
  const ra = win(t, REW[0] - 0.05, REW[1] + 0.05, 0.08, 0.1);
  if (ra > 0) {
    sctx.clearRect(0, 0, W, H); sctx.drawImage(canvas, 0, 0);
    const r = rng(Math.floor(t * 60));
    for (let k = 0; k < 8; k++) { const yy = r() * H, hh = 20 + r() * 120, dx = (r() - 0.5) * 90 * ra; ctx.drawImage(scratch, 0, yy, W, hh, dx, yy, W, hh); }
    ctx.save(); ctx.globalAlpha = 0.18 * ra; ctx.fillStyle = '#000'; for (let yy = (t * 400) % 6; yy < H; yy += 6) ctx.fillRect(0, yy, W, 2); ctx.restore();
    text(ctx, '◀◀', 90, 560, { font: `900 72px ${FONT}`, color: '#fff', alpha: ra * (0.6 + 0.4 * Math.sin(t * 20)), stroke: 8 });
  }
  ctx.save(); ctx.globalCompositeOperation = 'overlay'; ctx.drawImage(GRAIN[i % 4], 0, 0, W, H); ctx.restore();
  ctx.drawImage(vignette, 0, 0); ctx.drawImage(topVeil, 0, 0); ctx.drawImage(botVeil, 0, H - 700);
  if (inTr) { ctx.save(); ctx.globalAlpha = 1 - clamp(into / trd); S[SCENES[cur - 1].name].fg(ctx, t, lt(SCENES[cur - 1], t)); ctx.restore(); ctx.save(); ctx.globalAlpha = clamp(into / trd); S[sc.name].fg(ctx, t, lt(sc, t)); ctx.restore(); }
  else S[sc.name].fg(ctx, t, lt(sc, t));
  // painel do topo com o odômetro ao vivo (some no odômetro gigante, no fecho e na marca)
  const pa = sstep(0.2, 0.6, t) * (1 - sstep(SCN.odometro.t0 - 0.2, SCN.odometro.t0 + 0.2, t)) * (t < TL.total - 0.6 ? 1 : 0);
  const [lab, val] = camada(t);
  panel(ctx, t, pa, [['VOCÊ JÁ PERCORREU*', `${fmt(KMS * t)} km`, C.yellow], [lab, val]]);
  if (!inTr && sc.name !== 'cta') credit(ctx, sc.name, t);
  const pg = TL.pages.find(p => t >= p.t0 && t < p.t1);
  if (!opts.noCaptions && !(pg && pg.line === 'fecho')) drawCaptions(ctx, t);
}

// ---------------------------------------------------------------- main
(async () => {
  await loadImages();
  const argv = process.argv.slice(2), pi = argv.indexOf('--preview');
  if (argv.includes('--capa')) {
    ctx.fillStyle = '#000'; ctx.fillRect(0, 0, W, H);
    sky(ctx, 0, [40, 90, 200]);
    await globe(ctx, 'gira', 1, 1.0);
    bloom(0.35);
    const g = ctx.createLinearGradient(0, 1100, 0, H); g.addColorStop(0, 'rgba(0,0,0,0)'); g.addColorStop(0.4, 'rgba(0,0,0,0.85)'); g.addColorStop(1, 'rgba(0,0,0,0.97)');
    ctx.fillStyle = g; ctx.fillRect(0, 1100, W, H - 1100); ctx.drawImage(vignette, 0, 0);
    text(ctx, '1.331.280 km/h', W / 2, 330, { font: `300 112px ${MONO_L}`, color: C.yellow, align: 'center', shadow: 30 });
    text(ctx, 'É A SUA VELOCIDADE AGORA', W / 2, 400, { font: `26px ${MONO_M}`, color: 'rgba(235,240,255,0.92)', align: 'center', spacing: 8 });
    text(ctx, 'Você acha que', W / 2, 1470, { font: `italic 400 110px ${SERIF_I}`, color: '#fff6ea', align: 'center', shadow: 30 });
    text(ctx, 'está parado?', W / 2, 1590, { font: `italic 400 110px ${SERIF_I}`, color: '#fff6ea', align: 'center', shadow: 30 });
    text(ctx, 'Luzes da Terra: NASA Black Marble 2016', W - 60, 1780, { font: `500 18px ${FONT}`, color: 'rgba(220,228,255,0.6)', align: 'right' });
    const out = path.join(ROOT, 'output/capa.png'); fs.mkdirSync(path.dirname(out), { recursive: true });
    fs.writeFileSync(out, canvas.toBuffer('image/png')); console.log(out);
  } else if (pi >= 0) {
    const dir = path.join(ROOT, 'build/preview'); fs.mkdirSync(dir, { recursive: true });
    for (const s of argv[pi + 1].split(',')) {
      const i = clamp(Math.round(parseFloat(s) * FPS), 0, N - 1); const t0 = Date.now(); await frame(i);
      const out = path.join(dir, `t${(i / FPS).toFixed(2).padStart(6, '0')}.png`);
      fs.writeFileSync(out, canvas.toBuffer('image/png')); console.log(out, (Date.now() - t0) + 'ms');
    }
  } else {
    const out = path.join(ROOT, 'build/video.mp4');
    const ff = spawn('ffmpeg', ['-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgba', '-s', `${W}x${H}`, '-r', String(FPS), '-i', '-',
      '-c:v', 'libx264', '-preset', 'slow', '-crf', '20', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', out], { stdio: ['pipe', 'inherit', 'inherit'] });
    const tr = Date.now();
    for (let i = 0; i < N; i++) {
      await frame(i);
      if (!ff.stdin.write(Buffer.from(canvas.data()))) await new Promise(r => ff.stdin.once('drain', r));
      if ((i + 1) % 150 === 0) console.log(`  quadro ${i + 1}/${N} (${((Date.now() - tr) / 1000).toFixed(0)}s)`);
    }
    ff.stdin.end();
    ff.on('close', code => { console.log('ffmpeg terminou:', code, out); process.exit(code); });
  }
})();
