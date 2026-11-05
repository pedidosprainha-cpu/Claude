// Ciência #4 — "Você nunca viu o presente"
// Imagens reais do espaço: NASA (domínio público) e ESA/Hubble, ESA/Webb, ESO (CC BY 4.0), com crédito na tela.
// Céu, feixes de luz, constelação, tipografia e transições são gerados aqui.
//   node src/render.js                   -> build/video.mp4
//   node src/render.js --preview 3,20    -> build/preview/*.png
//   node src/render.js --capa            -> output/capa.png
const { createCanvas, loadImage } = require('@napi-rs/canvas');
const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');

const ROOT = path.resolve(__dirname, '..');
const TL = JSON.parse(fs.readFileSync(path.join(ROOT, 'build/timeline.json'), 'utf8'));
const W = 1080, H = 1920, FPS = TL.fps, N = TL.frames;
const FONT = '"Inter Display"', MONO = '"JetBrains Mono"';
const C = { yellow: '#FFD23F', cyan: '#4FD1FF', red: '#FF3B4E', orange: '#FF8A3D', ink: '#070A14', label: '#A9B4D8' };
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



// ================================================================ vídeo 06: "Você nunca viu o presente"
const popIn = (t, t0, d = 0.38) => t < t0 ? 0 : easeOutBack((t - t0) / d);
const SERIF = '"Bitstream Charter"';
const ANO = 365.25 * 86400, C_KM = 299792.458;
const R0 = rng(606);

// ---------------------------------------------------------------- imagens (NASA domínio público; ESA/ESO CC BY 4.0)
const IMG = {};
const CREDITO = {
  sol: 'Imagem: NASA/SDO', terra: 'Imagem: NASA', lua: 'Imagem: NASA', nascer_do_sol_iss: 'Foto: NASA (ISS)',
  proxima: 'Imagem: ESA/Hubble & NASA · CC BY 4.0', betelgeuse: 'Imagem: ALMA (ESO/NAOJ/NRAO)/E. O’Gorman/P. Kervella · CC BY 4.0',
  andromeda: 'Imagem: NASA/JPL-Caltech (GALEX)', webb_campo_profundo: 'Imagem: NASA, ESA, CSA, STScI (James Webb)',
  cupula: 'Foto: NASA (ISS) · astronauta da ESA', via_lactea_iss: 'Foto: NASA (ISS)', penhascos_cosmicos: 'NASA, ESA, CSA, STScI · CC BY 4.0',
};
async function loadImages() { for (const k of Object.keys(CREDITO)) IMG[k] = await loadImage(path.join(ROOT, 'assets', k + '.jpg')); }

// objeto com fundo preto: mistura "screen" (o preto some e o astro se funde ao céu)
function astro(ctx, img, cx, cy, size, o = {}) {
  const { rot = 0, alpha = 1, sx = 0.5, sy = 0.5, crop = 1, tint = null } = o;
  const s = Math.min(img.width, img.height) * crop;
  ctx.save(); ctx.globalAlpha *= alpha; ctx.globalCompositeOperation = 'screen';
  ctx.translate(cx, cy); ctx.rotate(rot);
  ctx.drawImage(img, img.width * sx - s / 2, img.height * sy - s / 2, s, s, -size / 2, -size / 2, size, size);
  if (tint) { ctx.globalCompositeOperation = 'soft-light'; ctx.fillStyle = tint; ctx.fillRect(-size / 2, -size / 2, size, size); }
  ctx.restore();
}
// foto de tela cheia com movimento lento de câmera
function plate(ctx, img, p, o = {}) {
  const { fx = 0.5, fy = 0.5, z0 = 1.05, z1 = 1.18, x = 0, y = 0, w = W, h = H, alpha = 1 } = o;
  const z = lerp(z0, z1, p), s = Math.max(w / img.width, h / img.height) * z;
  const iw = img.width * s, ih = img.height * s;
  const ix = clamp(x + w / 2 - iw * fx, x + w - iw, x), iy = clamp(y + h / 2 - ih * fy, y + h - ih, y);
  ctx.save(); ctx.globalAlpha *= alpha; ctx.drawImage(img, ix, iy, iw, ih); ctx.restore();
}

