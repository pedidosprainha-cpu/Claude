// Vídeo 04 — "A banda que vendeu 2 milhões de discos e durou 8 meses" (Mamonas Assassinas)
// TODAS as ilustrações são desenhadas neste arquivo (vetor/código), sem arte de terceiros.
// O mapa do Brasil é desenhado a partir de dados geográficos de domínio público (Natural Earth).
//   node src/render.js                   -> build/video.mp4
//   node src/render.js --preview 3,20    -> build/preview/*.png
//   node src/render.js --capa            -> output/capa.png
const { createCanvas } = require('@napi-rs/canvas');
const WORLD = require('world-atlas/countries-110m.json');
const { feature } = require('topojson-client');
const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');

const ROOT = path.resolve(__dirname, '..');
const TL = JSON.parse(fs.readFileSync(path.join(ROOT, 'build/timeline.json'), 'utf8'));
const W = 1080, H = 1920, FPS = TL.fps, N = TL.frames;
const FONT = '"Inter Display"', MONO = '"JetBrains Mono"';
const C = { yellow: '#FFD23F', cyan: '#4FD1FF', red: '#FF3B4E', orange: '#FF8A3D', ink: '#070A14', label: '#A99BD8' };
const L = TL.lines;
const Wt = (line, i, k = 't0') => L[line].words[i][k];
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


// ================================================================ vídeo 04: ilustrações próprias (nenhuma arte de terceiros)
const popIn = (t, t0, d = 0.38) => t < t0 ? 0 : easeOutBack((t - t0) / d);
const P = { teal: '#19c3b1', pink: '#ff3e9d', purple: '#7b3fe4', yellow: '#FFD23F', orange: '#ff8a3d', blue: '#2f7cff', ink: '#0b0b16', cream: '#fff4e0', green: '#3ccf6e' };
const R0 = rng(404);
const STARS = Array.from({ length: 300 }, () => ({ x: R0() * W, y: R0() * H * 0.75, r: 0.4 + R0() * R0() * 2.2, a: 0.25 + R0() * 0.75, tw: R0() * 6.28 }));
const BEAT = 60 / 120;
const beatPulse = t => Math.pow(Math.max(0, Math.cos((t % BEAT) / BEAT * Math.PI)), 6);

// ---------------------------------------------------------------- fundo "Memphis" anos 90
const MEMPHIS = Array.from({ length: 34 }, (_, k) => { const r = rng(900 + k); return { kind: Math.floor(r() * 5), x: r() * W, y: 440 + r() * 1100, s: 40 + r() * 70, rot: r() * 6.28, sp: (r() - 0.5) * 0.4, col: [P.pink, P.teal, P.yellow, P.purple, P.orange, '#ffffff'][Math.floor(r() * 6)], ph: r() * 6.28 }; });
function memphis(ctx, lt, a = 1) {
  ctx.save();
  for (const m of MEMPHIS) {
    ctx.globalAlpha = a * 0.85;
    ctx.save(); ctx.translate(m.x + Math.sin(lt * 0.4 + m.ph) * 14, m.y + Math.cos(lt * 0.3 + m.ph) * 14); ctx.rotate(m.rot + lt * m.sp);
    ctx.strokeStyle = m.col; ctx.fillStyle = m.col; ctx.lineWidth = 9; ctx.lineCap = 'round'; ctx.lineJoin = 'round';
    if (m.kind === 0) { ctx.beginPath(); for (let k = 0; k <= 20; k++) { const x = -m.s + k * m.s / 10, y = Math.sin(k * 0.9) * m.s * 0.18; k ? ctx.lineTo(x, y) : ctx.moveTo(x, y); } ctx.stroke(); }
    else if (m.kind === 1) { ctx.beginPath(); ctx.moveTo(0, -m.s * 0.5); ctx.lineTo(m.s * 0.45, m.s * 0.3); ctx.lineTo(-m.s * 0.45, m.s * 0.3); ctx.closePath(); ctx.stroke(); }
    else if (m.kind === 2) { for (let i = 0; i < 3; i++) for (let j = 0; j < 3; j++) { ctx.beginPath(); ctx.arc(i * m.s * 0.28, j * m.s * 0.28, 5, 0, 6.283); ctx.fill(); } }
    else if (m.kind === 3) { ctx.beginPath(); for (let k = 0; k < 6; k++) ctx.lineTo(-m.s * 0.6 + k * m.s * 0.24, k % 2 ? -m.s * 0.15 : m.s * 0.15); ctx.stroke(); }
    else { ctx.beginPath(); ctx.arc(0, 0, m.s * 0.28, 0, 6.283); ctx.stroke(); }
    ctx.restore();
  }
  ctx.restore();
}
function sunburst(ctx, cx, cy, lt, colA, colB, n = 18, a = 1) {
  ctx.save(); ctx.globalAlpha = a; ctx.translate(cx, cy); ctx.rotate(lt * 0.15);
  for (let k = 0; k < n; k++) { ctx.fillStyle = k % 2 ? colA : colB; ctx.beginPath(); ctx.moveTo(0, 0); ctx.arc(0, 0, 1800, k / n * 6.283, (k + 1) / n * 6.283); ctx.fill(); }
  ctx.restore();
}

// ---------------------------------------------------------------- CD iridescente (com furo real)
const cdBuf = createCanvas(900, 900), cdCtx = cdBuf.getContext('2d');
function drawCD(ctx, x, y, R, rot, o = {}) {
  const S = Math.ceil(R * 2 + 8), c = cdCtx, h = S / 2;
  c.clearRect(0, 0, Math.min(900, S + 6), Math.min(900, S + 6)); c.save(); c.translate(h, h);
  const base = c.createRadialGradient(0, 0, R * 0.2, 0, 0, R);
  base.addColorStop(0, '#f4f6fb'); base.addColorStop(1, '#c9ced9');
  c.fillStyle = base; c.beginPath(); c.arc(0, 0, R, 0, 6.283); c.fill();
  // brilho de arco-íris girando
  const ir = c.createConicGradient(rot, 0, 0);
  ['#ff6ad5', '#ffd36a', '#7affc4', '#6ad0ff', '#c79bff', '#ff6ad5', '#ffd36a', '#7affc4', '#6ad0ff', '#c79bff', '#ff6ad5'].forEach((col, k, arr) => ir.addColorStop(k / (arr.length - 1), col));
  c.globalAlpha = 0.6; c.fillStyle = ir; c.beginPath(); c.arc(0, 0, R, 0, 6.283); c.fill(); c.globalAlpha = 1;
  // trilhas
  c.strokeStyle = 'rgba(255,255,255,0.12)'; c.lineWidth = 1;
  for (let k = 0; k < 18; k++) { c.beginPath(); c.arc(0, 0, R * (0.4 + k * 0.032), 0, 6.283); c.stroke(); }
  // reflexos especulares
  const sp = c.createConicGradient(-rot * 0.7 + 0.6, 0, 0);
  sp.addColorStop(0, 'rgba(255,255,255,0)'); sp.addColorStop(0.06, 'rgba(255,255,255,0.75)'); sp.addColorStop(0.13, 'rgba(255,255,255,0)');
  sp.addColorStop(0.5, 'rgba(255,255,255,0)'); sp.addColorStop(0.56, 'rgba(255,255,255,0.55)'); sp.addColorStop(0.63, 'rgba(255,255,255,0)'); sp.addColorStop(1, 'rgba(255,255,255,0)');
  c.fillStyle = sp; c.beginPath(); c.arc(0, 0, R, 0, 6.283); c.fill();
  // rótulo impresso
  if (o.label) {
    c.save(); c.rotate(rot * 0.999);
    const lg = c.createRadialGradient(0, 0, R * 0.3, 0, 0, R * 0.66);
    lg.addColorStop(0, o.label.c0); lg.addColorStop(1, o.label.c1);
    c.fillStyle = lg; c.beginPath(); c.arc(0, 0, R * 0.66, 0, 6.283); c.arc(0, 0, R * 0.29, 0, 6.283, true); c.fill('evenodd');
    if (o.label.dots) for (let k = 0; k < 14; k++) { c.fillStyle = [P.pink, P.teal, P.yellow, P.purple][k % 4]; c.beginPath(); c.arc(Math.cos(k * 0.45) * R * 0.48, Math.sin(k * 0.45) * R * 0.48, R * 0.035, 0, 6.283); c.fill(); }
    c.font = `900 ${R * 0.13}px ${FONT}`; c.textAlign = 'center'; c.fillStyle = o.label.ink;
    c.fillText(o.label.text, 0, -R * 0.4); if (o.label.sub) { c.font = `700 ${R * 0.07}px ${FONT}`; c.fillText(o.label.sub, 0, R * 0.5); }
    c.restore();
  }
  // miolo de plástico transparente e furo
  c.fillStyle = 'rgba(235,240,250,0.55)'; c.beginPath(); c.arc(0, 0, R * 0.28, 0, 6.283); c.fill();
  c.strokeStyle = 'rgba(255,255,255,0.7)'; c.lineWidth = 2; c.beginPath(); c.arc(0, 0, R * 0.2, 0, 6.283); c.stroke();
  c.globalCompositeOperation = 'destination-out'; c.beginPath(); c.arc(0, 0, R * 0.085, 0, 6.283); c.fill(); c.globalCompositeOperation = 'source-over';
  c.strokeStyle = 'rgba(255,255,255,0.8)'; c.lineWidth = 2.5; c.beginPath(); c.arc(0, 0, R - 1.5, 0, 6.283); c.stroke();
  c.restore();
  ctx.save();
  if (o.shadow !== false) { ctx.shadowColor = 'rgba(0,0,0,0.45)'; ctx.shadowBlur = R * 0.25; ctx.shadowOffsetY = R * 0.08; }
  ctx.globalAlpha *= o.alpha ?? 1;
  ctx.drawImage(cdBuf, 0, 0, S, S, x - h, y - h, S, S);
  ctx.restore();
}

