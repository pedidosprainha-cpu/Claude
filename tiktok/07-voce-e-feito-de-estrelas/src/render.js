// Ciência #5 — "Você é feito de estrelas"
// Imagens reais: ESA/Webb e ESO (CC BY 4.0) e NASA (domínio público), com crédito na tela.
// Sangue, átomos, Big Bang, DNA, tabela periódica, céu de 1054, anel de ouro, ondas gravitacionais,
// poeira de estrelas, tipografia e transições são gerados aqui.
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
const FONT = '"Inter Display"', SERIF = '"Bitstream Charter"';
const C = { yellow: '#FFD23F', cyan: '#4FD1FF', ink: '#070A14' };
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
const rgba = (c, a = 1) => `rgba(${c[0] | 0},${c[1] | 0},${c[2] | 0},${a})`;
const mixc = (a, b, t) => a.map((v, i) => v + (b[i] - v) * t);

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
function glowAt(ctx, x, y, r, col, a) {
  if (a <= 0 || r <= 0) return;
  const g = ctx.createRadialGradient(x, y, 0, x, y, r);
  g.addColorStop(0, rgba(col, a)); g.addColorStop(1, rgba(col, 0));
  ctx.fillStyle = g; ctx.beginPath(); ctx.arc(x, y, r, 0, 6.283); ctx.fill();
}
// brilho pré-renderizado (muito mais rápido que criar gradientes por partícula)
const SPRITES = new Map();
function sprite(col) {
  const key = col.join(',');
  if (!SPRITES.has(key)) {
    const c = createCanvas(128, 128), x = c.getContext('2d');
    const g = x.createRadialGradient(64, 64, 0, 64, 64, 64);
    g.addColorStop(0, rgba(col, 1)); g.addColorStop(0.18, rgba(col, 0.55)); g.addColorStop(0.5, rgba(col, 0.12)); g.addColorStop(1, rgba(col, 0));
    x.fillStyle = g; x.fillRect(0, 0, 128, 128); SPRITES.set(key, c);
  }
  return SPRITES.get(key);
}
function spark(ctx, x, y, r, col, a) { if (a <= 0.003 || r <= 0) return; ctx.globalAlpha = a; ctx.drawImage(sprite(col), x - r, y - r, 2 * r, 2 * r); }