// ---------------------------------------------------------------- céu, brilhos e feixes de luz
const STARL = [0, 1, 2].map(k => Array.from({ length: 140 + k * 60 }, () => ({ x: R0() * W, y: R0() * H, r: (0.4 + R0() * R0() * 2) * (1 + k * 0.3), a: 0.2 + R0() * 0.7, tw: R0() * 6.28 })));
function sky(ctx, lt, tint = [40, 60, 120], a = 1) {
  ctx.fillStyle = '#020309'; ctx.fillRect(0, 0, W, H);
  const g = ctx.createRadialGradient(W * 0.5, H * 0.42, 50, W * 0.5, H * 0.45, H * 0.75);
  g.addColorStop(0, rgba(tint, 0.35 * a)); g.addColorStop(0.5, rgba(tint, 0.1 * a)); g.addColorStop(1, 'rgba(0,0,0,0)');
  ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
  STARL.forEach((layer, k) => {
    for (const s of layer) {
      const y = (s.y + lt * (4 + k * 6)) % H;
      ctx.globalAlpha = s.a * (0.65 + 0.35 * Math.sin(lt * (1.5 + k) + s.tw)); ctx.fillStyle = '#fff';
      ctx.beginPath(); ctx.arc(s.x, y, s.r, 0, 6.283); ctx.fill();
    }
  });
  ctx.globalAlpha = 1;
}
function bloom(ctx, x, y, r, col, a) { glowAt(ctx, x, y, r, col, a); glowAt(ctx, x, y, r * 0.35, [255, 255, 255], a * 0.5); }
// feixe de luz do astro até o espectador (base da tela), com pulsos viajando
function beam(ctx, x, y, lt, a = 1, col = [255, 244, 220]) {
  if (a <= 0) return;
  const tx = 540, ty = H + 140;
  ctx.save(); ctx.globalCompositeOperation = 'lighter';
  const g = ctx.createLinearGradient(x, y, tx, ty); g.addColorStop(0, rgba(col, 0.0)); g.addColorStop(0.3, rgba(col, 0.22 * a)); g.addColorStop(1, rgba(col, 0.5 * a));
  ctx.strokeStyle = g; ctx.lineWidth = 3; ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(tx, ty); ctx.stroke();
  for (let k = 0; k < 3; k++) {
    const q = ((lt * 0.7 + k / 3) % 1), px = lerp(x, tx, q * q), py = lerp(y, ty, q * q);
    glowAt(ctx, px, py, 26 + 30 * q, col, 0.7 * a * Math.sin(Math.PI * q));
  }
  ctx.restore();
}
function streaks(ctx, lt, amt, cx = W / 2, cy = H * 0.45) {
  if (amt <= 0.01) return;
  const r = rng(77);
  ctx.save(); ctx.globalCompositeOperation = 'lighter'; ctx.strokeStyle = '#dfe9ff'; ctx.lineCap = 'round';
  for (let k = 0; k < 90; k++) {
    const ang = r() * 6.283, ph = r(), sp = 0.6 + r();
    const q = (ph + lt * sp * 1.4) % 1, r0 = 60 + q * q * 1300, len = 40 + 520 * amt * q;
    ctx.globalAlpha = amt * 0.55 * q; ctx.lineWidth = 1 + r() * 2.2;
    ctx.beginPath(); ctx.moveTo(cx + Math.cos(ang) * r0, cy + Math.sin(ang) * r0); ctx.lineTo(cx + Math.cos(ang) * (r0 + len), cy + Math.sin(ang) * (r0 + len)); ctx.stroke();
  }
  ctx.restore();
}

