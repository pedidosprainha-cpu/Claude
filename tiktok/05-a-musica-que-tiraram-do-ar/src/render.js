// Vídeo 05 — "A música que tiraram do ar em 1992"
// Documentário com acervo real: fotos e vídeo de arquivo com licenças livres (Wikimedia Commons / Agência Brasil /
// Senado Federal / EBC), com crédito na tela. Tipografia, carimbos e interface do rádio são desenhados aqui.
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
const C = { yellow: '#FFD23F', cyan: '#4FD1FF', red: '#FF3B4E', orange: '#FF8A3D', ink: '#070A14', label: '#b8ab92' };
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



// ================================================================ vídeo 05: documentário com acervo real
const popIn = (t, t0, d = 0.38) => t < t0 ? 0 : easeOutBack((t - t0) / d);
const K = { paper: '#efe6d2', ink: '#14110d', red: '#d7263d', yellow: '#FFD23F', green: '#35d07f', cyan: '#4FD1FF' };
const SERIF = '"Liberation Serif"', TYPE = '"Courier 10 Pitch"';
const R0 = rng(505);
const STARS = Array.from({ length: 300 }, () => ({ x: R0() * W, y: R0() * H, r: 0.4 + R0() * R0() * 2.2, a: 0.25 + R0() * 0.75, tw: R0() * 6.28 }));

// ---------------------------------------------------------------- acervo (fotos e vídeo de arquivo, com créditos)
const IMG = {};
const CRED = {
  collor_retrato_1992: 'Foto: Ubirajara Dettimar / Agência Brasil · CC BY 3.0 BR',
  fita_cassete: 'Foto: Tim Reckmann · CC BY 2.0 · imagem ilustrativa',
  collor_carro_aberto: 'Foto: Roberto Barroso / Agência Brasil · CC BY 3.0 BR',
  collor_corrida: 'Foto: Antonio Cruz / Agência Brasil · CC BY 3.0 BR',
  carapintadas_planalto: 'Foto: Sergio Lima / Agência Brasil · CC BY 3.0 BR',
  carapintadas_senado: 'Foto: Senado Federal · CC BY 2.0',
  esplanada_impeachment: 'Foto: Senado Federal · CC BY 2.0',
  collor_deixa_presidencia: 'Foto: Elza Fiuza / Agência Brasil · CC BY 3.0 BR',
  gabriel_2003: 'Foto: Ana Nascimento / Agência Brasil · CC BY 3.0 BR',
  confisco: 'Vídeo: EBC (arquivo) · CC BY 3.0 BR',
};
let CONF = [];
const MISSING = [];
function placeholder(label) {
  const c = createCanvas(800, 560), x = c.getContext('2d');
  x.fillStyle = '#2a2622'; x.fillRect(0, 0, 800, 560); x.fillStyle = '#d7263d'; x.font = `900 44px ${FONT}`; x.textAlign = 'center';
  x.fillText('ARQUIVO PENDENTE', 400, 260); x.fillStyle = '#ccc'; x.font = `600 28px ${FONT}`; x.fillText(label, 400, 320); return c;
}
async function loadMedia() {
  for (const k of Object.keys(CRED)) {
    if (k === 'confisco') continue;
    const f = path.join(ROOT, 'assets', k + '.jpg');
    if (fs.existsSync(f)) IMG[k] = await loadImage(f); else { IMG[k] = placeholder(k); MISSING.push(k); }
  }
  const dir = path.join(ROOT, 'build', 'confisco');
  const files = fs.existsSync(dir) ? fs.readdirSync(dir).filter(f => f.endsWith('.jpg')).sort() : [];
  for (const f of files) CONF.push(await loadImage(path.join(dir, f)));
  if (!CONF.length) { CONF.push(placeholder('confisco_1990.webm')); MISSING.push('confisco'); }
  if (MISSING.length) console.log('AVISO: arquivos de acervo ausentes:', MISSING.join(', '));
}

