// Ciência #8 — "A gosma sem cérebro" (Physarum polycephalum)
// Todas as imagens da gosma são simulações próprias (src/cenas.py), com os modelos matemáticos dos próprios
// pesquisadores (Tero et al. 2007 e 2010) e crescimento em malha orgânica. Mapa: Natural Earth (domínio público).
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
const FONT = '"Inter Display"', MONO = '"Plex"', MONO_M = '"Plex Medium"', SERIF = '"Cormorant"', SERIF_I = '"Cormorant Italic"';
const C = { yellow: '#FFD23F', cyan: '#4FD1FF', ink: '#070A14', slime: [255, 205, 40], rail: [110, 220, 255] };
const L = TL.lines, M = TL.marks, REW = TL.rew;
const Wt = (line, i, k = 't0') => L[line].words[i][k];

// ---------------------------------------------------------------- utilidades
const clamp = (x, a = 0, b = 1) => Math.max(a, Math.min(b, x));
const lerp = (a, b, t) => a + (b - a) * t;
const sstep = (a, b, x) => { const t = clamp((x - a) / (b - a)); return t * t * (3 - 2 * t); };
const easeOutCubic = p => 1 - Math.pow(1 - clamp(p), 3);
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
  if (shadow) { ctx.shadowColor = 'rgba(0,0,0,0.8)'; ctx.shadowBlur = shadow; ctx.shadowOffsetY = shadow / 4; }
  if (stroke) { ctx.lineJoin = 'round'; ctx.lineWidth = stroke; ctx.strokeStyle = strokeColor; ctx.strokeText(s, x, y); ctx.shadowBlur = 0; }
  ctx.fillStyle = color; ctx.fillText(s, x, y); ctx.restore();
}
function glowAt(ctx, x, y, r, col, a) {
  if (a <= 0 || r <= 0) return;
  const g = ctx.createRadialGradient(x, y, 0, x, y, r);
  g.addColorStop(0, rgba(col, a)); g.addColorStop(1, rgba(col, 0));
  ctx.fillStyle = g; ctx.beginPath(); ctx.arc(x, y, r, 0, 6.283); ctx.fill();
}

// ---------------------------------------------------------------- tipografia e UI de laboratório
function chip(ctx, s, x, y, a, { align = 'center', col = 'rgba(235,240,255,0.94)', size = 24, dot = null, strike = 0 } = {}) {
  if (a <= 0) return;
  ctx.save(); ctx.globalAlpha *= a; ctx.font = `${size}px ${MONO}`; ctx.letterSpacing = '5px';
  const tw = ctx.measureText(s).width, w = tw + (dot ? 30 : 0), px = 22, h = size + 26;
  const x0 = align === 'center' ? x - w / 2 - px : align === 'right' ? x - w - 2 * px : x;
  ctx.fillStyle = 'rgba(6,8,12,0.6)'; rr(ctx, x0, y - h / 2, w + 2 * px, h, h / 2); ctx.fill();
  ctx.strokeStyle = 'rgba(255,255,255,0.18)'; ctx.lineWidth = 1.2; rr(ctx, x0, y - h / 2, w + 2 * px, h, h / 2); ctx.stroke();
  if (dot) { ctx.fillStyle = dot; ctx.beginPath(); ctx.arc(x0 + px + 7, y, 7, 0, 6.283); ctx.fill(); }
  ctx.fillStyle = col; ctx.textBaseline = 'middle'; ctx.fillText(s, x0 + px + (dot ? 30 : 0), y + 1);
  if (strike > 0) { ctx.strokeStyle = '#ff5a4a'; ctx.lineWidth = 4; ctx.lineCap = 'round'; ctx.beginPath(); ctx.moveTo(x0 + 10, y); ctx.lineTo(x0 + 10 + (w + 2 * px - 20) * easeOutCubic(strike), y); ctx.stroke(); }
  ctx.restore();
}
function credito(ctx, titulo, meta, a, y = 300) { // referência do artigo, no canto (é também o crédito)
  if (a <= 0) return;
  ctx.save(); ctx.globalAlpha *= a;
  ctx.fillStyle = 'rgba(255,214,80,0.9)'; ctx.fillRect(70, y - 42, 3, 70);
  text(ctx, titulo, 92, y, { font: `italic 400 42px ${SERIF_I}`, color: '#fff6df', shadow: 16 });
  text(ctx, meta, 94, y + 32, { font: `17px ${MONO}`, color: 'rgba(240,232,210,0.85)', spacing: 3, shadow: 10 });
  ctx.restore();
}
function relogio(ctx, rotulo, valor, a, t) { // HUD de câmera de laboratório (time-lapse)
  if (a <= 0) return;
  ctx.save(); ctx.globalAlpha *= a;
  const on = Math.sin(t * 6) > -0.2;
  ctx.fillStyle = on ? '#ff4d3d' : 'rgba(255,77,61,0.35)'; ctx.beginPath(); ctx.arc(1010, 150, 9, 0, 6.283); ctx.fill();
  text(ctx, rotulo, 988, 158, { font: `18px ${MONO}`, color: 'rgba(240,244,255,0.85)', align: 'right', spacing: 4, shadow: 8 });
  if (valor) text(ctx, valor, 1010, 214, { font: `500 44px ${MONO_M}`, color: '#fff', align: 'right', spacing: 2, shadow: 12 });
  ctx.restore();
}
function escala(ctx, px, rot, a, y = 1690) {
  if (a <= 0) return;
  ctx.save(); ctx.globalAlpha *= a; ctx.fillStyle = 'rgba(255,255,255,0.9)';
  ctx.fillRect(80, y, px, 4); ctx.fillRect(80, y - 8, 3, 20); ctx.fillRect(80 + px - 3, y - 8, 3, 20);
  text(ctx, rot, 80 + px / 2, y - 18, { font: `18px ${MONO}`, color: 'rgba(255,255,255,0.9)', align: 'center', spacing: 3 }); ctx.restore();
}
function simulacao(ctx, a, y = 368, s = 'SIMULAÇÃO') { chip(ctx, s, 92, y, a, { align: 'left', size: 17, col: 'rgba(255,224,140,0.95)', dot: 'rgba(255,205,40,0.9)' }); }

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