// ---------------------------------------------------------------- caixinha de CD com capas próprias
function coverUtopia(c, w, h) {
  const g = c.createLinearGradient(0, 0, 0, h); g.addColorStop(0, '#2a2d36'); g.addColorStop(1, '#0d0e12'); c.fillStyle = g; c.fillRect(0, 0, w, h);
  c.strokeStyle = 'rgba(220,220,230,0.8)'; c.lineWidth = w * 0.012;
  c.beginPath(); c.moveTo(w * 0.5, h * 0.2); c.lineTo(w * 0.78, h * 0.68); c.lineTo(w * 0.22, h * 0.68); c.closePath(); c.stroke();
  c.beginPath(); c.arc(w * 0.5, h * 0.52, w * 0.09, 0, 6.283); c.stroke();
  c.fillStyle = 'rgba(230,230,240,0.9)'; c.font = `400 ${w * 0.12}px "DejaVu Serif"`; c.textAlign = 'center'; c.letterSpacing = `${w * 0.03}px`;
  c.fillText('UTOPIA', w * 0.5, h * 0.88); c.letterSpacing = '0px';
}
function coverMamonas(c, w, h, lt = 0) {
  c.fillStyle = P.yellow; c.fillRect(0, 0, w, h);
  c.save(); c.beginPath(); c.rect(0, 0, w, h); c.clip(); sunburst(c, w * 0.5, h * 0.42, lt, 'rgba(255,62,157,0.35)', 'rgba(255,255,255,0)', 16); c.restore();
  const r = rng(77);
  for (let k = 0; k < 26; k++) { c.fillStyle = [P.pink, P.teal, P.purple, P.blue][k % 4]; c.save(); c.translate(r() * w, r() * h); c.rotate(r() * 6); c.fillRect(-w * 0.02, -w * 0.008, w * 0.04, w * 0.016); c.restore(); }
  c.textAlign = 'center'; c.lineJoin = 'round';
  [['MAMONAS', h * 0.5, P.pink], ['ASSASSINAS', h * 0.7, P.purple]].forEach(([s, y, col], k) => {
    const fs = w * (k ? 0.13 : 0.18); c.font = `900 ${fs}px ${FONT}`;
    c.save(); c.translate(w / 2, y); c.rotate(-0.06);
    c.lineWidth = fs * 0.22; c.strokeStyle = P.ink; c.strokeText(s, 0, 0); c.fillStyle = col; c.fillText(s, 0, 0); c.restore();
  });
}
function drawCase(ctx, x, y, w, rot, cover, o = {}) {
  const h = w * 0.88;
  ctx.save(); ctx.translate(x, y); ctx.rotate(rot); ctx.globalAlpha *= o.alpha ?? 1;
  ctx.shadowColor = 'rgba(0,0,0,0.45)'; ctx.shadowBlur = w * 0.08; ctx.shadowOffsetY = w * 0.04;
  ctx.fillStyle = '#202533'; rr(ctx, -w / 2, -h / 2, w, h, w * 0.025); ctx.fill(); ctx.shadowBlur = 0; ctx.shadowOffsetY = 0;
  ctx.save(); rr(ctx, -w / 2 + w * 0.09, -h / 2 + w * 0.025, w * 0.885, h - w * 0.05, w * 0.01); ctx.clip();
  ctx.translate(-w / 2 + w * 0.09, -h / 2 + w * 0.025); cover(ctx, w * 0.885, h - w * 0.05, o.lt || 0); ctx.restore();
  // dobradiça
  const hg = ctx.createLinearGradient(-w / 2, 0, -w / 2 + w * 0.09, 0); hg.addColorStop(0, '#3a4152'); hg.addColorStop(1, '#151922');
  ctx.fillStyle = hg; ctx.fillRect(-w / 2, -h / 2, w * 0.09, h);
  ctx.strokeStyle = 'rgba(255,255,255,0.15)'; ctx.lineWidth = 1; for (let k = 1; k < 12; k++) { ctx.beginPath(); ctx.moveTo(-w / 2 + 3, -h / 2 + k * h / 12); ctx.lineTo(-w / 2 + w * 0.08, -h / 2 + k * h / 12); ctx.stroke(); }
  // brilho do acrílico
  const gl = ctx.createLinearGradient(-w / 2, -h / 2, w / 2, h / 2);
  gl.addColorStop(0, 'rgba(255,255,255,0.35)'); gl.addColorStop(0.35, 'rgba(255,255,255,0.05)'); gl.addColorStop(0.5, 'rgba(255,255,255,0.18)'); gl.addColorStop(0.6, 'rgba(255,255,255,0)');
  ctx.fillStyle = gl; rr(ctx, -w / 2, -h / 2, w, h, w * 0.025); ctx.fill();
  ctx.strokeStyle = 'rgba(255,255,255,0.45)'; ctx.lineWidth = 2; rr(ctx, -w / 2, -h / 2, w, h, w * 0.025); ctx.stroke();
  ctx.restore();
}

// ---------------------------------------------------------------- TV de tubo
function drawTV(ctx, x, y, w, screen, lt) {
  const h = w * 0.78;
  ctx.save(); ctx.translate(x, y);
  ctx.strokeStyle = '#8b8f99'; ctx.lineWidth = 5; ctx.lineCap = 'round';
  ctx.beginPath(); ctx.moveTo(0, -h / 2); ctx.lineTo(-w * 0.28, -h / 2 - w * 0.36); ctx.moveTo(0, -h / 2); ctx.lineTo(w * 0.22, -h / 2 - w * 0.4); ctx.stroke();
  ctx.fillStyle = '#c9ccd4'; for (const [ax, ay] of [[-w * 0.28, -h / 2 - w * 0.36], [w * 0.22, -h / 2 - w * 0.4]]) { ctx.beginPath(); ctx.arc(ax, ay, 8, 0, 6.283); ctx.fill(); }
  ctx.shadowColor = 'rgba(0,0,0,0.5)'; ctx.shadowBlur = 30; ctx.shadowOffsetY = 14;
  const bg = ctx.createLinearGradient(0, -h / 2, 0, h / 2); bg.addColorStop(0, '#3a3d48'); bg.addColorStop(1, '#1b1d24');
  ctx.fillStyle = bg; rr(ctx, -w / 2, -h / 2, w, h, w * 0.08); ctx.fill(); ctx.shadowBlur = 0; ctx.shadowOffsetY = 0;
  ctx.fillStyle = '#121318'; rr(ctx, -w / 2 + w * 0.06, -h / 2 + w * 0.06, w * 0.68, h - w * 0.12, w * 0.07); ctx.fill();
  const sx = -w / 2 + w * 0.085, sy = -h / 2 + w * 0.085, sw = w * 0.63, sh = h - w * 0.17;
  ctx.save(); rr(ctx, sx, sy, sw, sh, w * 0.06); ctx.clip();
  ctx.translate(sx, sy); screen(ctx, sw, sh, lt);
  ctx.globalAlpha = 0.18; ctx.fillStyle = '#000'; for (let yy = (lt * 60) % 4; yy < sh; yy += 4) ctx.fillRect(0, yy, sw, 1.5);
  ctx.globalAlpha = 1;
  const gl = ctx.createRadialGradient(sw * 0.3, sh * 0.25, 10, sw * 0.5, sh * 0.5, sw * 0.8);
  gl.addColorStop(0, 'rgba(255,255,255,0.22)'); gl.addColorStop(0.5, 'rgba(255,255,255,0)'); gl.addColorStop(1, 'rgba(0,0,0,0.45)');
  ctx.fillStyle = gl; ctx.fillRect(0, 0, sw, sh);
  ctx.restore();
  // painel
  for (let k = 0; k < 2; k++) {
    const kx = w * 0.36, ky = -h / 2 + w * 0.14 + k * w * 0.16;
    ctx.fillStyle = '#0d0e12'; ctx.beginPath(); ctx.arc(kx, ky, w * 0.055, 0, 6.283); ctx.fill();
    ctx.fillStyle = '#5b5f6b'; ctx.beginPath(); ctx.arc(kx, ky, w * 0.04, 0, 6.283); ctx.fill();
    ctx.strokeStyle = '#d9dce4'; ctx.lineWidth = 3; ctx.beginPath(); ctx.moveTo(kx, ky); ctx.lineTo(kx + Math.cos(k * 2 + 0.5) * w * 0.035, ky + Math.sin(k * 2 + 0.5) * w * 0.035); ctx.stroke();
  }
  ctx.strokeStyle = 'rgba(255,255,255,0.18)'; ctx.lineWidth = 2;
  for (let k = 0; k < 6; k++) { ctx.beginPath(); ctx.moveTo(w * 0.3, h * 0.08 + k * 12); ctx.lineTo(w * 0.42, h * 0.08 + k * 12); ctx.stroke(); }
  ctx.fillStyle = '#ff3b4e'; ctx.beginPath(); ctx.arc(w * 0.36, h * 0.38, 6, 0, 6.283); ctx.fill();
  ctx.fillStyle = '#2a2c34'; ctx.fillRect(-w * 0.32, h / 2, w * 0.1, w * 0.05); ctx.fillRect(w * 0.22, h / 2, w * 0.1, w * 0.05);
  ctx.restore();
}

// ---------------------------------------------------------------- rádio portátil com toca-fitas
function drawBoombox(ctx, x, y, w, lt) {
  const h = w * 0.5, pulse = beatPulse(lt);
  ctx.save(); ctx.translate(x, y);
  ctx.strokeStyle = '#9aa0ad'; ctx.lineWidth = w * 0.025; ctx.lineCap = 'round';
  ctx.beginPath(); ctx.moveTo(-w * 0.3, -h / 2); ctx.quadraticCurveTo(-w * 0.3, -h / 2 - w * 0.12, -w * 0.2, -h / 2 - w * 0.12); ctx.lineTo(w * 0.2, -h / 2 - w * 0.12); ctx.quadraticCurveTo(w * 0.3, -h / 2 - w * 0.12, w * 0.3, -h / 2); ctx.stroke();
  ctx.lineWidth = 3; ctx.beginPath(); ctx.moveTo(w * 0.42, -h / 2); ctx.lineTo(w * 0.58, -h / 2 - w * 0.35); ctx.stroke();
  ctx.shadowColor = 'rgba(0,0,0,0.5)'; ctx.shadowBlur = 30; ctx.shadowOffsetY = 14;
  const bg = ctx.createLinearGradient(0, -h / 2, 0, h / 2); bg.addColorStop(0, '#e9ecf2'); bg.addColorStop(0.5, '#b9bfcb'); bg.addColorStop(1, '#8d94a3');
  ctx.fillStyle = bg; rr(ctx, -w / 2, -h / 2, w, h, w * 0.05); ctx.fill(); ctx.shadowBlur = 0; ctx.shadowOffsetY = 0;
  ctx.fillStyle = '#23262f'; rr(ctx, -w / 2 + w * 0.03, -h / 2 + w * 0.03, w - w * 0.06, h - w * 0.06, w * 0.035); ctx.fill();
  for (const sxp of [-w * 0.3, w * 0.3]) {
    const sr = h * 0.36 * (1 + 0.04 * pulse);
    ctx.fillStyle = '#3b3f4a'; ctx.beginPath(); ctx.arc(sxp, h * 0.04, h * 0.4, 0, 6.283); ctx.fill();
    const cg = ctx.createRadialGradient(sxp - sr * 0.3, h * 0.04 - sr * 0.3, sr * 0.1, sxp, h * 0.04, sr);
    cg.addColorStop(0, '#5a5f6c'); cg.addColorStop(1, '#0d0e12'); ctx.fillStyle = cg; ctx.beginPath(); ctx.arc(sxp, h * 0.04, sr, 0, 6.283); ctx.fill();
    ctx.strokeStyle = 'rgba(255,255,255,0.12)'; ctx.lineWidth = 2; for (let k = 1; k < 4; k++) { ctx.beginPath(); ctx.arc(sxp, h * 0.04, sr * k / 4, 0, 6.283); ctx.stroke(); }
    ctx.fillStyle = '#c9ced8'; ctx.beginPath(); ctx.arc(sxp, h * 0.04, sr * 0.18, 0, 6.283); ctx.fill();
  }
  // toca-fitas
  ctx.fillStyle = '#0e1015'; rr(ctx, -w * 0.12, -h * 0.28, w * 0.24, h * 0.36, 8); ctx.fill();
  ctx.fillStyle = '#e8e0cf'; rr(ctx, -w * 0.1, -h * 0.24, w * 0.2, h * 0.26, 6); ctx.fill();
  for (const rx of [-w * 0.045, w * 0.045]) {
    ctx.save(); ctx.translate(rx, -h * 0.11); ctx.rotate(lt * 4);
    ctx.fillStyle = '#2b2b2b'; ctx.beginPath(); ctx.arc(0, 0, w * 0.025, 0, 6.283); ctx.fill();
    ctx.strokeStyle = '#fff'; ctx.lineWidth = 2; for (let k = 0; k < 3; k++) { ctx.rotate(2.09); ctx.beginPath(); ctx.moveTo(0, 0); ctx.lineTo(w * 0.02, 0); ctx.stroke(); }
    ctx.restore();
  }
  ctx.fillStyle = P.pink; ctx.fillRect(-w * 0.1, -h * 0.24, w * 0.2, h * 0.035);
  for (let k = 0; k < 5; k++) { ctx.fillStyle = k === 1 ? P.orange : '#9aa0ad'; rr(ctx, -w * 0.11 + k * w * 0.047, h * 0.14, w * 0.035, h * 0.08, 3); ctx.fill(); }
  ctx.restore();
  // ondas sonoras
  ctx.save(); ctx.strokeStyle = P.teal; ctx.lineCap = 'round';
  for (let k = 0; k < 3; k++) {
    const ph = ((lt * 1.6 + k / 3) % 1); ctx.globalAlpha = (1 - ph) * 0.9; ctx.lineWidth = 8 * (1 - ph) + 2;
    for (const s of [-1, 1]) { ctx.beginPath(); ctx.arc(x + s * w * 0.3, y, w * 0.25 + ph * w * 0.28, s > 0 ? -0.6 : Math.PI - 0.6, s > 0 ? 0.6 : Math.PI + 0.6); ctx.stroke(); }
  }
  ctx.restore();
}