// tratamento de arquivo: recorte "cover", Ken Burns, tom envelhecido
const photoBuf = createCanvas(W, H), pctx = photoBuf.getContext('2d');
function photo(ctx, img, x, y, w, h, o = {}) {
  const { p = 0, z0 = 1.04, z1 = 1.14, fx = 0.5, fy = 0.45, dx = 0, dy = 0, tone = 0.35, bw = false, alpha = 1, credit = null, border = 0, rot = 0, shadow = true } = o;
  const z = lerp(z0, z1, p);
  const s = Math.max(w / img.width, h / img.height) * z;
  const iw = img.width * s, ih = img.height * s;
  const ix = x + w / 2 - iw * fx + (iw * fx - w / 2) * 0 + dx * p, iy = y + h / 2 - ih * fy + dy * p;
  ctx.save(); ctx.globalAlpha *= alpha;
  ctx.translate(x + w / 2, y + h / 2); ctx.rotate(rot); ctx.translate(-(x + w / 2), -(y + h / 2));
  if (border) {
    if (shadow) { ctx.shadowColor = 'rgba(0,0,0,0.6)'; ctx.shadowBlur = 40; ctx.shadowOffsetY = 18; }
    ctx.fillStyle = '#f4efe4'; ctx.fillRect(x - border, y - border, w + 2 * border, h + 2 * border + (o.caption ? 70 : 0));
    ctx.shadowBlur = 0; ctx.shadowOffsetY = 0;
  }
  ctx.save(); ctx.beginPath(); ctx.rect(x, y, w, h); ctx.clip();
  ctx.filter = bw ? 'grayscale(1) contrast(1.15) brightness(1.02)' : `sepia(${tone}) saturate(${1 - tone * 0.6}) contrast(1.08)`;
  ctx.drawImage(img, ix, iy, iw, ih);
  ctx.filter = 'none';
  const v = ctx.createRadialGradient(x + w / 2, y + h / 2, Math.min(w, h) * 0.3, x + w / 2, y + h / 2, Math.max(w, h) * 0.75);
  v.addColorStop(0, 'rgba(0,0,0,0)'); v.addColorStop(1, 'rgba(0,0,0,0.45)');
  ctx.fillStyle = v; ctx.fillRect(x, y, w, h);
  ctx.restore();
  if (o.caption) text(ctx, o.caption, x + 10, y + h + 52, { font: `700 34px ${TYPE}`, color: '#2a241c' });
  ctx.restore();
  if (credit) creditLine(ctx, credit, x + (border ? 0 : 0), y + h - 10 + (o.caption ? 0 : 0), w, alpha);
}
function creditLine(ctx, s, x, yBottom, w, a = 1) {
  ctx.save(); ctx.globalAlpha *= a; ctx.font = `600 21px ${FONT}`;
  const tw = ctx.measureText(s).width;
  ctx.fillStyle = 'rgba(0,0,0,0.6)'; ctx.fillRect(x + 8, yBottom - 30, tw + 20, 28);
  ctx.fillStyle = 'rgba(255,255,255,0.88)'; ctx.fillText(s, x + 18, yBottom - 9);
  ctx.restore();
}

// ---------------------------------------------------------------- textura de filme (grão, poeira, riscos)
const GRAIN = Array.from({ length: 4 }, (_, k) => {
  const c = createCanvas(540, 960), x = c.getContext('2d'), img = x.createImageData(540, 960), r = rng(30 + k);
  for (let i = 0; i < img.data.length; i += 4) { const v = r() * 255; img.data[i] = img.data[i + 1] = img.data[i + 2] = v; img.data[i + 3] = 26; }
  x.putImageData(img, 0, 0); return c;
});
function filmFx(ctx, i, amount = 1) {
  ctx.save(); ctx.globalCompositeOperation = 'overlay'; ctx.globalAlpha = 0.8 * amount;
  ctx.drawImage(GRAIN[i % 4], 0, 0, W, H); ctx.restore();
  const r = rng(i * 13 + 7);
  ctx.save();
  for (let k = 0; k < 6; k++) { if (r() < 0.55) continue; ctx.globalAlpha = 0.25 * amount; ctx.fillStyle = r() < 0.5 ? '#fff' : '#000'; ctx.beginPath(); ctx.arc(r() * W, r() * H, 1 + r() * 3, 0, 6.283); ctx.fill(); }
  if (r() < 0.25) { ctx.globalAlpha = 0.18 * amount; ctx.fillStyle = '#fff'; ctx.fillRect(r() * W, 0, 1.5, H); }
  ctx.restore();
}

// ---------------------------------------------------------------- tipografia de jornal, carimbos e documentos
function stamp(ctx, s, x, y, size, col, rot, p, a = 1) {
  if (p <= 0 || a <= 0) return;
  const sc = lerp(2.2, 1, easeOutCubic(clamp(p)));
  ctx.save(); ctx.globalAlpha *= a * clamp(p * 3); ctx.translate(x, y); ctx.rotate(rot); ctx.scale(sc, sc);
  ctx.font = `900 ${size}px ${FONT}`; const tw = ctx.measureText(s).width;
  ctx.strokeStyle = col; ctx.lineWidth = size * 0.09; rr(ctx, -tw / 2 - size * 0.35, -size * 0.75, tw + size * 0.7, size * 1.1, size * 0.15); ctx.stroke();
  ctx.fillStyle = col; ctx.textAlign = 'center'; ctx.fillText(s, 0, size * 0.2);
  // textura de tinta falhada
  ctx.globalCompositeOperation = 'destination-out'; const r = rng(s.length * 7);
  for (let k = 0; k < 40; k++) { ctx.globalAlpha = 0.35; ctx.beginPath(); ctx.arc((r() - 0.5) * (tw + size * 0.6), (r() - 0.5) * size, 1 + r() * size * 0.05, 0, 6.283); ctx.fill(); }
  ctx.restore();
}
function newsprint(ctx, x, y, w, h, rot = 0) {
  ctx.save(); ctx.translate(x + w / 2, y + h / 2); ctx.rotate(rot); ctx.translate(-w / 2, -h / 2);
  ctx.shadowColor = 'rgba(0,0,0,0.55)'; ctx.shadowBlur = 40; ctx.shadowOffsetY = 18;
  ctx.fillStyle = K.paper; ctx.fillRect(0, 0, w, h); ctx.shadowBlur = 0; ctx.shadowOffsetY = 0;
  const g = ctx.createRadialGradient(w / 2, h / 2, w * 0.2, w / 2, h / 2, w * 0.8); g.addColorStop(0, 'rgba(255,250,235,0)'); g.addColorStop(1, 'rgba(120,95,60,0.25)');
  ctx.fillStyle = g; ctx.fillRect(0, 0, w, h);
  ctx.restore();
}
function typewriter(s, p) { return s.slice(0, Math.floor(s.length * clamp(p))); }
function headline(ctx, lines, x, y, size, p, o = {}) {
  ctx.save(); ctx.globalAlpha *= clamp(p * 2);
  lines.forEach((ln, k) => {
    const q = clamp((p - k * 0.15) / 0.5); if (q <= 0) return;
    ctx.save(); ctx.translate(x, y + k * size * 1.02 + (1 - easeOutCubic(q)) * 30);
    text(ctx, ln, 0, 0, { font: `700 ${size}px ${SERIF}`, color: o.color || K.ink, align: o.align || 'center', alpha: q });
    ctx.restore();
  });
  ctx.restore();
}