// ---------------------------------------------------------------- tipografia
function fmtTau(s) {
  if (s < 0) return '—';
  if (s < 1e-6) return `${nf(s * 1e9, 0)} bilionésimos de s`;
  if (s < 60) return `${nf(s, s < 10 ? 1 : 0)} s`;
  if (s < 3600) { const m = Math.floor(s / 60), r = Math.round(s - m * 60); return r ? `${m} min ${r} s` : `${m} min`; }
  if (s < 86400) return `${nf(s / 3600, 1)} h`;
  const y = s / ANO;
  if (y < 1) return `${nf(s / 86400, 0)} dias`;
  if (y < 1000) return `${nf(y, y < 10 ? 1 : 0)} ${y < 2 ? 'ano' : 'anos'}`;
  if (y < 1e6) return `${nf(y / 1e3, 0)} mil anos`;
  if (y < 1e9) { const v = y / 1e6; return `${nf(v, v < 10 ? 1 : 0)} ${v < 2 ? 'milhão' : 'milhões'} de anos`; }
  const v = y / 1e9; return `${nf(v, v < 10 ? 1 : 0)} ${v < 2 ? 'bilhão' : 'bilhões'} de anos`;
}
function fmtDist(s) {
  if (s < 0) return '—';
  const km = s * C_KM;
  if (km < 1) return `${nf(km * 1000, 0)} m`;
  if (km < 1e6) return `${nf(Math.round(km), 0)} km`;
  if (km < 1e9) { const v = km / 1e6; return `${nf(v, 0)} milhões de km`; }
  const ly = s / ANO;
  if (ly < 0.05) { const v = km / 1e9; return `${nf(v, 0)} bilhões de km`; }
  if (ly < 1000) return `${nf(ly, ly < 10 ? 1 : 0)} anos-luz`;
  if (ly < 1e6) return `${nf(ly / 1e3, 0)} mil anos-luz`;
  if (ly < 1e9) { const v = ly / 1e6; return `${nf(v, v < 10 ? 1 : 0)} ${v < 2 ? 'milhão' : 'milhões'} de anos-luz`; }
  return 'início do universo';
}
// "cartela" do valor: rótulo espaçado + número fino e grande
function cartela(ctx, t, t0, t1, label, value, y = 1280, col = '#ffffff') {
  const a = win(t, t0, t1, 0.35, 0.4); if (a <= 0) return;
  const p = easeOutCubic((t - t0) / 0.6);
  ctx.save(); ctx.globalAlpha = a; ctx.translate(540, y + (1 - p) * 30);
  text(ctx, label, 0, -86, { font: `600 26px ${FONT}`, color: 'rgba(220,228,255,0.85)', align: 'center', spacing: 9 });
  let fs = 132; ctx.font = `200 ${fs}px ${FONT}`; while (ctx.measureText(value).width > 960 && fs > 60) { fs -= 4; ctx.font = `200 ${fs}px ${FONT}`; }
  ctx.shadowColor = 'rgba(0,0,0,0.6)'; ctx.shadowBlur = 30;
  text(ctx, value, 0, 40, { font: `200 ${fs}px ${FONT}`, color: col, align: 'center' });
  ctx.restore();
}
function poem(ctx, lines, y, a, size = 92) {
  if (a <= 0) return;
  ctx.save(); ctx.globalAlpha = a; ctx.shadowColor = 'rgba(0,0,0,0.8)'; ctx.shadowBlur = 40;
  lines.forEach((ln, k) => text(ctx, ln, 540, y + k * size * 1.18, { font: `italic 400 ${size}px ${SERIF}`, color: '#fff7e8', align: 'center' }));
  ctx.restore();
}