// ---------------------------------------------------------------- balões e festa
function balloon(ctx, x, y, r, col, lt, ph) {
  const bx = x + Math.sin(lt * 1.2 + ph) * 10, by = y + Math.sin(lt * 1.6 + ph) * 8;
  ctx.save();
  ctx.strokeStyle = 'rgba(255,255,255,0.7)'; ctx.lineWidth = 2; ctx.beginPath(); ctx.moveTo(bx, by + r * 1.18);
  ctx.bezierCurveTo(bx + 14, by + r * 1.6, bx - 14, by + r * 2.1, bx + 4, by + r * 2.8); ctx.stroke();
  const g = ctx.createRadialGradient(bx - r * 0.35, by - r * 0.45, r * 0.08, bx, by, r * 1.15);
  g.addColorStop(0, '#ffffff'); g.addColorStop(0.18, col); g.addColorStop(1, rgba(hex(col).map(v => v * 0.6)));
  ctx.fillStyle = g; ctx.beginPath(); ctx.ellipse(bx, by, r, r * 1.18, 0, 0, 6.283); ctx.fill();
  ctx.fillStyle = rgba(hex(col).map(v => v * 0.7)); ctx.beginPath(); ctx.moveTo(bx - 7, by + r * 1.22); ctx.lineTo(bx + 7, by + r * 1.22); ctx.lineTo(bx, by + r * 1.1); ctx.fill();
  ctx.restore();
}
function partyHat(ctx, x, y, s, col, rot) {
  ctx.save(); ctx.translate(x, y); ctx.rotate(rot);
  ctx.fillStyle = col; ctx.beginPath(); ctx.moveTo(-s * 0.4, 0); ctx.lineTo(0, -s); ctx.lineTo(s * 0.4, 0); ctx.closePath(); ctx.fill();
  ctx.save(); ctx.clip(); ctx.strokeStyle = 'rgba(255,255,255,0.75)'; ctx.lineWidth = s * 0.08; for (let k = 0; k < 5; k++) { ctx.beginPath(); ctx.moveTo(-s, -k * s * 0.25); ctx.lineTo(s, -k * s * 0.25 - s * 0.4); ctx.stroke(); } ctx.restore();
  ctx.fillStyle = P.yellow; ctx.beginPath(); ctx.arc(0, -s, s * 0.12, 0, 6.283); ctx.fill();
  ctx.restore();
}
function confetti(ctx, lt, n, seed, a = 1, y0 = 400, y1 = 1500) {
  const r = rng(seed);
  for (let k = 0; k < n; k++) {
    const x = r() * W, sp = 80 + r() * 160, ph = r() * 20, col = [P.pink, P.teal, P.yellow, P.purple, P.orange][k % 5];
    const y = y0 + ((lt * sp + ph * 120) % (y1 - y0));
    ctx.save(); ctx.globalAlpha = a; ctx.translate(x + Math.sin(lt * 2 + ph) * 30, y); ctx.rotate(lt * 3 + ph);
    ctx.fillStyle = col; ctx.fillRect(-10, -4, 20, 8 * Math.abs(Math.cos(lt * 4 + ph))); ctx.restore();
  }
}

// ---------------------------------------------------------------- palco, holofotes e silhuetas
function curtain(ctx, col0, col1, x0 = 0, x1 = W, y0 = 0, y1 = 1480) {
  const g = ctx.createLinearGradient(x0, 0, x1, 0);
  const n = 18;
  for (let k = 0; k <= n; k++) { g.addColorStop(k / n, k % 2 ? col0 : col1); }
  ctx.fillStyle = g; ctx.fillRect(x0, y0, x1 - x0, y1 - y0);
  const v = ctx.createLinearGradient(0, y0, 0, y1); v.addColorStop(0, 'rgba(0,0,0,0.55)'); v.addColorStop(0.4, 'rgba(0,0,0,0)'); v.addColorStop(1, 'rgba(0,0,0,0.5)');
  ctx.fillStyle = v; ctx.fillRect(x0, y0, x1 - x0, y1 - y0);
}
function stageFloor(ctx, y, col = '#2a1a14') {
  const g = ctx.createLinearGradient(0, y, 0, H); g.addColorStop(0, col); g.addColorStop(1, '#050505');
  ctx.fillStyle = g; ctx.fillRect(0, y, W, H - y);
  ctx.strokeStyle = 'rgba(255,255,255,0.06)'; ctx.lineWidth = 2;
  for (let k = -8; k <= 8; k++) { ctx.beginPath(); ctx.moveTo(W / 2 + k * 60, y); ctx.lineTo(W / 2 + k * 260, H); ctx.stroke(); }
  ctx.fillStyle = 'rgba(255,255,255,0.12)'; ctx.fillRect(0, y, W, 3);
}
function spotlight(ctx, x, y, tx, ty, col, a) {
  if (a <= 0.01) return;
  ctx.save(); ctx.globalCompositeOperation = 'lighter';
  const ang = Math.atan2(ty - y, tx - x), len = Math.hypot(tx - x, ty - y) * 1.15, wd = 0.2;
  const g = ctx.createLinearGradient(x, y, tx, ty);
  g.addColorStop(0, rgba(col, 0.55 * a)); g.addColorStop(1, rgba(col, 0.06 * a));
  ctx.fillStyle = g; ctx.beginPath(); ctx.moveTo(x, y);
  ctx.lineTo(x + Math.cos(ang - wd) * len, y + Math.sin(ang - wd) * len); ctx.lineTo(x + Math.cos(ang + wd) * len, y + Math.sin(ang + wd) * len); ctx.fill();
  const pg = ctx.createRadialGradient(tx, ty + 10, 5, tx, ty + 10, 200);
  pg.addColorStop(0, rgba(col, 0.5 * a)); pg.addColorStop(1, rgba(col, 0));
  ctx.fillStyle = pg; ctx.beginPath(); ctx.ellipse(tx, ty + 10, 200, 45, 0, 0, 6.283); ctx.fill();
  ctx.restore();
  ctx.save(); ctx.translate(x, y); ctx.rotate(ang - Math.PI / 2);
  ctx.fillStyle = '#1c1c22'; rr(ctx, -26, -40, 52, 60, 10); ctx.fill();
  ctx.fillStyle = rgba(mixc(col, [255, 255, 255], 0.6), 0.4 + 0.6 * a); ctx.beginPath(); ctx.ellipse(0, 22, 22, 8, 0, 0, 6.283); ctx.fill();
  ctx.restore();
}
// figura humana estilizada (silhueta com luz de recorte)
function figurePath(ctx, kind, h, lt, ph) {
  const s = h / 300, bob = Math.sin(lt * 6.28 * 2 + ph) * 4 * s;
  ctx.save(); ctx.scale(s, s); ctx.translate(0, bob / s);
  ctx.beginPath(); ctx.ellipse(0, -262, 22, 26, 0, 0, 6.283); ctx.fill();                 // cabeça
  ctx.beginPath(); ctx.ellipse(-4 + (ph % 2) * 6, -283, 26, 14, 0.2, 0, 6.283); ctx.fill();  // cabelo
  rr(ctx, -9, -240, 18, 20, 6); ctx.fill();                                                   // pescoço
  ctx.beginPath(); ctx.moveTo(-40, -222); ctx.quadraticCurveTo(0, -232, 40, -222); ctx.lineTo(30, -120); ctx.lineTo(-30, -120); ctx.closePath(); ctx.fill();
  ctx.lineCap = 'round'; ctx.lineWidth = 24; ctx.strokeStyle = ctx.fillStyle;
  if (kind !== 'drums') { ctx.beginPath(); ctx.moveTo(-14, -125); ctx.lineTo(-24, -10); ctx.stroke(); ctx.beginPath(); ctx.moveTo(14, -125); ctx.lineTo(26, -10); ctx.stroke(); }
  ctx.lineWidth = 17;
  const sw = Math.sin(lt * 12.56 + ph);
  if (kind === 'vocal') {
    ctx.beginPath(); ctx.moveTo(-34, -214); ctx.lineTo(-56, -160); ctx.lineTo(-30, -238); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(34, -214); ctx.lineTo(70, -250 + sw * 10); ctx.lineTo(80, -310 + sw * 14); ctx.stroke();
  } else if (kind === 'guitar' || kind === 'bass') {
    ctx.beginPath(); ctx.moveTo(-34, -214); ctx.lineTo(-62, -170); ctx.lineTo(-90, -160); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(34, -214); ctx.lineTo(44, -160); ctx.lineTo(20 + sw * 8, -140); ctx.stroke();
  } else if (kind === 'keys') {
    ctx.beginPath(); ctx.moveTo(-34, -214); ctx.lineTo(-50, -160); ctx.lineTo(-40 + sw * 6, -128); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(34, -214); ctx.lineTo(50, -160); ctx.lineTo(44 - sw * 6, -128); ctx.stroke();
  } else if (kind === 'drums') {
    ctx.beginPath(); ctx.moveTo(-34, -214); ctx.lineTo(-70, -170); ctx.lineTo(-100, -190 + sw * 18); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(34, -214); ctx.lineTo(70, -170); ctx.lineTo(100, -180 - sw * 18); ctx.stroke();
  }
  ctx.restore();
}
function instrumentPath(ctx, kind, h, lt, ph) {
  const s = h / 300; ctx.save(); ctx.scale(s, s);
  if (kind === 'guitar' || kind === 'bass') {
    ctx.save(); ctx.translate(-20, -150); ctx.rotate(-0.42);
    ctx.beginPath(); ctx.ellipse(40, 0, 46, 36, 0, 0, 6.283); ctx.fill(); ctx.beginPath(); ctx.ellipse(78, 0, 34, 28, 0, 0, 6.283); ctx.fill();
    ctx.fillRect(-130 - (kind === 'bass' ? 30 : 0), -7, 170, 14); ctx.fillRect(-160 - (kind === 'bass' ? 30 : 0), -12, 34, 24);
    ctx.restore();
  } else if (kind === 'vocal') {
    ctx.lineWidth = 6; ctx.strokeStyle = ctx.fillStyle; ctx.beginPath(); ctx.moveTo(-70, 0); ctx.lineTo(-70, -200); ctx.lineTo(-48, -236); ctx.stroke();
    ctx.beginPath(); ctx.ellipse(-44, -244, 10, 14, 0.6, 0, 6.283); ctx.fill();
    ctx.beginPath(); ctx.moveTo(-100, 0); ctx.lineTo(-40, 0); ctx.lineTo(-70, -16); ctx.fill();
  } else if (kind === 'keys') {
    ctx.fillRect(-110, -132, 220, 22); ctx.lineWidth = 6; ctx.strokeStyle = ctx.fillStyle;
    ctx.beginPath(); ctx.moveTo(-90, -110); ctx.lineTo(90, 0); ctx.moveTo(90, -110); ctx.lineTo(-90, 0); ctx.stroke();
  } else if (kind === 'drums') {
    ctx.beginPath(); ctx.arc(0, -70, 72, 0, 6.283); ctx.fill();
    ctx.beginPath(); ctx.ellipse(-110, -118, 44, 16, 0, 0, 6.283); ctx.fill(); ctx.beginPath(); ctx.ellipse(105, -122, 44, 16, 0, 0, 6.283); ctx.fill();
    ctx.lineWidth = 5; ctx.strokeStyle = ctx.fillStyle; ctx.beginPath(); ctx.moveTo(-150, -200); ctx.lineTo(-150, 0); ctx.moveTo(160, -210); ctx.lineTo(160, 0); ctx.stroke();
    ctx.beginPath(); ctx.ellipse(-150, -205, 62, 8, -0.15, 0, 6.283); ctx.fill(); ctx.beginPath(); ctx.ellipse(160, -215, 62, 8, 0.15, 0, 6.283); ctx.fill();
  }
  ctx.restore();
}
function member(ctx, kind, x, y, h, lt, ph, rim, dark = '#0a0a12', a = 1) {
  if (a <= 0) return;
  ctx.save(); ctx.globalAlpha *= a; ctx.translate(x, y);
  for (const [dx, dy, col] of [[-3, -3, rim], [0, 0, dark]]) {
    ctx.save(); ctx.translate(dx, dy); ctx.fillStyle = col; ctx.strokeStyle = col;
    if (kind === 'drums') { ctx.save(); ctx.translate(0, -40); figurePath(ctx, kind, h, lt, ph); ctx.restore(); instrumentPath(ctx, kind, h, lt, ph); }
    else { figurePath(ctx, kind, h, lt, ph); instrumentPath(ctx, kind, h, lt, ph); }
    ctx.restore();
  }
  ctx.restore();
}
const BAND = [['keys', 150, 1.1], ['guitar', 330, 2.3], ['vocal', 540, 0.4], ['bass', 750, 3.1], ['drums', 930, 4.7]];