// ---------------------------------------------------------------- tomadas simuladas (build/shots)
const SHOTS = ['macro', 'labirinto', 'toquio', 'rastro', 'sal', 'fusao'];
const META = {}, COUNT = {};
for (const k of SHOTS) {
  const d = path.join(ROOT, 'build/shots', k);
  META[k] = fs.existsSync(path.join(d, 'meta.json')) ? JSON.parse(fs.readFileSync(path.join(d, 'meta.json'), 'utf8')) : { frames: 1 };
  COUNT[k] = fs.existsSync(d) ? fs.readdirSync(d).filter(f => f.endsWith('.jpg')).length : 0;
}
const CACHE = new Map();
async function frameOf(name, k) { // k: índice 0-based (fracionário é arredondado)
  k = clamp(Math.round(k), 0, Math.max(0, COUNT[name] - 1));
  const key = name + k;
  if (!CACHE.has(key)) {
    CACHE.set(key, await loadImage(path.join(ROOT, 'build/shots', name, String(k + 1).padStart(5, '0') + '.jpg')));
    if (CACHE.size > 24) CACHE.delete(CACHE.keys().next().value);
  }
  return CACHE.get(key);
}
// desenha a tomada com câmera: z = zoom, (cx, cy) = ponto da tomada no centro da tela; devolve a transformação
async function shot(ctx, name, k, { z = 1, cx = 540, cy = 960, alpha = 1 } = {}) {
  const img = await frameOf(name, k);
  if (z >= 1) { cx = clamp(cx, 540 / z, W - 540 / z); cy = clamp(cy, 960 / z, H - 960 / z); }
  const T = { s: z, ox: 540 - cx * z, oy: 960 - cy * z };
  ctx.save(); ctx.globalAlpha *= alpha; ctx.translate(T.ox, T.oy); ctx.scale(z, z); ctx.drawImage(img, 0, 0); ctx.restore();
  return T;
}
const P = (T, x, y) => [T.ox + x * T.s, T.oy + y * T.s];