// ---- encerramento com a marca (idêntico à série)
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
function sceneCTA(ctx, t, lt) {
  const g = ctx.createRadialGradient(540, 860, 40, 540, 960, 1100); g.addColorStop(0, '#1d2d5c'); g.addColorStop(1, '#04060f');
  ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
  for (const s of STARL[1]) { ctx.globalAlpha = s.a * 0.6; ctx.fillStyle = '#fff'; ctx.beginPath(); ctx.arc(s.x, s.y, s.r, 0, 6.283); ctx.fill(); }
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

// ---- legendas palavra por palavra (padrão da série)
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

// ================================================================ vídeo 07: "Você é feito de estrelas"
const R0 = rng(707);
const popIn = (t, t0, d = 0.38) => t < t0 ? 0 : easeOutBack((t - t0) / d);

// ---------------------------------------------------------------- imagens
const IMG = {};
const ARQ = ['caranguejo', 'cas_a', 'anel_sul', 'pilares', 'kilonova', 'helix', 'sol', 'terra'];
const CREDITO = {
  caranguejo: 'NASA, ESA, CSA, STScI, T. Temim (Princeton University) · CC BY 4.0',
  cas_a: 'NASA, ESA, CSA, STScI, D. Milisavljevic (Purdue University), T. Temim (Princeton University), I. De Looze (University of Gent) · CC BY 4.0',
  anel_sul: 'NASA, ESA, CSA, STScI, and the Webb ERO Production Team · CC BY 4.0',
  pilares: 'NASA, ESA, CSA, STScI; J. DePasquale, A. Koekemoer, A. Pagan (STScI) · CC BY 4.0',
  kilonova: 'Ilustração: ESO/L. Calçada/M. Kornmesser · CC BY 4.0',
  helix: 'ESO/VISTA/J. Emerson. Acknowledgment: Cambridge Astronomical Survey Unit · CC BY 4.0',
  nasa: 'Imagens do Sol e da Terra: NASA',
};
async function loadImages() { for (const k of ARQ) IMG[k] = await loadImage(path.join(ROOT, 'assets', k + '.jpg')); }

// foto de tela cheia com movimento de câmera (zoom em torno de um ponto focal, rotação leve)
function plate(ctx, img, o = {}) {
  const { fx = 0.5, fy = 0.5, z = 1.1, rot = 0, alpha = 1, cx = W / 2, cy = H / 2 } = o;
  if (alpha <= 0) return;
  const s = Math.max(W / img.width, H / img.height) * z;
  ctx.save(); ctx.globalAlpha *= alpha; ctx.translate(cx, cy); ctx.rotate(rot); ctx.scale(s, s);
  ctx.drawImage(img, -img.width * fx, -img.height * fy); ctx.restore();
}
// astro com fundo preto: mistura "screen"
function astro(ctx, img, cx, cy, size, o = {}) {
  const { rot = 0, alpha = 1, crop = 1 } = o;
  if (alpha <= 0) return;
  const s = Math.min(img.width, img.height) * crop;
  ctx.save(); ctx.globalAlpha *= alpha; ctx.globalCompositeOperation = 'screen';
  ctx.translate(cx, cy); ctx.rotate(rot);
  ctx.drawImage(img, img.width / 2 - s / 2, img.height / 2 - s / 2, s, s, -size / 2, -size / 2, size, size);
  ctx.restore();
}
function darken(ctx, y0, a = 0.92, y1 = H) {
  const g = ctx.createLinearGradient(0, y0, 0, y1); g.addColorStop(0, 'rgba(2,3,9,0)'); g.addColorStop(1, `rgba(2,3,9,${a})`);
  ctx.fillStyle = g; ctx.fillRect(0, y0, W, y1 - y0);
}

// ---------------------------------------------------------------- céu estrelado
const STARL = [0, 1, 2].map(k => Array.from({ length: 140 + k * 60 }, () => ({ x: R0() * W, y: R0() * H, r: (0.4 + R0() * R0() * 2) * (1 + k * 0.3), a: 0.2 + R0() * 0.7, tw: R0() * 6.28 })));
function sky(ctx, lt, tint = [40, 60, 120], a = 1, drift = 1) {
  ctx.fillStyle = '#020309'; ctx.fillRect(0, 0, W, H);
  const g = ctx.createRadialGradient(W * 0.5, H * 0.42, 50, W * 0.5, H * 0.45, H * 0.75);
  g.addColorStop(0, rgba(tint, 0.35 * a)); g.addColorStop(0.5, rgba(tint, 0.1 * a)); g.addColorStop(1, 'rgba(0,0,0,0)');
  ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
  STARL.forEach((layer, k) => {
    for (const s of layer) {
      const y = (s.y + lt * (4 + k * 6) * drift) % H;
      ctx.globalAlpha = s.a * (0.65 + 0.35 * Math.sin(lt * (1.5 + k) + s.tw)); ctx.fillStyle = '#fff';
      ctx.fillRect(s.x - s.r, y - s.r, s.r * 2, s.r * 2);
    }
  });
  ctx.globalAlpha = 1;
}
function streaks(ctx, lt, amt, cx = W / 2, cy = H * 0.45, col = '#dfe9ff') {
  if (amt <= 0.01) return;
  const r = rng(77);
  ctx.save(); ctx.globalCompositeOperation = 'lighter'; ctx.strokeStyle = col; ctx.lineCap = 'round';
  for (let k = 0; k < 90; k++) {
    const ang = r() * 6.283, ph = r(), sp = 0.6 + r();
    const q = (ph + lt * sp * 1.4) % 1, r0 = 60 + q * q * 1300, len = 40 + 520 * amt * q;
    ctx.globalAlpha = amt * 0.55 * q; ctx.lineWidth = 1 + r() * 2.2;
    ctx.beginPath(); ctx.moveTo(cx + Math.cos(ang) * r0, cy + Math.sin(ang) * r0); ctx.lineTo(cx + Math.cos(ang) * (r0 + len), cy + Math.sin(ang) * (r0 + len)); ctx.stroke();
  }
  ctx.restore();
}

// ---------------------------------------------------------------- tipografia
function cartela(ctx, t, t0, t1, label, value, y = 1290, col = '#ffffff', serif = false) {
  const a = win(t, t0, t1, 0.35, 0.4); if (a <= 0) return;
  const p = easeOutCubic((t - t0) / 0.6);
  ctx.save(); ctx.globalAlpha = a; ctx.translate(540, y + (1 - p) * 30);
  text(ctx, label, 0, -86, { font: `600 26px ${FONT}`, color: 'rgba(220,228,255,0.85)', align: 'center', spacing: 9, shadow: 10 });
  const f = s => serif ? `italic 400 ${s}px ${SERIF}` : `200 ${s}px ${FONT}`;
  let fs = serif ? 150 : 128; ctx.font = f(fs); while (ctx.measureText(value).width > 960 && fs > 60) { fs -= 4; ctx.font = f(fs); }
  ctx.shadowColor = 'rgba(0,0,0,0.7)'; ctx.shadowBlur = 30;
  text(ctx, value, 0, 40, { font: f(fs), color: col, align: 'center' });
  ctx.restore();
}
function label(ctx, s, a, y = 528, sub = null) {
  if (a <= 0) return;
  text(ctx, s, 540, y, { font: `600 28px ${FONT}`, color: 'rgba(235,240,255,0.92)', align: 'center', spacing: 10, alpha: a, shadow: 14 });
  if (sub) text(ctx, sub, 540, y + 44, { font: `400 26px ${FONT}`, color: 'rgba(220,228,255,0.75)', align: 'center', spacing: 2, alpha: a, shadow: 12 });
}
function poem(ctx, lines, y, a, size = 92) {
  if (a <= 0) return;
  ctx.save(); ctx.globalAlpha = a; ctx.shadowColor = 'rgba(0,0,0,0.85)'; ctx.shadowBlur = 40;
  lines.forEach((ln, k) => text(ctx, ln, 540, y + k * size * 1.18, { font: `italic 400 ${size}px ${SERIF}`, color: '#fff7e8', align: 'center' }));
  ctx.restore();
}

// ---------------------------------------------------------------- elementos (tabela periódica)
const ORIG = {
  bb: { nome: 'Big Bang', col: [110, 190, 255] },
  mortas: { nome: 'Estrelas que morreram', col: [96, 230, 186] },
  super: { nome: 'Supernovas', col: [255, 92, 150] },
  ns: { nome: 'Estrelas de nêutrons', col: [255, 214, 92] },
};
// massa num adulto de 70 kg (Emsley, Nature's Building Blocks)
const EL = {
  H: { z: 1, nome: 'Hidrogênio', o: 'bb', m: '7 kg' }, C: { z: 6, nome: 'Carbono', o: 'mortas', m: '16 kg' }, N: { z: 7, nome: 'Nitrogênio', o: 'mortas', m: '1,8 kg' },
  O: { z: 8, nome: 'Oxigênio', o: 'super', m: '43 kg' }, Na: { z: 11, nome: 'Sódio', o: 'super', m: '100 g' }, Mg: { z: 12, nome: 'Magnésio', o: 'super', m: '19 g' },
  P: { z: 15, nome: 'Fósforo', o: 'super', m: '780 g' }, S: { z: 16, nome: 'Enxofre', o: 'super', m: '140 g' }, Cl: { z: 17, nome: 'Cloro', o: 'super', m: '95 g' },
  K: { z: 19, nome: 'Potássio', o: 'super', m: '140 g' }, Ca: { z: 20, nome: 'Cálcio', o: 'super', m: '1 kg' }, Fe: { z: 26, nome: 'Ferro', o: 'super', m: '4,2 g' },
  Zn: { z: 30, nome: 'Zinco', o: 'super', m: '2,3 g' }, I: { z: 53, nome: 'Iodo', o: 'ns', m: '' }, Au: { z: 79, nome: 'Ouro', o: 'ns', m: '0,2 mg' },
};
const CICLO = ['O', 'C', 'H', 'N', 'Ca', 'P', 'K', 'S', 'Na', 'Cl', 'Mg', 'Fe'];
const SIMB = 'H He Li Be B C N O F Ne Na Mg Al Si P S Cl Ar K Ca Sc Ti V Cr Mn Fe Co Ni Cu Zn Ga Ge As Se Br Kr Rb Sr Y Zr Nb Mo Tc Ru Rh Pd Ag Cd In Sn Sb Te I Xe Cs Ba La Ce Pr Nd Pm Sm Eu Gd Tb Dy Ho Er Tm Yb Lu Hf Ta W Re Os Ir Pt Au Hg Tl Pb Bi Po At Rn Fr Ra Ac Th Pa U Np Pu Am Cm Bk Cf Es Fm Md No Lr Rf Db Sg Bh Hs Mt Ds Rg Cn Nh Fl Mc Lv Ts Og'.split(' ');
function posTabela(z) { // [linha, coluna], linhas 7 e 8 = bloco f
  if (z === 1) return [0, 0]; if (z === 2) return [0, 17];
  if (z <= 4) return [1, z - 3]; if (z <= 10) return [1, z + 7];
  if (z <= 12) return [2, z - 11]; if (z <= 18) return [2, z - 1];
  if (z <= 36) return [3, z - 19]; if (z <= 54) return [4, z - 37];
  if (z <= 56) return [5, z - 55]; if (z <= 70) return [7, z - 57 + 2]; if (z <= 86) return [5, z - 69];
  if (z <= 88) return [6, z - 87]; if (z <= 102) return [7 + 1, z - 89 + 2]; return [6, z - 101];
}
// cartão de elemento (vidro, cor da origem)
function tile(ctx, sym, cx, cy, S, a = 1) {
  if (a <= 0) return;
  const e = EL[sym], col = ORIG[e.o].col, w = S, h = S * 1.16, x = cx - w / 2, y = cy - h / 2, r = S * 0.12;
  ctx.save(); ctx.globalAlpha *= a;
  ctx.shadowColor = rgba(col, 0.55); ctx.shadowBlur = S * 0.25;
  const g = ctx.createLinearGradient(x, y, x + w, y + h); g.addColorStop(0, rgba(mixc(col, [20, 24, 40], 0.45), 0.85)); g.addColorStop(1, 'rgba(8,10,22,0.88)');
  ctx.fillStyle = g; rr(ctx, x, y, w, h, r); ctx.fill(); ctx.shadowBlur = 0;
  ctx.save(); rr(ctx, x, y, w, h, r); ctx.clip();
  const sh = ctx.createLinearGradient(x, y, x + w * 0.8, y + h * 0.6); sh.addColorStop(0, 'rgba(255,255,255,0.18)'); sh.addColorStop(0.5, 'rgba(255,255,255,0.03)'); sh.addColorStop(1, 'rgba(255,255,255,0)');
  ctx.fillStyle = sh; ctx.fillRect(x, y, w, h); ctx.restore();
  ctx.strokeStyle = rgba(col, 0.95); ctx.lineWidth = Math.max(1.5, S * 0.012); rr(ctx, x, y, w, h, r); ctx.stroke();
  text(ctx, String(e.z), x + S * 0.1, y + S * 0.2, { font: `600 ${S * 0.13}px ${FONT}`, color: rgba(mixc(col, [255, 255, 255], 0.5)) });
  ctx.beginPath(); ctx.arc(x + w - S * 0.13, y + S * 0.15, S * 0.04, 0, 6.283); ctx.fillStyle = rgba(col); ctx.fill();
  text(ctx, sym, cx, cy + S * 0.16, { font: `700 ${S * 0.5}px ${FONT}`, color: '#ffffff', align: 'center' });
  let fs = S * 0.115; ctx.font = `500 ${fs}px ${FONT}`; while (ctx.measureText(e.nome).width > w * 0.86) { fs -= 1; ctx.font = `500 ${fs}px ${FONT}`; }
  text(ctx, e.nome, cx, y + h - S * 0.11, { font: `500 ${fs}px ${FONT}`, color: 'rgba(230,236,255,0.85)', align: 'center' });
  ctx.restore();
}

// ---------------------------------------------------------------- painel (HUD) no topo
const PX = 60, PY = 186, PW = 960, PH = 220, TILE_CX = PX + 112, TILE_CY = PY + PH / 2, TILE_S = 150;
// cartão de elemento que surge no centro e voa até o painel
const HEROS = [
  { sym: 'Fe', t0: Wt('hook', 1), fly: Wt('hook', 7), x: 540, y: 1140 },
  { sym: 'H', t0: Wt('hidrogenio', 3), fly: Wt('hidrogenio', 9), x: 540, y: 1250 },
  { sym: 'C', t0: Wt('carbono', 1), fly: Wt('carbono', 5), x: 540, y: 1250 },
  { sym: 'O', t0: Wt('oxigenio', 1), fly: Wt('oxigenio', 5), x: 380, y: 1200 },
  { sym: 'Ca', t0: Wt('oxigenio', 7), fly: Wt('oxigenio', 11), x: 700, y: 1200 },
  { sym: 'Au', t0: Wt('ouro', 2), fly: Wt('ouro', 5), x: 540, y: 1210 },
];
const FLY = 0.55;
function drawHeroes(ctx, t) {
  for (const h of HEROS) {
    if (t < h.t0 || t > h.fly + FLY) continue;
    const pin = popIn(t, h.t0, 0.45), q = easeInOutCubic((t - h.fly) / FLY);
    const x = lerp(h.x, TILE_CX, q), y = lerp(h.y, TILE_CY, q) - (1 - q) * 6 * Math.sin(t * 2);
    const S = lerp(280, TILE_S, q) * (0.6 + 0.4 * pin);
    tile(ctx, h.sym, x, y, S, clamp((t - h.t0) / 0.12));
  }
}
const cell = (lab, val, foot = false) => ({ lab, val, foot });
const elemCells = s => [{ tile: s }, cell('NO SEU CORPO*', EL[s].m, true), cell('ORIGEM', ORIG[EL[s].o].nome)];
const PANEL = [
  [-1, null],
  [Wt('hook', 7) + FLY, elemCells('Fe')],
  [L.tudo.start - 0.2, 'ciclo'],
  [L.hidrogenio.start - 0.4, null],
  [Wt('hidrogenio', 9) + FLY, elemCells('H')],
  [Wt('carbono', 5) + FLY, elemCells('C')],
  [Wt('oxigenio', 5) + FLY, elemCells('O')],
  [Wt('oxigenio', 11) + FLY, elemCells('Ca')],
  [L.caranguejo.start - 0.2, [cell('ANO', '1054'), cell('VISÍVEL DE DIA', '23 dias'), cell('DISTÂNCIA', '6.500 anos-luz')]],
  [Wt('ouro', 5) + FLY, elemCells('Au')],
  [L.viagem.start - 0.2, [cell('ÁTOMOS NO SEU CORPO*', '7 octilhões', true), cell('IDADE DA TERRA', '4,5 bilhões de anos')]],
  [L.fecho.start - 0.6, null],
];
function panelCells(k, t) {
  const c = PANEL[k][1];
  if (c !== 'ciclo') return c;
  const i = Math.floor((t - PANEL[k][0]) / 0.42) % CICLO.length;
  return elemCells(CICLO[i]);
}
function drawCells(ctx, cells, a, dy) {
  if (!cells || a <= 0) return;
  ctx.save(); ctx.globalAlpha *= a; ctx.translate(0, dy);
  const hasTile = cells[0].tile, rest = hasTile ? cells.slice(1) : cells;
  let x0 = PX;
  if (hasTile) { tile(ctx, cells[0].tile, TILE_CX, TILE_CY, TILE_S); x0 = PX + 224; ctx.fillStyle = 'rgba(255,255,255,0.1)'; ctx.fillRect(x0 - 1, PY + 34, 1.5, PH - 68); }
  const cw = (PX + PW - x0) / rest.length;
  rest.forEach((c, k) => {
    const cx = x0 + cw * (k + 0.5);
    if (k) { ctx.fillStyle = 'rgba(255,255,255,0.1)'; ctx.fillRect(x0 + cw * k, PY + 34, 1.5, PH - 68); }
    let ls = 22; ctx.font = `600 ${ls}px ${FONT}`; ctx.letterSpacing = '6px'; while (ctx.measureText(c.lab).width > cw - 30 && ls > 15) { ls -= 1; ctx.font = `600 ${ls}px ${FONT}`; }
    ctx.letterSpacing = '0px';
    text(ctx, c.lab, cx, PY + 70, { font: `600 ${ls}px ${FONT}`, color: 'rgba(200,212,240,0.85)', align: 'center', spacing: 6 });
    let fs = 60; ctx.font = `300 ${fs}px ${FONT}`; while (ctx.measureText(c.val).width > cw - 34 && fs > 26) { fs -= 2; ctx.font = `300 ${fs}px ${FONT}`; }
    text(ctx, c.val, cx, PY + 152, { font: `300 ${fs}px ${FONT}`, color: '#fff', align: 'center' });
  });
  ctx.restore();
}
function drawPanel(ctx, t) {
  let k = 0; for (let j = 0; j < PANEL.length; j++) if (t >= PANEL[j][0]) k = j;
  const cur = panelCells(k, t), prev = k > 0 ? panelCells(k - 1, PANEL[k][0] - 0.01) : null;
  let f = sstep(PANEL[k][0], PANEL[k][0] + 0.35, t);
  let pa = cur ? (prev ? 1 : f) : (prev ? 1 - f : 0);
  // no ciclo, troca rápida a cada elemento
  if (PANEL[k][1] === 'ciclo') f = 1;
  if (pa <= 0) return;
  ctx.save(); ctx.globalAlpha = pa;
  ctx.fillStyle = 'rgba(4,6,14,0.58)'; rr(ctx, PX, PY, PW, PH, 34); ctx.fill();
  ctx.strokeStyle = 'rgba(255,255,255,0.12)'; ctx.lineWidth = 1.5; rr(ctx, PX, PY, PW, PH, 34); ctx.stroke();
  ctx.restore();
  ctx.save(); ctx.globalAlpha = pa; rr(ctx, PX, PY, PW, PH, 34); ctx.clip();
  if (cur && prev && f < 1) drawCells(ctx, prev, 1 - sstep(0, 0.5, f), -18 * f);
  drawCells(ctx, cur || prev, cur ? (prev ? sstep(0.4, 1, f) : 1) : 1, cur && prev ? 18 * (1 - f) : 0);
  ctx.restore();
  const cells = cur || prev;
  if (cells && cells.some(c => c.foot)) text(ctx, '*adulto de 70 kg', PX + PW - 24, PY + PH + 34, { font: `500 19px ${FONT}`, color: 'rgba(220,228,255,0.6)', align: 'right', alpha: pa, shadow: 8 });
}

// ================================================================ cenas
const REW = TL.rew;

// ---- sangue: hemácias (sprites pré-desfocados para profundidade de campo)
const RBC = (() => {
  const base = createCanvas(256, 256), x = base.getContext('2d');
  const g = x.createRadialGradient(128, 128, 0, 128, 128, 120);
  g.addColorStop(0, 'rgb(120,6,16)'); g.addColorStop(0.32, 'rgb(150,12,22)'); g.addColorStop(0.6, 'rgb(212,40,44)');
  g.addColorStop(0.8, 'rgb(250,92,82)'); g.addColorStop(0.92, 'rgb(196,28,34)'); g.addColorStop(1, 'rgba(110,0,10,0)');
  x.fillStyle = g; x.beginPath(); x.arc(128, 128, 120, 0, 6.283); x.fill();
  const s = x.createRadialGradient(92, 84, 0, 92, 84, 70); s.addColorStop(0, 'rgba(255,220,210,0.35)'); s.addColorStop(1, 'rgba(255,220,210,0)');
  x.fillStyle = s; x.beginPath(); x.arc(128, 128, 118, 0, 6.283); x.fill();
  return [0, 3, 7, 12, 18].map(b => { const c = createCanvas(320, 320), y = c.getContext('2d'); if (b) y.filter = `blur(${b}px)`; y.drawImage(base, 32, 32); return c; });
})();
const CELLS = Array.from({ length: 46 }, () => ({ z: R0(), x: R0() * 1600 - 260, y: R0() * H, ph: R0() * 6.28, rot: R0() * 6.28, sq: R0() })).sort((a, b) => a.z - b.z);
const PLASMA = Array.from({ length: 160 }, () => ({ x: R0() * W, y: R0() * H, z: R0(), ph: R0() * 6.28 }));
function blood(ctx, lt, push = 0, ironA = 0) {
  const g = ctx.createRadialGradient(540, 860, 60, 540, 900, 1200); g.addColorStop(0, '#6e0a12'); g.addColorStop(0.6, '#2e0306'); g.addColorStop(1, '#120002');
  ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
  const Z = 1 + push * push * 9, ox = 540, oy = 860; // câmera
  ctx.save(); ctx.translate(ox, oy); ctx.scale(Z, Z); ctx.translate(-ox, -oy);
  for (const p of PLASMA) {
    const x = ((p.x + lt * (30 + 120 * p.z)) % (W + 40)) - 20, y = p.y + Math.sin(lt * 0.8 + p.ph) * 20;
    spark(ctx, x, y, 3 + 5 * p.z, [255, 150, 120], 0.12 + 0.18 * p.z);
  }
  ctx.globalAlpha = 1;
  for (const c of CELLS) {
    const size = lerp(70, 340, Math.pow(c.z, 1.4)), sp = lerp(35, 210, c.z);
    const x = ((c.x + lt * sp) % 1700) - 300, y = c.y + Math.sin(lt * 0.7 + c.ph) * 30 * c.z;
    if (Math.abs(x - 540) < 200 && Math.abs(y - 860) < 260 && c.z > 0.5) continue; // espaço da hemácia principal
    const blur = Math.min(4, Math.round(Math.abs(c.z - 0.5) * 9));
    const sq = 0.35 + 0.65 * Math.abs(Math.sin(c.sq * 6 + lt * 0.35));
    ctx.save(); ctx.translate(x, y); ctx.rotate(c.rot + lt * 0.15 * (c.z - 0.5)); ctx.scale(1, sq);
    ctx.globalAlpha = lerp(0.35, 1, c.z); const s = size * 1.25;
    ctx.drawImage(RBC[blur], -s / 2, -s / 2, s, s); ctx.restore();
  }
  // hemácia principal, nítida, com os átomos de ferro brilhando
  const hs = 560, hx = 540, hy = 860;
  ctx.save(); ctx.translate(hx, hy + Math.sin(lt * 0.9) * 10); ctx.rotate(-0.3 + lt * 0.05); ctx.scale(1, 0.86);
  ctx.drawImage(RBC[0], -hs * 1.25 / 2, -hs * 1.25 / 2, hs * 1.25, hs * 1.25); ctx.restore();
  if (ironA > 0) {
    ctx.save(); ctx.globalCompositeOperation = 'lighter';
    const pts = [[-120, -60], [110, -90], [-60, 120], [150, 80], [10, -10]];
    pts.forEach(([dx, dy], k) => {
      const pu = 0.75 + 0.25 * Math.sin(lt * 5 + k * 1.7);
      spark(ctx, hx + dx, hy + dy, 60 * pu, [255, 200, 120], 0.9 * ironA);
      spark(ctx, hx + dx, hy + dy, 18, [255, 255, 240], ironA);
    });
    ctx.restore(); ctx.globalAlpha = 1;
    text(ctx, 'Fe', hx + 10 + 34, hy - 10 - 30, { font: `600 34px ${FONT}`, color: '#fff3d6', alpha: ironA * (1 - push), shadow: 10 });
  }
  ctx.restore();
  // paredes do vaso
  const v = ctx.createLinearGradient(0, 0, 0, H); v.addColorStop(0, 'rgba(10,0,2,0.75)'); v.addColorStop(0.22, 'rgba(10,0,2,0)'); v.addColorStop(0.78, 'rgba(10,0,2,0)'); v.addColorStop(1, 'rgba(10,0,2,0.8)');
  ctx.fillStyle = v; ctx.fillRect(0, 0, W, H);
}

// ---- supernova gerada (filamentos + onda de choque)
const SNP = Array.from({ length: 300 }, () => ({ a: R0() * 6.283, r: 0.55 + R0() * 0.55, s: 40 + R0() * 120, c: [[255, 120, 50], [255, 70, 80], [90, 200, 255], [255, 200, 140], [210, 90, 255]][Math.floor(R0() * 5)], ph: R0() * 10 }));
const SNF = Array.from({ length: 360 }, () => ({ a: R0() * 6.283, v: 0.45 + R0() * 0.6, len: 0.03 + R0() * 0.14, w: 0.8 + R0() * 2.6, c: [[255, 140, 60], [255, 84, 70], [120, 220, 255], [255, 226, 170], [255, 110, 170]][Math.floor(R0() * 5)], wob: R0() * 10 }));
function supernova(ctx, age, cx, cy, S = 1, a = 1) {
  if (a <= 0 || age < 0) return;
  const R = S * (70 + 640 * (1 - Math.exp(-age * 0.9)));
  ctx.save(); ctx.globalCompositeOperation = 'lighter';
  glowAt(ctx, cx, cy, S * R * 1.4, [255, 110, 60], a * 0.4 * Math.exp(-age * 0.3));
  spark(ctx, cx, cy, S * 260, [255, 235, 210], a * (0.35 + 0.65 * Math.exp(-age * 1.2)));
  glowAt(ctx, cx, cy, S * (220 + 900 * (1 - Math.exp(-age * 5))), [255, 244, 225], a * Math.exp(-age * 1.7));
  for (const q of SNP) {
    const n = noise3(Math.cos(q.a) * 1.3, Math.sin(q.a) * 1.3, q.ph + age * 0.2);
    const rr0 = R * q.r * (1 + 0.25 * n);
    spark(ctx, cx + Math.cos(q.a) * rr0, cy + Math.sin(q.a) * rr0, q.s * S * (0.6 + 0.4 * clamp(age)), q.c, a * 0.32 * clamp(age * 2.5));
  }
  ctx.lineCap = 'round';
  for (const f of SNF) {
    const n = noise3(Math.cos(f.a) * 1.6, Math.sin(f.a) * 1.6, age * 0.25 + f.wob);
    const r0 = R * f.v * (1 + 0.22 * n), r1 = r0 + R * f.len * (1 + n);
    const ang = f.a + n * 0.08;
    ctx.globalAlpha = a * 0.4 * clamp(age * 3) * (0.5 + 0.5 * f.v); ctx.strokeStyle = rgba(f.c); ctx.lineWidth = f.w * S * 0.7;
    ctx.beginPath(); ctx.moveTo(cx + Math.cos(ang) * r0, cy + Math.sin(ang) * r0 * 0.96); ctx.lineTo(cx + Math.cos(ang + n * 0.05) * r1, cy + Math.sin(ang + n * 0.05) * r1 * 0.96); ctx.stroke();
  }
  ctx.globalAlpha = a * 0.5 * Math.exp(-age * 0.6); ctx.strokeStyle = 'rgb(170,220,255)'; ctx.lineWidth = 3 * S;
  ctx.beginPath(); ctx.arc(cx, cy, R * 1.12, 0, 6.283); ctx.stroke();
  ctx.restore(); ctx.globalAlpha = 1;
}

function sceneHook(ctx, _t, lt) {
  const t = lt; // o gancho também é desenhado no fim (loop), então usa o tempo local
  const pushT0 = Wt('hook', 8), boom = Wt('hook', 14);
  const push = easeInCubic((t - pushT0) / (Wt('hook', 12) - pushT0));
  if (t < boom - 0.05) {
    blood(ctx, lt, push, sstep(Wt('hook', 1), Wt('hook', 1) + 0.4, t));
    // a luz do átomo de ferro toma a tela
    const wa = sstep(Wt('hook', 10), boom, t);
    if (wa > 0) { ctx.fillStyle = `rgba(255,236,205,${wa})`; ctx.fillRect(0, 0, W, H); }
  } else {
    const age = t - boom;
    sky(ctx, lt, [120, 50, 30]);
    supernova(ctx, age, 540, 820, 1);
    const wa = 1 - sstep(boom - 0.05, boom + 0.35, t);
    if (wa > 0) { ctx.fillStyle = `rgba(255,236,205,${wa})`; ctx.fillRect(0, 0, W, H); }
    cartela(ctx, t, Wt('hook', 15) - 0.1, REW[0] + 0.1, 'ISSO ACONTECEU HÁ MAIS DE', '4,6 bilhões de anos', 1290, '#ffe0c8');
  }
}

// ---- tabela periódica de origem
function sceneTudo(ctx, t, lt) {
  sky(ctx, lt, [70, 40, 120]);
  const cs = 50, gap = 4, pitch = cs + gap, x0 = (W - (18 * pitch - gap)) / 2, y0 = 770;
  const appear = sstep(L.tudo.start - 0.4, L.tudo.start + 0.5, t);
  const tFe = Wt('tudo', 5), tAll = Wt('tudo', 6);
  const fe = posTabela(26);
  ctx.save(); ctx.translate(540, 1020); const sc = 0.96 + 0.04 * easeOutCubic((t - L.tudo.start + 0.4) / 3); ctx.scale(sc, sc); ctx.translate(-540, -1020);
  for (let z = 1; z <= 118; z++) {
    const [r, c] = posTabela(z), sym = SIMB[z - 1];
    const x = x0 + c * pitch, y = y0 + r * pitch + (r >= 7 ? 18 : 0);
    const delay = (r + c * 0.4) * 0.025, a = appear * sstep(0, 0.3, t - (L.tudo.start - 0.4) - delay);
    if (a <= 0) continue;
    const e = EL[sym];
    let lit = 0;
    if (e && sym !== 'Au') {
      const d = Math.hypot(r - fe[0], c - fe[1]);
      lit = sym === 'Fe' ? sstep(tFe, tFe + 0.25, t) : sstep(tAll + d * 0.12, tAll + d * 0.12 + 0.3, t);
    }
    ctx.globalAlpha = a;
    if (lit > 0) {
      const col = ORIG[e.o].col;
      ctx.save(); ctx.globalCompositeOperation = 'lighter'; spark(ctx, x + cs / 2, y + cs / 2, 70, col, 0.55 * lit); ctx.restore(); ctx.globalAlpha = a;
      ctx.fillStyle = rgba(col, 0.15 + 0.75 * lit); rr(ctx, x, y, cs, cs, 7); ctx.fill();
      ctx.strokeStyle = rgba(mixc(col, [255, 255, 255], 0.4), lit); ctx.lineWidth = 2; rr(ctx, x, y, cs, cs, 7); ctx.stroke();
      text(ctx, sym, x + cs / 2, y + cs / 2 + 8, { font: `700 22px ${FONT}`, color: lit > 0.5 ? '#0a0d1c' : '#fff', align: 'center' });
    } else {
      ctx.fillStyle = 'rgba(255,255,255,0.05)'; rr(ctx, x, y, cs, cs, 7); ctx.fill();
      ctx.strokeStyle = 'rgba(200,210,255,0.16)'; ctx.lineWidth = 1; rr(ctx, x, y, cs, cs, 7); ctx.stroke();
      text(ctx, sym, x + cs / 2, y + cs / 2 + 7, { font: `500 19px ${FONT}`, color: 'rgba(200,210,255,0.35)', align: 'center' });
    }
  }
  ctx.restore(); ctx.globalAlpha = 1;
  // 90%
  const pa = sstep(tAll - 0.1, tAll + 0.4, t), pct = Math.round(90 * easeOutCubic((t - tAll) / 1.3));
  if (pa > 0) {
    text(ctx, `${pct}%`, 540, 660, { font: `200 190px ${FONT}`, color: '#fff', align: 'center', alpha: pa, shadow: 30 });
    text(ctx, 'DA MASSA DO SEU CORPO', 540, 718, { font: `600 26px ${FONT}`, color: 'rgba(225,232,255,0.9)', align: 'center', spacing: 9, alpha: pa });
  }
  // legenda de cores
  const la = sstep(Wt('tudo', 14) - 0.2, Wt('tudo', 14) + 0.4, t);
  if (la > 0) {
    const items = ['bb', 'mortas', 'super', 'ns'];
    items.forEach((k, j) => {
      const x = j % 2 ? 590 : 120, y = 1320 + Math.floor(j / 2) * 52;
      ctx.globalAlpha = la; ctx.fillStyle = rgba(ORIG[k].col); ctx.beginPath(); ctx.arc(x + 12, y - 9, 11, 0, 6.283); ctx.fill(); ctx.globalAlpha = 1;
      text(ctx, ORIG[k].nome, x + 36, y, { font: `500 30px ${FONT}`, color: 'rgba(235,240,255,0.92)', alpha: la, shadow: 8 });
    });
  }
}

// ---- hidrogênio: o átomo, o Big Bang
const CLOUD = Array.from({ length: 3600 }, () => {
  const r = -0.5 * (Math.log(R0() + 1e-9) + Math.log(R0() + 1e-9) + Math.log(R0() + 1e-9));
  const u = R0() * 2 - 1, th = R0() * 6.283, s = Math.sqrt(1 - u * u);
  return [r * s * Math.cos(th), r * u, r * s * Math.sin(th)];
});
const PUFF = Array.from({ length: 240 }, () => ({ a: R0() * 6.283, r: Math.pow(R0(), 0.6), s: 120 + R0() * 260, ph: R0() * 10 }));
const ATOMS = Array.from({ length: 220 }, () => ({ x: (R0() - 0.5) * 2600, y: (R0() - 0.5) * 4200, ph: R0() * 6.28, s: 0.6 + R0() * 0.8 }));
function hAtom(ctx, cx, cy, a0, lt, a = 1) {
  if (a <= 0) return;
  const ca = Math.cos(lt * 0.35), sa = Math.sin(lt * 0.35);
  ctx.save(); ctx.globalCompositeOperation = 'lighter';
  const ds = Math.max(1.4, a0 * 0.02);
  for (const [x, y, z] of CLOUD) {
    const X = x * ca - z * sa, Z = x * sa + z * ca;
    ctx.globalAlpha = a * (0.3 + 0.16 * Z / 3); ctx.fillStyle = '#9ad6ff';
    ctx.fillRect(cx + X * a0 - ds / 2, cy + y * a0 - ds / 2, ds, ds);
  }
  spark(ctx, cx, cy, a0 * 1.6, [80, 150, 255], a * 0.35);
  spark(ctx, cx, cy, a0 * 0.45, [255, 240, 220], a);
  spark(ctx, cx, cy, a0 * 0.16, [255, 255, 255], a);
  ctx.restore(); ctx.globalAlpha = 1;
}
function sceneHidrogenio(ctx, t, lt) {
  const tPull = Wt('hidrogenio', 10), tBang = Wt('hidrogenio', 15);
  sky(ctx, lt, [40, 80, 170]);
  if (t < tBang) {
    const pull = easeInOutCubic((t - tPull) / (tBang - tPull));
    const zoom = lerp(1, 0.08, pull);
    // mar de átomos aparece ao afastar
    ctx.save(); ctx.globalCompositeOperation = 'lighter';
    for (const p of ATOMS) {
      const x = 540 + p.x * zoom * 3.2, y = 820 + p.y * zoom * 3.2 + Math.sin(lt + p.ph) * 6;
      if (x < -60 || x > W + 60 || y < -60 || y > H + 60) continue;
      spark(ctx, x, y, 60 * zoom * p.s * 3, [120, 190, 255], 0.5 * pull);
      spark(ctx, x, y, 14 * p.s, [230, 245, 255], 0.8 * pull);
    }
    ctx.restore(); ctx.globalAlpha = 1;
    hAtom(ctx, 540, 820, 150 * zoom * (1 + 0.02 * Math.sin(lt * 2)), lt, 1);
    const la = win(t, Wt('hidrogenio', 4), tPull + 0.3, 0.4, 0.4);
    text(ctx, '1 PRÓTON  ·  1 ELÉTRON', 540, 548, { font: `600 26px ${FONT}`, color: 'rgba(205,228,255,0.85)', align: 'center', spacing: 8, alpha: la * (1 - clamp((t - Wt('hidrogenio', 9)) / 0.3)), shadow: 10 });
  } else {
    // Big Bang: bola de fogo que esfria num mar de hidrogênio
    const age = t - tBang;
    const Rf = 80 + 1500 * (1 - Math.exp(-age * 1.2));
    ctx.save(); ctx.globalCompositeOperation = 'lighter';
    for (const p of ATOMS) {
      const k = 1 + age * 0.08, x = 540 + p.x * 0.42 * k, y = 820 + p.y * 0.42 * k;
      if (x < -20 || x > W + 20 || y < -20 || y > H + 20) continue;
      spark(ctx, x, y, 12 * p.s, [150, 205, 255], 0.85 * sstep(0.8, 2.0, age));
      spark(ctx, x, y, 40 * p.s, [90, 140, 255], 0.25 * sstep(0.8, 2.0, age));
    }
    const T = Math.exp(-age * 0.55);
    for (const q of PUFF) {
      const n = noise3(Math.cos(q.a) * 2, Math.sin(q.a) * 2, q.ph + age * 0.4), rad = Rf * q.r * (1 + 0.2 * n);
      const col = T > 0.5 ? mixc([255, 160, 70], [255, 248, 230], (T - 0.5) * 2) : mixc([120, 70, 210], [255, 160, 70], T * 2);
      spark(ctx, 540 + Math.cos(q.a) * rad, 820 + Math.sin(q.a) * rad, q.s * (0.7 + 0.6 * (1 - T)), col, (0.18 + 0.3 * T) * clamp(age * 4));
    }
    const fa = Math.exp(-age * 0.6);
    const g = ctx.createRadialGradient(540, 820, 0, 540, 820, Rf);
    g.addColorStop(0, `rgba(255,255,255,${fa})`); g.addColorStop(0.25, `rgba(255,240,200,${0.9 * fa})`); g.addColorStop(0.55, `rgba(255,150,70,${0.6 * fa})`);
    g.addColorStop(0.85, `rgba(190,60,90,${0.35 * fa})`); g.addColorStop(1, 'rgba(60,20,80,0)');
    ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
    ctx.restore();
    streaks(ctx, age, 0.9 * Math.exp(-age * 0.8), 540, 820, '#fff0d8');
    cartela(ctx, t, Wt('hidrogenio', 17) - 0.15, L.hidrogenio.end + 0.8, 'ESSES ÁTOMOS SURGIRAM HÁ', '13,8 bilhões de anos', 1290, '#dfefff');
  }
  if (t >= tBang - 0.02 && t < tBang + 0.4) { ctx.fillStyle = `rgba(255,255,255,${1 - (t - tBang) / 0.4})`; ctx.fillRect(0, 0, W, H); }
}

// ---- carbono: DNA diante de uma estrela que morreu (Anel do Sul)
function sceneCarbono(ctx, t, lt) {
  const tHeart = Wt('carbono', 8), tSpread = Wt('carbono', 11);
  const zin = easeInOutCubic((t - tHeart) / 1.6);
  plate(ctx, IMG.anel_sul, { fx: 0.49, fy: 0.455, z: lerp(1.0, 1.18, clamp(lt / 7)) * lerp(1, 1.5, zin), rot: -0.08 + lt * 0.01, cy: 860 });
  darken(ctx, 1100, 0.9);
  ctx.save(); ctx.globalCompositeOperation = 'lighter';
  spark(ctx, 540, 860, 260 + 140 * zin, [180, 220, 255], 0.25 + 0.45 * zin * (0.85 + 0.15 * Math.sin(lt * 6)));
  ctx.restore(); ctx.globalAlpha = 1;
  // dupla hélice de partículas
  const ha = win(t, Wt('carbono', 3), tHeart + 0.6, 0.5, 0.6);
  const spread = clamp((t - tSpread) / 2.6);
  const veil = Math.max(ha, spread > 0 ? 1 - spread : 0);
  if (veil > 0) { ctx.fillStyle = `rgba(2,3,9,${0.5 * veil})`; ctx.fillRect(0, 0, W, H); }
  if (ha > 0 || spread > 0) {
    ctx.save(); ctx.globalCompositeOperation = 'lighter';
    const r = rng(31);
    for (let y = 430; y <= 1330; y += 15) {
      const phi = y * 0.012 + lt * 1.4;
      for (let s = 0; s < 2; s++) {
        const ph = phi + s * Math.PI, depth = Math.cos(ph), x = 540 + 170 * Math.sin(ph);
        const ang = r() * 6.283, sp = 200 + r() * 600, k = easeOutCubic(spread);
        const px = x + Math.cos(ang) * sp * k, py = y + Math.sin(ang) * sp * k - 60 * k;
        const a = (ha + (spread > 0 ? (1 - spread) : 0)) * (0.55 + 0.45 * (depth + 1) / 2);
        spark(ctx, px, py, 26 + 14 * depth, s ? [255, 190, 110] : [120, 210, 255], a * 0.9);
        spark(ctx, px, py, 6 + 3 * depth, [255, 255, 255], a);
      }
      if (y % 45 === 0 && spread === 0) {
        const xa = 540 + 170 * Math.sin(phi), xb = 540 + 170 * Math.sin(phi + Math.PI);
        ctx.globalAlpha = ha * 0.55 * (0.6 + 0.4 * Math.abs(Math.cos(phi))); ctx.strokeStyle = ((y / 45) | 0) % 2 ? '#ffd7a0' : '#a8e4ff'; ctx.lineWidth = 4;
        ctx.beginPath(); ctx.moveTo(xa, y); ctx.lineTo(xb, y); ctx.stroke();
      }
    }
    ctx.restore(); ctx.globalAlpha = 1;
  }
  label(ctx, 'NEBULOSA DO ANEL DO SUL', sstep(Wt('carbono', 14), Wt('carbono', 15), t), 528, 'o que sobrou de uma estrela que morreu');
}

// ---- oxigênio e cálcio: Cassiopeia A
function sceneOxigenio(ctx, t, lt) {
  const tBoom = Wt('oxigenio', 16);
  const shake = t > tBoom ? Math.exp(-(t - tBoom) * 2.2) : 0;
  plate(ctx, IMG.cas_a, { fx: 0.49, fy: 0.47, z: lerp(1.05, 1.32, clamp(lt / 7)), rot: 0.05 - lt * 0.008, cy: 860 });
  darken(ctx, 1100, 0.9);
  if (t > tBoom - 0.1) {
    const age = t - tBoom;
    ctx.save(); ctx.globalCompositeOperation = 'lighter';
    glowAt(ctx, 540, 860, 300 + 1200 * (1 - Math.exp(-age * 3)), [255, 220, 200], 0.8 * Math.exp(-age * 2.5));
    ctx.globalAlpha = 0.7 * Math.exp(-age * 1.2); ctx.strokeStyle = '#cfe8ff'; ctx.lineWidth = 6;
    ctx.beginPath(); ctx.arc(540, 860, 100 + 1400 * (1 - Math.exp(-age * 1.4)), 0, 6.283); ctx.stroke();
    ctx.restore(); ctx.globalAlpha = 1;
    streaks(ctx, age, 0.8 * shake, 540, 860, '#ffd9e6');
  }
  label(ctx, 'CASSIOPEIA A', sstep(tBoom - 0.2, tBoom + 0.4, t), 528, 'restos de uma supernova');
}

// ---- 1054: céu diurno com a "estrela convidada"
const CLOUDS = (() => {
  const w = 270, h = 480, c = createCanvas(w, h), x = c.getContext('2d'), im = x.createImageData(w, h);
  for (let j = 0; j < h; j++) for (let i = 0; i < w; i++) {
    const n = fbm3(i * 0.016, j * 0.04, 3.3, 5), dens = sstep(0.0, 0.25, n + 0.05 - (j / h) * 0.12);
    const q = (j * w + i) * 4; im.data[q] = im.data[q + 1] = im.data[q + 2] = 255; im.data[q + 3] = Math.round(dens * 200);
  }
  x.putImageData(im, 0, 0); return c;
})();
function daySky(ctx, lt, a = 1) {
  if (a <= 0) return;
  ctx.save(); ctx.globalAlpha = a;
  const g = ctx.createLinearGradient(0, 0, 0, H); g.addColorStop(0, '#1d4f9e'); g.addColorStop(0.55, '#5f9ad6'); g.addColorStop(0.8, '#a9cbe9'); g.addColorStop(1, '#d8e6ef');
  ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
  glowAt(ctx, 960, 260, 700, [255, 250, 230], 0.55);
  glowAt(ctx, 960, 260, 140, [255, 255, 250], 0.9);
  ctx.globalAlpha = a * 0.85; ctx.drawImage(CLOUDS, -40 - lt * 14, 120, W + 300, H * 0.85); ctx.globalAlpha = a;
  // a estrela convidada, visível em pleno dia
  const sx = 400, sy = 720, pu = 0.9 + 0.1 * Math.sin(lt * 7);
  ctx.globalCompositeOperation = 'lighter';
  glowAt(ctx, sx, sy, 190 * pu, [255, 250, 240], 0.75);
  ctx.strokeStyle = 'rgba(255,255,255,0.85)'; ctx.lineCap = 'round';
  for (let k = 0; k < 4; k++) { const an = k * Math.PI / 2 + 0.2, len = (k % 2 ? 120 : 190) * pu; ctx.lineWidth = 3; ctx.beginPath(); ctx.moveTo(sx - Math.cos(an) * len, sy - Math.sin(an) * len); ctx.lineTo(sx + Math.cos(an) * len, sy + Math.sin(an) * len); ctx.stroke(); }
  glowAt(ctx, sx, sy, 34, [255, 255, 255], 1);
  ctx.globalCompositeOperation = 'source-over';
  // horizonte
  const tp = { seed: 4, base: 1560, amp: 160, freq: 0.0022, oct: 4 };
  ctx.beginPath(); ctx.moveTo(-10, H + 10);
  for (let x = -10; x <= W + 10; x += 6) ctx.lineTo(x, tp.base - tp.amp * ridge1(x * tp.freq, tp.seed, tp.oct));
  ctx.lineTo(W + 10, H + 10); ctx.closePath(); ctx.fillStyle = '#1b2a3e'; ctx.fill();
  ctx.restore();
}
function sceneCaranguejo(ctx, t, lt) {
  const tDay = Wt('caranguejo', 13), tNow = Wt('caranguejo', 21);
  const dayA = win(t, tDay - 0.15, tNow + 0.35, 0.3, 0.5);
  const back = easeOutCubic((t - tNow) / 2.2);
  if (dayA < 1) {
    const z = t < tNow ? lerp(1.04, 1.22, clamp(lt / 7)) : lerp(2.4, 1.12, back);
    plate(ctx, IMG.caranguejo, { fx: 0.5, fy: 0.5, z, rot: t < tNow ? lt * 0.006 : 0.1 * (1 - back), cy: 860 });
    darken(ctx, 1100, 0.9);
  }
  daySky(ctx, lt, dayA);
  if (dayA > 0 && dayA < 1) { ctx.fillStyle = `rgba(255,255,255,${0.6 * Math.sin(Math.PI * dayA) * (t < tNow ? 1 : 0.6)})`; ctx.fillRect(0, 0, W, H); }
  cartela(ctx, t, Wt('caranguejo', 8) - 0.15, tDay + 0.1, 'VISTA DA TERRA EM', '1054', 1300, '#ffffff', true);
  cartela(ctx, t, Wt('caranguejo', 16), tNow + 0.2, 'VISÍVEL EM PLENO DIA POR', '23 dias', 1290);
  label(ctx, 'NEBULOSA DO CARANGUEJO', sstep(tNow + 0.2, tNow + 0.8, t), 528, 'o que restou daquela explosão');
}

// ---- ouro: anel, estrelas de nêutrons em espiral, ondas gravitacionais
function goldRing(ctx, cx, cy, R, lt, a = 1) {
  if (a <= 0) return;
  const tilt = 0.56 + 0.08 * Math.sin(lt * 0.7), ry = R * tilt, th = R * 0.27;
  ctx.save(); ctx.globalAlpha *= a; ctx.translate(cx, cy); ctx.rotate(-0.22 + 0.05 * Math.sin(lt * 0.5));
  const sh = Math.sin(lt * 0.9) * R * 0.6;
  const grd = (dark) => { const g = ctx.createLinearGradient(-R + sh, -R, R + sh, R); const s = dark ? 0.55 : 1;
    g.addColorStop(0, rgba([110 * s, 70 * s, 10 * s])); g.addColorStop(0.3, rgba([225 * s, 168 * s, 52 * s])); g.addColorStop(0.47, rgba([255 * s, 244 * s, 196 * s]));
    g.addColorStop(0.58, rgba([242 * s, 192 * s, 80 * s])); g.addColorStop(0.82, rgba([150 * s, 100 * s, 18 * s])); g.addColorStop(1, rgba([80 * s, 50 * s, 6 * s])); return g; };
  ctx.lineCap = 'butt';
  ctx.lineWidth = th; ctx.strokeStyle = grd(true); ctx.beginPath(); ctx.ellipse(0, 0, R, ry, 0, Math.PI, 2 * Math.PI); ctx.stroke();
  ctx.lineWidth = th * 0.25; ctx.strokeStyle = 'rgba(60,35,4,0.5)'; ctx.beginPath(); ctx.ellipse(0, th * 0.18, R - th * 0.4, ry - th * 0.3, 0, Math.PI, 2 * Math.PI); ctx.stroke();
  ctx.lineWidth = th; ctx.strokeStyle = grd(false); ctx.beginPath(); ctx.ellipse(0, 0, R, ry, 0, 0, Math.PI); ctx.stroke();
  ctx.lineWidth = 2.5; ctx.strokeStyle = 'rgba(255,248,215,0.8)'; ctx.beginPath(); ctx.ellipse(0, -th * 0.42, R, ry, 0, 0.15, Math.PI - 0.15); ctx.stroke();
  ctx.globalCompositeOperation = 'lighter';
  for (let k = 0; k < 3; k++) { const an = (lt * 0.6 + k * 2.1) % Math.PI; const x = R * Math.cos(an), y = ry * Math.sin(an) - th * 0.3, pu = Math.sin(an);
    spark(ctx, x, y, 70 * pu, [255, 236, 170], 0.8 * pu * a); ctx.globalAlpha = 0.9 * pu * a; ctx.strokeStyle = '#fff8e0'; ctx.lineWidth = 2;
    ctx.beginPath(); ctx.moveTo(x - 50 * pu, y); ctx.lineTo(x + 50 * pu, y); ctx.moveTo(x, y - 34 * pu); ctx.lineTo(x, y + 34 * pu); ctx.stroke(); }
  ctx.restore(); ctx.globalAlpha = 1;
}
const GOLD = Array.from({ length: 160 }, () => ({ x: R0() * W, y: R0() * H, z: R0(), ph: R0() * 6.28, a: R0() * 6.283, v: 0.3 + R0() }));
function sceneOuro(ctx, t, lt) {
  const tSpiral = Wt('ouro', 3), tMerge = Wt('ouro', 14), tShake = Wt('ouro', 19);
  const ringA = 1 - sstep(tSpiral, tSpiral + 0.6, t);
  sky(ctx, lt, [70, 60, 30], 1, 0.4);
  if (ringA > 0) {
    ctx.save(); ctx.globalCompositeOperation = 'lighter';
    for (const p of GOLD) spark(ctx, (p.x + Math.sin(lt * 0.5 + p.ph) * 30) % W, (p.y - lt * 30 * p.v + H * 2) % H, 4 + 10 * p.z, [255, 205, 110], 0.5 * p.z * ringA);
    ctx.restore(); ctx.globalAlpha = 1;
    goldRing(ctx, 540, 820, 270 * (0.9 + 0.1 * easeOutBack(lt / 0.6)), lt, ringA);
  }
  const ka = sstep(tSpiral - 0.1, tSpiral + 0.8, t);
  if (ka > 0) {
    const after = clamp((t - tMerge) / 4);
    plate(ctx, IMG.kilonova, { fx: 0.5, fy: 0.52, z: t < tMerge ? 1.25 : lerp(1.7, 1.12, easeOutCubic(after)), cy: 860, alpha: ka * (t < tMerge ? 0.32 : lerp(0.32, 1, sstep(tMerge, tMerge + 0.4, t))) });
    darken(ctx, 1150, 0.9);
    const Tp = tMerge - tSpiral, cx = 540, cy = 860;
    const phase = tt => { const tau = Math.max(1e-4, tMerge - tt); return -8 * Math.PI * Math.pow(tau / Tp, 5 / 8); };
    const sep = tt => 300 * Math.pow(Math.max(0, tMerge - tt) / Tp, 0.25);
    ctx.save(); ctx.globalCompositeOperation = 'lighter';
    // ondas gravitacionais (anéis: fase retardada pela distância)
    const amp = t < tMerge ? 0.25 + 0.75 * Math.pow(1 - clamp((tMerge - t) / Tp), 3) : Math.exp(-(t - tMerge) * 0.7);
    for (let r = 40; r < 1400; r += 7) {
      const te = t - r / 520; if (te < tSpiral) break;
      const ph = te < tMerge ? phase(te) : phase(tMerge - 1e-3) + (te - tMerge) * 60;
      const ia = Math.pow(0.5 + 0.5 * Math.cos(2 * ph), 10) * (te < tMerge ? 0.25 + 0.75 * Math.pow(1 - clamp((tMerge - te) / Tp), 3) : Math.exp(-(te - tMerge) * 1.5));
      if (ia < 0.03) continue;
      ctx.globalAlpha = ia * ka * 0.32 * clamp(1.3 - r / 1400); ctx.strokeStyle = '#9fd4ff'; ctx.lineWidth = 2.5;
      ctx.beginPath(); ctx.ellipse(cx, cy, r, r * 0.62, 0, 0, 6.283); ctx.stroke();
    }
    if (t < tMerge) {
      for (let k = 24; k >= 0; k--) {
        const tt = t - k * 0.014; if (tt < tSpiral) continue;
        const p = phase(tt), d = sep(tt) / 2;
        for (const s of [0, Math.PI]) {
          const x = cx + Math.cos(p + s) * d, y = cy + Math.sin(p + s) * d * 0.55;
          spark(ctx, x, y, k ? 26 * (1 - k / 25) : 90, k ? [140, 200, 255] : [220, 240, 255], ka * (k ? 0.35 * (1 - k / 25) : 1));
          if (!k) spark(ctx, x, y, 22, [255, 255, 255], ka);
        }
      }
    } else {
      const age = t - tMerge;
      glowAt(ctx, cx, cy, 200 + 1300 * (1 - Math.exp(-age * 4)), [235, 245, 255], Math.exp(-age * 2));
      // ouro arremessado para fora
      for (const g of GOLD) {
        const rr0 = (60 + 1100 * (1 - Math.exp(-age * g.v * 0.9))) * (0.5 + g.z);
        spark(ctx, cx + Math.cos(g.a) * rr0, cy + Math.sin(g.a) * rr0 * 0.8, 6 + 8 * g.z, [255, 206, 100], 0.85 * Math.exp(-age * 0.35) * clamp(age * 4));
      }
    }
    ctx.restore(); ctx.globalAlpha = 1;
    label(ctx, 'ESTRELAS DE NÊUTRONS', win(t, tSpiral + 0.5, tMerge + 0.1, 0.5, 0.3), 528, 'estrelas mortas e superdensas');
    label(ctx, 'COLISÃO DE ESTRELAS DE NÊUTRONS', sstep(tMerge + 0.6, tMerge + 1.1, t), 528, 'ilustração artística');
  }
}

// ---- viagem: Pilares da Criação → Sol → Terra → "você"
const DUST = Array.from({ length: 260 }, () => ({ x: R0() * W, y: R0() * H, z: R0(), ph: R0() * 6.28 }));
const VOCE = (() => {
  const w = 1080, h = 520, c = createCanvas(w, h), x = c.getContext('2d');
  x.font = `italic 400 300px ${SERIF}`; x.textAlign = 'center'; x.textBaseline = 'middle'; x.fillStyle = '#fff'; x.fillText('você', w / 2, h / 2);
  const d = x.getImageData(0, 0, w, h).data, pts = [], r = rng(55);
  const glow = createCanvas(w, h), gx = glow.getContext('2d');
  gx.font = x.font; gx.textAlign = 'center'; gx.textBaseline = 'middle'; gx.shadowColor = 'rgba(255,190,110,0.95)'; gx.shadowBlur = 40; gx.fillStyle = '#fff6e6';
  gx.fillText('você', w / 2, h / 2); gx.shadowBlur = 12; gx.fillText('você', w / 2, h / 2);
  for (let j = 0; j < h; j += 5) for (let i = 0; i < w; i += 5) if (d[(j * w + i) * 4 + 3] > 140) pts.push({ tx: i, ty: j - h / 2, a: r() * 6.283, r: 500 + r() * 700, dl: r() * 0.7, s: 0.6 + r() * 0.8, gold: r() < 0.35 });
  return { canvas: glow, pts };
})();
function sceneViagem(ctx, t, lt) {
  const tSol = Wt('viagem', 9), tTerra = Wt('viagem', 13), tVoce = Wt('viagem', 14);
  const pa = 1 - sstep(tSol - 0.3, tSol + 0.5, t);
  if (pa > 0) {
    plate(ctx, IMG.pilares, { fx: 0.5, fy: lerp(0.62, 0.45, clamp(lt / 5)), z: lerp(1.08, 1.25, clamp(lt / 5)), cy: 860, alpha: 1 });
    darken(ctx, 1100, 0.9);
  }
  if (pa < 1) {
    ctx.save(); ctx.globalAlpha = 1 - pa; sky(ctx, lt, [130, 80, 40]); ctx.restore(); ctx.globalAlpha = 1;
    // disco de poeira girando em volta do Sol nascente
    const da = win(t, tSol - 0.3, tVoce + 0.8, 0.5, 0.8), r = rng(9);
    ctx.save(); ctx.globalCompositeOperation = 'lighter';
    for (let k = 0; k < 420; k++) {
      const rad = 120 + Math.pow(r(), 0.7) * 520, an = r() * 6.283 + lt * (260 / rad);
      spark(ctx, 540 + Math.cos(an) * rad, 820 + Math.sin(an) * rad * 0.3, 5 + r() * 9, r() < 0.5 ? [255, 190, 120] : [255, 230, 190], da * 0.45);
    }
    ctx.restore(); ctx.globalAlpha = 1;
    const sa = win(t, tSol + 0.1, tVoce + 0.4, 0.6, 0.6);
    glowAt(ctx, 540, 820, 420, [255, 150, 60], 0.45 * sa);
    astro(ctx, IMG.sol, 540, 820, 470 * (0.9 + 0.1 * sstep(tSol, tSol + 1, t)), { alpha: sa, rot: lt * 0.03 });
    const ea = win(t, tTerra - 0.1, tVoce + 0.4, 0.5, 0.6), eo = (t - tTerra - 0.5) * 0.25;
    astro(ctx, IMG.terra, 540 + Math.cos(eo) * 380, 820 + Math.sin(eo) * 120, 150, { alpha: ea, rot: lt * 0.1 });
  }
  // poeira de estrelas fluindo
  const fa = 1 - sstep(tVoce, tVoce + 0.5, t);
  ctx.save(); ctx.globalCompositeOperation = 'lighter';
  for (const p of DUST) {
    const x = (p.x + lt * (40 + 140 * p.z)) % (W + 40) - 20, y = (p.y - lt * (20 + 60 * p.z) + H * 4) % H;
    spark(ctx, x, y, 4 + 12 * p.z, [255, 214, 160], (0.25 + 0.5 * p.z) * fa);
  }
  // a poeira se junta e forma "você"
  if (t > tVoce - 0.6) {
    ctx.fillStyle = `rgba(2,3,9,${0.75 * sstep(tVoce - 0.6, tVoce, t)})`; ctx.globalCompositeOperation = 'source-over'; ctx.fillRect(0, 0, W, H);
    ctx.globalCompositeOperation = 'lighter';
    const cy = 860;
    for (const p of VOCE.pts) {
      const q = easeInOutCubic((t - (tVoce - 0.6) - p.dl * 0.6) / 1.5);
      const an = p.a + (1 - q) * 2.5, rad = p.r * (1 - q);
      const x = lerp(540 + Math.cos(an) * rad, p.tx, q), y = lerp(cy + Math.sin(an) * rad, cy + p.ty, q);
      spark(ctx, x, y, (3 + 5 * p.s) * (1 + (1 - q) * 1.5), p.gold ? [255, 210, 130] : [235, 240, 255], 0.55 * clamp((t - tVoce + 0.6) * 3));
    }
    const va = sstep(Wt('viagem', 17) - 0.15, Wt('viagem', 17) + 0.5, t);
    ctx.globalCompositeOperation = 'source-over'; ctx.globalAlpha = va;
    ctx.drawImage(VOCE.canvas, 0, cy - VOCE.canvas.height / 2);
    ctx.globalCompositeOperation = 'lighter';
    spark(ctx, 540, cy, 620, [255, 200, 130], 0.3 * va);
    const fl = Wt('viagem', 17); if (t > fl && t < fl + 0.6) spark(ctx, 540, cy, 900, [255, 240, 220], 0.6 * (1 - (t - fl) / 0.6));
    ctx.globalAlpha = 1;
  }
  ctx.restore(); ctx.globalAlpha = 1;
  label(ctx, 'PILARES DA CRIAÇÃO', win(t, L.viagem.start, tSol, 0.5, 0.3), 528, 'onde estrelas novas nascem');
}

// ---- fecho: o "olho" da Nebulosa Hélice
function sceneFecho(ctx, t, lt) {
  const p = easeOutCubic(clamp(lt / 6.5));
  const beat = 1 + 0.008 * Math.pow(Math.max(0, Math.sin(Math.PI * 2 * t * 72 / 60)), 12);
  plate(ctx, IMG.helix, { fx: 0.5, fy: 0.49, z: lerp(3.2, 1.12, p) * beat, rot: lerp(0.3, 0, p), cy: 820 });
  ctx.fillStyle = 'rgba(2,3,9,0.18)'; ctx.fillRect(0, 0, W, H);
  darken(ctx, 1050, 0.92);
  const a1 = win(t, Wt('fecho', 0) - 0.1, Wt('fecho', 7) - 0.1, 0.5, 0.35);
  const a2 = win(t, Wt('fecho', 7), L.cta.start + 0.3, 0.6, 0.5);
  poem(ctx, ['Você não está só', 'olhando pro universo.'], 1300, a1, 80);
  poem(ctx, ['Você é o universo', 'olhando pra si mesmo.'], 1300, a2, 84);
}

// ---------------------------------------------------------------- composição
const SCENE_FN = { hook: sceneHook, tudo: sceneTudo, hidrogenio: sceneHidrogenio, carbono: sceneCarbono, oxigenio: sceneOxigenio, caranguejo: sceneCaranguejo, ouro: sceneOuro, viagem: sceneViagem, fecho: sceneFecho, cta: sceneCTA };
const SCENES = [
  { name: 'hook', t0: -1, local0: 0 },
  { name: 'tudo', t0: L.tudo.start - 0.4, tr: 'zoom' },
  { name: 'hidrogenio', t0: L.hidrogenio.start - 0.4, tr: 'zoom' },
  { name: 'carbono', t0: L.carbono.start - 0.45, tr: 'iris' },
  { name: 'oxigenio', t0: L.oxigenio.start - 0.35, tr: 'flash' },
  { name: 'caranguejo', t0: L.caranguejo.start - 0.4, tr: 'zoom' },
  { name: 'ouro', t0: L.ouro.start - 0.45, tr: 'iris' },
  { name: 'viagem', t0: L.viagem.start - 0.45, tr: 'flash' },
  { name: 'fecho', t0: L.fecho.start - 0.55, tr: 'iris' },
  { name: 'cta', t0: L.cta.start - 0.4, tr: 'zoom' },
  { name: 'hook', t0: TL.total - 0.5, local0: TL.total, tr: 'fade' },
];
const TR = 0.7;
const CRED = (name, t) => {
  if (name === 'carbono') return 'anel_sul';
  if (name === 'oxigenio') return 'cas_a';
  if (name === 'caranguejo') return (t > Wt('caranguejo', 13) - 0.1 && t < Wt('caranguejo', 21) + 0.3) ? null : 'caranguejo';
  if (name === 'ouro') return t > Wt('ouro', 3) ? 'kilonova' : null;
  if (name === 'viagem') return t < Wt('viagem', 9) ? 'pilares' : (t < Wt('viagem', 14) + 0.3 ? 'nasa' : null);
  if (name === 'fecho') return 'helix';
  return null;
};
function credit(ctx, key) {
  const s = CREDITO[key]; ctx.font = `500 19px ${FONT}`;
  const words = s.split(' '), lines = []; let cur = '';
  for (const w of words) { const tst = cur ? cur + ' ' + w : w; if (ctx.measureText(tst).width > 900 && cur) { lines.push(cur); cur = w; } else cur = tst; }
  lines.push(cur);
  lines.forEach((ln, k) => text(ctx, ln, W - 60, 1452 - (lines.length - 1 - k) * 25, { font: `500 19px ${FONT}`, color: 'rgba(220,228,255,0.62)', align: 'right', shadow: 8 }));
}
const vignette = (() => { const c = createCanvas(W, H), x = c.getContext('2d'); const g = x.createRadialGradient(W / 2, H * 0.46, H * 0.22, W / 2, H * 0.5, H * 0.8); g.addColorStop(0, 'rgba(0,0,0,0)'); g.addColorStop(1, 'rgba(0,0,0,0.7)'); x.fillStyle = g; x.fillRect(0, 0, W, H); return c; })();
const topVeil = (() => { const c = createCanvas(W, 760), x = c.getContext('2d'); const g = x.createLinearGradient(0, 0, 0, 760); g.addColorStop(0, 'rgba(2,3,9,0.6)'); g.addColorStop(0.6, 'rgba(2,3,9,0.35)'); g.addColorStop(1, 'rgba(2,3,9,0)'); x.fillStyle = g; x.fillRect(0, 0, W, 760); return c; })();
const GRAIN = Array.from({ length: 3 }, (_, k) => { const c = createCanvas(540, 960), x = c.getContext('2d'), im = x.createImageData(540, 960), r = rng(60 + k); for (let q = 0; q < im.data.length; q += 4) { const v = r() * 255; im.data[q] = im.data[q + 1] = im.data[q + 2] = v; im.data[q + 3] = 14; } x.putImageData(im, 0, 0); return c; });
const canvas = createCanvas(W, H), ctx = canvas.getContext('2d');
const bufA = createCanvas(W, H), ctxA = bufA.getContext('2d');
const bufB = createCanvas(W, H), ctxB = bufB.getContext('2d');
const scratch = createCanvas(W, H), sctx = scratch.getContext('2d');
function renderScene(target, idx, t) {
  const sc = SCENES[idx], lt = t - (sc.local0 !== undefined ? sc.local0 : sc.t0);
  target.save(); target.setTransform(1, 0, 0, 1, 0, 0); target.globalAlpha = 1; target.globalCompositeOperation = 'source-over';
  SCENE_FN[sc.name](target, t, lt); target.restore();
}
function drawScaled(src, s, a) {
  ctx.save(); ctx.globalAlpha = a; ctx.translate(W / 2, H * 0.44); ctx.scale(s, s); ctx.translate(-W / 2, -H * 0.44); ctx.drawImage(src, 0, 0); ctx.restore();
}
// tremor de câmera nos impactos
const SHAKES = [[Wt('hook', 14), 16], [Wt('hidrogenio', 15), 12], [Wt('oxigenio', 16), 14], [Wt('ouro', 14), 12], [Wt('ouro', 19), 18]];
function shakeAt(t) {
  let dx = 0, dy = 0;
  for (const [t0, A] of SHAKES) { if (t < t0 || t > t0 + 1.6) continue; const e = A * Math.exp(-(t - t0) * 3.2); dx += e * noise3(t * 14, 1.3, t0); dy += e * noise3(4.1, t * 14, t0); }
  return [dx, dy];
}
function frame(i, opts = {}) {
  const t = i / FPS;
  let cur = 0; for (let k = 0; k < SCENES.length; k++) if (t >= SCENES[k].t0) cur = k;
  ctx.save(); ctx.fillStyle = '#000'; ctx.fillRect(0, 0, W, H);
  const [sx, sy] = shakeAt(t);
  ctx.translate(sx, sy); if (sx || sy) { ctx.translate(W / 2, H / 2); ctx.scale(1.03, 1.03); ctx.translate(-W / 2, -H / 2); }
  const sc = SCENES[cur], into = t - sc.t0, inTr = cur > 0 && into < TR;
  if (inTr) {
    const p = easeInOutCubic(into / TR);
    renderScene(ctxA, cur - 1, t); renderScene(ctxB, cur, t);
    if (sc.tr === 'fade') { ctx.drawImage(bufA, 0, 0); ctx.globalAlpha = sstep(0, 0.6, into / TR); ctx.drawImage(bufB, 0, 0); ctx.globalAlpha = 1; }
    else if (sc.tr === 'iris') {
      ctx.drawImage(bufA, 0, 0);
      const R = 1300 * p;
      ctx.save(); ctx.beginPath(); ctx.arc(540, 860, Math.max(1, R), 0, 6.283); ctx.clip(); ctx.drawImage(bufB, 0, 0); ctx.restore();
      ctx.save(); ctx.globalCompositeOperation = 'lighter'; ctx.globalAlpha = Math.sin(Math.PI * p) * 0.8; ctx.strokeStyle = '#fff4e0'; ctx.lineWidth = 6; ctx.shadowColor = '#ffd9a0'; ctx.shadowBlur = 30;
      ctx.beginPath(); ctx.arc(540, 860, Math.max(1, R), 0, 6.283); ctx.stroke(); ctx.restore();
    } else if (sc.tr === 'flash') {
      ctx.drawImage(into / TR < 0.5 ? bufA : bufB, 0, 0);
      ctx.fillStyle = `rgba(255,246,232,${0.9 * Math.pow(Math.sin(Math.PI * clamp(into / TR)), 1.5)})`; ctx.fillRect(0, 0, W, H);
    } else {
      drawScaled(bufA, lerp(1, 0.72, p), 1 - p);
      drawScaled(bufB, lerp(1.35, 1, p), p);
      streaks(ctx, t, Math.sin(Math.PI * p) * 0.9);
    }
  } else { renderScene(ctxA, cur, t); ctx.drawImage(bufA, 0, 0); }
  ctx.restore();
  ctx.save();
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
  ctx.drawImage(topVeil, 0, 0);
  drawPanel(ctx, t);
  drawHeroes(ctx, t);
  const ck = CRED(SCENES[cur].name, t);
  if (ck && !inTr) credit(ctx, ck);
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
    plate(ctx, IMG.helix, { fx: 0.5, fy: 0.49, z: 1.3, cy: 760 });
    const g = ctx.createLinearGradient(0, 950, 0, H); g.addColorStop(0, 'rgba(2,3,9,0)'); g.addColorStop(0.4, 'rgba(2,3,9,0.85)'); g.addColorStop(1, 'rgba(2,3,9,0.97)');
    ctx.fillStyle = g; ctx.fillRect(0, 950, W, H - 950);
    ctx.drawImage(vignette, 0, 0);
    text(ctx, 'DE ONDE VIERAM OS SEUS ÁTOMOS', W / 2, 1250, { font: `600 30px ${FONT}`, color: 'rgba(230,236,255,0.9)', align: 'center', spacing: 9 });
    poem(ctx, ['Você é feito', 'de estrelas.'], 1400, 1, 120);
    text(ctx, 'ESO/VISTA/J. Emerson. Acknowledgment: Cambridge Astronomical Survey Unit · CC BY 4.0', W - 60, 1740, { font: `500 18px ${FONT}`, color: 'rgba(220,228,255,0.6)', align: 'right' });
    const out = path.join(ROOT, 'output/capa.png'); fs.mkdirSync(path.dirname(out), { recursive: true });
    fs.writeFileSync(out, canvas.toBuffer('image/png')); console.log(out);
  } else if (pi >= 0) {
    const dir = path.join(ROOT, 'build/preview'); fs.mkdirSync(dir, { recursive: true });
    for (const s of argv[pi + 1].split(',')) {
      const i = clamp(Math.round(parseFloat(s) * FPS), 0, N - 1); const t0 = Date.now(); frame(i);
      const out = path.join(dir, `t${(i / FPS).toFixed(2).padStart(6, '0')}.png`);
      fs.writeFileSync(out, canvas.toBuffer('image/png')); console.log(out, (Date.now() - t0) + 'ms');
    }
  } else {
    const out = path.join(ROOT, 'build/video.mp4');
    const ff = spawn('ffmpeg', ['-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgba', '-s', `${W}x${H}`, '-r', String(FPS), '-i', '-',
      '-c:v', 'libx264', '-preset', 'slow', '-crf', '18', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', out], { stdio: ['pipe', 'inherit', 'inherit'] });
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
