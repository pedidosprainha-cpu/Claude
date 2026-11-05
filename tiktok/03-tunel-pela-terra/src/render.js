// Vídeo 03 — "E se você pulasse num túnel que atravessa a Terra?"
// Renderiza quadro a quadro (1080x1920, 30 fps) e envia para o ffmpeg.
//   node src/render.js                   -> build/video.mp4
//   node src/render.js --preview 3,20    -> build/preview/*.png
//   node src/render.js --capa            -> output/capa.png
const { createCanvas, loadImage } = require('@napi-rs/canvas');
const { getIconData, iconToSVG, iconToHTML, replaceIDs } = require('@iconify/utils');
const FLUENT = require('@iconify-json/fluent-emoji/icons.json');
const WORLD = require('world-atlas/countries-110m.json');
const { feature } = require('topojson-client');
const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');

const ROOT = path.resolve(__dirname, '..');
const TL = JSON.parse(fs.readFileSync(path.join(ROOT, 'build/timeline.json'), 'utf8'));
const W = 1080, H = 1920, FPS = TL.fps, N = TL.frames;
const FONT = '"Inter Display"', MONO = '"JetBrains Mono"';
const C = { yellow: '#FFD23F', cyan: '#4FD1FF', red: '#FF3B4E', orange: '#FF8A3D', ink: '#070A14', label: '#8FA3C8' };
const L = TL.lines;
const Wt = (line, i, k = 't0') => L[line].words[i][k];
const SPRITES = {};
// ---------------------------------------------------------------- utilidades
const clamp = (x, a = 0, b = 1) => Math.max(a, Math.min(b, x));
const lerp = (a, b, t) => a + (b - a) * t;
const sstep = (a, b, x) => { const t = clamp((x - a) / (b - a)); return t * t * (3 - 2 * t); };
const easeOutCubic = p => 1 - Math.pow(1 - clamp(p), 3);
const easeInCubic = p => Math.pow(clamp(p), 3);
const easeInOutCubic = p => (p = clamp(p), p < 0.5 ? 4 * p * p * p : 1 - Math.pow(-2 * p + 2, 3) / 2);
const easeOutBack = p => { p = clamp(p); const c1 = 1.70158, c3 = c1 + 1; return 1 + c3 * Math.pow(p - 1, 3) + c1 * Math.pow(p - 1, 2); };
const win = (t, a, b, fi = 0.2, fo = 0.2) => Math.min(sstep(a, a + fi, t), 1 - sstep(b - fo, b, t));
function rng(seed) { return () => { seed |= 0; seed = seed + 0x6D2B79F5 | 0; let t = Math.imul(seed ^ seed >>> 15, 1 | seed); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
const hex = h => [parseInt(h.slice(1, 3), 16), parseInt(h.slice(3, 5), 16), parseInt(h.slice(5, 7), 16)];
const mixc = (a, b, t) => a.map((v, i) => v + (b[i] - v) * t);
const rgba = (c, a = 1) => `rgba(${c[0] | 0},${c[1] | 0},${c[2] | 0},${a})`;
const nf = (x, d) => x.toLocaleString('pt-BR', { minimumFractionDigits: d, maximumFractionDigits: d });

// ---------------------------------------------------------------- ruído (Perlin 3D)
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
function fbm3(x, y, z, oct = 5) { let a = 0.5, f = 1, s = 0; for (let i = 0; i < oct; i++) { s += a * noise3(x * f, y * f, z * f); a *= 0.5; f *= 2.03; } return s; }
const ridge1 = (x, seed, oct = 4) => fbm3(x, seed * 7.31, seed * 1.7, oct);


const tintCv = createCanvas(1200, 1200), tintCtx = tintCv.getContext('2d');
// desenha uma ilustração centrada em (x, y = base) com tamanho em px; tint integra a luz da cena
function sprite(ctx, name, x, y, size, o = {}) {
  const img = SPRITES[name]; if (!img) return;
  const { rot = 0, alpha = 1, flip = false, tint = null, shadow = 0, anchor = 'bottom', sx = 1, sy = 1, glow = null } = o;
  if (alpha <= 0.003 || size < 1) return;
  const w = size * (img.width / img.height), h = size;
  ctx.save(); ctx.globalAlpha *= alpha;
  if (shadow > 0) {
    const g = ctx.createRadialGradient(x, y, 0, x, y, w * 0.5);
    g.addColorStop(0, `rgba(0,0,0,${0.45 * shadow})`); g.addColorStop(1, 'rgba(0,0,0,0)');
    ctx.fillStyle = g; ctx.beginPath(); ctx.ellipse(x, y + 2, w * 0.5, h * 0.06, 0, 0, 6.283); ctx.fill();
  }
  ctx.translate(x, y); ctx.rotate(rot); ctx.scale((flip ? -1 : 1) * sx, sy);
  const oy = anchor === 'bottom' ? -h : -h / 2;
  if (glow) { ctx.shadowColor = glow; ctx.shadowBlur = size * 0.25; }
  if (tint && w < 1200 && h < 1200) {
    tintCtx.clearRect(0, 0, Math.ceil(w) + 2, Math.ceil(h) + 2);
    tintCtx.globalCompositeOperation = 'source-over'; tintCtx.globalAlpha = 1;
    tintCtx.drawImage(img, 0, 0, w, h);
    tintCtx.globalCompositeOperation = 'source-atop'; tintCtx.globalAlpha = tint[3];
    tintCtx.fillStyle = rgba(tint); tintCtx.fillRect(0, 0, w, h);
    tintCtx.globalCompositeOperation = 'source-over'; tintCtx.globalAlpha = 1;
    ctx.drawImage(tintCv, 0, 0, w, h, -w / 2, oy, w, h);
  } else ctx.drawImage(img, -w / 2, oy, w, h);
  ctx.restore();
}
const popIn = (t, t0, d = 0.38) => t < t0 ? 0 : easeOutBack((t - t0) / d);


function rr(ctx, x, y, w, h, r) {
  ctx.beginPath(); ctx.moveTo(x + r, y); ctx.arcTo(x + w, y, x + w, y + h, r); ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r); ctx.arcTo(x, y, x + w, y, r); ctx.closePath();
}
function text(ctx, s, x, y, { font, color = '#fff', align = 'left', base = 'alphabetic', stroke = 0, strokeColor = 'rgba(0,0,0,0.9)', spacing = 0, alpha = 1, shadow = 0 } = {}) {
  if (alpha <= 0) return;
  ctx.save(); ctx.globalAlpha *= alpha; ctx.font = font; ctx.textAlign = align; ctx.textBaseline = base; ctx.letterSpacing = spacing + 'px';
  if (shadow) { ctx.shadowColor = 'rgba(0,0,0,0.6)'; ctx.shadowBlur = shadow; ctx.shadowOffsetY = shadow / 3; }
  if (stroke) { ctx.lineJoin = 'round'; ctx.lineWidth = stroke; ctx.strokeStyle = strokeColor; ctx.strokeText(s, x, y); ctx.shadowBlur = 0; }
  ctx.fillStyle = color; ctx.fillText(s, x, y); ctx.restore();
}
function gradSky(ctx, stops, y0 = 0, y1 = H) {
  const g = ctx.createLinearGradient(0, y0, 0, y1);
  stops.forEach(([p, c]) => g.addColorStop(p, typeof c === 'string' ? c : rgba(c)));
  ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
}
// camada de relevo (silhueta) com borda iluminada
function terrain(ctx, { seed, base, amp, freq = 0.0025, color, rim = null, scroll = 0, oct = 4, sharp = 0 }) {
  ctx.beginPath(); ctx.moveTo(-10, H + 10);
  for (let x = -10; x <= W + 10; x += 6) {
    let n = ridge1((x + scroll) * freq, seed, oct);
    if (sharp) n = lerp(n, 0.5 - Math.abs(n) * 1.4, sharp);
    ctx.lineTo(x, base - amp * n);
  }
  ctx.lineTo(W + 10, H + 10); ctx.closePath();
  if (Array.isArray(color)) { const g = ctx.createLinearGradient(0, base - amp, 0, base + 500); g.addColorStop(0, color[0]); g.addColorStop(1, color[1]); ctx.fillStyle = g; }
  else ctx.fillStyle = color;
  ctx.fill();
  if (rim) { ctx.save(); ctx.clip(); ctx.strokeStyle = rim; ctx.lineWidth = 5; ctx.beginPath();
    for (let x = -10; x <= W + 10; x += 6) { let n = ridge1((x + scroll) * freq, seed, oct); if (sharp) n = lerp(n, 0.5 - Math.abs(n) * 1.4, sharp); const y = base - amp * n + 2; x === -10 ? ctx.moveTo(x, y) : ctx.lineTo(x, y); }
    ctx.stroke(); ctx.restore(); }
}
const terrainY = (x, { seed, base, amp, freq = 0.0025, scroll = 0, oct = 4, sharp = 0 }) => { let n = ridge1((x + scroll) * freq, seed, oct); if (sharp) n = lerp(n, 0.5 - Math.abs(n) * 1.4, sharp); return base - amp * n; };
function godRays(ctx, t, alpha, color = '200,240,255') {
  ctx.save(); ctx.globalCompositeOperation = 'lighter';
  const ox = 620, oy = -300;
  for (let i = 0; i < 9; i++) {
    const a = -0.55 + i * 0.13 + Math.sin(t * 0.25 + i * 1.7) * 0.03, wa = 0.025 + 0.03 * ((i * 7) % 3) / 2;
    const flick = 0.6 + 0.4 * Math.sin(t * 0.7 + i * 2.3);
    const g = ctx.createLinearGradient(ox, oy, ox + Math.sin(a) * 1900, oy + Math.cos(a) * 1900);
    g.addColorStop(0.25, `rgba(${color},${0.13 * alpha * flick})`); g.addColorStop(0.8, `rgba(${color},0)`);
    ctx.fillStyle = g; ctx.beginPath(); ctx.moveTo(ox, oy);
    ctx.lineTo(ox + Math.sin(a - wa) * 2000, oy + Math.cos(a - wa) * 2000); ctx.lineTo(ox + Math.sin(a + wa) * 2000, oy + Math.cos(a + wa) * 2000); ctx.fill();
  }
  ctx.restore();
}
function marineSnow(ctx, t, alpha, col = '220,240,255') {
  ctx.save();
  for (const p of DUST) {
    const x = (p.x * W + Math.sin(t * p.s + p.ph) * 30) % W, y = ((p.y * H - t * 18 * p.s) % H + H) % H;
    ctx.globalAlpha = alpha * (0.25 + 0.4 * p.s); ctx.fillStyle = `rgb(${col})`;
    ctx.beginPath(); ctx.arc(x, y, p.r * 0.7, 0, 6.283); ctx.fill();
  }
  ctx.restore();
}

function embers(ctx, t, alpha, n = 60, seed = 5, col = [255, 170, 60]) {
  const r = rng(seed);
  ctx.save(); ctx.globalCompositeOperation = 'lighter';
  for (let i = 0; i < n; i++) {
    const x0 = r() * W, sp = 60 + r() * 140, ph = r() * 20, sz = 1.5 + r() * 3.5;
    const y = 1500 - ((t * sp + ph * 90) % 1200), x = x0 + Math.sin(t * 1.5 + ph) * 25;
    ctx.globalAlpha = alpha * (0.4 + 0.6 * r()) * clamp((1500 - y) / 200);
    ctx.fillStyle = rgba(col); ctx.beginPath(); ctx.arc(x, y, sz, 0, 6.283); ctx.fill();
  }
  ctx.restore();
}
function smoke(ctx, t, x, y, alpha, scale = 1, col = '40,32,30', seed = 9) {
  const r = rng(seed);
  for (let i = 0; i < 14; i++) {
    const ph = (t * 0.25 + i / 14 + r() * 0.05) % 1;
    const px = x + Math.sin(ph * 4 + i) * 30 * scale + ph * 140 * scale, py = y - ph * 520 * scale, pr = (40 + ph * 160) * scale;
    const g = ctx.createRadialGradient(px, py, 0, px, py, pr);
    g.addColorStop(0, `rgba(${col},${0.32 * alpha * (1 - ph)})`); g.addColorStop(1, `rgba(${col},0)`);
    ctx.fillStyle = g; ctx.beginPath(); ctx.arc(px, py, pr, 0, 6.283); ctx.fill();
  }
}
function glowAt(ctx, x, y, r, col, a) {
  const g = ctx.createRadialGradient(x, y, 0, x, y, r);
  g.addColorStop(0, rgba(col, a)); g.addColorStop(1, rgba(col, 0));
  ctx.fillStyle = g; ctx.beginPath(); ctx.arc(x, y, r, 0, 6.283); ctx.fill();
}


// ---- encerramento com a marca
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
function sceneCTA(ctx, t, lt, i) {
  const g = ctx.createRadialGradient(540, 860, 40, 540, 960, 1100); g.addColorStop(0, '#1d2d5c'); g.addColorStop(1, '#04060f');
  ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
  for (const s of STARS) { ctx.globalAlpha = s.a * 0.6; ctx.fillStyle = '#fff'; ctx.beginPath(); ctx.arc(s.x, s.y, s.r, 0, 6.283); ctx.fill(); }
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
  let fs = 84; ctx.font = `900 ${fs}px ${FONT}`;
  const widths = () => pg.toks.map(k => ctx.measureText(k.txt).width);
  let ws = widths(), sp = fs * 0.3, total = ws.reduce((a, b) => a + b, 0) + sp * (ws.length - 1);
  while (total > 900 && fs > 50) { fs -= 4; ctx.font = `900 ${fs}px ${FONT}`; ws = widths(); sp = fs * 0.3; total = ws.reduce((a, b) => a + b, 0) + sp * (ws.length - 1); }
  const age = t - pg.t0, pin = easeOutBack(age / 0.2);
  const alpha = clamp(age / 0.08) * (1 - sstep(pg.t1 - 0.08, pg.t1, t));
  const cy = 1545;
  ctx.save(); ctx.globalAlpha = alpha; ctx.translate(W / 2, cy); ctx.scale(0.86 + 0.14 * pin, 0.86 + 0.14 * pin); ctx.translate(-W / 2, -cy);
  let x = W / 2 - total / 2;
  pg.toks.forEach((k, j) => {
    const active = t >= k.t0 - 0.03 && (j === pg.toks.length - 1 || t < pg.toks[j + 1].t0 - 0.03);
    const s = active ? 1 + 0.07 * (1 - easeOutCubic((t - k.t0) / 0.18)) + 0.02 : 1;
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


// ================================================================ vídeo 03: específico
const SPRITE_NAMES = ['astronaut', 'palm-tree', 'magnet', 'thermometer', 'sun', 'water-wave', 'infinity', 'feather', 'herb', 'deciduous-tree', 'high-voltage'];
async function loadSprites() {
  for (const n of SPRITE_NAMES) {
    const d = getIconData(FLUENT, n);
    if (!d) throw new Error('ilustração não encontrada: ' + n);
    const r = iconToSVG(d, { height: 1024 });
    const img = await loadImage(Buffer.from(iconToHTML(replaceIDs(r.body), r.attributes)));
    const cv = createCanvas(img.width, img.height); cv.getContext('2d').drawImage(img, 0, 0);
    SPRITES[n] = cv;
  }
}

// ---------------------------------------------------------------- física (amostras da simulação)
const Q = TL.queda, TQ = Q.total, AM = Q.amostras, DT_AM = AM[1].t - AM[0].t, DIAM = 12742;
AM.push({ t: TQ, prof: DIAM, v: 0, temp: 15 });
function stateAt(s) {
  const P = 2 * TQ; let u = ((s % P) + P) % P, back = false;
  if (u > TQ) { u = P - u; back = true; }
  const f = u / DT_AM, k = Math.min(AM.length - 2, Math.floor(f)), a = AM[k], b = AM[k + 1], w = clamp(f - k);
  const along = lerp(a.prof, b.prof, w);
  return { along: back ? along : along, dir: back ? -1 : 1, v: lerp(a.v, b.v, w), temp: lerp(a.temp, b.temp, w), depth: Math.min(along, DIAM - along) };
}
const SIM = TL.sim;
const simAt = i => SIM[clamp(i, 0, N - 1)];
const lapse = i => Math.abs(simAt(i + 1) - simAt(i - 1)) * FPS / 2;

// ---------------------------------------------------------------- vetores e projeção do globo
const dot = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
const cross = (a, b) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
const norm = a => { const l = Math.hypot(...a); return a.map(x => x / l); };
const vadd = (a, b, s = 1) => a.map((x, i) => x + b[i] * s);
const vs = (a, s) => a.map(x => x * s);
const ll = (lat, lon) => { const la = lat * Math.PI / 180, lo = lon * Math.PI / 180; return [Math.cos(la) * Math.cos(lo), Math.cos(la) * Math.sin(lo), Math.sin(la)]; };
const NORTH = [0, 0, 1];
const BR = ll(-15.8, -47.9);          // Brasília
const ANTI = vs(BR, -1);              // antípoda (mar das Filipinas)
const facing = p => { const right = norm(cross(NORTH, p)); return { right, up: cross(p, right), fwd: p }; };
const VA = facing(BR);
// θ = 0: Brasil de frente; θ = π/2: Brasil no topo (corte); θ = π: antípoda de frente
function basisAt(theta, northBlend = 0) {
  const fwd = norm(vadd(vs(BR, Math.cos(theta)), VA.up, -Math.sin(theta)));
  let up = norm(vadd(vs(VA.up, Math.cos(theta)), BR, Math.sin(theta)));
  if (northBlend > 0) { const nu = norm(vadd(NORTH, fwd, -dot(NORTH, fwd))); up = norm(vadd(vs(up, 1 - northBlend), nu, northBlend)); }
  const right = norm(cross(up, fwd)); up = cross(fwd, right);
  return { right, up, fwd };
}
const project = (p, B, cx, cy, R) => ({ x: cx + R * dot(p, B.right), y: cy - R * dot(p, B.up), z: dot(p, B.fwd) });

// ---------------------------------------------------------------- texturas
const MW = 2048, MH = 1024;
let MAP = null, CLOUD = null, CUT = null;
function buildMap() {
  const cv = createCanvas(MW, MH), x = cv.getContext('2d');
  const mk = createCanvas(MW, MH), m = mk.getContext('2d');
  const og = x.createLinearGradient(0, 0, 0, MH); og.addColorStop(0, '#1a4a86'); og.addColorStop(0.5, '#2a6fb5'); og.addColorStop(1, '#1a4a86');
  x.fillStyle = og; x.fillRect(0, 0, MW, MH);
  m.fillStyle = '#000'; m.fillRect(0, 0, MW, MH);
  const fc = feature(WORLD, WORLD.objects.countries);
  const P = (lon, lat) => [(lon + 180) / 360 * MW, (90 - lat) / 180 * MH];
  for (const f of fc.features) {
    const polys = f.geometry.type === 'Polygon' ? [f.geometry.coordinates] : f.geometry.coordinates;
    const name = f.properties.name;
    const id = name === 'Brazil' ? '#ff0000' : name === 'Japan' ? '#00ff00' : name === 'Philippines' ? '#0000ff' : null;
    for (const poly of polys) {
      for (const off of [-MW, 0, MW]) {
        for (const g of [x, m]) {
          if (g === m && !id) continue;
          g.beginPath();
          for (const ring of poly) {
            let prev = null, shift = 0;
            ring.forEach(([lon, lat], k) => {
              if (prev !== null && Math.abs(lon - prev) > 180) shift += lon < prev ? 360 : -360;
              prev = lon; const [px, py] = P(lon + shift, lat);
              k === 0 ? g.moveTo(px + off, py) : g.lineTo(px + off, py);
            });
            g.closePath();
          }
          if (g === x) {
            const lat0 = poly[0][0][1];
            g.fillStyle = Math.abs(lat0) > 62 && name !== 'Russia' && name !== 'Canada' ? '#e9f1f7' : '#5b9b4c';
            g.fill('evenodd');
            g.strokeStyle = 'rgba(30,60,30,0.35)'; g.lineWidth = 1.2; g.stroke();
          } else { g.fillStyle = id; g.fill('evenodd'); }
        }
      }
    }
  }
  const d = x.getImageData(0, 0, MW, MH).data, md = m.getImageData(0, 0, MW, MH).data;
  const rgb = new Uint8ClampedArray(MW * MH * 3), mask = new Uint8Array(MW * MH);
  for (let j = 0; j < MH; j++) {
    const lat = (0.5 - (j + 0.5) / MH) * Math.PI;
    for (let i = 0; i < MW; i++) {
      const k = j * MW + i, lon = ((i + 0.5) / MW) * 2 * Math.PI - Math.PI;
      let r = d[k * 4], g = d[k * 4 + 1], b = d[k * 4 + 2];
      const land = g > r + 20 && g > b;
      // variação de relevo/vegetação com ruído
      const px = Math.cos(lat) * Math.cos(lon), py = Math.cos(lat) * Math.sin(lon), pz = Math.sin(lat);
      const n = fbm3(px * 3 + 5, py * 3, pz * 3, 4);
      if (land) {
        const dry = clamp(0.5 + n * 1.6 - Math.abs(Math.abs(lat) - 0.42) * 1.2);
        r = lerp(70, 196, dry * 0.7) + n * 30; g = lerp(140, 170, dry * 0.5) + n * 20; b = lerp(62, 110, dry * 0.6);
        if (Math.abs(lat) > 1.12) { r = 232; g = 240; b = 246; }
      } else if (r < 100) { r += n * 18; g += n * 22; b += n * 26; }
      rgb[k * 3] = r; rgb[k * 3 + 1] = g; rgb[k * 3 + 2] = b;
      mask[k] = md[k * 4] > 128 ? 1 : md[k * 4 + 1] > 128 ? 2 : md[k * 4 + 2] > 128 ? 3 : 0;
    }
  }
  MAP = { rgb, mask };
  const CW = 1024, CH = 512, cl = new Uint8Array(CW * CH);
  for (let j = 0; j < CH; j++) {
    const lat = (0.5 - (j + 0.5) / CH) * Math.PI;
    for (let i = 0; i < CW; i++) {
      const lon = ((i + 0.5) / CW) * 2 * Math.PI - Math.PI;
      const px = Math.cos(lat) * Math.cos(lon), py = Math.cos(lat) * Math.sin(lon), pz = Math.sin(lat);
      cl[j * CW + i] = sstep(0.08, 0.36, fbm3(px * 2.6 - 7, py * 2.6, pz * 4, 5)) * 220;
    }
  }
  CLOUD = { cl, CW, CH };
}
// corte da Terra (camadas), pré-renderizado
const LAYERS = [ // [raio relativo externo, cor interna, cor externa]
  [0.1917, [255, 255, 240], [255, 232, 150]],
  [0.5462, [255, 196, 70], [240, 120, 30]],
  [0.895, [214, 92, 44], [168, 56, 34]],
  [0.975, [150, 52, 34], [120, 46, 32]],
  [1.0, [120, 92, 64], [92, 70, 50]],
];
function buildCut() {
  const S = 640, cv = createCanvas(S, S), x = cv.getContext('2d'), img = x.createImageData(S, S), d = img.data, c0 = S / 2, R = S / 2 - 2;
  for (let j = 0; j < S; j++) for (let i = 0; i < S; i++) {
    const dx = (i + 0.5 - c0) / R, dy = (j + 0.5 - c0) / R, r = Math.hypot(dx, dy);
    if (r > 1.004) continue;
    let k = 0; while (k < LAYERS.length - 1 && r > LAYERS[k][0]) k++;
    const r0 = k ? LAYERS[k - 1][0] : 0, r1 = LAYERS[k][0], w = clamp((r - r0) / (r1 - r0));
    let col = mixc(LAYERS[k][1], LAYERS[k][2], w);
    const ang = Math.atan2(dy, dx);
    if (k === 2 || k === 3) { const n = fbm3(Math.cos(ang) * 2 + r * 6, Math.sin(ang) * 2 + r * 3, 3, 4); col = mixc(col, [255, 140, 60], clamp(n * 1.4 + 0.15) * 0.45); }
    if (k === 1) { const n = fbm3(dx * 5, dy * 5, 7, 4); col = mixc(col, [255, 230, 140], clamp(n + 0.4) * 0.4); }
    if (k === 4) col = mixc(col, [70, 52, 38], (Math.sin(r * 900) * 0.5 + 0.5) * 0.4);
    const edge = Math.abs(r - r1) < 0.006 && k < 4 ? 0.75 : 1;
    const o = (j * S + i) * 4; d[o] = col[0] * edge; d[o + 1] = col[1] * edge; d[o + 2] = col[2] * edge; d[o + 3] = 255 * clamp((1.004 - r) * R);
  }
  x.putImageData(img, 0, 0);
  CUT = cv;
}

const LIGHT = norm([-0.6, 0.45, 0.66]);
const gcache = {};
function globe(R, B, o = {}) {
  const { cloudShift = 0, hl = [0, 0, 0] } = o;
  const S = Math.ceil(R * 2 + 4);
  if (!gcache[S]) { const cv = createCanvas(S, S); gcache[S] = { cv, ctx: cv.getContext('2d'), img: cv.getContext('2d').createImageData(S, S) }; }
  const g = gcache[S], d = g.img.data; d.fill(0);
  const c0 = S / 2, HL = [[250, 214, 60], [255, 120, 110], [255, 170, 80]];
  for (let y = 0; y < S; y++) {
    const ny = -(y + 0.5 - c0) / R; if (Math.abs(ny) > 1.01) continue;
    for (let x = 0; x < S; x++) {
      const nx = (x + 0.5 - c0) / R, r2 = nx * nx + ny * ny;
      if (r2 > 1 + 2 / R) continue;
      const aa = clamp((1 - Math.sqrt(r2)) * R + 0.5); if (aa <= 0) continue;
      const nz = Math.sqrt(Math.max(0, 1 - r2));
      const px = nx * B.right[0] + ny * B.up[0] + nz * B.fwd[0], py = nx * B.right[1] + ny * B.up[1] + nz * B.fwd[1], pz = nx * B.right[2] + ny * B.up[2] + nz * B.fwd[2];
      const lat = Math.asin(clamp(pz, -1, 1)), lon = Math.atan2(py, px);
      const u = (lon + Math.PI) / (2 * Math.PI), v = 0.5 - lat / Math.PI;
      const ti = Math.min(MH - 1, (v * MH) | 0) * MW + (Math.min(MW - 1, (u * MW) | 0));
      let cr = MAP.rgb[ti * 3], cg = MAP.rgb[ti * 3 + 1], cb = MAP.rgb[ti * 3 + 2];
      const mk = MAP.mask[ti];
      if (mk && hl[mk - 1] > 0) { const h = HL[mk - 1], a = hl[mk - 1]; cr = lerp(cr, h[0], a); cg = lerp(cg, h[1], a); cb = lerp(cb, h[2], a); }
      const uc = (((lon + cloudShift + Math.PI) / (2 * Math.PI)) % 1 + 1) % 1;
      const ca = CLOUD.cl[Math.min(CLOUD.CH - 1, (v * CLOUD.CH) | 0) * CLOUD.CW + ((uc * CLOUD.CW) | 0) % CLOUD.CW] / 255 * 0.85;
      const dif = Math.max(0, nx * LIGHT[0] + ny * LIGHT[1] + nz * LIGHT[2]);
      const lit = 0.16 + 0.95 * Math.pow(dif, 0.8);
      cr = lerp(cr, 248, ca) * lit; cg = lerp(cg, 250, ca) * lit; cb = lerp(cb, 255, ca) * lit;
      const spec = Math.pow(dif, 36) * 80 * (1 - ca) * (cb > cg ? 1 : 0.2);
      const rim = Math.pow(1 - nz, 2.6) * (0.3 + 0.7 * dif);
      const k = (y * S + x) * 4;
      d[k] = cr + 110 * rim + spec; d[k + 1] = cg + 170 * rim + spec; d[k + 2] = cb + 255 * rim + spec; d[k + 3] = aa * 255;
    }
  }
  g.ctx.putImageData(g.img, 0, 0);
  return g.cv;
}
function drawEarth(ctx, cx, cy, R, B, o = {}) {
  const hg = ctx.createRadialGradient(cx, cy, R * 0.92, cx, cy, R * 1.25);
  hg.addColorStop(0, 'rgba(110,180,255,0.5)'); hg.addColorStop(1, 'rgba(110,180,255,0)');
  ctx.fillStyle = hg; ctx.beginPath(); ctx.arc(cx, cy, R * 1.25, 0, 6.283); ctx.fill();
  const cv = globe(R, B, o); ctx.drawImage(cv, cx - cv.width / 2, cy - cv.height / 2);
  if (o.cut > 0) {
    ctx.save(); ctx.globalAlpha = o.cut; ctx.drawImage(CUT, cx - R, cy - R, 2 * R, 2 * R);
    glowAt(ctx, cx, cy, R * 0.32, [255, 240, 180], 0.5 * o.cut); ctx.restore();
  }
}
function drawTunnel(ctx, cx, cy, R, prog, alpha = 1, w = 7) {
  if (alpha <= 0 || prog <= 0) return;
  ctx.save(); ctx.globalAlpha = alpha; ctx.lineCap = 'round';
  ctx.strokeStyle = 'rgba(10,12,20,0.9)'; ctx.lineWidth = w + 6; ctx.beginPath(); ctx.moveTo(cx, cy - R); ctx.lineTo(cx, cy - R + 2 * R * prog); ctx.stroke();
  ctx.shadowColor = 'rgba(120,220,255,0.9)'; ctx.shadowBlur = 18; ctx.strokeStyle = '#9fe6ff'; ctx.lineWidth = w * 0.45;
  ctx.setLineDash([16, 10]); ctx.beginPath(); ctx.moveTo(cx, cy - R); ctx.lineTo(cx, cy - R + 2 * R * prog); ctx.stroke();
  ctx.restore();
}
function flagBR(ctx, x, y, w) {
  const h = w * 0.7; ctx.save(); ctx.translate(x, y);
  ctx.fillStyle = '#1f9a3e'; rr(ctx, 0, 0, w, h, w * 0.08); ctx.fill();
  ctx.fillStyle = '#ffd400'; ctx.beginPath(); ctx.moveTo(w * 0.08, h / 2); ctx.lineTo(w / 2, h * 0.1); ctx.lineTo(w * 0.92, h / 2); ctx.lineTo(w / 2, h * 0.9); ctx.fill();
  ctx.fillStyle = '#1e3f9a'; ctx.beginPath(); ctx.arc(w / 2, h / 2, h * 0.24, 0, 6.283); ctx.fill();
  ctx.strokeStyle = '#fff'; ctx.lineWidth = h * 0.05; ctx.beginPath(); ctx.arc(w / 2 + h * 0.1, h * 0.72, h * 0.32, -2.6, -1.4); ctx.stroke();
  ctx.restore();
}
function pin(ctx, x, y, col, label, a = 1, flag = false, up = true) {
  if (a <= 0) return;
  ctx.save(); ctx.globalAlpha *= a;
  const dy = up ? -1 : 1;
  ctx.strokeStyle = '#fff'; ctx.lineWidth = 4; ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x, y + dy * 70); ctx.stroke();
  ctx.fillStyle = col; ctx.beginPath(); ctx.arc(x, y, 11, 0, 6.283); ctx.fill(); ctx.strokeStyle = '#fff'; ctx.lineWidth = 3; ctx.stroke();
  ctx.font = `900 40px ${FONT}`; const tw = ctx.measureText(label).width + (flag ? 70 : 0);
  const bx = clamp(x - tw / 2 - 22, 40, W - tw - 84), by = up ? y - 70 - 66 : y + 70;
  ctx.fillStyle = 'rgba(6,10,22,0.85)'; rr(ctx, bx, by, tw + 44, 66, 33); ctx.fill();
  ctx.strokeStyle = col; ctx.lineWidth = 3; rr(ctx, bx, by, tw + 44, 66, 33); ctx.stroke();
  if (flag) flagBR(ctx, bx + 20, by + 16, 50);
  text(ctx, label, bx + 22 + (flag ? 70 : 0), by + 47, { font: `900 40px ${FONT}`, color: '#fff' });
  ctx.restore();
}

// ---------------------------------------------------------------- recursos de cena
const R0 = rng(91);
const STARS = Array.from({ length: 380 }, () => ({ x: R0() * W, y: R0() * H, r: 0.4 + R0() * R0() * 2.2, a: 0.25 + R0() * 0.75, tw: R0() * 6.28 }));
const DUST = [];
const STREAKS = Array.from({ length: 70 }, () => ({ a: R0() * 6.283, ph: R0(), sp: 0.6 + R0() * 0.9, w: 1 + R0() * 2.5 }));
const vignette = (() => {
  const c = createCanvas(W, H), x = c.getContext('2d');
  const g = x.createRadialGradient(W / 2, H * 0.48, H * 0.25, W / 2, H * 0.5, H * 0.78);
  g.addColorStop(0, 'rgba(0,0,0,0)'); g.addColorStop(1, 'rgba(0,0,0,0.6)'); x.fillStyle = g; x.fillRect(0, 0, W, H); return c;
})();
function space(ctx, lt, a = 1) {
  ctx.fillStyle = '#03040b'; ctx.fillRect(0, 0, W, H);
  const g = ctx.createRadialGradient(540, 900, 50, 540, 950, 1100); g.addColorStop(0, 'rgba(40,60,130,0.35)'); g.addColorStop(1, 'rgba(0,0,0,0)');
  ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
  for (const s of STARS) { ctx.globalAlpha = a * s.a * (0.7 + 0.3 * Math.sin(lt * 2 + s.tw)); ctx.fillStyle = '#fff'; ctx.beginPath(); ctx.arc(s.x, s.y, s.r, 0, 6.283); ctx.fill(); }
  ctx.globalAlpha = 1;
}

// ---------------------------------------------------------------- cenas
const GX = 540, GY = 960, GR = 330;
const REW = [L.hook.end + 0.25, L.hook.end + 0.95];
function sceneHook(ctx, t, lt, i) {
  space(ctx, lt);
  const rp = sstep(REW[0], REW[1], lt);
  const th = (Math.PI / 2) * easeInOutCubic((lt - Wt('hook', 3)) / (Wt('hook', 8) - Wt('hook', 3))) * (1 - rp);
  const cut = sstep(Wt('hook', 6) - 0.1, Wt('hook', 8) + 0.15, lt) * (1 - rp);
  const B = basisAt(th);
  drawEarth(ctx, GX, GY, GR, B, { cloudShift: lt * 0.05, hl: [1 - 0.6 * cut, 0, 0], cut });
  const lineP = sstep(Wt('hook', 8), Wt('hook', 10), lt) * (1 - rp);
  drawTunnel(ctx, GX, GY, GR, lineP, cut);
  // pino do Brasil
  const pb = project(BR, B, GX, GY, GR);
  pin(ctx, pb.x, pb.y, C.yellow, 'VOCÊ AQUI', (pb.z > -0.05 ? 1 : 0) * (1 - sstep(Wt('hook', 10) - 0.2, Wt('hook', 10) + 0.2, lt) * (1 - rp)), true);
  // viajante descendo pelo túnel
  if (lineP > 0.99 || (lt > Wt('hook', 10) && rp < 1)) {
    const st = stateAt(simAt(i)), y = GY - GR + 2 * GR * (st.along / DIAM);
    glowAt(ctx, GX, y, 60, [255, 255, 255], 0.5 * cut);
    sprite(ctx, 'astronaut', GX, y, 90, { anchor: 'center', alpha: cut, rot: lt * 2 });
  }
  const arr = Wt('hook', 19, 't1') + 0.1;
  const aa = win(lt, arr - 0.05, REW[0] + 0.05, 0.15, 0.1);
  if (aa > 0) pin(ctx, GX, GY + GR, C.red, 'OUTRO LADO', aa, false, false);
}

function sceneJump(ctx, t, lt, i) {
  gradSky(ctx, [[0, '#3f95e0'], [0.45, '#9fd4f5'], [0.66, '#fff1cf'], [1, '#3c7a32']], 0, 1420);
  glowAt(ctx, 860, 560, 260, [255, 245, 200], 0.7); ctx.fillStyle = '#fffbe8'; ctx.beginPath(); ctx.arc(860, 560, 64, 0, 6.283); ctx.fill();
  for (const [cx, cy, cw] of [[200, 640, 170], [620, 720, 230]]) {
    const x = cx + lt * 14; ctx.fillStyle = 'rgba(255,255,255,0.9)';
    ctx.beginPath(); ctx.ellipse(x, cy, cw, cw * 0.28, 0, 0, 6.283); ctx.fill();
    ctx.beginPath(); ctx.ellipse(x - cw * 0.3, cy - cw * 0.15, cw * 0.45, cw * 0.3, 0, 0, 6.283); ctx.fill();
    ctx.beginPath(); ctx.ellipse(x + cw * 0.25, cy - cw * 0.2, cw * 0.38, cw * 0.32, 0, 0, 6.283); ctx.fill();
  }
  terrain(ctx, { seed: 3, base: 1120, amp: 150, freq: 0.0024, color: '#7fb38a', scroll: lt * 4, sharp: 0.3 });
  terrain(ctx, { seed: 5, base: 1230, amp: 90, freq: 0.003, color: '#4f9a52', rim: 'rgba(255,255,220,0.35)', scroll: lt * 8 });
  const gy = 1340;
  ctx.fillStyle = (() => { const g = ctx.createLinearGradient(0, gy - 60, 0, H); g.addColorStop(0, '#6cb84f'); g.addColorStop(1, '#2d5e26'); return g; })();
  ctx.beginPath(); ctx.moveTo(0, H); for (let x = 0; x <= W; x += 10) ctx.lineTo(x, gy - 40 + Math.sin(x * 0.01) * 10); ctx.lineTo(W, H); ctx.fill();
  sprite(ctx, 'palm-tree', 110, gy - 10, 460, { shadow: 0.4, rot: Math.sin(lt) * 0.02 });
  sprite(ctx, 'palm-tree', 1000, gy, 380, { shadow: 0.4, flip: true, rot: Math.sin(lt + 1) * 0.02 });
  // bandeira
  ctx.strokeStyle = '#d8d8d8'; ctx.lineWidth = 8; ctx.beginPath(); ctx.moveTo(250, gy - 20); ctx.lineTo(250, gy - 330); ctx.stroke();
  ctx.save(); ctx.translate(254, gy - 330); ctx.transform(1, Math.sin(lt * 3) * 0.04, 0, 1, 0, 0); flagBR(ctx, 0, 0, 150); ctx.restore();
  // buraco do túnel
  const hx = 560, hy = gy + 20, hw = 250, hh = 72;
  const rg = ctx.createRadialGradient(hx, hy, 10, hx, hy, hw);
  rg.addColorStop(0, '#000'); rg.addColorStop(0.7, '#0b0807'); rg.addColorStop(1, '#3a2a1c');
  ctx.fillStyle = '#5b4330'; ctx.beginPath(); ctx.ellipse(hx, hy, hw + 26, hh + 14, 0, 0, 6.283); ctx.fill();
  ctx.fillStyle = rg; ctx.beginPath(); ctx.ellipse(hx, hy, hw, hh, 0, 0, 6.283); ctx.fill();
  glowAt(ctx, hx, hy + 10, 120, [255, 120, 40], 0.18);
  // astronauta pula no "pular"
  const jl = TL.jump - (t - lt);
  const p = clamp((lt - jl) / 0.55);
  let ax = 800, ay = gy + 6, s = 300, a = 1, rot = 0;
  if (lt >= jl) { ax = lerp(800, hx, p); ay = gy + 6 - Math.sin(Math.PI * Math.min(p, 1)) * 230 + (p >= 1 ? (lt - jl - 0.55) * 900 : 0); rot = -p * 0.6; s = 300 * (1 - sstep(0.55, 1.0, lt - jl) * 0.6); }
  if (ay < hy + 40 || lt < jl + 0.55) {
    if (lt >= jl + 0.5) { ctx.save(); ctx.beginPath(); ctx.rect(0, 0, W, hy); ctx.ellipse(hx, hy, hw, hh, 0, 0, Math.PI); ctx.clip(); }
    sprite(ctx, 'astronaut', ax, ay, s, { alpha: a, rot, shadow: lt < jl ? 0.5 : 0 });
    if (lt >= jl + 0.5) ctx.restore();
  }
}

// ---- túnel em perspectiva (queda)
function material(d) {
  d = Math.min(d, DIAM - d); // simétrico do outro lado
  if (d < 35) { const s = Math.sin(d * 1.7) * 0.5 + 0.5; return { c: mixc([120, 92, 66], [86, 64, 46], s), glow: 0 }; }
  if (d < 660) return { c: mixc([96, 40, 26], [140, 52, 30], (d - 35) / 625), glow: 0.25 };
  if (d < 2890) return { c: mixc([150, 52, 30], [205, 80, 36], (d - 660) / 2230), glow: 0.45 };
  if (d < 5150) return { c: mixc([255, 140, 34], [255, 190, 70], (d - 2890) / 2260), glow: 1 };
  return { c: [255, 250, 225], glow: 1.3 };
}
const LAYER_NAMES = [
  { d: 0, nome: 'CROSTA', sub: 'rocha sólida · 35 km', col: [190, 150, 110] },
  { d: 35, nome: 'MANTO', sub: 'rocha quente que flui', col: [235, 100, 60] },
  { d: 2890, nome: 'NÚCLEO EXTERNO', sub: 'oceano de ferro líquido', col: [255, 170, 60] },
  { d: 5150, nome: 'NÚCLEO INTERNO', sub: 'ferro sólido · 5.400 °C', col: [255, 236, 170] },
  { d: 6371, nome: 'CENTRO DA TERRA', sub: 'velocidade máxima', col: [255, 255, 255] },
];
// quadro em que cada camada é alcançada (a partir do pulo)
for (const ly of LAYER_NAMES) { ly.t = 1e9; for (let i = Math.ceil(TL.jump * FPS); i < N; i++) if (stateAt(simAt(i)).along >= ly.d - 0.01) { ly.t = i / FPS; break; } }
LAYER_NAMES[0].t = TL.jump + 0.8;
let PHASE = 0, PHASE_I = -1;
function sceneShaft(ctx, t, lt, i) {
  const st = stateAt(simAt(i));
  const vis = clamp(Math.log10(1 + st.v / 120) / 2.5);
  if (PHASE_I !== i) { for (let k = PHASE_I + 1; k <= i; k++) { const sk = stateAt(simAt(k)); PHASE += (0.5 + 9 * clamp(Math.log10(1 + sk.v / 120) / 2.5)) / FPS; } PHASE_I = i; }
  const cx = 540 + Math.sin(lt * 0.7) * 30, cy = 960 + Math.cos(lt * 0.5) * 22;
  const scaleKm = 6 + 230 * vis;
  ctx.fillStyle = '#000'; ctx.fillRect(0, 0, W, H);
  const K = 44, fr = PHASE % 1, base = Math.floor(PHASE);
  const exitNear = sstep(DIAM - 400, DIAM, st.along);
  for (let k = 0; k < K; k++) {
    const z = 0.1 + (k + 1 - fr) * 0.16, r = 520 / z;
    if (r > 2600) continue;
    const ahead = clamp(st.along + z * scaleKm, 0, DIAM);
    const m = material(ahead);
    const band = ((base + k) % 2) ? 0.86 : 1;
    const fog = Math.exp(-z * 0.32);
    const glowLift = m.glow * 0.35 * (1 - fog);
    const lum = m.glow >= 1 ? 0.72 + 0.28 * fog : fog + glowLift * 0.9;
    let col = m.c.map(v => v * band * lum + 8);
    const opening = ahead >= DIAM - 1;
    if (opening) col = mixc([20, 20, 24], [225, 238, 255], Math.max(exitNear, 0.6));
    ctx.fillStyle = rgba(col); ctx.beginPath(); ctx.arc(cx, cy, r, 0, 6.283); ctx.fill();
    // textura: pedras / bolhas de lava presas ao anel (andam junto com ele)
    const rIn = 520 / (z + 0.16), rm = (r + rIn) / 2, bw = r - rIn;
    if (bw > 3 && !opening) {
      const rg2 = rng((base + k) * 7919 + 13);
      const molten = m.glow >= 1;
      for (let q = 0; q < 7; q++) {
        const ang = rg2() * 6.283 + (molten ? Math.sin(lt * 0.8 + q) * 0.05 : 0), sz = bw * (0.18 + rg2() * 0.32);
        const tone = molten ? mixc(m.c, [255, 250, 220], 0.5 + 0.3 * Math.sin(lt * 3 + q)) : m.c.map(v => v * (0.55 + rg2() * 0.25));
        ctx.fillStyle = rgba(tone.map(v => v * (molten ? 1 : band * fog + 0.05)), molten ? 0.55 : 0.8);
        ctx.beginPath(); ctx.ellipse(cx + Math.cos(ang) * (rm + (rg2() - 0.5) * bw * 0.5), cy + Math.sin(ang) * (rm + (rg2() - 0.5) * bw * 0.5), sz * 1.6, sz, ang + 1.57, 0, 6.283); ctx.fill();
      }
    }
  }
  // fundo (fim do túnel)
  ctx.fillStyle = rgba(mixc([0, 0, 0], [235, 245, 255], exitNear)); ctx.beginPath(); ctx.arc(cx, cy, 520 / (0.1 + K * 0.16), 0, 6.283); ctx.fill();
  if (exitNear > 0) glowAt(ctx, cx, cy, 200 + 900 * exitNear, [230, 245, 255], 0.9 * exitNear);
  // brilho de calor
  const here = material(st.along);
  if (here.glow > 0) glowAt(ctx, cx, cy, 900, here.c, 0.18 * here.glow);
  if (here.glow > 1.2) { glowAt(ctx, cx, cy, 700, [255, 255, 240], 0.35); embers(ctx, lt, 0.7, 50, 77, [255, 255, 230]); }
  // riscos de velocidade
  ctx.save(); ctx.globalCompositeOperation = 'lighter';
  for (const s of STREAKS) {
    const q = (s.ph + lt * s.sp * (0.3 + 2.2 * vis)) % 1, r0 = 140 + q * q * 1100, len = (40 + 380 * vis) * q;
    ctx.globalAlpha = (0.08 + 0.4 * vis) * q; ctx.strokeStyle = '#fff'; ctx.lineWidth = s.w;
    ctx.beginPath(); ctx.moveTo(cx + Math.cos(s.a) * r0, cy + Math.sin(s.a) * r0); ctx.lineTo(cx + Math.cos(s.a) * (r0 + len), cy + Math.sin(s.a) * (r0 + len)); ctx.stroke();
  }
  ctx.restore();
  if (here.glow > 0.9) embers(ctx, lt, 0.5, 40, 61, [255, 230, 160]);
  // astronauta flutuando (sem peso)
  const stopA = sstep(DIAM - 60, DIAM, st.along);
  const tint = here.glow > 0 ? [...here.c, 0.12 + 0.2 * here.glow] : null;
  sprite(ctx, 'astronaut', 540 + Math.sin(lt * 1.3) * 16, 1050 + Math.sin(lt * 0.9) * 22, 330, { anchor: 'center', rot: lerp(lt * 0.55, 0, stopA), tint });
}

// mini-mapa (corte com a posição) — pode crescer para explicar o campo magnético
function miniMap(ctx, t, i, a = 1) {
  if (a <= 0) return;
  const st = stateAt(simAt(i));
  const mag = win(t, Wt('nucleo', 13) - 0.2, L.nucleo.end + 0.5, 0.45, 0.45);
  const cx = lerp(905, 540, mag), cy = lerp(590, 900, mag), r = lerp(100, 250, easeInOutCubic(mag));
  ctx.save(); ctx.globalAlpha *= a;
  if (mag > 0) { ctx.fillStyle = `rgba(3,5,12,${0.6 * mag})`; ctx.fillRect(0, 430, W, 1100); }
  ctx.fillStyle = 'rgba(6,10,22,0.7)'; ctx.beginPath(); ctx.arc(cx, cy, r + 14, 0, 6.283); ctx.fill();
  // linhas do campo magnético (dipolo)
  if (mag > 0) {
    ctx.save(); ctx.globalAlpha *= mag; ctx.strokeStyle = C.cyan; ctx.lineWidth = 3; ctx.shadowColor = 'rgba(79,209,255,0.8)'; ctx.shadowBlur = 12;
    ctx.setLineDash([14, 10]); ctx.lineDashOffset = -t * 60;
    for (const Lk of [1.5, 2.0, 2.7]) for (const sgn of [-1, 1]) {
      ctx.beginPath();
      for (let k = 0; k <= 60; k++) { const th = 0.2 + (Math.PI - 0.4) * k / 60, rr2 = Lk * Math.pow(Math.sin(th), 2); const x = cx + sgn * rr2 * Math.sin(th) * r, y = cy - rr2 * Math.cos(th) * r; k ? ctx.lineTo(x, y) : ctx.moveTo(x, y); }
      ctx.stroke();
    }
    ctx.restore();
    sprite(ctx, 'magnet', cx + r * 1.05, cy - r * 1.05, 150 * popIn(t, Wt('nucleo', 16) - 0.1), { anchor: 'center', rot: -0.3 });
    text(ctx, 'CAMPO MAGNÉTICO', cx, cy + r + 90, { font: `900 50px ${FONT}`, color: C.cyan, align: 'center', alpha: mag, stroke: 10 });
  }
  ctx.drawImage(CUT, cx - r, cy - r, 2 * r, 2 * r);
  drawTunnel(ctx, cx, cy, r, 1, 1, 4 + 3 * mag);
  const y = cy - r + 2 * r * (st.along / DIAM);
  glowAt(ctx, cx, y, 30, [255, 255, 255], 0.9);
  ctx.fillStyle = '#fff'; ctx.beginPath(); ctx.arc(cx, y, 8 + 4 * mag, 0, 6.283); ctx.fill();
  flagBR(ctx, cx - 22, cy - r - 46, 44);
  text(ctx, 'VOCÊ', cx + 20, y + 10, { font: `900 ${24 + 10 * mag}px ${FONT}`, color: '#fff', stroke: 6, alpha: 1 - mag * 0.3 });
  ctx.restore();
}
function layerLabel(ctx, t) {
  let cur = null;
  for (const ly of LAYER_NAMES) if (t >= ly.t && t < ly.t + 2.6) cur = ly;
  if (!cur) return;
  const a = win(t, cur.t, cur.t + 2.6, 0.2, 0.35), p = easeOutBack((t - cur.t) / 0.4);
  ctx.save(); ctx.globalAlpha = a; ctx.translate(80 - (1 - p) * 60, 0);
  ctx.fillStyle = rgba(cur.col); rr(ctx, 0, 470, 12, 118, 6); ctx.fill();
  text(ctx, cur.nome, 32, 540, { font: `900 ${cur.nome.length > 12 ? 58 : 70}px ${FONT}`, color: '#fff', stroke: 10 });
  text(ctx, cur.sub, 34, 584, { font: `700 34px ${FONT}`, color: rgba(cur.col), stroke: 8 });
  ctx.restore();
}
function shaftOverlays(ctx, t, i) {
  // "flutua, sem peso"
  const fa = win(t, Wt('pulo', 13) - 0.1, L.pulo.end + 0.4, 0.25, 0.3);
  if (fa > 0) {
    const p = easeOutBack((t - Wt('pulo', 13) + 0.1) / 0.4);
    ctx.save(); ctx.globalAlpha = fa; ctx.translate(540, 1330); ctx.scale(p, p);
    ctx.fillStyle = 'rgba(6,10,22,0.82)'; rr(ctx, -250, -50, 500, 100, 50); ctx.fill();
    text(ctx, 'GRAVIDADE ZERO', 30, 16, { font: `900 44px ${FONT}`, color: '#fff', align: 'center' });
    sprite(ctx, 'feather', -200, 0, 80, { anchor: 'center', rot: Math.sin(t * 2) * 0.3 });
    ctx.restore();
  }
  // comparação com o Sol
  const s0 = Wt('centro', 8), s1 = Wt('centro', 15) + 0.5;
  const sa = win(t, s0 - 0.1, s1, 0.25, 0.3);
  if (sa > 0) {
    const p = easeOutBack((t - s0 + 0.1) / 0.4);
    ctx.save(); ctx.globalAlpha = sa; ctx.translate(540, 1300); ctx.scale(0.85 + 0.15 * p, 0.85 + 0.15 * p);
    ctx.fillStyle = 'rgba(6,10,22,0.88)'; rr(ctx, -440, -130, 880, 260, 36); ctx.fill();
    ctx.strokeStyle = 'rgba(255,170,60,0.7)'; ctx.lineWidth = 3; rr(ctx, -440, -130, 880, 260, 36); ctx.stroke();
    const sunA = sstep(Wt('centro', 13), Wt('centro', 14), t);
    sprite(ctx, 'thermometer', -220, -62, 100, { anchor: 'center' });
    text(ctx, 'CENTRO DA TERRA', -220, 22, { font: `800 26px ${FONT}`, color: C.label, align: 'center', spacing: 2 });
    text(ctx, '5.400 °C', -220, 90, { font: `900 54px ${MONO}`, color: '#ffb35c', align: 'center' });
    text(ctx, '≈', 0, 70, { font: `900 72px ${FONT}`, color: '#fff', align: 'center', alpha: sunA });
    sprite(ctx, 'sun', 220, -62, 110 * popIn(t, Wt('centro', 13)), { anchor: 'center', rot: t * 0.3 });
    text(ctx, 'SUPERFÍCIE DO SOL', 220, 22, { font: `800 26px ${FONT}`, color: C.label, align: 'center', spacing: 2, alpha: sunA });
    text(ctx, '5.500 °C', 220, 90, { font: `900 54px ${MONO}`, color: C.yellow, align: 'center', alpha: sunA });
    ctx.restore();
  }
}

// ---- onde você sai (globo girando até o antípoda)
function sceneOnde(ctx, t, lt, i) {
  space(ctx, lt);
  const r0 = Wt('onde', 7), r1 = Wt('onde', 13) + 0.2;
  const q = easeInOutCubic((t - r0) / (r1 - r0));
  const th = Math.PI / 2 + q * Math.PI / 2;
  const B = basisAt(th, sstep(0.15, 0.85, q));
  const cut = 1 - sstep(0.0, 0.3, q);
  const hl = [cut, sstep(Wt('onde', 16) - 0.2, Wt('onde', 16) + 0.2, t), sstep(Wt('onde', 19) - 0.2, Wt('onde', 19) + 0.2, t)];
  drawEarth(ctx, GX, GY, GR, B, { cloudShift: lt * 0.04, hl, cut });
  drawTunnel(ctx, GX, GY, GR, 1, cut);
  const pb = project(BR, B, GX, GY, GR);
  pin(ctx, pb.x, pb.y, C.yellow, 'BRASIL', win(t, Wt('onde', 4) - 0.2, r0 + 0.5, 0.25, 0.3) * (pb.z > -0.1 ? 1 : 0), true);
  if (cut > 0.05) { glowAt(ctx, GX, GY + GR, 50, [255, 255, 255], 0.7 * cut); sprite(ctx, 'astronaut', GX, GY + GR, 80, { anchor: 'center', alpha: cut }); }
  // saída no Pacífico
  const pa = project(ANTI, B, GX, GY, GR);
  const sa = sstep(r1 - 0.3, r1 + 0.1, t);
  if (sa > 0 && pa.z > 0) {
    for (let k = 0; k < 3; k++) {
      const ph = ((t - r1) * 0.8 + k / 3) % 1;
      ctx.strokeStyle = `rgba(200,240,255,${sa * (1 - ph) * 0.9})`; ctx.lineWidth = 4; ctx.beginPath(); ctx.ellipse(pa.x, pa.y, 20 + ph * 90, (20 + ph * 90) * 0.6, 0, 0, 6.283); ctx.stroke();
    }
    sprite(ctx, 'water-wave', pa.x + 4, pa.y + 20, 120 * popIn(t, r1 - 0.2), {});
    sprite(ctx, 'astronaut', pa.x, pa.y - 6 + Math.sin(t * 3) * 5, 100 * popIn(t, r1 + 0.05), {});
    pin(ctx, pa.x, pa.y + 30, C.red, 'VOCÊ SAI AQUI', sa, false, false);
  }
  const lab = (p, s, a, dx, dy) => {
    const q2 = project(p, B, GX, GY, GR); if (q2.z <= 0 || a <= 0) return;
    ctx.save(); ctx.globalAlpha = a; ctx.strokeStyle = '#fff'; ctx.lineWidth = 3; ctx.beginPath(); ctx.moveTo(q2.x, q2.y); ctx.lineTo(q2.x + dx * 0.8, q2.y + dy * 0.8); ctx.stroke();
    ctx.fillStyle = '#fff'; ctx.beginPath(); ctx.arc(q2.x, q2.y, 6, 0, 6.283); ctx.fill(); ctx.restore();
    text(ctx, s, q2.x + dx, q2.y + dy, { font: `900 46px ${FONT}`, color: '#fff', align: dx < 0 ? 'right' : 'left', alpha: a, stroke: 10 });
  };
  lab(ll(36.2, 138.3), 'JAPÃO', sstep(Wt('onde', 16) - 0.15, Wt('onde', 16) + 0.2, t), 60, -40);
  lab(ll(12.9, 121.8), 'FILIPINAS', sstep(Wt('onde', 19) - 0.15, Wt('onde', 19) + 0.2, t), -60, 10);
  text(ctx, 'OCEANO PACÍFICO', GX + 40, GY + 230, { font: `900 44px ${FONT}`, color: '#cfeeff', align: 'center', alpha: sstep(Wt('onde', 12), Wt('onde', 13) + 0.2, t) * (pa.z > 0 ? 1 : 0), stroke: 10, strokeColor: 'rgba(5,30,60,0.8)' });
}

// ---- indo e voltando para sempre
function sceneVolta(ctx, t, lt, i) {
  space(ctx, lt);
  const R = 310, cx = 540, cy = 1000;
  glowAt(ctx, cx, cy, R * 1.3, [110, 180, 255], 0.25);
  ctx.drawImage(CUT, cx - R, cy - R, 2 * R, 2 * R);
  drawTunnel(ctx, cx, cy, R, 1, 1, 8);
  flagBR(ctx, cx - 40, cy - R - 110, 80);
  text(ctx, 'BRASIL', cx + 60, cy - R - 55, { font: `900 40px ${FONT}`, color: C.yellow, stroke: 8 });
  text(ctx, 'PACÍFICO', cx, cy + R + 62, { font: `900 40px ${FONT}`, color: '#cfeeff', align: 'center', stroke: 8 });
  // rastro + astronauta
  for (let k = 12; k >= 1; k--) {
    const sk = stateAt(simAt(i - k * 2)), y = cy - R + 2 * R * (sk.along / DIAM);
    ctx.globalAlpha = (1 - k / 13) * 0.6; ctx.fillStyle = '#bfe9ff'; ctx.beginPath(); ctx.arc(cx, y, 10 - k * 0.5, 0, 6.283); ctx.fill();
  }
  ctx.globalAlpha = 1;
  const st = stateAt(simAt(i)), y = cy - R + 2 * R * (st.along / DIAM);
  glowAt(ctx, cx, y, 60, [255, 255, 255], 0.6);
  sprite(ctx, 'astronaut', cx, y, 110, { anchor: 'center', rot: lt * 1.5 });
  const ia = sstep(Wt('volta', 9) - 0.1, Wt('volta', 10) + 0.2, t);
  if (ia > 0) {
    ctx.save(); ctx.globalAlpha = ia; ctx.fillStyle = 'rgba(6,10,22,0.85)'; rr(ctx, 170, 456, 740, 96, 48); ctx.fill();
    text(ctx, 'IDA E VOLTA A CADA 1h17', 540, 520, { font: `900 46px ${FONT}`, color: '#fff', align: 'center' }); ctx.restore();
  }
  const inf = popIn(t, Wt('volta', 14) - 0.05, 0.5);
  if (inf > 0) sprite(ctx, 'infinity', 860, 1240, 220 * inf, { anchor: 'center', glow: 'rgba(160,140,255,0.8)' });
}

const SCENE_FN = { hook: sceneHook, jump: sceneJump, shaft: sceneShaft, onde: sceneOnde, volta: sceneVolta, cta: sceneCTA };
const SCENES = [
  { name: 'hook', t0: -1, local0: 0 },
  { name: 'jump', t0: L.pulo.start - 0.35 },
  { name: 'shaft', t0: TL.jump + 0.75 },
  { name: 'onde', t0: L.onde.start - 0.35 },
  { name: 'volta', t0: L.volta.start - 0.35 },
  { name: 'cta', t0: L.cta.start - 0.35 },
  { name: 'hook', t0: TL.total - 0.5, local0: TL.total, fade: true },
];
const TR = 0.42;

// ---------------------------------------------------------------- HUD
function fmtTime(s) {
  s = Math.max(0, s); const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), sec = Math.floor(s % 60);
  return h ? `${h}:${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}` : `${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`;
}
function drawHUD(ctx, t, i) {
  const s = simAt(i), st = stateAt(s), x = 60, y = 186, w = 960, h = 236;
  ctx.save();
  ctx.fillStyle = 'rgba(6,10,22,0.7)'; rr(ctx, x, y, w, h, 34); ctx.fill();
  ctx.strokeStyle = 'rgba(255,255,255,0.09)'; ctx.lineWidth = 2; rr(ctx, x, y, w, h, 34); ctx.stroke();
  const peak = win(t, Wt('centro', 20) - 0.1, Wt('centro', 28, 't1') + 0.4, 0.15, 0.4);
  const tcol = mixc(mixc([255, 255, 255], [255, 170, 80], clamp(st.temp / 3000)), [255, 90, 70], clamp((st.temp - 3000) / 2400));
  const cells = [
    ['TEMPO', fmtTime(s), 'de queda', [255, 255, 255]],
    ['PROFUNDIDADE', nf(Math.round(st.depth), 0), 'km', hex(C.cyan)],
    ['VELOCIDADE', nf(Math.round(st.v), 0), 'km/h', hex(C.yellow)],
    ['TEMPERATURA', nf(Math.round(st.temp), 0), '°C', tcol],
  ];
  cells.forEach(([lab, val, unit, col], k) => {
    const cx = x + 24 + k * 233 + 104;
    if (k) { ctx.fillStyle = 'rgba(255,255,255,0.08)'; ctx.fillRect(x + 24 + k * 233 - 8, y + 36, 2, h - 72); }
    text(ctx, lab, cx, y + 62, { font: `700 21px ${FONT}`, color: C.label, align: 'center', spacing: 2 });
    let fs = 54; ctx.font = `800 ${fs}px ${MONO}`; while (ctx.measureText(val).width > 214 && fs > 30) { fs -= 2; ctx.font = `800 ${fs}px ${MONO}`; }
    const sc = k === 2 ? 1 + 0.12 * peak * (0.6 + 0.4 * Math.sin(t * 14)) : 1;
    ctx.save(); ctx.translate(cx, y + 142); ctx.scale(sc, sc);
    if (k === 2 && peak > 0) { ctx.shadowColor = 'rgba(255,210,63,0.9)'; ctx.shadowBlur = 30 * peak; }
    text(ctx, val, 0, 0, { font: `800 ${fs}px ${MONO}`, color: rgba(col), align: 'center' });
    ctx.restore();
    text(ctx, unit, cx, y + 190, { font: `700 26px ${FONT}`, color: 'rgba(220,230,255,0.75)', align: 'center' });
  });
  ctx.restore();
}
function lapseBadge(ctx, t, i, a = 1) {
  const f = lapse(i);
  if (f < 3 || a <= 0) return;
  const nice = f < 10 ? Math.round(f) : f < 100 ? Math.round(f / 5) * 5 : Math.round(f / 50) * 50;
  const s = `▶▶ ×${nf(nice, 0)}`;
  ctx.save(); ctx.globalAlpha = a * sstep(3, 6, f); ctx.font = `900 34px ${FONT}`; const tw = ctx.measureText(s).width;
  ctx.fillStyle = 'rgba(6,10,22,0.75)'; rr(ctx, 540 - tw / 2 - 26, 1400, tw + 52, 64, 32); ctx.fill();
  text(ctx, s, 540, 1444, { font: `900 34px ${FONT}`, color: '#fff', align: 'center' });
  ctx.restore();
}

// ---------------------------------------------------------------- composição
const canvas = createCanvas(W, H), ctx = canvas.getContext('2d');
const bufA = createCanvas(W, H), ctxA = bufA.getContext('2d');
const bufB = createCanvas(W, H), ctxB = bufB.getContext('2d');
const scratch = createCanvas(W, H), sctx = scratch.getContext('2d');
function renderScene(target, idx, t, i) {
  const sc = SCENES[idx], lt = t - (sc.local0 !== undefined ? sc.local0 : sc.t0);
  target.save(); target.setTransform(1, 0, 0, 1, 0, 0);
  if (sc.name === 'jump') { const z = 1 + Math.min(0.06, 0.012 * Math.max(0, lt)); target.translate(W / 2, H * 0.62); target.scale(z, z); target.translate(-W / 2, -H * 0.62); }
  SCENE_FN[sc.name](target, t, lt, i); target.restore();
}
function zoomBlurDraw(src, s, a, ox = W / 2, oy = H / 2) {
  for (let k = 0; k < 4; k++) {
    const sk = s * (1 + k * 0.045); ctx.globalAlpha = a * (k === 0 ? 1 : 0.35);
    ctx.drawImage(src, ox - ox * sk, oy - oy * sk, W * sk, H * sk);
  }
  ctx.globalAlpha = 1;
}
function frame(i, opts = {}) {
  const t = i / FPS;
  let cur = 0; for (let k = 0; k < SCENES.length; k++) if (t >= SCENES[k].t0) cur = k;
  ctx.save();
  ctx.fillStyle = '#000'; ctx.fillRect(-40, -40, W + 80, H + 80);
  const sc = SCENES[cur], into = t - sc.t0;
  const focus = name => name === 'jump' ? [560, 1360] : [W / 2, H / 2];
  if (cur > 0 && into < TR / 2 && !sc.fade) {
    const p = clamp((into + TR / 2) / TR), [fx, fy] = focus(SCENES[cur - 1].name);
    renderScene(ctxA, cur - 1, t, i); renderScene(ctxB, cur, t, i);
    zoomBlurDraw(bufA, 1 + (SCENES[cur - 1].name === 'jump' ? 2.2 : 0.55) * easeInCubic(p), 1 - sstep(0.35, 0.75, p), fx, fy);
    zoomBlurDraw(bufB, lerp(0.82, 1, easeOutCubic(p)), sstep(0.3, 0.8, p));
  } else if (cur + 1 < SCENES.length && SCENES[cur + 1].t0 - t < TR / 2 && !SCENES[cur + 1].fade) {
    const p = clamp((t - (SCENES[cur + 1].t0 - TR / 2)) / TR), [fx, fy] = focus(sc.name);
    renderScene(ctxA, cur, t, i); zoomBlurDraw(bufA, 1 + (sc.name === 'jump' ? 2.2 : 0.55) * easeInCubic(p), 1 - sstep(0.35, 0.75, p), fx, fy);
  } else if (sc.fade) {
    renderScene(ctxA, cur - 1, t, i); renderScene(ctxB, cur, t, i);
    ctx.drawImage(bufA, 0, 0); ctx.globalAlpha = sstep(0, 0.35, into); ctx.drawImage(bufB, 0, 0); ctx.globalAlpha = 1;
  } else { renderScene(ctxA, cur, t, i); ctx.drawImage(bufA, 0, 0); }
  const shaftA = SCENES[cur].name === 'shaft' ? 1 - sstep(SCENES[cur + 1].t0 - TR / 2, SCENES[cur + 1].t0, t) : 0;
  if (shaftA > 0) { miniMap(ctx, t, i, shaftA * sstep(SCENES[cur].t0, SCENES[cur].t0 + 0.4, t)); layerLabel(ctx, t); shaftOverlays(ctx, t, i); }
  lapseBadge(ctx, t, i, (shaftA) * (1 - win(t, Wt('centro', 8) - 0.2, Wt('centro', 15) + 0.6, 0.2, 0.2)));
  // rebobinar (assinatura da série)
  const ra = win(t, REW[0] - 0.05, REW[1] + 0.05, 0.08, 0.12);
  if (ra > 0) {
    sctx.clearRect(0, 0, W, H); sctx.drawImage(canvas, 0, 0);
    const r = rng(Math.floor(t * 60));
    for (let k = 0; k < 7; k++) { const yy = r() * H, hh = 20 + r() * 120, dx = (r() - 0.5) * 80 * ra; ctx.drawImage(scratch, 0, yy, W, hh, dx, yy, W, hh); }
    ctx.save(); ctx.globalAlpha = 0.18 * ra; ctx.fillStyle = '#000'; for (let yy = (t * 400) % 6; yy < H; yy += 6) ctx.fillRect(0, yy, W, 2);
    ctx.globalAlpha = 0.12 * ra; ctx.fillStyle = '#4fd1ff'; ctx.fillRect(0, 0, W, H); ctx.restore();
    text(ctx, '◀◀', 90, 560, { font: `900 72px ${FONT}`, color: '#fff', alpha: ra * (0.6 + 0.4 * Math.sin(t * 20)), stroke: 8 });
  }
  ctx.drawImage(vignette, 0, 0);
  drawHUD(ctx, t, i);
  if (!opts.noCaptions) drawCaptions(ctx, t);
  let fl = 0; const ah = Wt('hook', 19, 't1') + 0.1;
  if (t >= ah) fl = Math.max(fl, 0.5 * Math.exp(-(t - ah) / 0.25));
  const cT = LAYER_NAMES[4].t; if (t >= cT) fl = Math.max(fl, 0.45 * Math.exp(-(t - cT) / 0.3));
  if (fl > 0.01) { ctx.fillStyle = `rgba(255,250,235,${fl})`; ctx.fillRect(-40, -40, W + 80, H + 80); }
  ctx.restore();
}

// ---------------------------------------------------------------- main
(async () => {
  await loadSprites();
  const t0 = Date.now(); buildMap(); buildCut();
  console.log(`mapa e corte prontos (${((Date.now() - t0) / 1000).toFixed(1)}s)`);
  const argv = process.argv.slice(2), pi = argv.indexOf('--preview');
  if (argv.includes('--capa')) {
    const i = Math.round((Wt('hook', 15)) * FPS);
    frame(i, { noCaptions: true });
    const g = ctx.createLinearGradient(0, 1250, 0, 1800); g.addColorStop(0, 'rgba(3,5,12,0)'); g.addColorStop(0.35, 'rgba(3,5,12,0.85)'); g.addColorStop(1, 'rgba(3,5,12,0.95)');
    ctx.fillStyle = g; ctx.fillRect(0, 1250, W, 670);
    text(ctx, 'PULEI NUM BURACO', W / 2, 1450, { font: `900 84px ${FONT}`, color: '#fff', align: 'center', stroke: 14 });
    text(ctx, 'QUE ATRAVESSA A TERRA', W / 2, 1550, { font: `900 74px ${FONT}`, color: C.yellow, align: 'center', stroke: 14 });
    const out = path.join(ROOT, 'output/capa.png'); fs.mkdirSync(path.dirname(out), { recursive: true });
    fs.writeFileSync(out, canvas.toBuffer('image/png')); console.log(out);
  } else if (pi >= 0) {
    const dir = path.join(ROOT, 'build/preview'); fs.mkdirSync(dir, { recursive: true });
    for (const s of argv[pi + 1].split(',')) {
      const i = clamp(Math.round(parseFloat(s) * FPS), 0, N - 1); frame(i);
      const out = path.join(dir, `t${(i / FPS).toFixed(2).padStart(6, '0')}.png`);
      fs.writeFileSync(out, canvas.toBuffer('image/png')); console.log(out);
    }
  } else {
    const out = path.join(ROOT, 'build/video.mp4');
    const ff = spawn('ffmpeg', ['-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgba', '-s', `${W}x${H}`, '-r', String(FPS), '-i', '-',
      '-c:v', 'libx264', '-preset', 'slow', '-crf', '16', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', out], { stdio: ['pipe', 'inherit', 'inherit'] });
    let i = 0; const tr = Date.now();
    const write = () => {
      while (i < N) {
        frame(i); const ok = ff.stdin.write(Buffer.from(canvas.data())); i++;
        if (i % 150 === 0) console.log(`  quadro ${i}/${N} (${((Date.now() - tr) / 1000).toFixed(0)}s)`);
        if (!ok) { ff.stdin.once('drain', write); return; }
      }
      ff.stdin.end();
    };
    ff.on('close', code => { console.log('ffmpeg terminou:', code, out); process.exit(code); });
    write();
  }
})();