// ---------------------------------------------------------------- cenas
const REW = TL.rew;
function sceneHook(ctx, t, lt, i) {
  sky(ctx, lt, [120, 60, 20]);
  const gone = Wt('hook', 3) + 0.1, end = REW[0];
  const rp = sstep(REW[0], REW[1], lt);
  const sunA = 1 - (lt > gone && rp < 0.5 ? sstep(gone, gone + 0.25, lt) : 0) * (1 - rp);
  const sx = 540, sy = 760, ex = 830, ey = 1330;
  // Terra (pequena)
  astro(ctx, IMG.terra, ex, ey, 190, { rot: lt * 0.05 });
  // Sol
  if (sunA > 0.01) {
    bloom(ctx, sx, sy, 520, [255, 140, 40], 0.55 * sunA);
    astro(ctx, IMG.sol, sx, sy, 720, { sx: 0.5, sy: 0.5, crop: 1.0, alpha: sunA, rot: lt * 0.03 });
  }
  // flash no instante em que some
  if (lt > gone && lt < gone + 0.5) glowAt(ctx, sx, sy, 600, [255, 230, 190], 0.9 * (1 - (lt - gone) / 0.5));
  // a última luz do Sol ainda viajando até a Terra
  if (lt > gone && rp < 1) {
    const q = clamp((lt - gone) / (end - gone)) * (1 - rp);
    const R = lerp(60, Math.hypot(ex - sx, ey - sy) + 40, q);
    ctx.save(); ctx.globalCompositeOperation = 'lighter';
    for (let k = 0; k < 3; k++) { ctx.strokeStyle = `rgba(255,${200 - k * 30},${120 - k * 30},${0.55 - k * 0.15})`; ctx.lineWidth = 10 - k * 3; ctx.beginPath(); ctx.arc(sx, sy, R - k * 14, 0, 6.283); ctx.stroke(); }
    ctx.restore();
    // a Terra continua vendo o Sol
    const remain = Math.max(0, 500 * (1 - q)), m = Math.floor(remain / 60), s = Math.floor(remain % 60);
    const la = sstep(Wt('hook', 5) - 0.2, Wt('hook', 5) + 0.2, lt);
    if (la > 0) {
      glowAt(ctx, ex, ey, 180, [255, 200, 120], 0.35 * la * (1 - q));
      text(ctx, 'A TERRA AINDA VÊ O SOL', ex - 20, ey - 150, { font: `700 26px ${FONT}`, color: 'rgba(255,230,200,0.9)', align: 'center', spacing: 4, alpha: la });
      text(ctx, `${m}:${String(s).padStart(2, '0')}`, ex - 20, ey - 92, { font: `200 64px ${FONT}`, color: '#fff', align: 'center', alpha: la });
    }
  }
}
function sceneLuz(ctx, t, lt, i) {
  plate(ctx, IMG.nascer_do_sol_iss, clamp(lt / 6), { fx: 0.47, fy: 0.42, z0: 1.15, z1: 1.35 });
  const g = ctx.createLinearGradient(0, 900, 0, H); g.addColorStop(0, 'rgba(2,3,9,0)'); g.addColorStop(1, 'rgba(2,3,9,0.9)'); ctx.fillStyle = g; ctx.fillRect(0, 900, W, H - 900);
  streaks(ctx, lt, 0.35, 520, 700);
  const a = sstep(Wt('luz', 2) - 0.2, Wt('luz', 2) + 0.3, t);
  ctx.save(); ctx.globalAlpha = a;
  text(ctx, 'VELOCIDADE DA LUZ', 540, 1160, { font: `600 28px ${FONT}`, color: 'rgba(230,236,255,0.9)', align: 'center', spacing: 10 });
  text(ctx, '300.000 km/s', 540, 1290, { font: `200 128px ${FONT}`, color: '#fff', align: 'center', shadow: 30 });
  ctx.restore();
  beam(ctx, 520, 700, lt, sstep(Wt('luz', 9), Wt('luz', 13), t));
}
function sceneLua(ctx, t, lt, i) {
  sky(ctx, lt, [60, 80, 140]);
  const s = 1 + 0.03 * Math.sin(lt * 0.5);
  bloom(ctx, 540, 760, 520, [180, 200, 255], 0.22);
  astro(ctx, IMG.lua, 540, 760, 680 * s, { rot: -0.15 + lt * 0.01 });
  beam(ctx, 540, 760, lt, sstep(L.lua.start, L.lua.start + 0.6, t), [220, 230, 255]);
  cartela(ctx, t, Wt('lua', 9) - 0.2, L.lua.end + 0.6, 'A LUZ QUE VOCÊ VÊ SAIU HÁ', '1,3 s');
}
function sceneSol(ctx, t, lt, i) {
  sky(ctx, lt, [140, 60, 20]);
  bloom(ctx, 540, 740, 640, [255, 130, 40], 0.5);
  astro(ctx, IMG.sol, 540, 740, 900, { rot: 0.4 + lt * 0.02 });
  beam(ctx, 540, 740, lt, 1, [255, 220, 170]);
  cartela(ctx, t, Wt('sol', 6) - 0.2, L.sol.end + 0.6, 'A LUZ QUE VOCÊ VÊ SAIU HÁ', '8 min 20 s', 1300, '#ffe2b8');
}
function sceneProxima(ctx, t, lt, i) {
  sky(ctx, lt, [130, 50, 50]);
  const z = 1 + 0.08 * clamp(lt / 5);
  astro(ctx, IMG.proxima, 540, 760, 1000 * z, { rot: 0.0 });
  bloom(ctx, 540, 760, 260, [255, 170, 120], 0.35 + 0.05 * Math.sin(lt * 3));
  beam(ctx, 540, 760, lt, 1, [255, 200, 170]);
  text(ctx, 'PROXIMA CENTAURI', 540, 520, { font: `600 30px ${FONT}`, color: 'rgba(255,225,210,0.85)', align: 'center', spacing: 10, alpha: sstep(L.proxima.start, L.proxima.start + 0.5, t) });
  cartela(ctx, t, Wt('proxima', 14) - 0.2, L.proxima.end + 0.6, 'VOCÊ A VÊ COMO ELA ERA HÁ', '4,2 anos', 1300, '#ffd9c8');
}
// Órion: posições aproximadas (Betelgeuse na origem), em unidades do desenho
const ORION = { betelgeuse: [0, 0], meissa: [0.32, -0.3], bellatrix: [0.66, 0.04], alnitak: [0.26, 0.6], alnilam: [0.36, 0.56], mintaka: [0.46, 0.52], saiph: [0.2, 1.06], rigel: [0.76, 1.0] };
const ORION_LINES = [['betelgeuse', 'meissa'], ['meissa', 'bellatrix'], ['betelgeuse', 'alnitak'], ['bellatrix', 'mintaka'], ['alnitak', 'alnilam'], ['alnilam', 'mintaka'], ['alnitak', 'saiph'], ['mintaka', 'rigel']];
function sceneBetelgeuse(ctx, t, lt, i) {
  sky(ctx, lt, [150, 40, 30]);
  // câmera: começa na constelação inteira e aproxima até Betelgeuse
  const zq = easeInOutCubic(clamp((t - L.betelgeuse.start) / 2.2));
  const scale = lerp(520, 2600, zq), bx = lerp(330, 540, zq), by = lerp(560, 760, zq);
  ctx.save();
  const ca = 1 - sstep(0.55, 0.95, zq);
  ctx.globalAlpha = ca; ctx.strokeStyle = 'rgba(200,215,255,0.55)'; ctx.lineWidth = 2.5; ctx.setLineDash([6, 8]);
  for (const [a, b] of ORION_LINES) { const A = ORION[a], Bp = ORION[b]; ctx.beginPath(); ctx.moveTo(bx + A[0] * scale, by + A[1] * scale); ctx.lineTo(bx + Bp[0] * scale, by + Bp[1] * scale); ctx.stroke(); }
  ctx.setLineDash([]);
  for (const [k, [x, y]] of Object.entries(ORION)) {
    const px = bx + x * scale, py = by + y * scale, big = k === 'betelgeuse' || k === 'rigel';
    glowAt(ctx, px, py, big ? 40 : 26, k === 'betelgeuse' ? [255, 120, 60] : [190, 210, 255], 0.9);
    ctx.fillStyle = '#fff'; ctx.beginPath(); ctx.arc(px, py, big ? 5 : 3.5, 0, 6.283); ctx.fill();
  }
  text(ctx, 'ÓRION', bx + 0.42 * scale, by + 1.3 * scale, { font: `600 30px ${FONT}`, color: 'rgba(210,220,255,0.8)', align: 'center', spacing: 12 });
  ctx.restore();
  const ha = sstep(0.35, 0.9, zq);
  bloom(ctx, 540, 760, 560 * ha, [255, 90, 40], 0.45 * ha);
  astro(ctx, IMG.betelgeuse, 540, 760, 820 * ha, { alpha: ha, rot: lt * 0.03 });
  text(ctx, 'BETELGEUSE', 540, 470, { font: `600 30px ${FONT}`, color: 'rgba(255,215,200,0.9)', align: 'center', spacing: 10, alpha: ha });
  cartela(ctx, t, Wt('betelgeuse', 17) - 0.2, L.betelgeuse.end + 0.6, 'SE ELA EXPLODIR HOJE, VOCÊ SÓ VÊ DAQUI A', 'mais de 500 anos', 1310, '#ffcfbf');
}
function sceneAndromeda(ctx, t, lt, i) {
  sky(ctx, lt, [70, 60, 160]);
  bloom(ctx, 540, 800, 700, [120, 140, 255], 0.25);
  astro(ctx, IMG.andromeda, 540, 800, 1250 * (1 + 0.06 * clamp(lt / 7)), { rot: -0.35 + lt * 0.01, crop: 0.92 });
  beam(ctx, 540, 800, lt, 0.8, [200, 210, 255]);
  cartela(ctx, t, Wt('andromeda', 10) - 0.2, Wt('andromeda', 16) + 0.1, 'ESSA LUZ SAIU DE LÁ HÁ', '2,5 milhões de anos', 1300, '#dfe3ff');
  const fa = win(t, Wt('andromeda', 16) - 0.1, L.andromeda.end + 0.6, 0.4, 0.4);
  if (fa > 0) {
    poem(ctx, ['nossos ancestrais', 'ainda nem dominavam o fogo'], 1230, fa, 62);
    const r = rng(9);
    ctx.save(); ctx.globalCompositeOperation = 'lighter';
    for (let k = 0; k < 40; k++) { const x = 300 + r() * 480, sp = 60 + r() * 120, ph = r() * 10; const y = 1480 - ((lt * sp + ph * 50) % 400); ctx.globalAlpha = fa * 0.7 * clamp((1480 - y) / 80) * (1 - (1480 - y) / 400); ctx.fillStyle = '#ffb060'; ctx.beginPath(); ctx.arc(x + Math.sin(lt * 2 + ph) * 12, y, 2 + r() * 2.5, 0, 6.283); ctx.fill(); }
    ctx.restore();
  }
}
function sceneWebb(ctx, t, lt, i) {
  const p = clamp(lt / 6.5);
  plate(ctx, IMG.webb_campo_profundo, easeInOutCubic(p), { fx: 0.43, fy: 0.42, z0: 1.05, z1: 1.9 });
  const g = ctx.createLinearGradient(0, 1000, 0, H); g.addColorStop(0, 'rgba(2,3,9,0)'); g.addColorStop(1, 'rgba(2,3,9,0.92)'); ctx.fillStyle = g; ctx.fillRect(0, 1000, W, H - 1000);
  text(ctx, 'TELESCÓPIO JAMES WEBB', 540, 520, { font: `600 28px ${FONT}`, color: 'rgba(255,236,200,0.9)', align: 'center', spacing: 10, alpha: sstep(Wt('webb', 2), Wt('webb', 4, 't1'), t), shadow: 12 });
  cartela(ctx, t, Wt('webb', 12) - 0.2, Wt('webb', 16), 'LUZ QUE VIAJOU POR MAIS DE', '13 bilhões de anos', 1300, '#ffe9c4');
  poem(ctx, ['quase desde o começo', 'do universo'], 1230, win(t, Wt('webb', 16) - 0.1, L.webb.end + 0.7, 0.4, 0.4), 70);
}
function sceneVirada(ctx, t, lt, i) {
  const p = clamp(lt / 8);
  plate(ctx, IMG.cupula, easeInOutCubic(p), { fx: 0.66, fy: 0.42, z0: 1.12, z1: 1.45 });
  const g = ctx.createLinearGradient(0, 1050, 0, H); g.addColorStop(0, 'rgba(2,3,9,0)'); g.addColorStop(1, 'rgba(2,3,9,0.92)'); ctx.fillStyle = g; ctx.fillRect(0, 1050, W, H - 1050);
  // "1 metro": régua fina até a pessoa
  const ma = win(t, Wt('virada', 13) - 0.2, Wt('virada', 22), 0.3, 0.3);
  if (ma > 0) {
    ctx.save(); ctx.globalAlpha = ma; ctx.strokeStyle = '#fff'; ctx.lineWidth = 3;
    const x0 = 140, x1 = lerp(140, 760, easeOutCubic((t - Wt('virada', 13)) / 0.6)), y = 1180;
    ctx.beginPath(); ctx.moveTo(x0, y); ctx.lineTo(x1, y); ctx.moveTo(x0, y - 18); ctx.lineTo(x0, y + 18); ctx.moveTo(x1, y - 18); ctx.lineTo(x1, y + 18); ctx.stroke();
    text(ctx, '1 metro', (x0 + x1) / 2, y - 30, { font: `300 52px ${FONT}`, color: '#fff', align: 'center', shadow: 16 });
    ctx.restore();
  }
  cartela(ctx, t, Wt('virada', 22) - 0.2, L.virada.end + 0.7, 'VOCÊ A VÊ COMO ELA ERA HÁ', '0,000000003 s', 1300);
}
function sceneFecho(ctx, t, lt, i) {
  plate(ctx, IMG.via_lactea_iss, clamp(lt / 6), { fx: 0.62, fy: 0.42, z0: 1.12, z1: 1.25 });
  ctx.fillStyle = 'rgba(2,3,9,0.35)'; ctx.fillRect(0, 0, W, H);
  const a1 = win(t, Wt('fecho', 0) - 0.1, Wt('fecho', 7) - 0.1, 0.5, 0.35);
  const a2 = win(t, Wt('fecho', 7), L.cta.start + 0.3, 0.6, 0.5);
  poem(ctx, ['Tudo o que você vê', 'já aconteceu.'], 860, a1, 88);
  poem(ctx, ['Ninguém nunca viu', 'o presente.'], 860, a2, 96);
}