// ================================================================ cenas (bg recebe bloom e acabamento; fg são textos e gráficos)
const S = {};
const NM = () => COUNT.macro;
// ---- gancho: a gosma pulsando → a rede de Tóquio → a fusão que ensina; depois rebobina
S.hook = {
  async bg(ctx, t, lt) {
    const tt = lt <= REW[0] ? lt : lerp(REW[0], 0, easeInOutCubic((lt - REW[0]) / (REW[1] - REW[0])));
    this.tt = tt;
    const c1 = M.toquio_hook - 0.06, c2 = L.hook2.start - 0.08;
    if (tt < c1) { this.v = 0; await shot(ctx, 'macro', NM() - 200 + Math.max(0, tt) * 30, { z: lerp(1.22, 1.38, clamp(tt / c1)), cx: 560, cy: 1060 }); }
    else if (tt < c2) {
      this.v = 1; const p = (tt - c1) / (c2 - c1);
      this.T = await shot(ctx, 'toquio', COUNT.toquio - 1, { z: lerp(1.0, 1.07, p), cx: 540, cy: 940 });
    } else { this.v = 2; await shot(ctx, 'fusao', 60 + (tt - c2) * 45, { z: 1.12, cx: 540, cy: 980 }); }
  },
  fg(ctx, t, lt) {
    const tt = this.tt || 0, c1 = M.toquio_hook - 0.06;
    if (this.v === 1 && this.T) { const p = clamp((tt - c1 - 0.1) / 0.8); trilhos(ctx, this.T, p, 1); }
    relogio(ctx, 'TIME-LAPSE', null, this.v === 0 ? 1 : 0, t);
  },
};
// ---- "o nome dela é Physarum": o leque avançando de perto
S.nome = {
  async bg(ctx, t, lt) {
    const p = clamp(lt / (SCN.labirinto.t0 - SCN.nome.t0));
    await shot(ctx, 'macro', 40 + p * 300, { z: lerp(1.45, 1.25, p), cx: lerp(560, 520, p), cy: lerp(1100, 820, easeInOutCubic(p)) });
  },
  fg(ctx, t, lt) {
    const a = win(t, Wt('nome', 4) - 0.15, Wt('nome', 6), 0.25, 0.3);
    if (a > 0) {
      text(ctx, 'Physarum polycephalum', 540, 420, { font: `italic 400 92px ${SERIF_I}`, color: '#fff6df', align: 'center', alpha: a, shadow: 30 });
      text(ctx, 'BOLOR LIMOSO · O "BLOB"', 540, 476, { font: `22px ${MONO}`, color: 'rgba(255,236,190,0.9)', align: 'center', spacing: 6, alpha: a, shadow: 10 });
    }
    const fim = Wt('nome', 14) - 0.05;
    [['FUNGO', 9, 230], ['PLANTA', 11, 540], ['BICHO', 13, 850]].forEach(([s, i, x]) => {
      const a0 = win(t, Wt('nome', i) - 0.12, fim + 0.3, 0.2, 0.3);
      chip(ctx, s, x, 440, a0, { size: 26, strike: clamp((t - Wt('nome', i) - 0.1) / 0.3) });
    });
    chip(ctx, '1 CÉLULA · MILHARES DE NÚCLEOS', 540, 440, win(t, Wt('nome', 16) - 0.1, SCN.labirinto.t0 + 0.2, 0.25, 0.3), { size: 24, dot: rgba(C.slime) });
    escala(ctx, 200, '1 cm', win(t, Wt('nome', 21) - 0.2, SCN.labirinto.t0 + 0.3, 0.3, 0.3));
    relogio(ctx, 'TIME-LAPSE', null, sstep(SCN.nome.t0, SCN.nome.t0 + 0.4, t), t);
  },
};
// ---- o labirinto (Nakagaki, 2000)
const LABCAM = { z: 0.92, cx: 540, cy: 1040 };
S.labirinto = {
  async bg(ctx, t, lt) {
    const F = META.labirinto.fases || { enche: [0, 150], comida: 150, seleciona: [186, 426] };
    let k;
    if (t < M.lab_bota) k = 0;
    else if (t < M.lab_comida) k = F.enche[1] * clamp((t - M.lab_bota) / (M.lab_comida - M.lab_bota - 0.15));
    else if (t < M.lab_largou) k = F.comida + (F.seleciona[0] - F.comida) * clamp((t - M.lab_comida) / 0.8);
    else k = F.seleciona[0] + (F.seleciona[1] - F.seleciona[0] - 1) * clamp((t - M.lab_largou) / (M.lab_curto + 0.7 - M.lab_largou));
    this.T = await shot(ctx, 'labirinto', k, LABCAM);
    const dim = 1 - sstep(M.lab_bota - 0.4, M.lab_bota, t);
    if (dim > 0) { ctx.fillStyle = `rgba(0,0,0,${0.6 * dim})`; ctx.fillRect(0, 0, W, H); }
  },
  fg(ctx, t, lt) {
    const T = this.T, m = META.labirinto;
    const ca = win(t, SCN.labirinto.t0 + 0.05, M.lab_bota + 0.1, 0.3, 0.3);
    if (ca > 0) {
      text(ctx, '2000', 540, 900, { font: `400 150px ${SERIF}`, color: '#fff6df', align: 'center', alpha: ca, shadow: 30 });
      ctx.save(); ctx.globalAlpha = ca; ctx.fillStyle = 'rgba(255,240,200,0.7)'; const w = 280 * easeOutCubic(ca); ctx.fillRect(540 - w, 945, 2 * w, 2); ctx.restore();
      text(ctx, 'TOSHIYUKI NAKAGAKI · JAPÃO', 540, 1000, { font: `22px ${MONO}`, color: 'rgba(240,232,210,0.9)', align: 'center', spacing: 6, alpha: ca });
    }
    const after = sstep(M.lab_bota, M.lab_bota + 0.4, t);
    credito(ctx, 'Nakagaki, Yamada & Tóth', 'NATURE, 2000 · O LABIRINTO', after, 196);
    simulacao(ctx, after, 262, 'SIMULAÇÃO · MODELO DE TERO ET AL. (2007)');
    if (T && m.entrada) {
      const fa = win(t, M.lab_comida - 0.05, SCN.toquio.t0 + 0.3, 0.3, 0.3);
      const [ex, ey] = P(T, ...m.entrada), [sx, sy] = P(T, ...m.saida);
      glowAt(ctx, ex, ey, 70, [255, 240, 200], 0.35 * fa * (0.7 + 0.3 * Math.sin(t * 5))); glowAt(ctx, sx, sy, 70, [255, 240, 200], 0.35 * fa * (0.7 + 0.3 * Math.sin(t * 5 + 1)));
      chip(ctx, 'COMIDA', ex + 62, ey + 4, fa, { size: 18, align: 'left' });
      chip(ctx, 'COMIDA', sx - 62, sy - 64, fa, { size: 18, align: 'right' });
    }
    const sel = clamp((t - M.lab_largou) / (M.lab_curto + 0.7 - M.lab_largou));
    relogio(ctx, 'DEPOIS DA COMIDA', `${(8 * sel).toFixed(1).replace('.', ',')} h`, win(t, M.lab_largou - 0.1, SCN.toquio.t0 + 0.2, 0.3, 0.3), t);
    chip(ctx, 'SÓ O CAMINHO MAIS CURTO', 540, 1440, win(t, M.lab_curto + 0.3, SCN.toquio.t0 + 0.3, 0.3, 0.3), { size: 22, dot: rgba(C.slime) });
  },
};
// ---- Tóquio (Tero et al., 2010)
const TOQCAM = { z: 0.96, cx: 540, cy: 948 };
function trilhos(ctx, T, p, a) { // linhas de trem reais (Natural Earth), desenhando-se
  const tr = META.toquio.trilhos; if (!tr || a <= 0 || p <= 0) return;
  ctx.save(); ctx.globalAlpha *= a; ctx.lineJoin = 'round'; ctx.lineCap = 'round';
  for (const pass of [[12, 0.16], [3.2, 0.95]]) {
    ctx.strokeStyle = rgba(C.rail, pass[1]); ctx.lineWidth = pass[0];
    for (const ln of tr) {
      const n = Math.max(2, Math.ceil(ln.length * p)); ctx.beginPath();
      for (let i = 0; i < n; i++) { const [x, y] = P(T, ln[i][0], ln[i][1]); i ? ctx.lineTo(x, y) : ctx.moveTo(x, y); }
      ctx.stroke();
    }
  }
  ctx.restore();
}
S.toquio = {
  async bg(ctx, t, lt) {
    const F = META.toquio.fases || { cresce: [0, 150], adapta: [150, 450] };
    const k = t < M.liga ? 0 : (COUNT.toquio - 1) * clamp((t - M.liga) / (M.trilhos - 0.3 - M.liga));
    const z = lerp(TOQCAM.z, 1.04, sstep(M.liga, M.trilhos, t)) - 0.06 * sstep(M.trilhos, M.trilhos + 1.5, t);
    this.T = await shot(ctx, 'toquio', k, { z, cx: 560, cy: 948 });
  },
  fg(ctx, t, lt) {
    const T = this.T, m = META.toquio; if (!T) return;
    const t0 = SCN.toquio.t0;
    credito(ctx, 'Tero et al.', 'SCIENCE, 2010 · A REDE DE TÓQUIO', sstep(t0 + 0.2, t0 + 0.6, t), 196);
    simulacao(ctx, sstep(t0 + 0.4, t0 + 0.8, t), 262, 'SIMULAÇÃO · MODELO DOS AUTORES · MAPA: NATURAL EARTH');
    // as cidades (flocos de aveia)
    const ca = win(t, M.aveia - 0.1, M.liga + 1.2, 0.3, 0.5);
    if (m.cidades && ca > 0) {
      let k = 0;
      for (const [nome, [x, y]] of Object.entries(m.cidades)) {
        const [X, Y] = P(T, x, y), a = ca * sstep(M.aveia + k * 0.03, M.aveia + 0.3 + k * 0.03, t); k++;
        ctx.save(); ctx.globalAlpha = a; ctx.strokeStyle = 'rgba(255,240,200,0.9)'; ctx.lineWidth = 2; ctx.beginPath(); ctx.arc(X, Y, 14 + 4 * Math.sin(t * 5 + k), 0, 6.283); ctx.stroke(); ctx.restore();
        if (['Tóquio', 'Yokohama', 'Chiba', 'Ōmiya', 'Hachiōji', 'Narita', 'Odawara', 'Tsukuba'].includes(nome))
          text(ctx, nome.toUpperCase(), X + 18, Y - 16, { font: `16px ${MONO_M}`, color: '#fff', spacing: 3, alpha: a, shadow: 8 });
      }
    }
    chip(ctx, '36 CIDADES · 1 FLOCO DE AVEIA EM CADA', 540, 1470, win(t, M.aveia + 0.2, M.liga, 0.3, 0.3), { size: 20 });
    const g = clamp((t - M.liga) / (M.trilhos - 0.3 - M.liga));
    relogio(ctx, 'TIME-LAPSE', `${Math.round(26 * g)} h`, win(t, M.liga - 0.1, SCN.regra.t0 + 0.2, 0.3, 0.3), t);
    const ra = sstep(M.trilhos - 0.1, M.trilhos + 0.3, t);
    trilhos(ctx, T, clamp((t - M.trilhos + 0.1) / 1.0), ra);
    if (ra > 0) {
      chip(ctx, 'TRILHOS DE VERDADE', 540, 1395, ra, { size: 20, dot: rgba(C.rail) });
      chip(ctx, 'REDE DA GOSMA', 540, 1460, ra, { size: 20, dot: rgba(C.slime) });
    }
  },
};
// ---- a regra: fluxo engrossa, falta de uso some (diagrama)
const BG_REGRA = (() => {
  const c = createCanvas(W, H), x = c.getContext('2d');
  const g = x.createRadialGradient(540, 960, 60, 540, 960, 1150); g.addColorStop(0, '#16130d'); g.addColorStop(1, '#050403');
  x.fillStyle = g; x.fillRect(0, 0, W, H);
  x.strokeStyle = 'rgba(255,235,190,0.05)'; x.lineWidth = 1;
  for (let i = 0; i <= W; i += 60) { x.beginPath(); x.moveTo(i, 0); x.lineTo(i, H); x.stroke(); }
  for (let j = 0; j <= H; j += 60) { x.beginPath(); x.moveTo(0, j); x.lineTo(W, j); x.stroke(); }
  return c;
})();
const QB = (p0, p1, p2, u) => [(1 - u) * (1 - u) * p0[0] + 2 * (1 - u) * u * p1[0] + u * u * p2[0], (1 - u) * (1 - u) * p0[1] + 2 * (1 - u) * u * p1[1] + u * u * p2[1]];
function tubo(ctx, p0, p1, p2, w, a, t, fluxo) {
  if (a <= 0 || w <= 0.3) return;
  const path_ = () => { ctx.beginPath(); ctx.moveTo(...p0); ctx.quadraticCurveTo(...p1, ...p2); };
  ctx.save(); ctx.globalAlpha *= a; ctx.lineCap = 'round';
  ctx.shadowColor = 'rgba(255,190,40,0.6)'; ctx.shadowBlur = w * 1.2;
  path_(); ctx.strokeStyle = '#b7860c'; ctx.lineWidth = w; ctx.stroke(); ctx.shadowBlur = 0;
  path_(); ctx.strokeStyle = '#ffcf33'; ctx.lineWidth = w * 0.72; ctx.stroke();
  path_(); ctx.strokeStyle = 'rgba(255,250,210,0.75)'; ctx.lineWidth = Math.max(1, w * 0.18); ctx.stroke();
  // partículas do fluxo (protoplasma correndo)
  const n = 14, v = 0.12 * fluxo;
  for (let i = 0; i < n; i++) {
    const u = ((i / n + t * v) % 1 + 1) % 1, [x, y] = QB(p0, p1, p2, u);
    ctx.fillStyle = 'rgba(255,255,235,0.85)'; ctx.beginPath(); ctx.arc(x, y, Math.max(1.5, w * 0.16), 0, 6.283); ctx.fill();
  }
  ctx.restore();
}
function floco(ctx, x, y, s, a) {
  ctx.save(); ctx.globalAlpha *= a; ctx.translate(x, y); ctx.rotate(0.4);
  ctx.shadowColor = 'rgba(0,0,0,0.7)'; ctx.shadowBlur = 16; ctx.shadowOffsetY = 6;
  const g = ctx.createRadialGradient(-s * 0.3, -s * 0.3, 2, 0, 0, s * 1.2); g.addColorStop(0, '#efe0b8'); g.addColorStop(1, '#a8915e');
  ctx.fillStyle = g; ctx.beginPath(); ctx.ellipse(0, 0, s * 1.2, s * 0.8, 0, 0, 6.283); ctx.fill(); ctx.restore();
}
S.regra = {
  async bg(ctx, t, lt) {
    ctx.drawImage(BG_REGRA, 0, 0);
    const A = [190, 980], B = [890, 980];
    const g = sstep(M.engrossa - 0.2, M.engrossa + 0.8, t), s = sstep(M.some - 0.3, M.some + 1.2, t);
    tubo(ctx, A, [540, 700], B, lerp(16, 38, g), 1, t, lerp(1, 2.2, g));
    tubo(ctx, A, [540, 1380], B, lerp(16, 2, s), 1 - s * 0.9, t, lerp(1, 0.3, s));
    floco(ctx, ...A, 42, 1); floco(ctx, ...B, 42, 1);
  },
  fg(ctx, t, lt) {
    const t0 = SCN.regra.t0;
    const a = sstep(t0 + 0.1, t0 + 0.5, t);
    text(ctx, 'dD/dt = f(|Q|) − D', 540, 400, { font: `500 58px ${MONO_M}`, color: '#fff6df', align: 'center', alpha: a, shadow: 20 });
    text(ctx, 'D = ESPESSURA DO TUBO · Q = FLUXO', 540, 452, { font: `19px ${MONO}`, color: 'rgba(255,236,190,0.85)', align: 'center', spacing: 4, alpha: a });
    chip(ctx, 'MAIS FLUXO → ENGROSSA', 540, 770, win(t, M.engrossa - 0.1, SCN.memoria.t0 + 0.2, 0.25, 0.3), { size: 21, dot: rgba(C.slime) });
    chip(ctx, 'QUASE SEM USO → SOME', 540, 1290, win(t, M.some - 0.1, SCN.memoria.t0 + 0.2, 0.25, 0.3), { size: 21, dot: 'rgba(255,90,74,0.9)' });
    credito(ctx, 'Tero, Kobayashi & Nakagaki', 'JOURNAL OF THEORETICAL BIOLOGY, 2007', a, 1700);
  },
};
// ---- memória: rastro (Reid 2012), sal (Boisseau 2016), fusão (Vogel & Dussutour 2016)
S.memoria = {
  async bg(ctx, t, lt) {
    const a1 = M.sal - 0.12, a2 = M.junta - 0.12, t0 = SCN.memoria.t0;
    if (t < a1) await shot(ctx, 'rastro', (COUNT.rastro - 1) * clamp((t - t0) / (a1 - t0)), { z: 1.04, cx: 540, cy: 1060 });
    else if (t < a2) await shot(ctx, 'sal', (COUNT.sal - 1) * clamp((t - a1) / (a2 - a1)), { z: 1.0, cx: 540, cy: 990 });
    else {
      const fa = META.fusao.fusao || 82, k = t < M.aprende - 0.3 ? fa * clamp((t - a2) / (M.aprende - 0.3 - a2)) : fa + (COUNT.fusao - 1 - fa) * clamp((t - M.aprende + 0.3) / 1.4);
      await shot(ctx, 'fusao', k, { z: 1.0, cx: 540, cy: 990 });
    }
    // cortes rápidos entre as três provas
    for (const c of [a1, a2]) { const d = t - c; if (d >= 0 && d < 0.25) { ctx.fillStyle = `rgba(255,240,210,${0.35 * (1 - d / 0.25)})`; ctx.fillRect(0, 0, W, H); } }
  },
  fg(ctx, t, lt) {
    const a1 = M.sal - 0.12, a2 = M.junta - 0.12, t0 = SCN.memoria.t0, fim = SCN.fecho.t0 + 0.2;
    // rastro
    const r = win(t, t0 + 0.2, a1, 0.3, 0.12);
    credito(ctx, 'Reid et al.', 'PNAS, 2012 · MEMÓRIA ESPACIAL EXTERNA', r, 196); simulacao(ctx, r, 262);
    chip(ctx, 'MUCO: "JÁ PASSEI AQUI"', 300, 330 + 120, win(t, M.rastro + 0.2, a1, 0.3, 0.12), { size: 19 });
    // sal
    const s = win(t, a1, a2, 0.12, 0.12);
    credito(ctx, 'Boisseau, Vogel & Dussutour', 'PROC. R. SOC. B, 2016 · HABITUAÇÃO SEM NEURÔNIOS', s, 196); simulacao(ctx, s, 262);
    const ys = (META.sal.pontes || [640, 990, 1340]);
    ['DIA 1', 'DIA 3', 'DIA 5'].forEach((d, j) => chip(ctx, d, 80, ys[j] - 112, s, { size: 19, align: 'left' }));
    chip(ctx, 'SAL', 540, ys[0] - 112, s, { size: 19, dot: 'rgba(230,236,245,0.95)' });
    // fusão
    const f = win(t, a2, fim, 0.12, 0.3);
    credito(ctx, 'Vogel & Dussutour', 'PROC. R. SOC. B, 2016 · APRENDIZADO PASSADO POR FUSÃO', f, 196); simulacao(ctx, f, 262);
    const A = META.fusao.A || [330, 720], B = META.fusao.B || [760, 1260];
    chip(ctx, 'JÁ APRENDEU', A[0], A[1] - 150, f, { size: 19, dot: rgba([90, 215, 255]) });
    const nv = 1 - sstep(M.aprende - 0.1, M.aprende + 0.3, t);
    chip(ctx, 'NUNCA VIU SAL', B[0], B[1] + 160, f * nv, { size: 19 });
    chip(ctx, 'APRENDEU TAMBÉM', B[0], B[1] + 160, f * (1 - nv), { size: 19, dot: rgba([90, 215, 255]) });
    relogio(ctx, 'TIME-LAPSE', null, win(t, t0, fim, 0.3, 0.3), t);
  },
};
// ---- fecho: zero neurônios
S.fecho = {
  async bg(ctx, t, lt) {
    const p = clamp(lt / (SCN.cta.t0 - SCN.fecho.t0));
    await shot(ctx, 'macro', NM() - 1, { z: lerp(1.5, 1.0, easeOutCubic(p)), cx: 560, cy: lerp(1150, 960, p) });
    ctx.fillStyle = `rgba(0,0,0,${0.35 * sstep(M.zero - 0.4, M.zero + 0.3, t)})`; ctx.fillRect(0, 0, W, H);
  },
  fg(ctx, t, lt) {
    const a = win(t, M.zero - 0.3, SCN.cta.t0 + 0.2, 0.35, 0.4), pop = easeOutBack((t - M.zero + 0.3) / 0.45);
    if (a > 0) {
      ctx.save(); ctx.translate(540, 820); ctx.scale(0.8 + 0.2 * pop, 0.8 + 0.2 * pop);
      text(ctx, '0', 0, 80, { font: `900 300px ${FONT}`, color: '#fff6df', align: 'center', alpha: a, shadow: 40, stroke: 14 });
      text(ctx, 'NEURÔNIOS', 0, 170, { font: `500 34px ${MONO_M}`, color: 'rgba(255,224,140,0.95)', align: 'center', spacing: 14, alpha: a });
      ctx.restore();
    }
  },
};
S.cta = { async bg(ctx, t, lt) { ctaScene(ctx, t, lt); }, fg() {} };