// ---------------------------------------------------------------- mostrador de rádio FM (interface)
function radioDial(ctx, x, y, w, freq, onAir, lt, a = 1) {
  if (a <= 0) return;
  const h = 170;
  ctx.save(); ctx.globalAlpha *= a; ctx.translate(x, y);
  ctx.fillStyle = 'rgba(10,9,8,0.88)'; rr(ctx, -w / 2, -h / 2, w, h, 26); ctx.fill();
  ctx.strokeStyle = 'rgba(255,255,255,0.12)'; ctx.lineWidth = 2; rr(ctx, -w / 2, -h / 2, w, h, 26); ctx.stroke();
  const sx = -w / 2 + 50, ex = w / 2 - 50, sy = 6;
  const g = ctx.createLinearGradient(0, sy - 40, 0, sy + 40); g.addColorStop(0, 'rgba(255,190,90,0.12)'); g.addColorStop(1, 'rgba(255,190,90,0.03)');
  ctx.fillStyle = g; rr(ctx, sx - 20, sy - 44, ex - sx + 40, 88, 12); ctx.fill();
  for (let f = 88; f <= 108; f += 0.5) {
    const px = lerp(sx, ex, (f - 88) / 20), major = f % 2 === 0;
    ctx.strokeStyle = 'rgba(255,220,170,0.7)'; ctx.lineWidth = major ? 3 : 1.5;
    ctx.beginPath(); ctx.moveTo(px, sy + 10); ctx.lineTo(px, sy + (major ? 34 : 24)); ctx.stroke();
    if (major) text(ctx, String(f), px, sy - 14, { font: `700 24px ${TYPE}`, color: 'rgba(255,220,170,0.85)', align: 'center' });
  }
  const nx = lerp(sx, ex, (freq - 88) / 20);
  ctx.strokeStyle = K.red; ctx.lineWidth = 5; ctx.shadowColor = 'rgba(255,40,60,0.9)'; ctx.shadowBlur = 14;
  ctx.beginPath(); ctx.moveTo(nx, sy - 42); ctx.lineTo(nx, sy + 42); ctx.stroke(); ctx.shadowBlur = 0;
  text(ctx, 'FM', -w / 2 + 26, -h / 2 + 40, { font: `800 28px ${FONT}`, color: 'rgba(255,220,170,0.8)' });
  // lâmpada NO AR
  const lx = w / 2 - 120, ly = -h / 2 + 32;
  ctx.fillStyle = onAir > 0.5 ? K.red : '#3a1a1e'; rr(ctx, lx - 10, ly - 20, 120, 38, 8); ctx.fill();
  if (onAir > 0.5) glowAt(ctx, lx + 50, ly, 90, [255, 50, 70], 0.5 + 0.2 * Math.sin(lt * 8));
  text(ctx, 'NO AR', lx + 50, ly + 9, { font: `900 24px ${FONT}`, color: onAir > 0.5 ? '#fff' : 'rgba(255,255,255,0.3)', align: 'center' });
  ctx.restore();
}
function waves(ctx, x, y, lt, a) {
  if (a <= 0) return;
  ctx.save(); ctx.strokeStyle = K.yellow; ctx.lineCap = 'round';
  for (let k = 0; k < 3; k++) { const ph = ((lt * 1.2 + k / 3) % 1); ctx.globalAlpha = a * (1 - ph); ctx.lineWidth = 6; ctx.beginPath(); ctx.arc(x, y, 40 + ph * 160, -2.2, -0.9); ctx.stroke(); }
  ctx.restore();
}