// plateia (cabeças e braços)
const CROWD = Array.from({ length: 3 }, (_, row) => Array.from({ length: 13 - row * 2 }, (_, k) => { const r = rng(row * 100 + k); return { x: (k + 0.5) * W / (13 - row * 2) + (r() - 0.5) * 40, s: 1 - row * 0.15 + r() * 0.12, arm: r() < 0.45, side: r() < 0.5 ? -1 : 1, ph: r() * 6.28, phone: r() < 0.55 }; }));
function crowd(ctx, base, lt, o = {}) {
  const { rim = [255, 200, 120], phones = 0, laugh = 0 } = o;
  for (let row = 2; row >= 0; row--) {
    const y = base + row * 70, col = mixc([18, 14, 24], [6, 5, 10], row / 2);
    for (const p of CROWD[row]) {
      const jump = Math.max(0, Math.sin(lt * 6.28 * 2 + p.ph)) * 10 * (o.energy ?? 1);
      const px = p.x, py = y - jump, s = p.s * 1.25;
      if (p.arm || phones) {
        ctx.strokeStyle = rgba(col); ctx.lineWidth = 16 * s; ctx.lineCap = 'round';
        const ax = px + p.side * 34 * s, ay = py - 150 * s + Math.sin(lt * 4 + p.ph) * 10;
        ctx.beginPath(); ctx.moveTo(px + p.side * 22 * s, py - 60 * s); ctx.lineTo(ax, ay); ctx.stroke();
        if (phones && p.phone) {
          glowAt(ctx, ax, ay - 10, 70, [255, 255, 240], 0.45 * phones);
          ctx.fillStyle = rgba([235, 240, 255], phones); rr(ctx, ax - 9, ay - 26, 18, 30, 4); ctx.fill();
        }
      }
      ctx.fillStyle = rgba(col); ctx.beginPath(); ctx.ellipse(px, py - 92 * s, 30 * s, 36 * s, 0, 0, 6.283); ctx.fill();
      rr(ctx, px - 52 * s, py - 60 * s, 104 * s, 120 * s, 40 * s); ctx.fill();
      ctx.strokeStyle = rgba(rim, 0.45); ctx.lineWidth = 3; ctx.beginPath(); ctx.arc(px, py - 92 * s, 31 * s, -2.6, -0.6); ctx.stroke();
      if (laugh > 0 && row === 0 && ((p.x | 0) % 3 === 0)) {
        const q = clamp(laugh * 1.6 - (p.x / W) * 0.6);
        if (q > 0) text(ctx, 'HAHA', px, py - 150 * s - 20 * Math.sin(lt * 8 + p.ph), { font: `900 ${34 * q}px ${FONT}`, color: P.yellow, align: 'center', stroke: 8, alpha: q });
      }
    }
  }
}

// ---------------------------------------------------------------- cenas
function bgGradient(ctx, a, b) { const g = ctx.createLinearGradient(0, 0, 0, H); g.addColorStop(0, a); g.addColorStop(1, b); ctx.fillStyle = g; ctx.fillRect(0, 0, W, H); }

function sceneHook(ctx, t, lt, i) {
  bgGradient(ctx, '#2a0f4a', '#0a0420');
  sunburst(ctx, 540, 930, lt, 'rgba(255,62,157,0.10)', 'rgba(25,195,177,0.06)', 22);
  memphis(ctx, lt, 0.8);
  const spin = lt * 2.2 + (TL.discos[i] / 2e6) * 6;
  const s = 1 + 0.03 * beatPulse(lt);
  drawCD(ctx, 540, 900, 330 * s, spin, { label: { text: 'MAMONAS ASSASSINAS', sub: '1995', c0: '#ffe680', c1: '#ffb3d9', ink: '#0b0b16', dots: true } });
  // calendário de 8 meses
  const c0 = Wt('hook', 16), c1 = Wt('hook', 19);
  const ca = win(lt, c0 - 0.2, TL.rew[0] + 0.1, 0.25, 0.15);
  if (ca > 0) {
    const months = ['JUN', 'JUL', 'AGO', 'SET', 'OUT', 'NOV', 'DEZ', 'JAN', 'FEV'];
    const k = Math.min(8, Math.floor(8 * clamp((lt - c0) / (c1 - c0))));
    ctx.save(); ctx.globalAlpha = ca; ctx.translate(820, 1270); ctx.rotate(0.08); ctx.scale(popIn(lt, c0 - 0.2), popIn(lt, c0 - 0.2));
    calendarPage(ctx, 0, 0, 220, months[k], k < 7 ? '1995' : '1996');
    text(ctx, `${k} ${k === 1 ? 'MÊS' : 'MESES'}`, 0, 170, { font: `900 46px ${FONT}`, color: P.yellow, align: 'center', stroke: 10 });
    ctx.restore();
  }
}
function calendarPage(ctx, x, y, w, big, small, accent = P.pink) {
  const h = w * 1.1;
  ctx.save(); ctx.translate(x, y);
  ctx.shadowColor = 'rgba(0,0,0,0.5)'; ctx.shadowBlur = 24; ctx.shadowOffsetY = 10;
  ctx.fillStyle = '#fbf7ee'; rr(ctx, -w / 2, -h / 2, w, h, 16); ctx.fill(); ctx.shadowBlur = 0; ctx.shadowOffsetY = 0;
  ctx.fillStyle = accent; ctx.beginPath(); ctx.moveTo(-w / 2, -h / 2 + 16); ctx.arcTo(-w / 2, -h / 2, -w / 2 + 16, -h / 2, 16); ctx.lineTo(w / 2 - 16, -h / 2); ctx.arcTo(w / 2, -h / 2, w / 2, -h / 2 + 16, 16); ctx.lineTo(w / 2, -h / 2 + h * 0.28); ctx.lineTo(-w / 2, -h / 2 + h * 0.28); ctx.fill();
  for (const rx of [-w * 0.25, w * 0.25]) { ctx.fillStyle = '#2a2a35'; rr(ctx, rx - 7, -h / 2 - 16, 14, 34, 7); ctx.fill(); }
  text(ctx, small, 0, -h / 2 + h * 0.2, { font: `900 ${w * 0.16}px ${FONT}`, color: '#fff', align: 'center' });
  let fs = w * 0.36; ctx.font = `900 ${fs}px ${FONT}`; while (ctx.measureText(big).width > w * 0.86) { fs -= 2; ctx.font = `900 ${fs}px ${FONT}`; }
  text(ctx, big, 0, h * 0.24, { font: `900 ${fs}px ${FONT}`, color: '#1b1b26', align: 'center' });
  ctx.restore();
}