// ---------------------------------------------------------------- composição
const SCENES = [
  { name: 'hook', t0: -1, local0: 0 },
  { name: 'nome', t0: REW[1] - 0.02, tr: 'cut' },
  { name: 'labirinto', t0: L.labirinto.start - 0.35, tr: 'dissolve' },
  { name: 'toquio', t0: L.toquio.start - 0.35, tr: 'dissolve' },
  { name: 'regra', t0: L.regra.start - 0.3, tr: 'dissolve' },
  { name: 'memoria', t0: L.memoria.start - 0.35, tr: 'dissolve' },
  { name: 'fecho', t0: L.fecho.start - 0.4, tr: 'dissolve' },
  { name: 'cta', t0: L.cta.start - 0.45, tr: 'dissolve' },
  { name: 'hook', t0: TL.total - 0.5, local0: TL.total, tr: 'dissolve' },
];
const SCN = {}; SCENES.forEach(s => { if (!SCN[s.name]) SCN[s.name] = s; });
const TR = { cut: 0, dissolve: 0.5 };
const vignette = (() => { const c = createCanvas(W, H), x = c.getContext('2d'); const g = x.createRadialGradient(W / 2, H * 0.47, H * 0.22, W / 2, H * 0.5, H * 0.75); g.addColorStop(0, 'rgba(0,0,0,0)'); g.addColorStop(1, 'rgba(0,0,0,0.72)'); x.fillStyle = g; x.fillRect(0, 0, W, H); return c; })();
const topVeil = (() => { const c = createCanvas(W, 620), x = c.getContext('2d'); const g = x.createLinearGradient(0, 0, 0, 620); g.addColorStop(0, 'rgba(0,0,0,0.62)'); g.addColorStop(1, 'rgba(0,0,0,0)'); x.fillStyle = g; x.fillRect(0, 0, W, 620); return c; })();
const botVeil = (() => { const c = createCanvas(W, 700), x = c.getContext('2d'); const g = x.createLinearGradient(0, 0, 0, 700); g.addColorStop(0, 'rgba(0,0,0,0)'); g.addColorStop(1, 'rgba(0,0,0,0.72)'); x.fillStyle = g; x.fillRect(0, 0, W, 700); return c; })();
const GRAIN = Array.from({ length: 4 }, (_, k) => { const c = createCanvas(540, 960), x = c.getContext('2d'), im = x.createImageData(540, 960), r = rng(60 + k); for (let q = 0; q < im.data.length; q += 4) { const v = r() * 255; im.data[q] = im.data[q + 1] = im.data[q + 2] = v; im.data[q + 3] = 12; } x.putImageData(im, 0, 0); return c; });
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
const BLOOM = { hook: 0.3, nome: 0.3, labirinto: 0.25, toquio: 0.3, regra: 0.35, memoria: 0.28, fecho: 0.3, cta: 0 };
async function frame(i, opts = {}) {
  const t = i / FPS;
  let cur = 0; for (let k = 0; k < SCENES.length; k++) if (t >= SCENES[k].t0) cur = k;
  const sc = SCENES[cur], into = t - sc.t0, trd = TR[sc.tr || 'cut'] || 0, inTr = cur > 0 && into < trd;
  ctx.save(); ctx.fillStyle = '#000'; ctx.fillRect(0, 0, W, H);
  if (inTr) {
    const p = easeInOutCubic(into / trd), prev = SCENES[cur - 1];
    await renderBg(ctxA, prev, t); await renderBg(ctxB, sc, t);
    ctx.drawImage(bufA, 0, 0); ctx.globalAlpha = p; ctx.drawImage(bufB, 0, 0); ctx.globalAlpha = 1;
  } else { await renderBg(ctxA, sc, t); ctx.drawImage(bufA, 0, 0); }
  ctx.restore();
  const bl = inTr ? lerp(BLOOM[SCENES[cur - 1].name] || 0, BLOOM[sc.name] || 0, into / trd) : (BLOOM[sc.name] || 0);
  if (bl > 0) bloom(bl);
  // rebobinar (assinatura da série)
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
  if (!opts.noCaptions) drawCaptions(ctx, t);
}