// ---------------------------------------------------------------- cenas
function darkBg(ctx, a = '#16130f', b = '#050403') { const g = ctx.createRadialGradient(W / 2, H * 0.45, 100, W / 2, H * 0.5, H * 0.8); g.addColorStop(0, a); g.addColorStop(1, b); ctx.fillStyle = g; ctx.fillRect(0, 0, W, H); }
const REW = TL.rew;
function sceneHook(ctx, t, lt, i) {
  darkBg(ctx);
  const p = clamp(lt / 6);
  photo(ctx, IMG.collor_retrato_1992, 0, 0, W, 1480, { p, z0: 1.05, z1: 1.18, fy: 0.3, bw: true, credit: CRED.collor_retrato_1992 });
  const g = ctx.createLinearGradient(0, 900, 0, 1480); g.addColorStop(0, 'rgba(5,4,3,0)'); g.addColorStop(1, 'rgba(5,4,3,0.95)'); ctx.fillStyle = g; ctx.fillRect(0, 900, W, 580);
  const off = lt > Wt('hook', 10);
  radioDial(ctx, 540, 1190, 900, 98.3 + Math.sin(lt * 0.8) * 0.4 * (off ? 0 : 1), off ? 0 : 1, lt, 1);
  stamp(ctx, 'FORA DO AR', 540, 870, 110, K.red, -0.12, (lt - Wt('hook', 10)) / 0.25, 1);
  text(ctx, '1992', 90, 560, { font: `700 64px ${TYPE}`, color: '#fff', alpha: clamp(lt / 0.4), shadow: 10 });
}
function sceneFita(ctx, t, lt, i) {
  darkBg(ctx, '#1c1812', '#060504');
  const p = clamp(lt / 6);
  photo(ctx, IMG.fita_cassete, 90, 560, 900, 600, { p, z0: 1.1, z1: 1.22, fx: 0.5, fy: 0.5, tone: 0.45, border: 18, rot: -0.03, credit: CRED.fita_cassete });
  // etiqueta datilografada (ilustrativa)
  const la = popIn(t, Wt('fita', 12) - 0.1, 0.4);
  if (la > 0) {
    ctx.save(); ctx.translate(540, 840); ctx.rotate(-0.05); ctx.scale(la, la);
    ctx.fillStyle = '#f6efdc'; ctx.shadowColor = 'rgba(0,0,0,0.5)'; ctx.shadowBlur = 16; ctx.fillRect(-260, -60, 520, 120); ctx.shadowBlur = 0;
    ctx.strokeStyle = 'rgba(200,40,50,0.6)'; ctx.lineWidth = 2; ctx.beginPath(); ctx.moveTo(-240, -20); ctx.lineTo(240, -20); ctx.stroke();
    text(ctx, typewriter('DEMO · RJ · 1992', (t - Wt('fita', 12)) / 0.8), -230, -30, { font: `700 40px ${TYPE}`, color: '#1b1610' });
    text(ctx, typewriter('lado A — faixa 1', (t - Wt('fita', 13)) / 0.8), -230, 36, { font: `400 34px ${TYPE}`, color: '#3a3226' });
    ctx.restore();
  }
  text(ctx, typewriter('RIO DE JANEIRO · SETEMBRO DE 1992', (t - L.fita.start) / 1.2), 540, 1290, { font: `700 34px ${TYPE}`, color: K.paper, align: 'center' });
  const ag = popIn(t, Wt('fita', 8) - 0.1, 0.45);
  if (ag > 0) { ctx.save(); ctx.translate(800, 520); ctx.rotate(0.08); ctx.scale(ag, ag); ctx.fillStyle = K.yellow; rr(ctx, -120, -50, 240, 100, 50); ctx.fill(); text(ctx, '18 ANOS', 0, 16, { font: `900 46px ${FONT}`, color: K.ink, align: 'center' }); ctx.restore(); }
  const ra = sstep(Wt('fita', 15) - 0.2, Wt('fita', 15) + 0.3, t);
  radioDial(ctx, 540, 1400, 900, lerp(90, 98.3, easeInOutCubic((t - Wt('fita', 15)) / 1.2)), 0, lt, ra);
}
function sceneTitulo(ctx, t, lt, i) {
  darkBg(ctx, '#1a1611', '#050403');
  newsprint(ctx, 70, 520, 940, 860, -0.02);
  ctx.save(); ctx.translate(540, 950); ctx.rotate(-0.02);
  text(ctx, 'A MÚSICA', 0, -300, { font: `700 34px ${TYPE}`, color: '#5a4c38', align: 'center', spacing: 8 });
  ctx.fillStyle = K.ink; ctx.fillRect(-400, -270, 800, 4);
  const p1 = sstep(Wt('titulo', 4) - 0.1, Wt('titulo', 5, 't1'), t), p2 = sstep(Wt('titulo', 6) - 0.1, Wt('titulo', 8, 't1'), t);
  text(ctx, typewriter('TÔ FELIZ', p1 * 1.2), 0, -120, { font: `700 150px ${SERIF}`, color: K.ink, align: 'center' });
  text(ctx, typewriter('(MATEI O', p2 * 1.6), 0, 40, { font: `700 118px ${SERIF}`, color: K.red, align: 'center' });
  text(ctx, typewriter('PRESIDENTE)', (p2 - 0.35) * 1.6), 0, 170, { font: `700 118px ${SERIF}`, color: K.red, align: 'center' });
  ctx.fillStyle = K.ink; ctx.fillRect(-400, 230, 800, 4);
  text(ctx, 'rap · fita demo · 1992', 0, 300, { font: `400 36px ${TYPE}`, color: '#5a4c38', align: 'center', alpha: p2 });
  ctx.restore();
}
function sceneContexto(ctx, t, lt, i) {
  darkBg(ctx, '#121212', '#030303');
  const cut = Wt('contexto', 15);
  // trecho de TV de 1990 (arquivo EBC)
  const va = 1 - sstep(cut - 0.2, cut + 0.2, t);
  if (va > 0 && CONF.length) {
    const f = CONF[Math.min(CONF.length - 1, Math.floor(Math.max(0, t - L.contexto.start + 0.4) * 30))];
    ctx.save(); ctx.globalAlpha = va;
    const x = 40, y = 560, w = 1000, h = 750;
    ctx.fillStyle = '#000'; ctx.fillRect(x - 6, y - 6, w + 12, h + 12);
    ctx.filter = 'contrast(1.1) saturate(0.85)'; ctx.drawImage(f, x, y, w, h); ctx.filter = 'none';
    ctx.globalAlpha = va * 0.22; ctx.fillStyle = '#000'; for (let yy = y + (lt * 50) % 5; yy < y + h; yy += 5) ctx.fillRect(x, yy, w, 2);
    ctx.globalAlpha = va;
    text(ctx, 'ARQUIVO DE TV · 16 MAR 1990', x + 24, y + 54, { font: `700 34px ${TYPE}`, color: '#fff', shadow: 8 });
    text(ctx, '● REC', x + w - 24, y + 54, { font: `700 34px ${TYPE}`, color: K.red, align: 'right', alpha: Math.floor(lt * 2) % 2 ? 1 : 0.3, shadow: 8 });
    ctx.restore();
    creditLine(ctx, CRED.confisco, 40, 1310, 1000, va);
    const ca = sstep(Wt('contexto', 10) - 0.1, Wt('contexto', 12, 't1'), t) * va;
    if (ca > 0) { ctx.save(); ctx.globalAlpha = ca; ctx.fillStyle = K.yellow; rr(ctx, 120, 1350, 840, 110, 20); ctx.fill(); text(ctx, 'CONFISCO DA POUPANÇA', 540, 1425, { font: `900 54px ${FONT}`, color: K.ink, align: 'center' }); ctx.restore(); }
  }
  // depois: escândalo de corrupção
  const pa = sstep(cut - 0.2, cut + 0.3, t);
  if (pa > 0) {
    photo(ctx, IMG.collor_carro_aberto, 0, 440, W, 1040, { p: clamp((t - cut) / 3), z0: 1.08, z1: 1.2, alpha: pa, tone: 0.3, credit: CRED.collor_carro_aberto });
    stamp(ctx, 'ESCÂNDALO', 540, 1000, 120, K.red, -0.1, (t - Wt('contexto', 23)) / 0.25, pa);
  }
}
function sceneSucesso(ctx, t, lt, i) {
  darkBg(ctx, '#1b120c', '#050302');
  radioDial(ctx, 540, 640, 940, 98.3 + Math.sin(lt * 1.3) * 0.15, 1, lt, 1);
  waves(ctx, 540, 760, lt, 0.7);
  // pedidos dos ouvintes (5 dias)
  const x0 = 140, base = 1330, bw = 130, gap = 30, hmax = 440;
  text(ctx, 'PEDIDOS DOS OUVINTES', 540, 860, { font: `800 40px ${FONT}`, color: K.paper, align: 'center', spacing: 4 });
  const d0 = Wt('sucesso', 4);
  for (let k = 0; k < 5; k++) {
    const q = easeOutCubic((t - d0 - k * 0.22) / 0.5), hh = hmax * Math.pow((k + 1) / 5, 1.8) * q;
    const x = x0 + k * (bw + gap);
    ctx.fillStyle = k === 4 ? K.yellow : 'rgba(239,230,210,0.75)'; rr(ctx, x, base - hh, bw, Math.max(hh, 1), 10); ctx.fill();
    text(ctx, `DIA ${k + 1}`, x + bw / 2, base + 44, { font: `700 30px ${TYPE}`, color: K.paper, align: 'center' });
  }
  stamp(ctx, 'ENTRE AS MAIS PEDIDAS', 540, 1000, 66, K.yellow, -0.05, (t - Wt('sucesso', 13)) / 0.25, 1);
}
function scenePressao(ctx, t, lt, i) {
  darkBg(ctx, '#170c0c', '#040202');
  const off = Wt('pressao', 13);
  const shake = t > Wt('pressao', 11) && t < off ? Math.sin(lt * 40) * 0.6 : 0;
  radioDial(ctx, 540, 640, 940, 98.3 + shake, t < off ? 1 : 0, lt, 1);
  newsprint(ctx, 90, 820, 900, 470, 0.015);
  ctx.save(); ctx.translate(540, 1055); ctx.rotate(0.015);
  headline(ctx, ['RÁDIOS SÃO', 'PRESSIONADAS'], 0, -60, 96, sstep(Wt('pressao', 8) - 0.2, Wt('pressao', 11, 't1'), t));
  text(ctx, '“Tô Feliz (Matei o Presidente)” sai da programação', 0, 160, { font: `400 34px ${TYPE}`, color: '#3a3226', align: 'center', alpha: sstep(Wt('pressao', 12), Wt('pressao', 13), t) });
  // tarja de censura
  const bar = sstep(off - 0.1, off + 0.4, t);
  if (bar > 0) { ctx.fillStyle = '#0b0b0b'; ctx.fillRect(-420, 130, 840 * bar, 46); }
  ctx.restore();
  stamp(ctx, 'FORA DO AR', 540, 640, 100, K.red, -0.1, (t - off) / 0.25, 1);
}
function sceneMae(ctx, t, lt, i) {
  darkBg(ctx, '#15130f', '#050403');
  photo(ctx, IMG.collor_corrida, 0, 440, W, 760, { p: clamp(lt / 4.5), z0: 1.06, z1: 1.16, tone: 0.35, credit: CRED.collor_corrida });
  // ficha de dossiê
  const p = popIn(t, Wt('mae', 4) - 0.15, 0.5);
  if (p > 0) {
    ctx.save(); ctx.translate(540, 1300); ctx.rotate(-0.025); ctx.scale(0.9 + 0.1 * p, 0.9 + 0.1 * p); ctx.globalAlpha = clamp(p);
    ctx.fillStyle = '#f2e8cf'; ctx.shadowColor = 'rgba(0,0,0,0.55)'; ctx.shadowBlur = 30; ctx.fillRect(-440, -150, 880, 300); ctx.shadowBlur = 0;
    ctx.fillStyle = 'rgba(160,120,60,0.25)'; ctx.fillRect(-440, -150, 880, 56);
    text(ctx, 'DETALHE', -410, -110, { font: `700 34px ${TYPE}`, color: '#5a4022', spacing: 6 });
    text(ctx, typewriter('A mãe do garoto trabalhou', (t - Wt('mae', 4)) / 1.0), -410, -20, { font: `700 44px ${TYPE}`, color: '#1b1610' });
    text(ctx, typewriter('na campanha de Collor (1989).', (t - Wt('mae', 9)) / 1.0), -410, 50, { font: `700 44px ${TYPE}`, color: '#1b1610' });
    ctx.restore();
    stamp(ctx, '!', 900, 1150, 120, K.red, 0.15, (t - Wt('mae', 13)) / 0.25, 1);
  }
}
function sceneRuas(ctx, t, lt, i) {
  darkBg(ctx, '#11120f', '#030303');
  const sets = [
    [IMG.carapintadas_planalto, CRED.carapintadas_planalto, L.ruas.start - 0.3, -0.04, 70, 500],
    [IMG.carapintadas_senado, CRED.carapintadas_senado, Wt('ruas', 5) - 0.2, 0.05, 110, 760],
    [IMG.esplanada_impeachment, CRED.esplanada_impeachment, Wt('ruas', 9) - 0.2, -0.02, 60, 1010],
  ];
  sets.forEach(([img, cr, t0, rot, x, y]) => {
    const q = easeOutCubic((t - t0) / 0.5); if (q <= 0) return;
    photo(ctx, img, x, y - (1 - q) * 120, 900, 600, { p: clamp((t - t0) / 4), z0: 1.05, z1: 1.15, tone: 0.3, border: 16, rot, alpha: clamp(q * 1.5), credit: cr });
  });
  const ta = sstep(Wt('ruas', 6) - 0.1, Wt('ruas', 6, 't1'), t);
  if (ta > 0) { ctx.save(); ctx.translate(540, 470); ctx.rotate(-0.04); text(ctx, 'CARAS-PINTADAS', 0, 0, { font: `900 96px ${FONT}`, color: K.yellow, align: 'center', stroke: 16, strokeColor: '#0a2a14', alpha: ta }); ctx.restore(); }
}
function sceneImpeach(ctx, t, lt, i) {
  darkBg(ctx, '#121212', '#030303');
  const ph = sstep(Wt('impeach', 13) + 0.3, Wt('impeach', 14), t);
  if (ph < 1) {
    newsprint(ctx, 80, 560, 920, 760, -0.015);
    ctx.save(); ctx.translate(540, 900); ctx.rotate(-0.015); ctx.globalAlpha = 1 - ph;
    text(ctx, typewriter('BRASÍLIA · 29 DE SETEMBRO DE 1992', (t - L.impeach.start) / 1.2), 0, -230, { font: `700 34px ${TYPE}`, color: '#5a4c38', align: 'center' });
    ctx.fillStyle = K.ink; ctx.fillRect(-400, -200, 800, 4);
    headline(ctx, ['CÂMARA', 'APROVA O', 'IMPEACHMENT'], 0, -70, 116, sstep(Wt('impeach', 9) - 0.2, Wt('impeach', 13, 't1'), t));
    ctx.restore();
  }
  if (ph > 0) {
    photo(ctx, IMG.collor_deixa_presidencia, 0, 440, W, 1040, { p: clamp((t - Wt('impeach', 13)) / 3), z0: 1.05, z1: 1.15, alpha: ph, tone: 0.3, credit: CRED.collor_deixa_presidencia });
    text(ctx, '29/09/1992', 80, 540, { font: `700 48px ${TYPE}`, color: '#fff', alpha: ph, shadow: 10 });
    stamp(ctx, 'AFASTADO', 540, 1080, 130, K.red, -0.1, (t - Wt('impeach', 15)) / 0.25, ph);
  }
}
function sceneGabriel(ctx, t, lt, i) {
  darkBg(ctx, '#151210', '#050403');
  photo(ctx, IMG.gabriel_2003, 180, 470, 720, 860, { p: clamp(lt / 7), z0: 1.03, z1: 1.12, fy: 0.35, tone: 0.15, border: 18, rot: 0.02, credit: CRED.gabriel_2003, caption: 'Gabriel o Pensador, 2003' });
  const na = sstep(Wt('gabriel', 4) - 0.1, Wt('gabriel', 6, 't1'), t);
  if (na > 0) { ctx.save(); ctx.translate(540, 1440); ctx.rotate(-0.03); text(ctx, 'GABRIEL O PENSADOR', 0, 0, { font: `900 82px ${FONT}`, color: K.yellow, align: 'center', stroke: 14, strokeColor: K.ink, alpha: na }); ctx.restore(); }
  const ca = sstep(Wt('gabriel', 18) - 0.1, Wt('gabriel', 21, 't1'), t);
  if (ca > 0) stamp(ctx, '+30 ANOS DE CARREIRA', 540, 560, 56, K.yellow, 0.04, (t - Wt('gabriel', 18)) / 0.25, 1);
}
function sceneFinal(ctx, t, lt, i) {
  darkBg(ctx, '#0c0c0c', '#020202');
  photo(ctx, IMG.collor_retrato_1992, 140, 470, 800, 900, { p: clamp(lt / 4), z0: 1.05, z1: 1.14, fy: 0.3, bw: true, credit: CRED.collor_retrato_1992, border: 14 });
  text(ctx, '1992', 170, 540, { font: `700 44px ${TYPE}`, color: '#fff', shadow: 8 });
  const ya = sstep(Wt('final', 3) - 0.1, Wt('final', 8, 't1'), t);
  if (ya > 0) { ctx.save(); ctx.globalAlpha = ya; ctx.fillStyle = 'rgba(0,0,0,0.55)'; ctx.fillRect(0, 440, W, 1040); ctx.restore(); text(ctx, '2025', 540, 900, { font: `700 220px ${TYPE}`, color: '#fff', align: 'center', alpha: ya, shadow: 20 }); }
  stamp(ctx, 'PRESO', 540, 1150, 140, K.red, -0.1, (t - Wt('final', 13)) / 0.25, 1);
  text(ctx, '25 de abril de 2025', 540, 1300, { font: `700 40px ${TYPE}`, color: '#fff', align: 'center', alpha: sstep(Wt('final', 13), Wt('final', 13) + 0.4, t), shadow: 8 });
}