// ---- garagem em Guarulhos (banda Utopia)
function bricks(ctx, x0, y0, x1, y1, base) {
  ctx.fillStyle = rgba(base.map(v => v * 0.55)); ctx.fillRect(x0, y0, x1 - x0, y1 - y0);
  const r = rng(5), bw = 90, bh = 40;
  for (let row = 0, y = y0; y < y1; row++, y += bh) for (let x = x0 - (row % 2) * bw / 2; x < x1; x += bw) {
    const v = 0.8 + r() * 0.35; ctx.fillStyle = rgba(base.map(c => c * v)); rr(ctx, x + 3, y + 3, bw - 6, bh - 6, 4); ctx.fill();
  }
}
function sceneGaragem(ctx, t, lt, i) {
  bricks(ctx, 0, 0, W, 1420, [150, 70, 52]);
  const light = 0.75 + 0.05 * Math.sin(lt * 13) * Math.sin(lt * 7);
  const lg = ctx.createRadialGradient(540, 560, 40, 540, 700, 900); lg.addColorStop(0, `rgba(255,200,120,${0.35 * light})`); lg.addColorStop(1, 'rgba(0,0,0,0.65)');
  ctx.fillStyle = lg; ctx.fillRect(0, 0, W, H);
  // pôster da banda séria (arte própria)
  ctx.save(); ctx.translate(820, 640); ctx.rotate(0.05); ctx.shadowColor = 'rgba(0,0,0,0.5)'; ctx.shadowBlur = 16; coverUtopiaPoster(ctx, 240, 320); ctx.restore();
  ctx.save(); ctx.translate(240, 620); ctx.rotate(-0.06); ctx.fillStyle = '#e9e2cf'; ctx.shadowColor = 'rgba(0,0,0,0.5)'; ctx.shadowBlur = 16; rr(ctx, -110, -80, 220, 160, 6); ctx.fill(); ctx.restore();
  text(ctx, 'ENSAIO', 240, 610, { font: `900 44px ${FONT}`, color: '#3a2a20', align: 'center' }); text(ctx, 'sáb · 14h', 240, 660, { font: `700 30px ${FONT}`, color: '#6a5040', align: 'center' });
  // lâmpada pendurada
  ctx.strokeStyle = '#111'; ctx.lineWidth = 3; ctx.beginPath(); ctx.moveTo(540, 430); ctx.lineTo(540 + Math.sin(lt) * 6, 520); ctx.stroke();
  glowAt(ctx, 540 + Math.sin(lt) * 6, 540, 200, [255, 210, 140], 0.6 * light);
  ctx.fillStyle = '#fff3c4'; ctx.beginPath(); ctx.arc(540 + Math.sin(lt) * 6, 540, 22, 0, 6.283); ctx.fill();
  stageFloor(ctx, 1380, '#3a2f2a');
  // amplificador
  const ax = 860, ay = 1380;
  ctx.fillStyle = '#16161c'; rr(ctx, ax - 90, ay - 170, 180, 170, 12); ctx.fill();
  ctx.fillStyle = '#2b2b33'; rr(ctx, ax - 78, ay - 130, 156, 118, 8); ctx.fill();
  ctx.strokeStyle = 'rgba(255,255,255,0.08)'; for (let k = 0; k < 10; k++) { ctx.beginPath(); ctx.moveTo(ax - 76, ay - 128 + k * 12); ctx.lineTo(ax + 76, ay - 128 + k * 12); ctx.stroke(); }
  for (let k = 0; k < 5; k++) { ctx.fillStyle = '#c9ccd4'; ctx.beginPath(); ctx.arc(ax - 60 + k * 30, ay - 150, 7, 0, 6.283); ctx.fill(); }
  // os cinco amigos (silhuetas genéricas)
  BAND.forEach(([kind, x, ph], k) => member(ctx, kind, x, 1385, kind === 'drums' ? 300 : 330, lt * 0.9, ph, [255, 190, 120], '#0d0b10', popIn(t, Wt('antes', 5) - 0.1 + k * 0.08, 0.4) > 0 ? 1 : 0));
  // mapa: Guarulhos (SP)
  const ga = win(t, Wt('antes', 7) - 0.2, L.antes.end - 0.4, 0.25, 0.3);
  if (ga > 0) brazilInset(ctx, 540, 860, 230, ga, t - Wt('antes', 7));
}
function coverUtopiaPoster(ctx, w, h) {
  ctx.save(); ctx.translate(-w / 2, -h / 2); coverUtopia(ctx, w, h); ctx.restore();
}
let BR_PATH = null;
function brazilInset(ctx, cx, cy, size, a, lt) {
  if (!BR_PATH) {
    const fc = feature(WORLD, WORLD.objects.countries);
    const br = fc.features.find(f => f.properties.name === 'Brazil');
    BR_PATH = br.geometry.type === 'Polygon' ? [br.geometry.coordinates] : br.geometry.coordinates;
  }
  const lon0 = -54, lat0 = -14.5, sc = size / 40;
  const Pp = (lon, lat) => [cx + (lon - lon0) * sc * Math.cos(lat0 * Math.PI / 180), cy - (lat - lat0) * sc];
  ctx.save(); ctx.globalAlpha *= a;
  ctx.fillStyle = 'rgba(6,10,22,0.88)'; rr(ctx, cx - size * 1.15, cy - size * 1.15, size * 2.3, size * 2.3, 40); ctx.fill();
  ctx.strokeStyle = P.teal; ctx.lineWidth = 4; rr(ctx, cx - size * 1.15, cy - size * 1.15, size * 2.3, size * 2.3, 40); ctx.stroke();
  ctx.beginPath();
  for (const poly of BR_PATH) for (const ring of poly) { ring.forEach(([lon, lat], k) => { const [x, y] = Pp(lon, lat); k ? ctx.lineTo(x, y) : ctx.moveTo(x, y); }); ctx.closePath(); }
  const g = ctx.createLinearGradient(cx, cy - size, cx, cy + size); g.addColorStop(0, '#3ccf6e'); g.addColorStop(1, '#1f9a4c');
  ctx.fillStyle = g; ctx.fill('evenodd'); ctx.strokeStyle = '#eafff1'; ctx.lineWidth = 3; ctx.stroke();
  const [gx, gy] = Pp(-46.53, -23.46);
  for (let k = 0; k < 2; k++) { const ph = (lt * 0.8 + k / 2) % 1; ctx.strokeStyle = `rgba(255,62,157,${1 - ph})`; ctx.lineWidth = 4; ctx.beginPath(); ctx.arc(gx, gy, 10 + ph * 50, 0, 6.283); ctx.stroke(); }
  ctx.fillStyle = P.pink; ctx.beginPath(); ctx.arc(gx, gy, 12, 0, 6.283); ctx.fill(); ctx.strokeStyle = '#fff'; ctx.lineWidth = 3; ctx.stroke();
  text(ctx, 'GUARULHOS (SP)', gx - 20, gy + 66, { font: `900 40px ${FONT}`, color: '#fff', align: 'right', stroke: 8 });
  ctx.restore();
}

// ---- loja de discos: quase ninguém comprou
function sceneLoja(ctx, t, lt, i) {
  bgGradient(ctx, '#3b2a4a', '#150d1c');
  // prateleiras cheias (lombadas coloridas)
  const r = rng(12);
  for (let row = 0; row < 3; row++) {
    const y = 560 + row * 250;
    ctx.fillStyle = '#5a3d2a'; ctx.fillRect(40, y + 170, W - 80, 26);
    ctx.fillStyle = 'rgba(0,0,0,0.3)'; ctx.fillRect(40, y + 196, W - 80, 14);
    for (let x = 60; x < W - 60;) { const w = 18 + r() * 10, hh = 140 + r() * 26; ctx.fillStyle = [P.pink, P.teal, P.yellow, P.purple, P.orange, P.blue, '#e6e6e6'][Math.floor(r() * 7)]; ctx.fillRect(x, y + 170 - hh, w, hh); ctx.fillStyle = 'rgba(0,0,0,0.25)'; ctx.fillRect(x + w - 3, y + 170 - hh, 3, hh); x += w + 2; }
  }
  ctx.fillStyle = 'rgba(10,6,14,0.55)'; ctx.fillRect(0, 0, W, H);
  // placa
  ctx.save(); ctx.translate(540, 520); ctx.rotate(-0.03); ctx.fillStyle = P.yellow; rr(ctx, -250, -50, 500, 100, 14); ctx.fill();
  text(ctx, 'ENCALHADOS', 0, 22, { font: `900 62px ${FONT}`, color: P.ink, align: 'center' }); ctx.restore();
  // o disco solitário com teia de aranha
  const p = popIn(t, Wt('fracasso', 2) - 0.1, 0.5);
  drawCase(ctx, 540, 930, 420 * p, -0.04, coverUtopia, { alpha: clamp(p) });
  const cw = sstep(Wt('fracasso', 4), Wt('fracasso', 6), t);
  if (cw > 0) {
    ctx.save(); ctx.globalAlpha = cw * 0.8; ctx.strokeStyle = '#f0f0f0'; ctx.lineWidth = 2; const ox = 735, oy = 740;
    for (let k = 0; k < 7; k++) { const a = Math.PI / 2 + k * 0.26; ctx.beginPath(); ctx.moveTo(ox, oy); ctx.lineTo(ox + Math.cos(a) * 200, oy + Math.sin(a) * 200); ctx.stroke(); }
    for (let q = 1; q < 5; q++) { ctx.beginPath(); for (let k = 0; k < 7; k++) { const a = Math.PI / 2 + k * 0.26; const x = ox + Math.cos(a) * q * 45, y = oy + Math.sin(a) * q * 45; k ? ctx.lineTo(x, y) : ctx.moveTo(x, y); } ctx.stroke(); }
    ctx.restore();
  }
  // poeira
  ctx.save(); for (let k = 0; k < 40; k++) { const rr2 = rng(50 + k); const x = rr2() * W, y = (rr2() * 900 + 500 + lt * 20 * rr2()) % 1400; ctx.globalAlpha = 0.25; ctx.fillStyle = '#fff'; ctx.beginPath(); ctx.arc(x, y, 2, 0, 6.283); ctx.fill(); } ctx.restore();
  const ta = sstep(Wt('fracasso', 6) - 0.1, Wt('fracasso', 6) + 0.2, t);
  if (ta > 0) { ctx.save(); ctx.translate(540, 1260); ctx.rotate(-0.05); text(ctx, 'VENDAS: QUASE ZERO', 0, 0, { font: `900 60px ${FONT}`, color: '#ff5a6a', align: 'center', stroke: 12, alpha: ta }); ctx.restore(); }
}

// ---- palco pequeno: a plateia ri
function scenePalco(ctx, t, lt, i) {
  curtain(ctx, '#5a0f1f', '#8c1a30');
  const gx = 540;
  spotlight(ctx, 200, 420, 420, 1330, [255, 210, 150], 0.9); spotlight(ctx, 880, 420, 660, 1330, [255, 120, 200], 0.9);
  stageFloor(ctx, 1240, '#2a1a14');
  BAND.forEach(([kind, x, ph]) => member(ctx, kind, x, 1250, kind === 'drums' ? 260 : 290, lt, ph, [255, 220, 170]));
  const laugh = sstep(Wt('virada', 10), Wt('virada', 11, 't1'), t);
  crowd(ctx, 1560, lt, { laugh, rim: [255, 200, 150] });
  // medidor de risadas
  const m = 0.15 + 0.85 * laugh;
  ctx.save(); ctx.translate(540, 520);
  ctx.fillStyle = 'rgba(6,10,22,0.85)'; rr(ctx, -330, -50, 660, 100, 50); ctx.fill();
  text(ctx, 'RISADÔMETRO', -300, 12, { font: `900 34px ${FONT}`, color: '#fff' });
  ctx.fillStyle = 'rgba(255,255,255,0.12)'; rr(ctx, -40, -18, 340, 36, 18); ctx.fill();
  const gg = ctx.createLinearGradient(-40, 0, 300, 0); gg.addColorStop(0, P.teal); gg.addColorStop(0.6, P.yellow); gg.addColorStop(1, P.pink);
  ctx.fillStyle = gg; rr(ctx, -40, -18, 340 * m * (0.96 + 0.04 * Math.sin(lt * 20)), 36, 18); ctx.fill();
  ctx.restore();
}