// ---------------------------------------------------------------- HUD
function drawHUD(ctx, t, i) {
  const tau = TL.tau[i], x = 60, y = 186, w = 960, h = 236;
  ctx.save();
  ctx.fillStyle = 'rgba(4,6,14,0.55)'; rr(ctx, x, y, w, h, 34); ctx.fill();
  ctx.strokeStyle = 'rgba(255,255,255,0.12)'; ctx.lineWidth = 1.5; rr(ctx, x, y, w, h, 34); ctx.stroke();
  const cells = [['A LUZ SAIU HÁ', fmtTau(tau)], ['DISTÂNCIA', fmtDist(tau)]];
  cells.forEach(([lab, val], k) => {
    const cx = x + 240 + k * 480;
    if (k) { ctx.fillStyle = 'rgba(255,255,255,0.1)'; ctx.fillRect(x + 480, y + 36, 1.5, h - 72); }
    text(ctx, lab, cx, y + 64, { font: `600 24px ${FONT}`, color: 'rgba(200,212,240,0.85)', align: 'center', spacing: 7 });
    let fs = 64; ctx.font = `300 ${fs}px ${FONT}`; while (ctx.measureText(val).width > 430 && fs > 26) { fs -= 2; ctx.font = `300 ${fs}px ${FONT}`; }
    text(ctx, val, cx, y + 158, { font: `300 ${fs}px ${FONT}`, color: '#fff', align: 'center' });
  });
  ctx.restore();
}
const CRED_SCENE = { hook: 'sol', luz: 'nascer_do_sol_iss', lua: 'lua', sol: 'sol', proxima: 'proxima', betelgeuse: 'betelgeuse', andromeda: 'andromeda', webb: 'webb_campo_profundo', virada: 'cupula', fecho: 'via_lactea_iss' };