// ---------------------------------------------------------------- HUD (data e status da música)
const STATUS = [
  [-1, '—', '#9aa0ad'], [L.fita.start, 'GRAVANDO', '#ffffff'], [Wt('sucesso', 1), 'NO AR', K.green], [Wt('sucesso', 13), 'MAIS PEDIDA', K.yellow],
  [Wt('pressao', 13), 'FORA DO AR', K.red], [Wt('gabriel', 3), 'CLÁSSICO', K.yellow], [L.cta.start - 0.3, '—', '#9aa0ad'],
];
const DATAS = [
  [-1, '1992'], [REW[0] + 0.3, '1990–1992'], [L.fita.start, 'SET 1992'], [L.titulo.start, 'SET 1992'], [L.contexto.start, '16 MAR 1990'], [Wt('contexto', 15), 'SET 1992'],
  [L.sucesso.start, '05 SET 1992'], [Wt('sucesso', 4), '10 SET 1992'], [L.mae.start, '1989'], [L.ruas.start, 'SET 1992'], [L.impeach.start, '29 SET 1992'],
  [L.gabriel.start, '1993 →'], [L.final.start + 0.5, '25 ABR 2025'], [L.cta.start - 0.3, '1992'],
];
const pick = (arr, t) => { let v = arr[0]; for (const e of arr) if (t >= e[0]) v = e; return v; };
function drawHUD(ctx, t, i) {
  const x = 60, y = 186, w = 960, h = 236;
  ctx.save();
  ctx.fillStyle = 'rgba(10,9,8,0.78)'; rr(ctx, x, y, w, h, 34); ctx.fill();
  ctx.strokeStyle = 'rgba(255,255,255,0.1)'; ctx.lineWidth = 2; rr(ctx, x, y, w, h, 34); ctx.stroke();
  const d = pick(DATAS, t)[1], [, st, col] = pick(STATUS, t);
  text(ctx, 'DATA', x + 250, y + 62, { font: `700 26px ${FONT}`, color: '#b8ab92', align: 'center', spacing: 5 });
  let fs = 84; ctx.font = `700 ${fs}px ${TYPE}`; while (ctx.measureText(d).width > 440) { fs -= 2; ctx.font = `700 ${fs}px ${TYPE}`; }
  text(ctx, d, x + 250, y + 160, { font: `700 ${fs}px ${TYPE}`, color: K.paper, align: 'center' });
  ctx.fillStyle = 'rgba(255,255,255,0.1)'; ctx.fillRect(x + 500, y + 36, 2, h - 72);
  text(ctx, 'STATUS DA MÚSICA', x + 730, y + 62, { font: `700 26px ${FONT}`, color: '#b8ab92', align: 'center', spacing: 4 });
  let fs2 = 64; ctx.font = `900 ${fs2}px ${FONT}`; while (ctx.measureText(st).width > 410) { fs2 -= 2; ctx.font = `900 ${fs2}px ${FONT}`; }
  if (st === 'NO AR' || st === 'MAIS PEDIDA') glowAt(ctx, x + 730, y + 140, 140, hex(col), 0.15 + 0.05 * Math.sin(t * 8));
  text(ctx, st, x + 730, y + 160, { font: `900 ${fs2}px ${FONT}`, color: col, align: 'center' });
  ctx.restore();
}