// ---- novo nome
function sceneNome(ctx, t, lt, i) {
  const sw = sstep(Wt('nome', 4) - 0.1, Wt('nome', 8, 't1'), t);     // vira banda de humor
  const nm = Wt('nome', 14);
  bgGradient(ctx, rgba(mixc([28, 28, 34], [255, 62, 157], sw)), rgba(mixc([8, 8, 10], [123, 63, 228], sw)));
  if (sw > 0) { sunburst(ctx, 540, 900, lt, `rgba(255,210,63,${0.25 * sw})`, 'rgba(255,255,255,0)', 20); memphis(ctx, lt, sw); }
  // nome antigo (sério), riscado e caindo
  const fall = easeInCubic((t - (nm - 0.6)) / 0.6);
  if (fall < 1) {
    ctx.save(); ctx.translate(540, 850 + fall * 900); ctx.rotate(fall * 0.6);
    ctx.font = `400 150px "DejaVu Serif"`; ctx.textAlign = 'center'; ctx.letterSpacing = '24px'; ctx.fillStyle = `rgba(230,230,240,${1 - fall})`; ctx.fillText('UTOPIA', 0, 50); ctx.letterSpacing = '0px';
    const x = sstep(Wt('nome', 2), Wt('nome', 3, 't1'), t);
    if (x > 0) { ctx.strokeStyle = '#ff3b4e'; ctx.lineWidth = 18; ctx.lineCap = 'round'; ctx.beginPath(); ctx.moveTo(-330, 0); ctx.lineTo(-330 + 660 * x, 10); ctx.stroke(); }
    ctx.restore();
  }
  // máscaras de humor (desenho próprio) quando viram banda de humor
  const mk = popIn(t, Wt('nome', 8) - 0.15, 0.5) * (1 - sstep(nm - 0.4, nm, t));
  if (mk > 0) laughMask(ctx, 540, 900, 260 * mk, lt);
  // nome novo, letra por letra
  if (t > nm - 0.1) {
    [['MAMONAS', 820, 150, P.yellow], ['ASSASSINAS', 990, 118, '#ffffff']].forEach(([word, y, fs, col], row) => {
      ctx.font = `900 ${fs}px ${FONT}`;
      const letters = [...word], ws = letters.map(ch => ctx.measureText(ch).width), tot = ws.reduce((a, b) => a + b, 0) + (letters.length - 1) * 4;
      let x = 540 - tot / 2;
      letters.forEach((ch, k) => {
        const p = popIn(t, nm - 0.05 + row * 0.25 + k * 0.035, 0.35);
        ctx.save(); ctx.translate(x + ws[k] / 2, y); ctx.rotate(Math.sin(k * 1.7 + row) * 0.12 + Math.sin(lt * 3 + k) * 0.03); ctx.scale(p, p);
        ctx.font = `900 ${fs}px ${FONT}`; ctx.textAlign = 'center'; ctx.lineJoin = 'round';
        ctx.fillStyle = P.ink; ctx.fillText(ch, 8, 10);
        ctx.lineWidth = fs * 0.16; ctx.strokeStyle = P.ink; ctx.strokeText(ch, 0, 0);
        ctx.fillStyle = row ? [P.teal, P.yellow, '#fff', P.orange][k % 4] : col; ctx.fillText(ch, 0, 0);
        ctx.restore(); x += ws[k] + 4;
      });
    });
    confetti(ctx, t - nm, 70, 31, sstep(nm, nm + 0.3, t));
  }
}
function laughMask(ctx, x, y, s, lt) {
  ctx.save(); ctx.translate(x, y); ctx.rotate(Math.sin(lt * 2) * 0.08);
  ctx.shadowColor = 'rgba(0,0,0,0.45)'; ctx.shadowBlur = 30; ctx.shadowOffsetY = 12;
  const g = ctx.createRadialGradient(-s * 0.3, -s * 0.4, s * 0.1, 0, 0, s);
  g.addColorStop(0, '#fff6c2'); g.addColorStop(1, P.yellow);
  ctx.fillStyle = g; ctx.beginPath(); ctx.ellipse(0, 0, s * 0.85, s, 0, 0, 6.283); ctx.fill(); ctx.shadowBlur = 0; ctx.shadowOffsetY = 0;
  ctx.fillStyle = P.ink;
  for (const sx of [-1, 1]) { ctx.beginPath(); ctx.ellipse(sx * s * 0.32, -s * 0.22, s * 0.16, s * 0.1, sx * 0.3, Math.PI, 0); ctx.fill(); }
  ctx.beginPath(); ctx.moveTo(-s * 0.5, s * 0.15); ctx.quadraticCurveTo(0, s * 0.95, s * 0.5, s * 0.15); ctx.closePath(); ctx.fill();
  ctx.fillStyle = '#ff6b8a'; ctx.beginPath(); ctx.ellipse(0, s * 0.5, s * 0.22, s * 0.1, 0, 0, 6.283); ctx.fill();
  ctx.fillStyle = 'rgba(255,90,120,0.35)'; for (const sx of [-1, 1]) { ctx.beginPath(); ctx.ellipse(sx * s * 0.55, s * 0.1, s * 0.12, s * 0.07, 0, 0, 6.283); ctx.fill(); }
  ctx.restore();
}

// ---- explosão de vendas
const FLY = Array.from({ length: 40 }, (_, k) => { const r = rng(700 + k); return { a: r() * 6.283, sp: 300 + r() * 900, rot: r() * 6, vr: (r() - 0.5) * 6, s: 70 + r() * 70, delay: r() * 0.6, kind: r() < 0.5 }; });
function sceneExplosao(ctx, t, lt, i) {
  const ex = Wt('explosao', 12);
  const boom = sstep(ex - 0.1, ex + 0.3, t);
  bgGradient(ctx, rgba(mixc([40, 14, 70], [255, 62, 157], boom * 0.6)), '#12062a');
  sunburst(ctx, 540, 900, lt, `rgba(255,210,63,${0.08 + 0.2 * boom})`, 'rgba(255,255,255,0)', 24);
  memphis(ctx, lt, 0.5 + 0.5 * boom);
  for (const f of FLY) {
    const q = t - ex - f.delay; if (q < 0) continue;
    const d = f.sp * q, x = 540 + Math.cos(f.a) * d, y = 900 + Math.sin(f.a) * d + 260 * q * q;
    if (y > H + 200 || x < -200 || x > W + 200) continue;
    if (f.kind) drawCD(ctx, x, y, f.s * 0.55, f.rot + q * f.vr, { shadow: false });
    else drawCase(ctx, x, y, f.s, f.rot + q * f.vr, coverMamonas, { lt });
  }
  const p = popIn(t, L.explosao.start - 0.1, 0.5);
  drawCase(ctx, 540, 900, 520 * p * (1 + 0.05 * boom * beatPulse(lt)), Math.sin(lt * 1.5) * 0.04, coverMamonas, { lt });
  const na = sstep(Wt('explosao', 16), Wt('explosao', 18, 't1'), t);
  if (na > 0) {
    ctx.save(); ctx.translate(540, 1320); ctx.rotate(-0.05); ctx.scale(0.8 + 0.2 * easeOutBack(na), 0.8 + 0.2 * easeOutBack(na));
    text(ctx, '+ 2 MILHÕES', 0, 0, { font: `900 110px ${FONT}`, color: P.yellow, align: 'center', stroke: 18, strokeColor: P.ink, alpha: na });
    ctx.restore();
  }
}

// ---- pilha de 20 km x Everest
function mountain(ctx, cx, base, w, h, colA, colB, snow = true) {
  const g = ctx.createLinearGradient(0, base - h, 0, base); g.addColorStop(0, colA); g.addColorStop(1, colB);
  ctx.fillStyle = g; ctx.beginPath(); ctx.moveTo(cx - w / 2, base); ctx.lineTo(cx - w * 0.2, base - h * 0.58); ctx.lineTo(cx - w * 0.1, base - h * 0.66);
  ctx.lineTo(cx, base - h); ctx.lineTo(cx + w * 0.12, base - h * 0.76); ctx.lineTo(cx + w * 0.22, base - h * 0.7); ctx.lineTo(cx + w / 2, base); ctx.fill();
  if (snow) { ctx.fillStyle = '#f4f8ff'; ctx.beginPath(); ctx.moveTo(cx - w * 0.08, base - h * 0.8); ctx.lineTo(cx, base - h); ctx.lineTo(cx + w * 0.07, base - h * 0.84); ctx.lineTo(cx + w * 0.03, base - h * 0.78); ctx.lineTo(cx - w * 0.02, base - h * 0.84); ctx.closePath(); ctx.fill(); }
}
function scenePilha(ctx, t, lt, i) {
  const g0 = ctx.createLinearGradient(0, 0, 0, H); g0.addColorStop(0, '#0b1a44'); g0.addColorStop(0.55, '#3a6fbf'); g0.addColorStop(0.8, '#ffc58a'); g0.addColorStop(1, '#ff8a6a');
  ctx.fillStyle = g0; ctx.fillRect(0, 0, W, H);
  const base = 1420, topY = 560, kmPx = (base - topY) / 21;
  const grow = easeInOutCubic((t - Wt('pilha', 0)) / (Wt('pilha', 9, 't1') - Wt('pilha', 0)));
  const hKm = 20.8 * grow;
  // régua
  ctx.strokeStyle = 'rgba(255,255,255,0.6)'; ctx.lineWidth = 2; ctx.beginPath(); ctx.moveTo(165, base); ctx.lineTo(165, topY - 20); ctx.stroke();
  for (let k = 0; k <= 20; k += 5) { const y = base - k * kmPx; ctx.beginPath(); ctx.moveTo(151, y); ctx.lineTo(165, y); ctx.stroke(); text(ctx, `${k} km`, 143, y + 9, { font: `700 26px ${FONT}`, color: '#fff', align: 'right' }); }
  // dois Everests empilhados (contorno)
  const ev = sstep(Wt('pilha', 10) - 0.2, Wt('pilha', 15, 't1'), t);
  mountain(ctx, 720, base, 520, 8.849 * kmPx, '#8fa3c8', '#3a4f78');
  if (ev > 0) {
    ctx.save(); ctx.globalAlpha = ev * 0.85; ctx.setLineDash([12, 10]); ctx.strokeStyle = '#fff'; ctx.lineWidth = 4;
    const b2 = base - 8.849 * kmPx; ctx.beginPath(); ctx.moveTo(720 - 260, b2); ctx.lineTo(720 - 104, b2 - 0.58 * 8.849 * kmPx); ctx.lineTo(720, b2 - 8.849 * kmPx); ctx.lineTo(720 + 260, b2); ctx.stroke(); ctx.restore();
    text(ctx, '2× EVEREST', 900, base - 17.7 * kmPx - 10, { font: `900 38px ${FONT}`, color: '#fff', align: 'center', stroke: 8, alpha: ev });
    text(ctx, '17,7 km', 900, base - 17.7 * kmPx + 34, { font: `700 30px ${FONT}`, color: '#dfe8ff', align: 'center', stroke: 6, alpha: ev });
  }
  text(ctx, 'EVEREST · 8,8 km', 720, base - 8.849 * kmPx - 18, { font: `800 30px ${FONT}`, color: '#fff', align: 'center', stroke: 7 });
  // chão
  ctx.fillStyle = '#2f5a2a'; ctx.fillRect(0, base, W, H - base);
  // a torre de CDs
  const tx = 330, tw = 120, tp = hKm * kmPx;
  const cg = ctx.createLinearGradient(tx - tw / 2, 0, tx + tw / 2, 0);
  cg.addColorStop(0, '#9aa4b8'); cg.addColorStop(0.3, '#eef2fa'); cg.addColorStop(0.6, '#c9d0de'); cg.addColorStop(1, '#7c879c');
  ctx.fillStyle = cg; ctx.fillRect(tx - tw / 2, base - tp, tw, tp);
  ctx.save(); ctx.beginPath(); ctx.rect(tx - tw / 2, base - tp, tw, tp); ctx.clip();
  for (let y = base; y > base - tp; y -= 12) { ctx.fillStyle = [P.pink, P.yellow, P.teal, P.purple][((base - y) / 12 | 0) % 4]; ctx.globalAlpha = 0.5; ctx.fillRect(tx - tw / 2 + 8, y - 5, 12, 6); }
  ctx.restore();
  if (tp > 4) { glowAt(ctx, tx, base - tp, 80, [255, 255, 255], 0.6); text(ctx, `${nf(hKm, 1)} km`, tx, base - tp - 24, { font: `900 46px ${MONO}`, color: P.yellow, align: 'center', stroke: 10 }); }
  // CDs entrando no topo
  if (grow > 0 && grow < 1) for (let k = 0; k < 4; k++) { const q = (lt * 2.2 + k / 4) % 1; drawCase(ctx, tx + (k % 2 ? 60 : -60) * (1 - q), base - tp - 160 * (1 - q), 90, q * 3, coverMamonas, { alpha: 1 - q * 0.3 }); }
  if (tp > 360) { ctx.save(); ctx.translate(tx + 14, base - 30); ctx.rotate(-Math.PI / 2); text(ctx, '2 MILHÕES DE CDs', 0, 0, { font: `900 40px ${FONT}`, color: P.ink, alpha: sstep(360, 460, tp) }); ctx.restore(); }
}

