// Ciência #6 — "O que acontece se você cair num buraco negro?"
// Base: simulação de supercomputador da NASA (Goddard, J. Schnittman e B. Powell, SVS 14576, domínio público),
// recortada em tomadas verticais por src/shots.py. Também: panorama da Via Láctea (ESO/S. Brunier) e a primeira
// imagem de Sagitário A* (EHT Collaboration), ambos CC BY 4.0, e a foto de Bruce McCandless (NASA).
// Painel com os relógios REAIS da simulação (lidos do filme "clock comparison" da NASA).
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

// ---------------------------------------------------------------- relógios reais da simulação (lidos do filme da NASA)
// [tempo do filme (s), relógio de quem cai (s)] e [tempo do filme, relógio de quem ficou longe (s)]
const LOCAL = [[0, 0], [0.25, 222.85], [2.25, 1497.56], [4.25, 2772.27], [6.25, 4046.99], [8.25, 5321.70], [10.25, 6596.41], [12.25, 7871.12],
  [14.25, 9145.83], [16.25, 10420.54], [18.25, 10753.62], [20.25, 10896.50], [22.25, 11013.65], [24.25, 11114.61], [26.25, 11205.99], [28.25, 11291.89],
  [30.25, 11374.53], [32.25, 11454.19], [34.25, 11528.28], [36.25, 11594.66], [37.25, 11623.87], [38.25, 11649.73], [39.25, 11671.76], [40.25, 11689.67],
  [41.25, 11703.43], [41.75, 11708.84], [42.25, 11713.34], [43.25, 11720.00], [44.25, 11724.17], [45, 11726.16], [49, 11729.10], [53, 11729.258], [58.7, 11729.264]];
const COORD = [[0, 0], [0.25, 227.46], [2.25, 1529.92], [4.25, 2835.23], [6.25, 4144.25], [8.25, 5458.29], [10.25, 6779.63], [12.25, 8112.73],
  [14.25, 9468.77], [16.25, 10896.52], [18.25, 11315.73], [20.25, 11515.17], [22.25, 11694.18], [24.25, 11862.56], [26.25, 12026.29], [28.25, 12188.27],
  [30.25, 12349.70], [32.25, 12509.69], [34.25, 12663.24], [36.25, 12807.86], [37.25, 12875.73], [38.25, 12940.12], [39.25, 13001.07], [40.25, 13059.73],
  [41.25, 13120.65], [41.75, 13157.20], [42.25, 13213.42]];