// ---------------------------------------------------------------- composição
const SCENE_FN = { hook: sceneHook, fita: sceneFita, titulo: sceneTitulo, contexto: sceneContexto, sucesso: sceneSucesso, pressao: scenePressao, mae: sceneMae, ruas: sceneRuas, impeach: sceneImpeach, gabriel: sceneGabriel, final: sceneFinal, cta: sceneCTA };
const SCENES = [
  { name: 'hook', t0: -1, local0: 0 },
  { name: 'fita', t0: L.fita.start - 0.35 }, { name: 'titulo', t0: L.titulo.start - 0.3 }, { name: 'contexto', t0: L.contexto.start - 0.35 },
  { name: 'sucesso', t0: L.sucesso.start - 0.3 }, { name: 'pressao', t0: L.pressao.start - 0.3 }, { name: 'mae', t0: L.mae.start - 0.35 },
  { name: 'ruas', t0: L.ruas.start - 0.35 }, { name: 'impeach', t0: L.impeach.start - 0.3 }, { name: 'gabriel', t0: L.gabriel.start - 0.35 },
  { name: 'final', t0: L.final.start - 0.35 }, { name: 'cta', t0: L.cta.start - 0.35 },
  { name: 'hook', t0: TL.total - 0.5, local0: TL.total, fade: true },
];
const TR = 0.36;
const vignette = (() => { const c = createCanvas(W, H), x = c.getContext('2d'); const g = x.createRadialGradient(W / 2, H * 0.48, H * 0.25, W / 2, H * 0.5, H * 0.78); g.addColorStop(0, 'rgba(0,0,0,0)'); g.addColorStop(1, 'rgba(0,0,0,0.6)'); x.fillStyle = g; x.fillRect(0, 0, W, H); return c; })();
const canvas = createCanvas(W, H), ctx = canvas.getContext('2d');
const bufA = createCanvas(W, H), ctxA = bufA.getContext('2d');
const bufB = createCanvas(W, H), ctxB = bufB.getContext('2d');
const scratch = createCanvas(W, H), sctx = scratch.getContext('2d');
function renderScene(target, idx, t, i) {
  const sc = SCENES[idx], lt = t - (sc.local0 !== undefined ? sc.local0 : sc.t0);
  target.save(); target.setTransform(1, 0, 0, 1, 0, 0); SCENE_FN[sc.name](target, t, lt, i); target.restore();
}
function frame(i, opts = {}) {
  const t = i / FPS;
  let cur = 0; for (let k = 0; k < SCENES.length; k++) if (t >= SCENES[k].t0) cur = k;
  ctx.save(); ctx.fillStyle = '#000'; ctx.fillRect(-40, -40, W + 80, H + 80);
  const sc = SCENES[cur], into = t - sc.t0;
  if (cur > 0 && into < TR) {
    // corte de arquivo: flash de projetor + deslize
    const p = clamp(into / TR);
    renderScene(ctxA, cur - 1, t, i); renderScene(ctxB, cur, t, i);
    ctx.drawImage(bufA, 0, 0); ctx.globalAlpha = sstep(0, 1, p); ctx.drawImage(bufB, (1 - easeOutCubic(p)) * (sc.fade ? 0 : 60), 0); ctx.globalAlpha = 1;
    if (!sc.fade) { const fl = Math.sin(Math.PI * p) * 0.35; ctx.fillStyle = `rgba(255,245,225,${fl})`; ctx.fillRect(0, 0, W, H); }
  } else { renderScene(ctxA, cur, t, i); ctx.drawImage(bufA, 0, 0); }
  // rebobinar (assinatura da série)
  const ra = win(t, REW[0] - 0.05, REW[1] + 0.05, 0.08, 0.12);
  if (ra > 0) {
    sctx.clearRect(0, 0, W, H); sctx.drawImage(canvas, 0, 0);
    const r = rng(Math.floor(t * 60));
    for (let k = 0; k < 8; k++) { const yy = r() * H, hh = 20 + r() * 120, dx = (r() - 0.5) * 90 * ra; ctx.drawImage(scratch, 0, yy, W, hh, dx, yy, W, hh); }
    ctx.save(); ctx.globalAlpha = 0.2 * ra; ctx.fillStyle = '#000'; for (let yy = (t * 400) % 6; yy < H; yy += 6) ctx.fillRect(0, yy, W, 2); ctx.restore();
    text(ctx, '◀◀ REW', 90, 600, { font: `900 64px ${TYPE}`, color: '#fff', alpha: ra * (0.6 + 0.4 * Math.sin(t * 20)), stroke: 8 });
  }
  filmFx(ctx, i, SCENES[cur].name === 'cta' ? 0.4 : 1);
  ctx.drawImage(vignette, 0, 0);
  drawHUD(ctx, t, i);
  if (!opts.noCaptions) drawCaptions(ctx, t);
  ctx.restore();
}

// ---------------------------------------------------------------- main
(async () => {
  await loadMedia();
  const argv = process.argv.slice(2), pi = argv.indexOf('--preview');
  if (argv.includes('--capa')) {
    const i = Math.round((Wt('pressao', 13) + 0.6) * FPS);
    frame(i, { noCaptions: true });
    const g = ctx.createLinearGradient(0, 1300, 0, 1800); g.addColorStop(0, 'rgba(3,3,3,0)'); g.addColorStop(0.35, 'rgba(3,3,3,0.88)'); g.addColorStop(1, 'rgba(3,3,3,0.96)');
    ctx.fillStyle = g; ctx.fillRect(0, 1300, W, 620);
    text(ctx, 'A MÚSICA QUE', W / 2, 1490, { font: `900 84px ${FONT}`, color: '#fff', align: 'center', stroke: 14 });
    text(ctx, 'TIRARAM DO AR EM 1992', W / 2, 1590, { font: `900 78px ${FONT}`, color: K.yellow, align: 'center', stroke: 14 });
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
      '-c:v', 'libx264', '-preset', 'slow', '-crf', '17', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', out], { stdio: ['pipe', 'inherit', 'inherit'] });
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