// ---- fenômeno: TV, rádio e festas
function cardPanel(ctx, x, y, w, h, col, a, p) {
  ctx.save(); ctx.globalAlpha *= a; ctx.translate(x, y); ctx.scale(p, p);
  ctx.fillStyle = P.ink; rr(ctx, -w / 2 + 12, -h / 2 + 12, w, h, 30); ctx.fill();
  ctx.fillStyle = col; rr(ctx, -w / 2, -h / 2, w, h, 30); ctx.fill();
  ctx.strokeStyle = P.ink; ctx.lineWidth = 6; rr(ctx, -w / 2, -h / 2, w, h, 30); ctx.stroke();
  ctx.restore();
}
function sceneFenomeno(ctx, t, lt, i) {
  bgGradient(ctx, '#16123a', '#07061a'); memphis(ctx, lt, 0.6);
  const tv = popIn(t, Wt('fenomeno', 5) - 0.15, 0.45), ra = popIn(t, Wt('fenomeno', 7) - 0.15, 0.45), fe = popIn(t, Wt('fenomeno', 9) - 0.15, 0.45);
  cardPanel(ctx, 540, 640, 860, 300, P.teal, clamp(tv), tv);
  if (tv > 0) { ctx.save(); ctx.translate(540, 640); ctx.scale(tv, tv); ctx.translate(-540, -640);
    drawTV(ctx, 400, 650, 300, (c, w, h, l) => { c.fillStyle = '#250b3d'; c.fillRect(0, 0, w, h); BAND.forEach(([kind, bx, ph]) => member(c, kind, bx / 1080 * w, h - 8, kind === 'drums' ? h * 0.6 : h * 0.68, l, ph, [255, 120, 210])); c.fillStyle = '#ff3b4e'; c.beginPath(); c.arc(16, 16, 7, 0, 6.283); c.fill(); text(c, 'AO VIVO', 28, 23, { font: `900 18px ${FONT}`, color: '#fff' }); }, lt);
    text(ctx, 'NA TV', 790, 670, { font: `900 72px ${FONT}`, color: P.ink, align: 'center' }); ctx.restore(); }
  cardPanel(ctx, 540, 990, 860, 300, P.yellow, clamp(ra), ra);
  if (ra > 0) { ctx.save(); ctx.translate(540, 990); ctx.scale(ra, ra); ctx.translate(-540, -990);
    drawBoombox(ctx, 400, 1005, 340, lt); text(ctx, 'NO RÁDIO', 800, 1015, { font: `900 64px ${FONT}`, color: P.ink, align: 'center' }); ctx.restore(); }
  cardPanel(ctx, 540, 1340, 860, 300, P.pink, clamp(fe), fe);
  if (fe > 0) { ctx.save(); ctx.translate(540, 1340); ctx.scale(fe, fe); ctx.translate(-540, -1340);
    balloon(ctx, 230, 1300, 56, P.yellow, lt, 0); balloon(ctx, 330, 1270, 64, P.teal, lt, 1); balloon(ctx, 430, 1310, 52, P.purple, lt, 2);
    partyHat(ctx, 260, 1460, 90, P.purple, -0.2); partyHat(ctx, 420, 1465, 80, P.teal, 0.25);
    text(ctx, 'NAS FESTAS', 780, 1365, { font: `900 64px ${FONT}`, color: '#fff', align: 'center', stroke: 10, strokeColor: P.ink }); ctx.restore(); }
}

// ---- homenagem: as luzes se apagam
function sceneLuzes(ctx, t, lt, i) {
  bgGradient(ctx, '#0b0a18', '#020205');
  const off0 = Wt('queda', 19);
  const offT = k => off0 + 0.15 + k * 0.42;
  const dim = sstep(Wt('queda', 13), off0, t);
  curtain(ctx, rgba(mixc([90, 15, 31], [30, 6, 12], dim)), rgba(mixc([140, 26, 48], [44, 9, 18], dim)));
  stageFloor(ctx, 1260, '#1a1010');
  const cols = [[255, 210, 150], [255, 150, 210], [150, 220, 255], [255, 230, 120], [190, 160, 255]];
  BAND.forEach(([kind, x, ph], k) => {
    const on = 1 - sstep(offT(k), offT(k) + 0.08, t);
    spotlight(ctx, x * 0.7 + 160, 440, x, 1270, cols[k], on);
    member(ctx, kind, x, 1270, kind === 'drums' ? 250 : 280, lt * (0.3 + 0.7 * (1 - dim)), ph, cols[k], '#0a0a12', 0.25 + 0.75 * on);
  });
  // calendário
  const ca = win(t, Wt('queda', 2) - 0.2, off0 + 0.2, 0.25, 0.4);
  if (ca > 0) { ctx.save(); ctx.globalAlpha = ca; calendarPage(ctx, 540, 820, 300, '2 MAR', '1996', '#9aa0ad'); ctx.restore(); }
  // microfone sozinho no fim
  const mic = sstep(offT(4) + 0.3, offT(4) + 1.2, t);
  if (mic > 0) {
    spotlight(ctx, 540, 440, 540, 1270, [255, 245, 225], 0.9 * mic);
    ctx.save(); ctx.fillStyle = '#e8ebf2'; ctx.strokeStyle = '#e8ebf2'; ctx.globalAlpha = mic; ctx.translate(610, 1270); instrumentPath(ctx, 'vocal', 330, 0, 0); ctx.restore();
  }
}

// ---- legado: cinco estrelas e 30 anos depois
function sceneLegado(ctx, t, lt, i) {
  bgGradient(ctx, '#0a0a2a', '#1d0f3a');
  for (const s of STARS) { ctx.globalAlpha = s.a * (0.7 + 0.3 * Math.sin(lt * 2 + s.tw)); ctx.fillStyle = '#fff'; ctx.beginPath(); ctx.arc(s.x, s.y, s.r, 0, 6.283); ctx.fill(); }
  ctx.globalAlpha = 1;
  const st = [[210, 640], [380, 560], [540, 610], [700, 560], [870, 640]];
  st.forEach(([x, y], k) => {
    const a = sstep(Wt('legado', 0) + k * 0.18, Wt('legado', 0) + k * 0.18 + 0.4, t), tw = 0.85 + 0.15 * Math.sin(lt * 3 + k);
    if (a <= 0) return;
    glowAt(ctx, x, y, 110 * tw, [255, 230, 160], 0.5 * a);
    ctx.save(); ctx.translate(x, y); ctx.rotate(lt * 0.2 + k); ctx.fillStyle = `rgba(255,244,210,${a})`; ctx.beginPath();
    for (let q = 0; q < 10; q++) { const r = q % 2 ? 9 : 26, an = q * Math.PI / 5; q ? ctx.lineTo(Math.cos(an) * r, Math.sin(an) * r) : ctx.moveTo(Math.cos(an) * r, Math.sin(an) * r); }
    ctx.closePath(); ctx.fill(); ctx.restore();
  });
  const later = sstep(Wt('legado', 7) - 0.2, Wt('legado', 9, 't1'), t);
  // palco ao fundo e plateia com lanternas do celular
  if (later > 0) {
    ctx.save(); ctx.globalAlpha = later;
    glowAt(ctx, 540, 1150, 600, [255, 120, 200], 0.35);
    for (let k = 0; k < 5; k++) spotlight(ctx, 160 + k * 190, 900, 540 + (k - 2) * 120, 1250, [[255, 62, 157], [25, 195, 177], [255, 210, 63], [123, 63, 228], [255, 138, 61]][k].map(v => v), 0.6 + 0.3 * Math.sin(lt * 3 + k));
    ctx.restore();
    crowd(ctx, 1600, lt, { phones: later, rim: [255, 180, 220], energy: 0.6 });
    // notas musicais (desenho próprio)
    for (let k = 0; k < 8; k++) {
      const q = ((lt * 0.35 + k / 8) % 1), x = 120 + k * 120 + Math.sin(lt + k) * 30, y = 1350 - q * 600;
      ctx.save(); ctx.globalAlpha = later * (1 - q) * 0.9; ctx.translate(x, y); ctx.rotate(Math.sin(lt * 2 + k) * 0.2);
      ctx.fillStyle = [P.yellow, P.pink, P.teal][k % 3]; ctx.beginPath(); ctx.ellipse(0, 0, 16, 12, -0.4, 0, 6.283); ctx.fill();
      ctx.fillRect(12, -60, 6, 60); if (k % 2) { ctx.beginPath(); ctx.moveTo(18, -60); ctx.quadraticCurveTo(46, -46, 34, -24); ctx.lineTo(18, -40); ctx.fill(); }
      ctx.restore();
    }
    const tb = sstep(Wt('legado', 7), Wt('legado', 9), t);
    text(ctx, '30 ANOS', 540, 860, { font: `900 130px ${FONT}`, color: P.yellow, align: 'center', stroke: 16, strokeColor: P.ink, alpha: tb });
  }
}