// ---------------------------------------------------------------- main
(async () => {
  const argv = process.argv.slice(2), pi = argv.indexOf('--preview');
  if (argv.includes('--capa')) {
    const T = await shot(ctx, 'toquio', COUNT.toquio - 1, { z: 1.12, cx: 560, cy: 860 });
    trilhos(ctx, T, 1, 0.85);
    bloom(0.35);
    ctx.drawImage(vignette, 0, 0);
    const g = ctx.createLinearGradient(0, 1000, 0, H); g.addColorStop(0, 'rgba(0,0,0,0)'); g.addColorStop(0.45, 'rgba(0,0,0,0.85)'); g.addColorStop(1, 'rgba(0,0,0,0.96)');
    ctx.fillStyle = g; ctx.fillRect(0, 1000, W, H - 1000);
    text(ctx, 'PHYSARUM POLYCEPHALUM', W / 2, 1290, { font: `26px ${MONO_M}`, color: 'rgba(255,224,140,0.95)', align: 'center', spacing: 10 });
    text(ctx, 'A gosma sem cérebro', W / 2, 1420, { font: `italic 400 104px ${SERIF_I}`, color: '#fff6df', align: 'center', shadow: 30 });
    text(ctx, 'que refez os trens de Tóquio', W / 2, 1520, { font: `italic 400 72px ${SERIF_I}`, color: '#fff6df', align: 'center', shadow: 30 });
    chip(ctx, 'TRILHOS DE VERDADE', 300, 1640, 1, { size: 18, dot: rgba(C.rail) }); chip(ctx, 'REDE DA GOSMA', 780, 1640, 1, { size: 18, dot: rgba(C.slime) });
    text(ctx, 'Simulação com o modelo de Tero et al. · mapa: Natural Earth', W - 60, 1780, { font: `500 18px ${FONT}`, color: 'rgba(240,228,205,0.6)', align: 'right' });
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
      '-c:v', 'libx264', '-preset', 'slow', '-crf', '22', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', out], { stdio: ['pipe', 'inherit', 'inherit'] });
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