// ---------------------------------------------------------------- composição
const SCENE_FN = { hook: sceneHook, luz: sceneLuz, lua: sceneLua, sol: sceneSol, proxima: sceneProxima, betelgeuse: sceneBetelgeuse, andromeda: sceneAndromeda, webb: sceneWebb, virada: sceneVirada, fecho: sceneFecho, cta: sceneCTA };
const SCENES = [
  { name: 'hook', t0: -1, local0: 0 },
  { name: 'luz', t0: L.luz.start - 0.4 }, { name: 'lua', t0: L.lua.start - 0.4 }, { name: 'sol', t0: L.sol.start - 0.35 },
  { name: 'proxima', t0: L.proxima.start - 0.35 }, { name: 'betelgeuse', t0: L.betelgeuse.start - 0.35 }, { name: 'andromeda', t0: L.andromeda.start - 0.4 },
  { name: 'webb', t0: L.webb.start - 0.4 }, { name: 'virada', t0: L.virada.start - 0.45 }, { name: 'fecho', t0: L.fecho.start - 0.5 },
  { name: 'cta', t0: L.cta.start - 0.4 },
  { name: 'hook', t0: TL.total - 0.5, local0: TL.total, fade: true },
];
const TR = 0.7;
const STARS = STARL[1];
const vignette = (() => { const c = createCanvas(W, H), x = c.getContext('2d'); const g = x.createRadialGradient(W / 2, H * 0.46, H * 0.22, W / 2, H * 0.5, H * 0.8); g.addColorStop(0, 'rgba(0,0,0,0)'); g.addColorStop(1, 'rgba(0,0,0,0.7)'); x.fillStyle = g; x.fillRect(0, 0, W, H); return c; })();
const GRAIN = Array.from({ length: 3 }, (_, k) => { const c = createCanvas(540, 960), x = c.getContext('2d'), im = x.createImageData(540, 960), r = rng(60 + k); for (let q = 0; q < im.data.length; q += 4) { const v = r() * 255; im.data[q] = im.data[q + 1] = im.data[q + 2] = v; im.data[q + 3] = 14; } x.putImageData(im, 0, 0); return c; });
const canvas = createCanvas(W, H), ctx = canvas.getContext('2d');
const bufA = createCanvas(W, H), ctxA = bufA.getContext('2d');
const bufB = createCanvas(W, H), ctxB = bufB.getContext('2d');
const scratch = createCanvas(W, H), sctx = scratch.getContext('2d');
function renderScene(target, idx, t, i) {
  const sc = SCENES[idx], lt = t - (sc.local0 !== undefined ? sc.local0 : sc.t0);
  target.save(); target.setTransform(1, 0, 0, 1, 0, 0); SCENE_FN[sc.name](target, t, lt, i); target.restore();
}
function drawScaled(src, s, a) {
  ctx.save(); ctx.globalAlpha = a; ctx.translate(W / 2, H * 0.42); ctx.scale(s, s); ctx.translate(-W / 2, -H * 0.42); ctx.drawImage(src, 0, 0); ctx.restore();
}
function frame(i, opts = {}) {
  const t = i / FPS;
  let cur = 0; for (let k = 0; k < SCENES.length; k++) if (t >= SCENES[k].t0) cur = k;
  ctx.save(); ctx.fillStyle = '#000'; ctx.fillRect(-40, -40, W + 80, H + 80);
  const sc = SCENES[cur], into = t - sc.t0;
  if (cur > 0 && into < TR) {
    // recuo pelo espaço: a cena anterior se afasta, a nova chega, com rastros de estrelas
    const p = easeInOutCubic(into / TR);
    renderScene(ctxA, cur - 1, t, i); renderScene(ctxB, cur, t, i);
    if (sc.fade) { ctx.drawImage(bufA, 0, 0); ctx.globalAlpha = sstep(0, 0.6, into / TR); ctx.drawImage(bufB, 0, 0); ctx.globalAlpha = 1; }
    else {
      drawScaled(bufA, lerp(1, 0.72, p), 1 - p);
      drawScaled(bufB, lerp(1.35, 1, p), p);
      streaks(ctx, t, Math.sin(Math.PI * p) * 0.9);
    }
  } else { renderScene(ctxA, cur, t, i); ctx.drawImage(bufA, 0, 0); }
  // rebobinar (assinatura da série)
  const ra = win(t, REW[0] - 0.05, REW[1] + 0.05, 0.08, 0.12);
  if (ra > 0) {
    sctx.clearRect(0, 0, W, H); sctx.drawImage(canvas, 0, 0);
    const r = rng(Math.floor(t * 60));
    for (let k = 0; k < 7; k++) { const yy = r() * H, hh = 20 + r() * 120, dx = (r() - 0.5) * 80 * ra; ctx.drawImage(scratch, 0, yy, W, hh, dx, yy, W, hh); }
    ctx.save(); ctx.globalAlpha = 0.18 * ra; ctx.fillStyle = '#000'; for (let yy = (t * 400) % 6; yy < H; yy += 6) ctx.fillRect(0, yy, W, 2); ctx.restore();
    text(ctx, '◀◀', 90, 560, { font: `900 72px ${FONT}`, color: '#fff', alpha: ra * (0.6 + 0.4 * Math.sin(t * 20)), stroke: 8 });
  }
  ctx.save(); ctx.globalCompositeOperation = 'overlay'; ctx.drawImage(GRAIN[i % 3], 0, 0, W, H); ctx.restore();
  ctx.drawImage(vignette, 0, 0);
  drawHUD(ctx, t, i);
  const ck = CRED_SCENE[SCENES[cur].name];
  if (ck && !(cur > 0 && into < TR)) text(ctx, CREDITO[ck], W - 60, 1452, { font: `500 19px ${FONT}`, color: 'rgba(220,228,255,0.62)', align: 'right', shadow: 8 });
  const pg = TL.pages.find(p => t >= p.t0 && t < p.t1);
  if (!opts.noCaptions && !(pg && pg.line === 'fecho')) drawCaptions(ctx, t);
  ctx.restore();
}