// ---------------------------------------------------------------- HUD, VHS e composição
function drawHUD(ctx, t, i) {
  const x = 60, y = 186, w = 960, h = 236;
  ctx.save();
  ctx.fillStyle = 'rgba(8,6,20,0.72)'; rr(ctx, x, y, w, h, 34); ctx.fill();
  ctx.strokeStyle = 'rgba(255,255,255,0.1)'; ctx.lineWidth = 2; rr(ctx, x, y, w, h, 34); ctx.stroke();
  const ano = Math.floor(TL.ano[i] + 1e-6), d = TL.discos[i];
  text(ctx, 'ANO', x + 170, y + 62, { font: `700 26px ${FONT}`, color: C.label, align: 'center', spacing: 5 });
  text(ctx, String(ano), x + 170, y + 170, { font: `800 104px ${MONO}`, color: P.teal, align: 'center' });
  ctx.fillStyle = 'rgba(255,255,255,0.1)'; ctx.fillRect(x + 340, y + 36, 2, h - 72);
  text(ctx, 'DISCOS VENDIDOS', x + 650, y + 62, { font: `700 26px ${FONT}`, color: C.label, align: 'center', spacing: 5 });
  const quase = t > Wt('fracasso', 4) - 0.05 && t < L.nome.end;
  const val = quase ? 'quase nada' : nf(d, 0);
  const full = d >= 2e6 && !quase;
  let fs = quase ? 70 : 92; ctx.font = `800 ${fs}px ${MONO}`; while (ctx.measureText(val).width > 560) { fs -= 2; ctx.font = `800 ${fs}px ${MONO}`; }
  text(ctx, val, x + 650, y + 160, { font: `800 ${fs}px ${MONO}`, color: quase ? '#ff6a7a' : P.yellow, align: 'center' });
  if (full) text(ctx, 'MAIS DE', x + 650, y + 202, { font: `800 26px ${FONT}`, color: '#fff', align: 'center', spacing: 4 });
  ctx.restore();
}
function vhsStamp(ctx, t) {
  const blink = Math.floor(t * 1.5) % 2 === 0;
  text(ctx, `${blink ? '▶' : ' '} PLAY`, 84, 486, { font: `800 34px ${MONO}`, color: '#f2f2f2', alpha: 0.85, shadow: 6 });
  const s = Math.floor(t), tc = `SP 0:${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`;
  text(ctx, tc, W - 84, 486, { font: `800 30px ${MONO}`, color: '#f2f2f2', align: 'right', alpha: 0.7, shadow: 6 });
}
const SCENE_FN = { hook: sceneHook, garagem: sceneGaragem, loja: sceneLoja, palco: scenePalco, nome: sceneNome, explosao: sceneExplosao, pilha: scenePilha, fenomeno: sceneFenomeno, luzes: sceneLuzes, legado: sceneLegado, cta: sceneCTA };
const SCENES = [
  { name: 'hook', t0: -1, local0: 0 },
  { name: 'garagem', t0: L.antes.start - 0.35 },
  { name: 'loja', t0: L.fracasso.start - 0.3 },
  { name: 'palco', t0: L.virada.start - 0.35 },
  { name: 'nome', t0: L.nome.start - 0.3 },
  { name: 'explosao', t0: L.explosao.start - 0.3 },
  { name: 'pilha', t0: L.pilha.start - 0.3 },
  { name: 'fenomeno', t0: L.fenomeno.start - 0.3 },
  { name: 'luzes', t0: L.queda.start - 0.35, soft: true },
  { name: 'legado', t0: L.legado.start - 0.5, soft: true },
  { name: 'cta', t0: L.cta.start - 0.35 },
  { name: 'hook', t0: TL.total - 0.5, local0: TL.total, fade: true },
];
const TR = 0.42;
const vignette = (() => { const c = createCanvas(W, H), x = c.getContext('2d'); const g = x.createRadialGradient(W / 2, H * 0.48, H * 0.25, W / 2, H * 0.5, H * 0.78); g.addColorStop(0, 'rgba(0,0,0,0)'); g.addColorStop(1, 'rgba(0,0,0,0.6)'); x.fillStyle = g; x.fillRect(0, 0, W, H); return c; })();
const scan = (() => { const c = createCanvas(W, H), x = c.getContext('2d'); x.fillStyle = 'rgba(0,0,0,0.07)'; for (let y = 0; y < H; y += 4) x.fillRect(0, y, W, 2); return c; })();
const canvas = createCanvas(W, H), ctx = canvas.getContext('2d');
const bufA = createCanvas(W, H), ctxA = bufA.getContext('2d');
const bufB = createCanvas(W, H), ctxB = bufB.getContext('2d');
const scratch = createCanvas(W, H), sctx = scratch.getContext('2d');
function renderScene(target, idx, t, i) {
  const sc = SCENES[idx], lt = t - (sc.local0 !== undefined ? sc.local0 : sc.t0);
  target.save(); target.setTransform(1, 0, 0, 1, 0, 0);
  const z = 1 + Math.min(0.05, 0.012 * Math.max(0, lt)); target.translate(W / 2, H * 0.55); target.scale(z, z); target.translate(-W / 2, -H * 0.55);
  SCENE_FN[sc.name](target, t, lt, i); target.restore();
}
function zoomBlurDraw(src, s, a) {
  for (let k = 0; k < 4; k++) { const sk = s * (1 + k * 0.045); ctx.globalAlpha = a * (k === 0 ? 1 : 0.35); ctx.drawImage(src, W / 2 - W * sk / 2, H / 2 - H * sk / 2, W * sk, H * sk); }
  ctx.globalAlpha = 1;
}
function frame(i, opts = {}) {
  const t = i / FPS;
  let cur = 0; for (let k = 0; k < SCENES.length; k++) if (t >= SCENES[k].t0) cur = k;
  ctx.save(); ctx.fillStyle = '#000'; ctx.fillRect(-40, -40, W + 80, H + 80);
  const sc = SCENES[cur], into = t - sc.t0, nxt = SCENES[cur + 1];
  const softIn = sc.soft || sc.fade, softOut = nxt && (nxt.soft || nxt.fade);
  if (cur > 0 && softIn && into < (sc.fade ? 0.5 : 0.7)) {
    renderScene(ctxA, cur - 1, t, i); renderScene(ctxB, cur, t, i);
    ctx.drawImage(bufA, 0, 0); ctx.globalAlpha = sstep(0, sc.fade ? 0.35 : 0.7, into); ctx.drawImage(bufB, 0, 0); ctx.globalAlpha = 1;
  } else if (cur > 0 && into < TR / 2) {
    const p = clamp((into + TR / 2) / TR);
    renderScene(ctxA, cur - 1, t, i); renderScene(ctxB, cur, t, i);
    zoomBlurDraw(bufA, 1 + 0.55 * easeInCubic(p), 1 - sstep(0.35, 0.75, p)); zoomBlurDraw(bufB, lerp(0.82, 1, easeOutCubic(p)), sstep(0.3, 0.8, p));
  } else if (nxt && !softOut && nxt.t0 - t < TR / 2) {
    const p = clamp((t - (nxt.t0 - TR / 2)) / TR);
    renderScene(ctxA, cur, t, i); zoomBlurDraw(bufA, 1 + 0.55 * easeInCubic(p), 1 - sstep(0.35, 0.75, p));
  } else { renderScene(ctxA, cur, t, i); ctx.drawImage(bufA, 0, 0); }
  // rebobinar VHS (assinatura da série)
  const ra = win(t, TL.rew[0] - 0.05, TL.rew[1] + 0.05, 0.08, 0.12);
  if (ra > 0) {
    sctx.clearRect(0, 0, W, H); sctx.drawImage(canvas, 0, 0);
    const r = rng(Math.floor(t * 60));
    for (let k = 0; k < 8; k++) { const yy = r() * H, hh = 20 + r() * 120, dx = (r() - 0.5) * 90 * ra; ctx.drawImage(scratch, 0, yy, W, hh, dx, yy, W, hh); }
    ctx.save(); ctx.globalAlpha = 0.2 * ra; ctx.fillStyle = '#000'; for (let yy = (t * 400) % 6; yy < H; yy += 6) ctx.fillRect(0, yy, W, 2);
    ctx.globalAlpha = 0.12 * ra; ctx.fillStyle = '#ff3e9d'; ctx.fillRect(0, 0, W, H); ctx.restore();
    text(ctx, '◀◀ REW', 90, 600, { font: `900 64px ${MONO}`, color: '#fff', alpha: ra * (0.6 + 0.4 * Math.sin(t * 20)), stroke: 8 });
  }
  ctx.drawImage(scan, 0, 0); ctx.drawImage(vignette, 0, 0);
  drawHUD(ctx, t, i);
  const stampA = (SCENES[cur].name === 'cta' || cur === SCENES.length - 1) ? 0 : sstep(0.4, 0.9, t);
  if (stampA > 0) { ctx.save(); ctx.globalAlpha = stampA; vhsStamp(ctx, t); ctx.restore(); }
  if (!opts.noCaptions) drawCaptions(ctx, t);
  let fl = 0; const ex = Wt('explosao', 12); if (t >= ex) fl = 0.55 * Math.exp(-(t - ex) / 0.25);
  if (fl > 0.01) { ctx.fillStyle = `rgba(255,250,235,${fl})`; ctx.fillRect(-40, -40, W + 80, H + 80); }
  ctx.restore();
}

// ---------------------------------------------------------------- main
(async () => {
  const argv = process.argv.slice(2), pi = argv.indexOf('--preview');
  if (argv.includes('--capa')) {
    const i = Math.round((Wt('explosao', 12) + 0.75) * FPS);
    frame(i, { noCaptions: true });
    const g = ctx.createLinearGradient(0, 1250, 0, 1800); g.addColorStop(0, 'rgba(3,5,12,0)'); g.addColorStop(0.35, 'rgba(3,5,12,0.85)'); g.addColorStop(1, 'rgba(3,5,12,0.95)');
    ctx.fillStyle = g; ctx.fillRect(0, 1250, W, 670);
    text(ctx, '2 MILHÕES DE DISCOS', W / 2, 1460, { font: `900 82px ${FONT}`, color: '#fff', align: 'center', stroke: 14 });
    text(ctx, 'E SÓ 8 MESES DE FAMA', W / 2, 1565, { font: `900 82px ${FONT}`, color: P.yellow, align: 'center', stroke: 14 });
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