const SRC_CROSS = 42.6;
function tab(T, x) { if (x <= T[0][0]) return T[0][1]; for (let i = 1; i < T.length; i++) if (x <= T[i][0]) { const [a, va] = T[i - 1], [b, vb] = T[i]; return lerp(va, vb, (x - a) / (b - a)); } return T[T.length - 1][1]; }
const localAt = src => tab(LOCAL, src);
const coordAt = src => src >= SRC_CROSS ? Infinity : (src <= 42.25 ? tab(COORD, src) : 13213.42 + 40 * (1 / (SRC_CROSS - src) - 1 / 0.35));
function hms(s, dec = 1) {
  if (!isFinite(s)) return '∞';
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), r = s - h * 3600 - m * 60;
  const rs = r.toFixed(dec).padStart(dec ? 3 + dec : 2, '0');
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${rs}`;
}

// ---------------------------------------------------------------- imagens e tomadas
const IMG = {};
async function loadImages() {
  for (const k of ['sgr_a', 'sol']) IMG[k] = await loadImage(path.join(ROOT, 'assets', k + '.jpg'));
  IMG.astro = await loadImage(path.join(ROOT, 'assets/astronauta.png'));
}
const SHOT = { aprox: 0.0, luz: 2.0, mergulho: 36.0, escape: 42.0, pano: 0 };
const COUNT = {}; for (const k of Object.keys(SHOT)) { const d = path.join(ROOT, 'build/shots', k); COUNT[k] = fs.existsSync(d) ? fs.readdirSync(d).filter(f => f.endsWith('.jpg')).length : 0; }
const CACHE = new Map();
async function shot(name, src) { // src = tempo no filme da NASA (ou progresso 0..1 no panorama)
  const k = name === 'pano' ? Math.round(clamp(src) * (COUNT.pano - 1)) + 1 : clamp(Math.round((src - SHOT[name]) * 30) + 1, 1, COUNT[name]);
  const key = name + k;
  if (!CACHE.has(key)) {
    CACHE.set(key, await loadImage(path.join(ROOT, 'build/shots', name, String(k).padStart(5, '0') + '.jpg')));
    if (CACHE.size > 14) CACHE.delete(CACHE.keys().next().value);
  }
  return CACHE.get(key);
}
function cover(ctx, img, { z = 1, cx = W / 2, cy = H / 2, ox = 0, oy = 0, alpha = 1, rot = 0 } = {}) {
  const s = Math.max(W / img.width, H / img.height) * z;
  ctx.save(); ctx.globalAlpha *= alpha; ctx.translate(cx + ox, cy + oy); ctx.rotate(rot); ctx.scale(s, s);
  ctx.drawImage(img, -img.width / 2 - (cx - W / 2) / s, -img.height / 2 - (cy - H / 2) / s); ctx.restore();
}

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
  ctx.save(); ctx.globalAlpha = a; ctx.shadowColor = 'rgba(0,0,0,0.9)'; ctx.shadowBlur = 40;
  lines.forEach((ln, k) => text(ctx, ln, 540, y + k * size * 1.12, { font: `italic 400 ${size}px ${SERIF_I}`, color: '#fff6ea', align: 'center' }));
  ctx.restore();
}
// painel de instrumentos: dois relógios lado a lado
function clocks(ctx, a, cells, { y = 186, warn = false } = {}) {
  if (a <= 0) return;
  const x = 60, w = 960, h = 178;
  ctx.save(); ctx.globalAlpha = a;
  ctx.fillStyle = 'rgba(4,6,14,0.5)'; rr(ctx, x, y, w, h, 22); ctx.fill();
  ctx.strokeStyle = warn ? 'rgba(255,110,90,0.55)' : 'rgba(255,255,255,0.14)'; ctx.lineWidth = 1.5; rr(ctx, x, y, w, h, 22); ctx.stroke();
  ctx.fillStyle = 'rgba(255,255,255,0.12)'; ctx.fillRect(x + w / 2, y + 30, 1.5, h - 60);
  cells.forEach(([lab, val, col], k) => {
    const cx = x + w / 4 + k * w / 2;
    text(ctx, lab, cx, y + 58, { font: `21px ${MONO}`, color: 'rgba(205,215,240,0.78)', align: 'center', spacing: 4 });
    let fs = 58; ctx.font = `${fs}px ${MONO_L}`; while (ctx.measureText(val).width > w / 2 - 40) { fs -= 2; ctx.font = `${fs}px ${MONO_L}`; }
    text(ctx, val, cx, y + 132, { font: `${fs}px ${MONO_L}`, color: col || '#fff', align: 'center' });
  });
  ctx.restore();
  ctx.save(); ctx.globalAlpha = a; ctx.fillStyle = 'rgb(255,90,70)'; ctx.beginPath(); ctx.arc(x + 12, y - 24, 6, 0, 6.283); ctx.fill(); ctx.restore();
  text(ctx, 'SIMULAÇÃO NASA · TEMPO REAL DE CADA RELÓGIO', x + 28, y - 18, { font: `18px ${MONO}`, color: 'rgba(255,170,150,0.85)', spacing: 3, alpha: a });
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

// ---------------------------------------------------------------- astronauta (vermelho, esticado)
const astroBuf = createCanvas(820, 940), abx = astroBuf.getContext('2d');
function astronaut(ctx, x, y, h, { rot = 0, red = 0, alpha = 1, sx = 1, sy = 1, streak = 0 } = {}) {
  if (alpha <= 0) return;
  const img = IMG.astro, s = h / img.height;
  abx.clearRect(0, 0, 820, 940); abx.globalCompositeOperation = 'source-over'; abx.globalAlpha = 1; abx.drawImage(img, 0, 0);
  if (red > 0) { abx.globalCompositeOperation = 'source-atop'; abx.fillStyle = `rgba(255,40,20,${0.75 * red})`; abx.fillRect(0, 0, 820, 940);
    abx.globalCompositeOperation = 'source-atop'; abx.fillStyle = `rgba(0,0,0,${0.35 * red})`; abx.fillRect(0, 0, 820, 940); }
  ctx.save(); ctx.translate(x, y); ctx.rotate(rot); ctx.scale(s * sx, s * sy);
  for (let k = streak; k > 0; k--) { ctx.globalAlpha = alpha * 0.12 * (1 - k / (streak + 1)); ctx.drawImage(astroBuf, -img.width / 2, -img.height / 2 + k * 40); }
  ctx.globalAlpha = alpha; ctx.drawImage(astroBuf, -img.width / 2, -img.height / 2); ctx.restore();
}

// ================================================================ cenas
// cada cena: bg (imagem de fundo, recebe bloom) e fg (gráficos por cima)
const S = {};
// ---- gancho: a queda já perto do disco; depois o filme rebobina até o começo
S.hook = {
  async bg(ctx, t, lt) {
    const tt = lt; // também desenhada no fim (loop)
    let src = 11.3 + tt;
    if (tt > REW[0]) src = lerp(11.3 + REW[0], 0.3, easeInOutCubic((tt - REW[0]) / (REW[1] - REW[0])));
    cover(ctx, await shot('aprox', src), { z: 1.0 + 0.06 * clamp(tt / 5) });
    const fl = tt - M.boom; if (fl > 0 && fl < 0.35) { ctx.save(); ctx.globalCompositeOperation = 'screen'; ctx.fillStyle = `rgba(255,236,215,${0.55 * Math.pow(1 - fl / 0.35, 2)})`; ctx.fillRect(0, 0, W, H); ctx.restore(); }
  },
  fg(ctx, t, lt) {
    const a = win(lt, Wt('nasa', 4), REW[0], 0.35, 0.2), p = easeOutCubic((lt - Wt('nasa', 4)) / 0.6);
    if (a > 0) {
      ctx.save(); ctx.globalAlpha = a; ctx.fillStyle = 'rgba(255,255,255,0.8)'; ctx.fillRect(90, 1268, 4, 96 * p);
      text(ctx, 'SUPERCOMPUTADOR DISCOVER · NASA', 116, 1300, { font: `24px ${MONO_M}`, color: '#fff', spacing: 4, shadow: 12 });
      text(ctx, '5 DIAS DE CÁLCULO · 10 TERABYTES', 116, 1344, { font: `24px ${MONO}`, color: 'rgba(225,232,255,0.85)', spacing: 4, shadow: 12 });
      ctx.restore();
    }
  },
};
// ---- destino: voo até o centro da Via Láctea e a primeira imagem de Sagitário A*
S.destino = {
  async bg(ctx, t, lt) {
    const t0 = SCN.destino.t0;
    if (t < M.eht) {
      const u = Math.pow(clamp((t - t0) / (M.eht - t0)), 1.3);
      cover(ctx, await shot('pano', u), { z: 1 + 0.25 * u * u });
    } else {
      ctx.fillStyle = '#000'; ctx.fillRect(0, 0, W, H);
      const e = t - M.eht, z = 0.92 + 0.08 * easeOutCubic(e / 3) + 0.01 * e;
      const s = 880 / IMG.sgr_a.width * z;
      ctx.save(); ctx.translate(540, 900); ctx.scale(s, s); ctx.drawImage(IMG.sgr_a, -IMG.sgr_a.width / 2, -IMG.sgr_a.height / 2); ctx.restore();
      const fl = clamp(1 - e / 0.35); if (fl > 0) { ctx.fillStyle = `rgba(255,240,225,${fl})`; ctx.fillRect(0, 0, W, H); }
    }
  },
  fg(ctx, t, lt) {
    const t0 = SCN.destino.t0;
    if (t < M.eht) { // retícula no centro galáctico
      const a = sstep(t0 + 0.6, t0 + 1.2, t) * (1 - sstep(M.eht - 0.25, M.eht, t)), r = lerp(120, 70, clamp((t - t0) / (M.eht - t0)));
      if (a > 0) {
        ctx.save(); ctx.globalAlpha = a; ctx.strokeStyle = 'rgba(255,255,255,0.85)'; ctx.lineWidth = 2;
        for (let k = 0; k < 4; k++) { ctx.beginPath(); ctx.arc(540, 960, r, k * Math.PI / 2 + 0.25, k * Math.PI / 2 + Math.PI / 2 - 0.25); ctx.stroke(); }
        ctx.beginPath(); ctx.arc(540, 960, 5, 0, 6.283); ctx.fillStyle = '#fff'; ctx.fill(); ctx.restore();
        chip(ctx, 'CENTRO DA VIA LÁCTEA', 540, 960 - r - 60, a);
      }
    } else {
      const a = sstep(M.eht + 0.2, M.eht + 0.8, t);
      text(ctx, 'Sagitário A*', 540, 400, { font: `italic 400 118px ${SERIF_I}`, color: '#fff3e6', align: 'center', alpha: a, shadow: 30 });
      text(ctx, 'O BURACO NEGRO NO CENTRO DA NOSSA GALÁXIA', 540, 462, { font: `22px ${MONO}`, color: 'rgba(225,232,255,0.8)', align: 'center', spacing: 4, alpha: a });
      const b = sstep(Wt('destino', 16) - 0.1, Wt('destino', 16) + 0.4, t);
      chip(ctx, '4,3 MILHÕES DE SÓIS', 300, 1390, b, { dot: rgba(C.accent) });
      chip(ctx, '27 MIL ANOS-LUZ', 790, 1390, sstep(Wt('destino', 18), Wt('destino', 18) + 0.4, t));
    }
  },
};
// ---- tamanho: o horizonte de eventos tem 25 milhões de km; cabem 18 sóis enfileirados
S.tamanho = {
  async bg(ctx, t, lt) {
    cover(ctx, await shot('pano', 1), { z: 1.4, alpha: 0.32 });
    ctx.fillStyle = 'rgba(2,3,8,0.35)'; ctx.fillRect(0, 0, W, H);
  },
  fg(ctx, t, lt) {
    const cx = 540, cy = 900, R = 420;
    const pc = easeInOutCubic((t - Wt('tamanho', 1)) / 0.9);
    if (pc > 0) {
      ctx.save(); ctx.fillStyle = `rgba(0,0,0,${0.85 * pc})`; ctx.beginPath(); ctx.arc(cx, cy, R, 0, 6.283); ctx.fill();
      const g = ctx.createRadialGradient(cx, cy, R * 0.9, cx, cy, R * 1.25); g.addColorStop(0, 'rgba(255,140,60,0)'); g.addColorStop(0.2, `rgba(255,150,70,${0.35 * pc})`); g.addColorStop(1, 'rgba(255,120,40,0)');
      ctx.fillStyle = g; ctx.beginPath(); ctx.arc(cx, cy, R * 1.25, 0, 6.283); ctx.fill();
      ctx.strokeStyle = 'rgba(255,215,170,0.95)'; ctx.lineWidth = 3; ctx.beginPath(); ctx.arc(cx, cy, R, -Math.PI / 2, -Math.PI / 2 + 6.283 * pc); ctx.stroke(); ctx.restore();
    }
    chip(ctx, 'HORIZONTE DE EVENTOS', cx, cy - R - 70, sstep(Wt('tamanho', 6) - 0.1, Wt('tamanho', 6) + 0.3, t));
    const pd = easeInOutCubic((t - Wt('tamanho', 10)) / 0.8);
    if (pd > 0) {
      ctx.save(); ctx.strokeStyle = 'rgba(255,255,255,0.9)'; ctx.lineWidth = 2;
      const x0 = cx - R * pd, x1 = cx + R * pd;
      ctx.beginPath(); ctx.moveTo(x0, cy); ctx.lineTo(x1, cy); ctx.stroke();
      for (const [x, d] of [[x0, 1], [x1, -1]]) { ctx.beginPath(); ctx.moveTo(x + 14 * d, cy - 9); ctx.lineTo(x, cy); ctx.lineTo(x + 14 * d, cy + 9); ctx.stroke(); }
      ctx.restore();
      const v = Math.round(25 * easeOutCubic((t - Wt('tamanho', 10)) / 1.3));
      text(ctx, `${v} milhões de km`, cx, cy - 34, { font: `300 52px ${MONO_L}`, color: '#fff', align: 'center', shadow: 16 });
    }
    // 18 sóis lado a lado (25,4 mi km ÷ 1,39 mi km)
    const ts = Wt('tamanho', 15), n = 18, d = 2 * R / 18.25;
    for (let k = 0; k < n; k++) {
      const a = sstep(ts + k * 0.05, ts + k * 0.05 + 0.2, t); if (a <= 0) continue;
      const x = cx - R + d * (k + 0.5) + (2 * R - d * 18.25) / 2;
      glowAt(ctx, x, cy + 70, d * 0.9, [255, 150, 60], 0.35 * a);
      ctx.save(); ctx.globalAlpha = a; ctx.globalCompositeOperation = 'screen'; ctx.beginPath(); ctx.arc(x, cy + 70, d / 2, 0, 6.283); ctx.clip();
      const s = d / 470; ctx.drawImage(IMG.sol, x - IMG.sol.width * s / 2, cy + 70 - IMG.sol.height * s / 2, IMG.sol.width * s, IMG.sol.height * s); ctx.restore();
    }
    chip(ctx, 'CABEM 18 SÓIS ENFILEIRADOS', cx, cy + R + 80, sstep(ts + 0.5, ts + 0.9, t), { dot: rgba(C.accent) });
  },
};
// ---- a queda: do começo até as órbitas, com relógios reais e minimapa
const qSrc = t => lerp(0.3, 16.5, clamp((t - SCN.queda.t0) / (SCN.luz.t0 - SCN.queda.t0)));
S.queda = {
  async bg(ctx, t, lt) { cover(ctx, await shot('aprox', qSrc(t)), { z: 1.26, oy: -240 }); },
  fg(ctx, t, lt) {
    const src = qSrc(t), a = sstep(SCN.queda.t0, SCN.queda.t0 + 0.3, t);
    clocks(ctx, a, [['SEU RELÓGIO', hms(localAt(src), 0)], ['LÁ FORA', hms(coordAt(src), 0)]]);
    chip(ctx, 'INÍCIO: 640 MILHÕES DE KM', 540, 470, win(t, SCN.queda.t0 + 0.2, SCN.queda.t0 + 1.8, 0.3, 0.3));
    minimap(ctx, 60, 470, src / SRC_CROSS, sstep(SCN.queda.t0 + 1.5, SCN.queda.t0 + 1.9, t));
  },
};
// trajetória esquemática: aproximação, quase duas voltas e mergulho
function pathPt(s) {
  if (s < 0.35) { const q = s / 0.35; return [lerp(1.0, 0.36, q), lerp(-0.85, -0.05, q)]; }
  const q = (s - 0.35) / 0.65, ang = -Math.PI / 2 + 0.2 + q * 1.85 * 2 * Math.PI, r = lerp(0.36, 0.0, Math.pow(q, 2.2));
  return [r * Math.cos(ang) * 0.95, r * Math.sin(ang) * 0.95];
}
function minimap(ctx, x, y, s, a) {
  if (a <= 0) return;
  const w = 270, h = 270, cx = x + w / 2, cy = y + h / 2 + 10, R = 112;
  ctx.save(); ctx.globalAlpha = a;
  ctx.fillStyle = 'rgba(4,6,14,0.5)'; rr(ctx, x, y, w, h + 30, 18); ctx.fill(); ctx.strokeStyle = 'rgba(255,255,255,0.14)'; ctx.lineWidth = 1.2; rr(ctx, x, y, w, h + 30, 18); ctx.stroke();
  text(ctx, 'TRAJETÓRIA (ESQUEMA)', x + w / 2, y + 28, { font: `17px ${MONO}`, color: 'rgba(205,215,240,0.75)', align: 'center', spacing: 2 });
  ctx.setLineDash([5, 6]); ctx.strokeStyle = 'rgba(255,255,255,0.45)'; ctx.beginPath(); ctx.arc(cx, cy, R * 0.34, 0, 6.283); ctx.stroke(); ctx.setLineDash([]);
  ctx.fillStyle = '#000'; ctx.strokeStyle = 'rgba(255,190,140,0.9)'; ctx.lineWidth = 2; ctx.beginPath(); ctx.arc(cx, cy, R * 0.17, 0, 6.283); ctx.fill(); ctx.stroke();
  ctx.strokeStyle = 'rgba(255,120,60,0.7)'; ctx.beginPath(); ctx.moveTo(cx - R * 0.95, cy); ctx.lineTo(cx - R * 0.42, cy); ctx.moveTo(cx + R * 0.42, cy); ctx.lineTo(cx + R * 0.95, cy); ctx.stroke();
  ctx.strokeStyle = 'rgba(255,255,255,0.9)'; ctx.lineWidth = 2.5; ctx.setLineDash([3, 6]); ctx.beginPath();
  for (let k = 0; k <= 80; k++) { const [px, py] = pathPt(clamp(s) * k / 80); k ? ctx.lineTo(cx + px * R, cy + py * R) : ctx.moveTo(cx + px * R, cy + py * R); } ctx.stroke(); ctx.setLineDash([]);
  const [px, py] = pathPt(clamp(s)); glowAt(ctx, cx + px * R, cy + py * R, 16, [255, 255, 255], 0.7); ctx.fillStyle = '#fff'; ctx.beginPath(); ctx.arc(cx + px * R, cy + py * R, 4.5, 0, 6.283); ctx.fill();
  ctx.restore();
}
// ---- luz: o disco visto por cima e por baixo ao mesmo tempo
const lSrc = t => lerp(2.0, 7.2, clamp((t - SCN.luz.t0) / (SCN.longe.t0 - SCN.luz.t0)));
S.luz = {
  async bg(ctx, t, lt) { cover(ctx, await shot('luz', lSrc(t)), { z: 1.0 }); },
  fg(ctx, t, lt) {
    const k = (lSrc(t) - 2) * 30 + 1, yTop = 820 + 0.22 * k, yBot = 1238 + 0.97 * k;
    const t1 = Wt('luz', 12), t2 = Wt('luz', 15), end = SCN.longe.t0;
    const a1 = win(t, t1 - 0.1, end, 0.25, 0.3), a2 = win(t, t2 - 0.1, end, 0.25, 0.3);
    leader(ctx, 980, 610, 700, yTop + 8, easeOutCubic((t - t1) / 0.5), a1);
    chip(ctx, 'DISCO VISTO POR CIMA', 1000, 610, a1, { align: 'right' });
    leader(ctx, 100, 1420, 450, yBot + 4, easeOutCubic((t - t2) / 0.5), a2);
    chip(ctx, '…E POR BAIXO', 80, 1420, a2, { align: 'left' });
    chip(ctx, 'A LUZ CONTORNA O BURACO NEGRO', 540, 470, win(t, Wt('luz', 1), t1 - 0.1, 0.3, 0.3));
  },
};
// ---- de longe: a imagem de quem cai fica lenta, vermelha e congela na beira
const FREEZE = M.fita + 1.0;
const slow = t => { // "relógio" visual de quem cai, visto de longe: desacelera e para
  const t0 = SCN.longe.t0, k = 0.55; return (1 - Math.exp(-k * (Math.min(t, FREEZE) - t0))) / k;
};
const SLOW_MAX = () => (1 - Math.exp(-0.55 * (FREEZE - SCN.longe.t0))) / 0.55;
S.longe = {
  async bg(ctx, t, lt) {
    const u = slow(t) / SLOW_MAX();
    cover(ctx, await shot('luz', 2.0), { z: 1.0 + 0.1 * u });
    ctx.fillStyle = 'rgba(2,3,8,0.18)'; ctx.fillRect(0, 0, W, H);
    const u2 = u, z = 1.0 + 0.1 * u;
    // astronauta: vem de cima/direita até a borda da sombra e congela
    const x = lerp(880, 640, easeOutCubic(u2)), y = lerp(380, 960, easeOutCubic(u2));
    const red = sstep(Wt('congela', 5) - 0.2, Wt('congela', 6, 't1'), t) * 0.85 + 0.15 * u2;
    const dim = 1 - 0.55 * sstep(Wt('congela', 5), FREEZE, t);
    ctx.save(); ctx.translate(540, 960); ctx.scale(z, z); ctx.translate(-540, -960);
    astronaut(ctx, x, y, lerp(300, 130, easeOutCubic(u2)), { rot: -0.4 + 0.5 * u2, red, alpha: dim });
    ctx.restore();
    const fz = sstep(FREEZE, FREEZE + 0.4, t);
    if (fz > 0) { ctx.save(); ctx.globalCompositeOperation = 'saturation'; ctx.fillStyle = `rgba(128,128,128,${0.55 * fz})`; ctx.fillRect(0, 0, W, H); ctx.restore(); }
  },
  fg(ctx, t, lt) {
    const a = sstep(SCN.longe.t0, SCN.longe.t0 + 0.4, t);
    const voce = 11715.67 - 1.6 * Math.exp(-1.2 * slow(t));
    const fora = 13150.0 + (t - SCN.longe.t0);
    const frozen = t >= FREEZE;
    clocks(ctx, a, [['VOCÊ, VISTO DE LONGE', hms(voce, 2), frozen ? rgba([255, 120, 100]) : '#fff'], ['QUEM FICOU', hms(fora, 2)]]);
    chip(ctx, 'CADA VEZ MAIS LENTO', 540, 470, win(t, Wt('congela', 3), Wt('congela', 5), 0.2, 0.2));
    chip(ctx, 'CADA VEZ MAIS VERMELHO', 540, 470, win(t, Wt('congela', 5), Wt('congela', 8), 0.2, 0.2), { dot: rgba(C.red) });
    chip(ctx, 'CONGELADO NA BEIRA', 540, 470, win(t, Wt('congela', 8), SCN.mergulho.t0 + 0.2, 0.15, 0.2), { dot: rgba([150, 210, 255]) });
  },
};
// ---- plano-sequência: cruza o horizonte, lá dentro o universo encolhe, o fim
const mSrc = t => { if (t < M.cross) return SRC_CROSS - (M.cross - t) * 0.82; const q = clamp((t - M.cross) / (M.blink - M.cross));
  return q < 0.75 ? lerp(SRC_CROSS, 52.5, q / 0.75) : lerp(52.5, 58.55, (q - 0.75) / 0.25); };
S.mergulho = {
  async bg(ctx, t, lt) {
    cover(ctx, await shot('mergulho', mSrc(t)), { z: 1.02 + 0.03 * clamp(lt / 20) });
    const c = t - M.cross;
    if (c > 0 && c < 0.5) { ctx.fillStyle = `rgba(255,255,255,${0.22 * (1 - c / 0.5)})`; ctx.fillRect(0, 0, W, H); }
    // corpo esticado (espaguetificação), puxado para o centro
    const t0 = Wt('fim', 8), st = clamp((t - t0) / (M.blink - t0));
    if (st > 0) { // esticado na direção do centro (para baixo), espremido dos lados, com rastro
      const sy = 1 + 2.2 * Math.pow(st, 1.5), sx = 1 / Math.pow(sy, 0.7), h = 250;
      ctx.save(); if (st > 0.15) ctx.filter = `blur(${(1.6 * st).toFixed(2)}px)`;
      astronaut(ctx, 540, 860 + h * sy / 2 + 120 * st, h, { rot: 0.03, sx, sy, red: 0.25 * st, alpha: sstep(0, 0.1, st) * (1 - 0.7 * sstep(0.8, 1, st)), streak: Math.round(5 * st) });
      ctx.restore();
    }
  },
  fg(ctx, t, lt) {
    const src = mSrc(t), crossed = t >= M.cross;
    const a = sstep(SCN.mergulho.t0, SCN.mergulho.t0 + 0.4, t) * (1 - sstep(M.blink - 0.1, M.blink + 0.1, t));
    clocks(ctx, a, [['SEU RELÓGIO', hms(localAt(src), 1)], ['LÁ FORA', hms(coordAt(src), 1), crossed ? rgba([255, 140, 110]) : '#fff']], { warn: crossed });
    chip(ctx, 'HORIZONTE DE EVENTOS CRUZADO', 540, 470, win(t, M.cross, M.cross + 2.4, 0.15, 0.4), { dot: rgba(C.red) });
    chip(ctx, 'O UNIVERSO LÁ FORA, CADA VEZ MENOR', 540, 470, win(t, Wt('dentro', 2), L.dentro.end + 0.2, 0.3, 0.3));
    // contagem: 12,8 s até o fim (anel que esvazia)
    const c0 = Wt('fim', 3), ca = win(t, c0 - 0.1, M.blink + 0.05, 0.3, 0.1);
    if (ca > 0) {
      const p = clamp((t - Wt('fim', 7, 't1')) / (M.blink - Wt('fim', 7, 't1')));
      const cy = 600, R = 140;
      ctx.save(); ctx.globalAlpha = ca; ctx.fillStyle = 'rgba(4,6,14,0.45)'; ctx.beginPath(); ctx.arc(540, cy, R, 0, 6.283); ctx.fill();
      ctx.strokeStyle = 'rgba(255,255,255,0.15)'; ctx.lineWidth = 5; ctx.beginPath(); ctx.arc(540, cy, R, 0, 6.283); ctx.stroke();
      ctx.strokeStyle = rgba([255, 120, 90]); ctx.lineWidth = 5; ctx.lineCap = 'round'; ctx.beginPath(); ctx.arc(540, cy, R, -Math.PI / 2, -Math.PI / 2 + 6.283 * (1 - p)); ctx.stroke(); ctx.restore();
      text(ctx, '12,8', 540, cy + 14, { font: `300 76px ${MONO_L}`, color: '#fff', align: 'center', alpha: ca });
      text(ctx, 'SEGUNDOS', 540, cy + 62, { font: `19px ${MONO}`, color: 'rgba(225,232,255,0.8)', align: 'center', spacing: 4, alpha: ca });
      text(ctx, 'ATÉ O FIM', 540, cy + R + 44, { font: `21px ${MONO}`, color: 'rgba(225,232,255,0.8)', align: 'center', spacing: 5, alpha: ca });
    }
  },
};
// ---- reviravolta: passar raspando e voltar; o buraco negro ficando para trás; fecho
const eSrc = t => t < M.whip ? 49.6 + (t - M.whip) : (t < M.whip + 0.9 ? 49.6 + (t - M.whip) : 50.5 + (t - M.whip - 0.9) * 1.5);
S.twist = {
  async bg(ctx, t, lt) {
    const src = eSrc(t), k = sstep(M.whip, M.whip + 0.9, t), z = lerp(1.02, 1.3, k), oy = lerp(0, -300, k);
    cover(ctx, await shot('escape', src), { z, oy });
    if (t > M.whip - 0.05 && t < M.whip + 0.95) { // borrão de movimento no chicote
      for (const d of [1, 2, 3]) { ctx.globalAlpha = 0.35 / d; cover(ctx, await shot('escape', src - d / 30), { z, oy }); }
      ctx.globalAlpha = 1;
    }
  },
  fg(ctx, t, lt) {
    chip(ctx, 'VOO RASANTE · 60% DA VELOCIDADE DA LUZ', 540, 470, win(t, Wt('twist', 3), M.whip - 0.1, 0.25, 0.2));
    const c0 = Wt('twist', 8), a = win(t, c0 - 0.1, L.twist.end + 0.4, 0.3, 0.35), p = easeOutCubic((t - c0) / 1.4);
    if (a > 0) {
      clocks(ctx, a, [['QUEM FICOU NA NAVE', hms(6 * 3600 * p, 0)], ['VOCÊ', hms((6 * 3600 - 36 * 60) * p, 0), C.yellow]]);
      chip(ctx, 'IDA E VOLTA DE 6 HORAS', 540, 470, a);
      const d = sstep(Wt('twist', 12) - 0.05, Wt('twist', 12) + 0.3, t);
      text(ctx, '−36 min', 540, 640, { font: `300 92px ${MONO_L}`, color: C.yellow, align: 'center', alpha: a * d, shadow: 24 });
    }
    // fecho
    const f1 = win(t, Wt('fecho', 0) - 0.1, SCN.cta.t0 + 0.2, 0.6, 0.4);
    poem(ctx, ['Perto de um buraco negro,', 'o tempo não passa', 'igual pra todo mundo.'], 560, f1, 80);
  },
};
S.cta = { async bg(ctx, t, lt) { ctaScene(ctx, t, lt); }, fg() {} };

// ---------------------------------------------------------------- composição
const SCENES = [
  { name: 'hook', t0: -1, local0: 0 },
  { name: 'destino', t0: REW[1] - 0.02, tr: 'cut' },
  { name: 'tamanho', t0: L.tamanho.start - 0.35, tr: 'push' },
  { name: 'queda', t0: L.queda.start - 0.25, tr: 'push' },
  { name: 'luz', t0: L.luz.start - 0.3, tr: 'cut' },
  { name: 'longe', t0: L.tempo.start - 0.45, tr: 'dissolve' },
  { name: 'mergulho', t0: L.cruza.start - 0.45, tr: 'cut' },
  { name: 'twist', t0: L.twist.start - 0.45, tr: 'cut' },
  { name: 'cta', t0: L.cta.start - 0.45, tr: 'dissolve' },
  { name: 'hook', t0: TL.total - 0.5, local0: TL.total, tr: 'dissolve' },
];
const SCN = {}; SCENES.forEach(s => { if (!SCN[s.name]) SCN[s.name] = s; });
const TR = { cut: 0, push: 0.5, dissolve: 0.6 };
const CRED = {
  hook: 'Simulação: NASA’s Goddard Space Flight Center/J. Schnittman and B. Powell',
  destino: t => t < M.eht ? 'Panorama da Via Láctea: ESO/S. Brunier · CC BY 4.0' : 'Imagem: EHT Collaboration (ESO) · CC BY 4.0',
  queda: 'Simulação: NASA’s Goddard Space Flight Center/J. Schnittman and B. Powell',
  luz: 'Simulação: NASA’s Goddard Space Flight Center/J. Schnittman and B. Powell',
  longe: 'Simulação: NASA Goddard/J. Schnittman and B. Powell · Astronauta: NASA',
  mergulho: 'Simulação: NASA’s Goddard Space Flight Center/J. Schnittman and B. Powell',
  twist: 'Simulação: NASA’s Goddard Space Flight Center/J. Schnittman and B. Powell',
  tamanho: 'Sol: NASA/SDO',
};
function credit(ctx, name, t) {
  let s = CRED[name]; if (typeof s === 'function') s = s(t); if (!s) return;
  ctx.font = `500 19px ${FONT}`;
  const words = s.split(' '), lines = []; let cur = '';
  for (const w of words) { const tst = cur ? cur + ' ' + w : w; if (ctx.measureText(tst).width > 880 && cur) { lines.push(cur); cur = w; } else cur = tst; }
  lines.push(cur);
  lines.forEach((ln, k) => text(ctx, ln, W - 60, 1452 - (lines.length - 1 - k) * 25, { font: `500 19px ${FONT}`, color: 'rgba(220,228,255,0.6)', align: 'right', shadow: 8 }));
}
const vignette = (() => { const c = createCanvas(W, H), x = c.getContext('2d'); const g = x.createRadialGradient(W / 2, H * 0.47, H * 0.25, W / 2, H * 0.5, H * 0.78); g.addColorStop(0, 'rgba(0,0,0,0)'); g.addColorStop(1, 'rgba(0,0,0,0.62)'); x.fillStyle = g; x.fillRect(0, 0, W, H); return c; })();
const topVeil = (() => { const c = createCanvas(W, 700), x = c.getContext('2d'); const g = x.createLinearGradient(0, 0, 0, 700); g.addColorStop(0, 'rgba(0,0,0,0.55)'); g.addColorStop(1, 'rgba(0,0,0,0)'); x.fillStyle = g; x.fillRect(0, 0, W, 700); return c; })();
const botVeil = (() => { const c = createCanvas(W, 700), x = c.getContext('2d'); const g = x.createLinearGradient(0, 0, 0, 700); g.addColorStop(0, 'rgba(0,0,0,0)'); g.addColorStop(1, 'rgba(0,0,0,0.6)'); x.fillStyle = g; x.fillRect(0, 0, W, 700); return c; })();
const GRAIN = Array.from({ length: 4 }, (_, k) => { const c = createCanvas(540, 960), x = c.getContext('2d'), im = x.createImageData(540, 960), r = rng(60 + k); for (let q = 0; q < im.data.length; q += 4) { const v = r() * 255; im.data[q] = im.data[q + 1] = im.data[q + 2] = v; im.data[q + 3] = 16; } x.putImageData(im, 0, 0); return c; });
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
function bloom(amount) { // halo nas partes brilhantes (disco, estrelas)
  smx.globalCompositeOperation = 'source-over'; smx.filter = 'none'; smx.drawImage(canvas, 0, 0, 270, 480);
  smx.globalCompositeOperation = 'multiply'; smx.drawImage(small, 0, 0); smx.globalCompositeOperation = 'source-over';
  smx.filter = 'blur(7px)'; smx.drawImage(small, 0, 0); smx.filter = 'none';
  ctx.save(); ctx.globalCompositeOperation = 'screen'; ctx.globalAlpha = amount; ctx.drawImage(small, 0, 0, W, H); ctx.restore();
}
const SHAKES = [[M.boom, 16], [M.cross, 10], [M.blink, 8]];
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
    if (sc.tr === 'push') { // empurrão: a cena anterior avança e some, a nova chega de trás
      ctx.save(); ctx.globalAlpha = 1 - p; ctx.translate(W / 2, H / 2); ctx.scale(1 + 0.5 * p, 1 + 0.5 * p); ctx.translate(-W / 2, -H / 2); ctx.drawImage(bufA, 0, 0); ctx.restore();
      ctx.save(); ctx.globalAlpha = p; ctx.translate(W / 2, H / 2); ctx.scale(0.8 + 0.2 * p, 0.8 + 0.2 * p); ctx.translate(-W / 2, -H / 2); ctx.drawImage(bufB, 0, 0); ctx.restore();
    } else { ctx.drawImage(bufA, 0, 0); ctx.globalAlpha = p; ctx.drawImage(bufB, 0, 0); ctx.globalAlpha = 1; }
  } else { await renderBg(ctxA, sc, t); ctx.drawImage(bufA, 0, 0); }
  ctx.restore();
  if (sc.name !== 'cta' && !(inTr && SCENES[cur - 1].name === 'cta')) bloom(sc.name === 'tamanho' ? 0.25 : 0.42);
  // rebobinar (assinatura da série): o próprio filme volta até o começo
  const ra = win(t, REW[0] - 0.05, REW[1] + 0.05, 0.08, 0.1);
  if (ra > 0) {
    sctx.clearRect(0, 0, W, H); sctx.drawImage(canvas, 0, 0);
    const r = rng(Math.floor(t * 60));
    for (let k = 0; k < 8; k++) { const yy = r() * H, hh = 20 + r() * 120, dx = (r() - 0.5) * 90 * ra; ctx.drawImage(scratch, 0, yy, W, hh, dx, yy, W, hh); }
    ctx.save(); ctx.globalAlpha = 0.18 * ra; ctx.fillStyle = '#000'; for (let yy = (t * 400) % 6; yy < H; yy += 6) ctx.fillRect(0, yy, W, 2); ctx.restore();
    text(ctx, '◀◀', 90, 560, { font: `900 72px ${FONT}`, color: '#fff', alpha: ra * (0.6 + 0.4 * Math.sin(t * 20)), stroke: 8 });
    const src = lerp(11.3 + REW[0], 0.3, easeInOutCubic((t - REW[0]) / (REW[1] - REW[0])));
    text(ctx, hms(localAt(clamp(src, 0, 18)), 0), 990, 560, { font: `36px ${MONO_M}`, color: '#fff', align: 'right', alpha: ra, shadow: 10 });
  }
  ctx.save(); ctx.globalCompositeOperation = 'overlay'; ctx.drawImage(GRAIN[i % 4], 0, 0, W, H); ctx.restore();
  ctx.drawImage(vignette, 0, 0); ctx.drawImage(topVeil, 0, 0); ctx.drawImage(botVeil, 0, H - 700);
  // gráficos por cima
  if (inTr) { ctx.save(); ctx.globalAlpha = 1 - clamp(into / trd); S[SCENES[cur - 1].name].fg(ctx, t, lt(SCENES[cur - 1], t)); ctx.restore(); ctx.save(); ctx.globalAlpha = clamp(into / trd); S[sc.name].fg(ctx, t, lt(sc, t)); ctx.restore(); }
  else S[sc.name].fg(ctx, t, lt(sc, t));
  if (!inTr && sc.name !== 'cta') credit(ctx, sc.name, t);
  // piscar de olhos: pálpebras fecham, preto, e abrem na reviravolta
  const open0 = SCN.twist.t0 + 0.05, cl = sstep(M.blink, M.blink + 0.16, t) * (1 - sstep(open0, open0 + 0.28, t));
  if (cl > 0) {
    ctx.save(); ctx.fillStyle = '#000';
    const hh = (H / 2 + 60) * cl;
    ctx.beginPath(); ctx.moveTo(0, 0); ctx.lineTo(W, 0); ctx.lineTo(W, hh - 40); ctx.quadraticCurveTo(W / 2, hh + 80, 0, hh - 40); ctx.closePath(); ctx.fill();
    ctx.beginPath(); ctx.moveTo(0, H); ctx.lineTo(W, H); ctx.lineTo(W, H - hh + 40); ctx.quadraticCurveTo(W / 2, H - hh - 80, 0, H - hh + 40); ctx.closePath(); ctx.fill();
    ctx.restore();
  }
  const pg = TL.pages.find(p => t >= p.t0 && t < p.t1);
  if (!opts.noCaptions && !(pg && pg.line === 'fecho')) drawCaptions(ctx, t);
}

// ---------------------------------------------------------------- main
(async () => {
  await loadImages();
  const argv = process.argv.slice(2), pi = argv.indexOf('--preview');
  if (argv.includes('--capa')) {
    ctx.fillStyle = '#000'; ctx.fillRect(0, 0, W, H);
    cover(ctx, await shot('mergulho', 47.0), { z: 1.32, oy: -330 });
    bloom(0.45);
    const g = ctx.createLinearGradient(0, 1000, 0, H); g.addColorStop(0, 'rgba(0,0,0,0)'); g.addColorStop(0.45, 'rgba(0,0,0,0.85)'); g.addColorStop(1, 'rgba(0,0,0,0.97)');
    ctx.fillStyle = g; ctx.fillRect(0, 1000, W, H - 1000); ctx.drawImage(vignette, 0, 0);
    text(ctx, 'SIMULAÇÃO REAL DA NASA', W / 2, 1270, { font: `28px ${MONO_M}`, color: 'rgba(255,200,170,0.95)', align: 'center', spacing: 8 });
    text(ctx, 'O que acontece se você', W / 2, 1400, { font: `italic 400 100px ${SERIF_I}`, color: '#fff6ea', align: 'center', shadow: 30 });
    text(ctx, 'cair num buraco negro?', W / 2, 1510, { font: `italic 400 100px ${SERIF_I}`, color: '#fff6ea', align: 'center', shadow: 30 });
    text(ctx, 'Simulação: NASA’s Goddard Space Flight Center/J. Schnittman and B. Powell', W - 60, 1760, { font: `500 18px ${FONT}`, color: 'rgba(220,228,255,0.6)', align: 'right' });
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
      '-c:v', 'libx264', '-preset', 'slow', '-crf', '18', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', out], { stdio: ['pipe', 'inherit', 'inherit'] });
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