// ---------------------------------------------------------------- main
(async () => {
  await loadImages();
  const argv = process.argv.slice(2), pi = argv.indexOf('--preview');
  if (argv.includes('--capa')) {
    ctx.fillStyle = '#000'; ctx.fillRect(0, 0, W, H);
    plate(ctx, IMG.webb_campo_profundo, 0.55, { fx: 0.43, fy: 0.42, z0: 1.05, z1: 1.9 });
    const g = ctx.createLinearGradient(0, 700, 0, H); g.addColorStop(0, 'rgba(2,3,9,0)'); g.addColorStop(0.45, 'rgba(2,3,9,0.85)'); g.addColorStop(1, 'rgba(2,3,9,0.97)');
    ctx.fillStyle = g; ctx.fillRect(0, 700, W, H - 700);
    ctx.drawImage(vignette, 0, 0);
    text(ctx, 'TUDO O QUE VOCÊ VÊ JÁ É PASSADO', W / 2, 1180, { font: `600 30px ${FONT}`, color: 'rgba(230,236,255,0.9)', align: 'center', spacing: 9 });
    poem(ctx, ['Você nunca viu', 'o presente.'], 1330, 1, 116);
    text(ctx, 'Imagem: NASA, ESA, CSA, STScI (James Webb)', W - 60, 1700, { font: `500 20px ${FONT}`, color: 'rgba(220,228,255,0.6)', align: 'right' });
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
