// História #1 — "O vulcão que criou o Frankenstein"
// Imagens de acervos de domínio público / CC0: gravuras da 1ª ed. ilustrada de Frankenstein (1831, Internet Archive),
// The Vampyre (1819, Internet Archive), retrato de Mary Shelley (gravura, 1889, Internet Archive), Villa Diodati
// (Rijksmuseum), Lord Byron (litografia segundo Rembrandt Peale, Art Institute of Chicago), A erupção do Vesúvio
// (Volaire, 1771, AIC), tempestade de neve (Turner, AIC), caricatura das draisianas (1819, Library of Congress),
// mapa-múndi de 1817 (Library of Congress) e a cratera do Tambora vista do espaço (NASA, 1988).
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



// ---------------------------------------------------------------- acervo
const IMG = {};
const ARQ = ['frankenstein_1831_gravura', 'frankenstein_1831_rosto', 'mary_shelley', 'o_vampiro_1819', 'villa_diodati', 'byron',
  'draisianas_1819', 'mapa_1817', 'erupcao_volaire', 'turner_tempestade', 'tambora_nasa'];
async function loadImages() { for (const k of ARQ) IMG[k] = await loadImage(path.join(ROOT, 'assets', k + '.jpg')); }
const SEPIA = [214, 186, 140];

// Ken Burns por ponto focal: a e b = {x, y (frações da imagem), z (1 = cobrir a tela)}; devolve a transformação
function kb(ctx, img, p, a, b, { alpha = 1, ease = true } = {}) {
  const q = ease ? easeInOutCubic(p) : clamp(p);
  const x = lerp(a.x, b.x, q), y = lerp(a.y, b.y, q), z = lerp(a.z, b.z, q);
  const s = Math.max(W / img.width, H / img.height) * z, iw = img.width * s, ih = img.height * s;
  const ox = clamp(W / 2 - x * iw, W - iw, 0), oy = clamp(H / 2 - y * ih, H - ih, 0);
  ctx.save(); ctx.globalAlpha *= alpha; ctx.drawImage(img, ox, oy, iw, ih); ctx.restore();
  return { ox, oy, s };
}
// mesa escura de arquivo, para mostrar páginas como documentos
const TABLE = (() => {
  const c = createCanvas(W, H), x = c.getContext('2d');
  const g = x.createRadialGradient(540, 860, 100, 540, 960, 1200); g.addColorStop(0, '#2a2118'); g.addColorStop(1, '#0b0805');
  x.fillStyle = g; x.fillRect(0, 0, W, H);
  const im = x.getImageData(0, 0, W, H), r = rng(5);
  for (let i = 0; i < im.data.length; i += 4) { const n = (r() - 0.5) * 18; im.data[i] += n; im.data[i + 1] += n; im.data[i + 2] += n; }
  x.putImageData(im, 0, 0); return c;
})();
function docCard(ctx, img, p, { w = 820, cy = 880, rot = -0.015, z0 = 1, z1 = 1.12, fy0 = 0.5, fy1 = 0.5 } = {}) {
  ctx.drawImage(TABLE, 0, 0);
  const z = lerp(z0, z1, easeInOutCubic(p)), h = w * img.height / img.width;
  const fy = lerp(fy0, fy1, easeInOutCubic(p));
  ctx.save(); ctx.translate(540, cy); ctx.rotate(rot); ctx.scale(z, z); ctx.translate(0, (0.5 - fy) * h);
  ctx.shadowColor = 'rgba(0,0,0,0.75)'; ctx.shadowBlur = 50; ctx.shadowOffsetY = 18; ctx.fillStyle = '#d9c9a6'; ctx.fillRect(-w / 2, -h / 2, w, h); ctx.shadowBlur = 0;
  ctx.drawImage(img, -w / 2, -h / 2, w, h); ctx.restore();
}

// ---------------------------------------------------------------- mapa de 1817: o Tambora e a nuvem
const TAMB = { x: 6068, y: 3014 }, KM_PX = 1 / 6.9; // ~16 px por grau perto do Equador nesta gravura
function mapView(ctx, p, a, b) { return kb(ctx, IMG.mapa_1817, p, { x: a.x / IMG.mapa_1817.width, y: a.y / IMG.mapa_1817.height, z: a.z }, { x: b.x / IMG.mapa_1817.width, y: b.y / IMG.mapa_1817.height, z: b.z }); }
const toScr = (T, mx, my) => [T.ox + mx * T.s, T.oy + my * T.s];
function pin(ctx, T, a, lt) {
  if (a <= 0) return;
  const [x, y] = toScr(T, TAMB.x, TAMB.y);
  glowAt(ctx, x, y, 60, [255, 80, 40], 0.6 * a * (0.7 + 0.3 * Math.sin(lt * 6)));
  ctx.save(); ctx.globalAlpha *= a; ctx.fillStyle = '#b3241a'; ctx.strokeStyle = '#fff3e0'; ctx.lineWidth = 3;
  ctx.beginPath(); ctx.arc(x, y, 11, 0, 6.283); ctx.fill(); ctx.stroke(); ctx.restore();
  text(ctx, 'TAMBORA', x + 24, y - 18, { font: `600 30px ${MONO_M}`, color: '#2a1206', spacing: 5, alpha: a });
}
const HAZE = (() => { // textura de névoa (enxofre) em baixa resolução
  const w = 270, h = 480, c = createCanvas(w, h), x = c.getContext('2d'), im = x.createImageData(w, h);
  for (let j = 0; j < h; j++) for (let i = 0; i < w; i++) {
    const n = 0.5 + 0.5 * noise3(i * 0.03, j * 0.03, 2.7) + 0.25 * noise3(i * 0.08, j * 0.08, 5.1);
    const q = (j * w + i) * 4; im.data[q] = 140; im.data[q + 1] = 125; im.data[q + 2] = 95; im.data[q + 3] = clamp(n, 0, 1) * 255;
  }
  x.putImageData(im, 0, 0); return c;
})();
function veil(ctx, T, R, a, lt) { // nuvem que se espalha a partir do Tambora
  if (a <= 0) return;
  const [x, y] = toScr(T, TAMB.x, TAMB.y), r = R * T.s;
  const mask = scratch2x; mask.save(); mask.setTransform(1, 0, 0, 1, 0, 0); mask.clearRect(0, 0, W, H);
  mask.globalAlpha = 1; mask.drawImage(HAZE, -60 + Math.sin(lt * 0.2) * 40, -40, W + 120, H + 80);
  mask.globalCompositeOperation = 'destination-in';
  const g = mask.createRadialGradient(x, y, r * 0.2, x, y, Math.max(r, 1)); g.addColorStop(0, 'rgba(0,0,0,1)'); g.addColorStop(0.75, 'rgba(0,0,0,0.85)'); g.addColorStop(1, 'rgba(0,0,0,0)');
  mask.fillStyle = g; mask.fillRect(0, 0, W, H); mask.restore();
  ctx.save(); ctx.globalAlpha *= a * 0.85; ctx.globalCompositeOperation = 'multiply'; ctx.drawImage(scratch2, 0, 0); ctx.restore();
}
const scratch2 = createCanvas(W, H), scratch2x = scratch2.getContext('2d');

// ---------------------------------------------------------------- partículas: chuva, neve, brasas, relâmpagos
const RAIN = Array.from({ length: 260 }, (_, i) => { const r = rng(300 + i); return { x: r() * W * 1.3, y: r() * H, v: 1600 + r() * 900, l: 30 + r() * 50, a: 0.08 + r() * 0.18 }; });
function rain(ctx, lt, a = 1) {
  if (a <= 0) return;
  ctx.save(); ctx.globalCompositeOperation = 'screen'; ctx.strokeStyle = '#dfe6ee'; ctx.lineWidth = 1.6;
  for (const d of RAIN) { const y = (d.y + lt * d.v) % (H + 100) - 50, x = (d.x - lt * d.v * 0.12) % (W * 1.3); ctx.globalAlpha = d.a * a; ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x - d.l * 0.12, y + d.l); ctx.stroke(); }
  ctx.restore();
}
const SNOW = Array.from({ length: 220 }, (_, i) => { const r = rng(700 + i); return { x: r() * W, y: r() * H, v: 60 + r() * 140, s: 1.5 + r() * 4, ph: r() * 6.28 }; });
function snow(ctx, lt, a = 1) {
  if (a <= 0) return;
  ctx.save(); ctx.fillStyle = '#fff';
  for (const f of SNOW) { const y = (f.y + lt * f.v) % (H + 40) - 20, x = (f.x + Math.sin(lt * 1.3 + f.ph) * 30) % W; ctx.globalAlpha = a * (0.35 + 0.5 * (f.s / 5.5)); ctx.beginPath(); ctx.arc(x, y, f.s, 0, 6.283); ctx.fill(); }
  ctx.restore();
}
const EMBER = Array.from({ length: 120 }, (_, i) => { const r = rng(1100 + i); return { x: r() * W, y: r() * H, v: 80 + r() * 220, s: 1 + r() * 3, ph: r() * 6.28 }; });
function embers(ctx, lt, a = 1) {
  if (a <= 0) return;
  ctx.save(); ctx.globalCompositeOperation = 'screen';
  for (const e of EMBER) { const y = H - ((H - e.y + lt * e.v) % (H + 40)), x = e.x + Math.sin(lt * 2 + e.ph) * 24; glowAt(ctx, x, y, e.s * 5, [255, 140, 50], 0.55 * a); }
  ctx.restore();
}
function lightning(ctx, t, strikes) { // clarão duplo de relâmpago
  let v = 0;
  for (const s of strikes) { const d = t - s; if (d < 0 || d > 0.6) continue; v = Math.max(v, Math.exp(-d * 9) + 0.6 * Math.exp(-Math.pow((d - 0.18) * 14, 2))); }
  if (v > 0.01) { ctx.save(); ctx.globalCompositeOperation = 'screen'; ctx.fillStyle = `rgba(225,232,255,${Math.min(0.55, v * 0.5)})`; ctx.fillRect(0, 0, W, H); ctx.restore(); }
}

// ---------------------------------------------------------------- tipografia de arquivo
function museum(ctx, title, meta, a, y = 330) { // etiqueta de museu (também é o crédito)
  if (a <= 0) return;
  ctx.save(); ctx.globalAlpha *= a;
  ctx.fillStyle = 'rgba(255,240,215,0.85)'; ctx.fillRect(70, y - 46, 3, 74);
  text(ctx, title, 92, y, { font: `italic 400 44px ${SERIF_I}`, color: '#fff3e0', shadow: 16 });
  text(ctx, meta, 94, y + 34, { font: `17px ${MONO}`, color: 'rgba(240,228,205,0.85)', spacing: 3, shadow: 10 });
  ctx.restore();
}
function dateCard(ctx, big, small, a, y = 900) {
  if (a <= 0) return;
  ctx.save(); ctx.globalAlpha *= a;
  text(ctx, big, 540, y, { font: `400 128px ${SERIF}`, color: '#f4e6c8', align: 'center', shadow: 30 });
  ctx.fillStyle = 'rgba(244,230,200,0.7)'; const w = 300 * easeOutCubic(a); ctx.fillRect(540 - w, y + 40, 2 * w, 2);
  text(ctx, small, 540, y + 92, { font: `22px ${MONO}`, color: 'rgba(240,228,205,0.85)', align: 'center', spacing: 6 });
  ctx.restore();
}
function tag(ctx, s, y, a, opts = {}) { chip(ctx, s, 540, y, a, Object.assign({ col: 'rgba(250,238,215,0.95)', size: 22 }, opts)); }

// ================================================================ cenas (bg recebe o acabamento; fg são os textos)
const S = {};
// ---- gancho: a erupção → o monstro → o vampiro → a draisiana; depois rebobina
S.hook = {
  async bg(ctx, t, lt) {
    const tt = lt <= REW[0] ? lt : lerp(REW[0], 0, easeInOutCubic((lt - REW[0]) / (REW[1] - REW[0])));
    const c1 = Wt('hook', 10) - 0.05, c2 = Wt('hook2', 3) - 0.05, c3 = Wt('hook2', 8) - 0.05;
    if (tt < c1) { kb(ctx, IMG.erupcao_volaire, tt / c1, { x: 0.2, y: 0.42, z: 1.18 }, { x: 0.27, y: 0.4, z: 1.32 }); embers(ctx, tt, 0.9); }
    else if (tt < c2) { kb(ctx, IMG.frankenstein_1831_gravura, (tt - c1) / (c2 - c1), { x: 0.35, y: 0.48, z: 1.05 }, { x: 0.32, y: 0.45, z: 1.35 }); lightning(ctx, tt, [c1 + 0.05, c1 + 1.1]); }
    else if (tt < c3) docCard(ctx, IMG.o_vampiro_1819, (tt - c2) / (c3 - c2), { w: 760, z0: 1.15, z1: 1.3, fy0: 0.25, fy1: 0.3 });
    else kb(ctx, IMG.draisianas_1819, (tt - c3) / 2, { x: 0.33, y: 0.14, z: 2.6 }, { x: 0.37, y: 0.14, z: 2.9 });
  },
  fg(ctx, t, lt) {},
};
// ---- Abril de 1815: cartela, o mapa de 1817 e a erupção
S.tambora = {
  async bg(ctx, t, lt) {
    const tMap = Wt('tambora', 3) - 0.1;
    if (t < tMap) { ctx.drawImage(TABLE, 0, 0); return; }
    if (t < M.boom) {
      const T = mapView(ctx, (t - tMap) / (M.boom - tMap), { x: 4700, y: 2700, z: 1.0 }, { x: TAMB.x, y: TAMB.y, z: 3.4 });
      this.T = T; return;
    }
    kb(ctx, IMG.erupcao_volaire, (t - M.boom) / 2.8, { x: 0.22, y: 0.42, z: 1.12 }, { x: 0.2, y: 0.38, z: 1.3 });
    embers(ctx, t, 1);
    const f = t - M.boom; if (f < 0.5) { ctx.save(); ctx.globalCompositeOperation = 'screen'; ctx.fillStyle = `rgba(255,190,120,${0.85 * Math.pow(1 - f / 0.5, 2)})`; ctx.fillRect(0, 0, W, H); ctx.restore(); }
  },
  fg(ctx, t, lt) {
    const tMap = Wt('tambora', 3) - 0.1;
    dateCard(ctx, 'Abril de 1815', 'MONTE TAMBORA · SUMBAWA, INDONÉSIA', win(t, SCN.tambora.t0 + 0.1, tMap + 0.05, 0.35, 0.15));
    if (t >= tMap && t < M.boom && this.T) { pin(ctx, this.T, sstep(Wt('tambora', 6) - 0.3, Wt('tambora', 7), t), t); museum(ctx, 'Mapa-múndi, 1817', 'LIBRARY OF CONGRESS', sstep(tMap + 0.2, tMap + 0.6, t)); }
    if (t >= M.boom) museum(ctx, 'A erupção do Vesúvio, 1771', 'ILUSTRATIVO · P.-J. VOLAIRE · ART INSTITUTE OF CHICAGO', sstep(M.boom + 0.4, M.boom + 0.9, t));
  },
};
// ---- o estrondo e a nuvem de enxofre
S.som = {
  async bg(ctx, t, lt) {
    const tN = L.nuvem.start - 0.3, p = clamp((t - SCN.som.t0) / (SCN.verao.t0 - SCN.som.t0));
    const T = mapView(ctx, p, { x: TAMB.x, y: TAMB.y, z: 2.6 }, { x: 4300, y: 2500, z: 1.0 });
    const R = 4200 * easeInCubic(clamp((t - tN) / (SCN.verao.t0 - tN)));
    veil(ctx, T, R, sstep(tN, tN + 0.5, t), t);
    const dim = 0.45 * sstep(Wt('nuvem', 8), Wt('nuvem', 13, 't1'), t); if (dim > 0) { ctx.fillStyle = `rgba(20,14,8,${dim})`; ctx.fillRect(0, 0, W, H); }
    this.T = T;
  },
  fg(ctx, t, lt) {
    const T = this.T; if (!T) return;
    const [x, y] = toScr(T, TAMB.x, TAMB.y), rmax = 2000 * KM_PX * T.s;
    // ondas do estrondo até 2.000 km
    const t0 = SCN.som.t0 + 0.2;
    ctx.save(); ctx.strokeStyle = '#7a1c10'; ctx.lineWidth = 3;
    for (let k = 0; k < 4; k++) { const q = clamp((t - t0 - k * 0.35) / 1.6); if (q <= 0 || q >= 1) continue; ctx.globalAlpha = (1 - q) * 0.9; ctx.beginPath(); ctx.arc(x, y, q * rmax * 1.05, 0, 6.283); ctx.stroke(); }
    const ra = win(t, t0 + 0.8, L.nuvem.start, 0.3, 0.3);
    ctx.globalAlpha = ra * 0.85; ctx.setLineDash([10, 8]); ctx.beginPath(); ctx.arc(x, y, rmax, 0, 6.283); ctx.stroke(); ctx.setLineDash([]); ctx.restore();
    pin(ctx, T, 1 - sstep(L.nuvem.start - 0.4, L.nuvem.start, t), t);
    tag(ctx, 'OUVIDO A MAIS DE 2.000 km', 470, ra);
    tag(ctx, 'A MONTANHA PERDEU QUASE 1,5 km DE ALTURA', 530, win(t, Wt('som', 7), L.nuvem.start, 0.3, 0.3));
    tag(ctx, 'ENXOFRE NA ESTRATOSFERA, AO REDOR DO MUNDO', 470, win(t, Wt('nuvem', 2), SCN.verao.t0 + 0.1, 0.3, 0.3));
    museum(ctx, 'Mapa-múndi, 1817', 'LIBRARY OF CONGRESS', sstep(SCN.som.t0, SCN.som.t0 + 0.4, t), 1290);
  },
};
// ---- 1816, o ano sem verão
S.verao = {
  async bg(ctx, t, lt) {
    kb(ctx, IMG.turner_tempestade, lt / 7, { x: 0.45, y: 0.45, z: 1.05 }, { x: 0.6, y: 0.4, z: 1.25 });
    snow(ctx, lt, sstep(Wt('verao', 6) - 0.4, Wt('verao', 6) + 0.2, t) * 0.9 + 0.1);
    ctx.fillStyle = 'rgba(20,24,30,0.2)'; ctx.fillRect(0, 0, W, H);
  },
  fg(ctx, t, lt) {
    dateCard(ctx, '1816', 'O ANO SEM VERÃO', win(t, SCN.verao.t0 + 0.05, Wt('verao', 6) - 0.1, 0.3, 0.3), 880);
    tag(ctx, 'NEVE EM JUNHO · NOVA INGLATERRA, EUA', 470, win(t, Wt('verao', 6), Wt('verao', 12), 0.25, 0.25));
    tag(ctx, 'A ÚLTIMA GRANDE FOME DO OCIDENTE', 470, win(t, Wt('verao', 13), SCN.suica.t0 + 0.1, 0.25, 0.3));
    museum(ctx, 'Vale de Aosta: tempestade de neve, 1836–37', 'ILUSTRATIVO · J. M. W. TURNER · ART INSTITUTE OF CHICAGO', sstep(Wt('verao', 6), Wt('verao', 6) + 0.5, t), 1290);
  },
};
// ---- Suíça: chuva, a Villa Diodati, Byron e o desafio
S.suica = {
  async bg(ctx, t, lt) {
    if (t < M.byron - 0.05) {
      kb(ctx, IMG.villa_diodati, (t - SCN.suica.t0) / (M.byron - SCN.suica.t0), { x: 0.3, y: 0.5, z: 1.0 }, { x: 0.32, y: 0.45, z: 1.35 });
      ctx.fillStyle = 'rgba(15,18,24,0.35)'; ctx.fillRect(0, 0, W, H);
      rain(ctx, lt, 1); lightning(ctx, t, [M.trovao + 0.1, Wt('suica', 6) + 0.2]);
    } else {
      kb(ctx, IMG.byron, (t - M.byron) / (SCN.mary.t0 - M.byron), { x: 0.45, y: 0.32, z: 1.05 }, { x: 0.43, y: 0.3, z: 1.3 });
      rain(ctx, lt, 0.35); lightning(ctx, t, [Wt('suica', 20)]);
    }
  },
  fg(ctx, t, lt) {
    if (t < M.byron - 0.05) museum(ctx, 'Villa Diodati, Lago de Genebra', 'GRAVURA DO SÉC. XIX · RIJKSMUSEUM', sstep(SCN.suica.t0 + 0.3, SCN.suica.t0 + 0.8, t));
    else museum(ctx, 'Lord Byron', 'LITOGRAFIA SEGUNDO REMBRANDT PEALE · ART INSTITUTE OF CHICAGO', sstep(M.byron + 0.2, M.byron + 0.6, t));
    tag(ctx, 'JUNHO DE 1816', 470, win(t, Wt('suica', 5), M.byron, 0.3, 0.2));
    tag(ctx, '"CADA UM VAI ESCREVER UMA HISTÓRIA DE FANTASMAS"', 1300, win(t, Wt('suica', 20) - 0.1, SCN.mary.t0 + 0.1, 0.3, 0.3), { size: 20 });
  },
};
// ---- Mary Shelley e Frankenstein
S.mary = {
  async bg(ctx, t, lt) {
    const nasce = Wt('mary', 18) - 0.05;
    if (t < M.visao - 0.05) { kb(ctx, IMG.mary_shelley, (t - SCN.mary.t0) / (M.visao - SCN.mary.t0), { x: 0.5, y: 0.42, z: 1.0 }, { x: 0.5, y: 0.38, z: 1.22 }); rain(ctx, lt, 0.2); }
    else if (t < nasce) { kb(ctx, IMG.frankenstein_1831_gravura, (t - M.visao) / (nasce - M.visao), { x: 0.45, y: 0.4, z: 1.1 }, { x: 0.3, y: 0.46, z: 1.5 }); lightning(ctx, t, [M.visao + 0.05, Wt('mary', 16), Wt('mary', 17, 't1')]); }
    else docCard(ctx, IMG.frankenstein_1831_rosto, (t - nasce) / 2.4, { w: 780, z0: 1.0, z1: 1.12, fy0: 0.3, fy1: 0.3 });
  },
  fg(ctx, t, lt) {
    const nasce = Wt('mary', 18) - 0.05;
    if (t < M.visao - 0.05) museum(ctx, 'Mary Shelley', 'RETRATO DE 1840 · GRAVURA DE 1889 · INTERNET ARCHIVE', sstep(SCN.mary.t0 + 0.2, SCN.mary.t0 + 0.6, t));
    else if (t < nasce) museum(ctx, 'Frankenstein, 1831', 'GRAVURA DE THEODOR VON HOLST · INTERNET ARCHIVE', sstep(M.visao + 0.2, M.visao + 0.6, t));
    tag(ctx, '18 ANOS', 470, win(t, Wt('mary', 3) - 0.1, M.visao - 0.1, 0.25, 0.2));
    if (t >= nasce) tag(ctx, '1ª EDIÇÃO: 1818 · SEM O NOME DA AUTORA', 1390, sstep(nasce + 0.3, nasce + 0.7, t), { size: 20 });
  },
};
// ---- O Vampiro, de Polidori
S.vampiro = {
  async bg(ctx, t, lt) { docCard(ctx, IMG.o_vampiro_1819, lt / 6.5, { w: 600, cy: 930, z0: 1.0, z1: 1.16, fy0: 0.45, fy1: 0.35, rot: 0.012 }); },
  fg(ctx, t, lt) {
    tag(ctx, 'JOHN POLIDORI · MÉDICO DE BYRON', 470, win(t, Wt('vampiro', 6), Wt('vampiro', 10), 0.25, 0.25));
    tag(ctx, '1819 · PUBLICADO COMO SE FOSSE DE BYRON', 470, win(t, Wt('vampiro', 10), Wt('vampiro', 15), 0.25, 0.25));
    tag(ctx, 'ABRIU CAMINHO PARA O DRÁCULA', 470, win(t, Wt('vampiro', 15), SCN.bike.t0 + 0.1, 0.25, 0.3));
    museum(ctx, 'The Vampyre, 1819', '1ª EDIÇÃO EM LIVRO · INTERNET ARCHIVE', sstep(SCN.vampiro.t0 + 0.3, SCN.vampiro.t0 + 0.7, t), 236);
  },
};
// ---- a draisiana, avô da bicicleta
S.bike = {
  async bg(ctx, t, lt) {
    const p = (t - SCN.bike.t0) / (SCN.fecho.t0 - SCN.bike.t0);
    if (p < 0.45) kb(ctx, IMG.draisianas_1819, p / 0.45, { x: 0.22, y: 0.62, z: 1.5 }, { x: 0.5, y: 0.6, z: 1.7 });
    else kb(ctx, IMG.draisianas_1819, (p - 0.45) / 0.55, { x: 0.45, y: 0.15, z: 2.6 }, { x: 0.78, y: 0.15, z: 2.6 });
  },
  fg(ctx, t, lt) {
    tag(ctx, '1817 · KARL DRAIS · A "MÁQUINA DE CORRER"', 470, win(t, M.drais - 0.1, SCN.fecho.t0 + 0.1, 0.25, 0.3), { size: 21 });
    tag(ctx, 'SEM PEDAIS: EMPURRADA COM OS PÉS', 530, win(t, M.drais + 0.6, SCN.fecho.t0 + 0.1, 0.25, 0.3), { size: 21 });
    museum(ctx, 'Feira de draisianas, 1819', 'CARICATURA INGLESA · LIBRARY OF CONGRESS', sstep(SCN.bike.t0 + 0.3, SCN.bike.t0 + 0.7, t), 1330);
  },
};
// ---- fecho: o Tambora hoje, visto do espaço
S.fecho = {
  async bg(ctx, t, lt) { kb(ctx, IMG.tambora_nasa, lt / 7.5, { x: 0.6, y: 0.47, z: 3.2 }, { x: 0.56, y: 0.48, z: 1.25 }); },
  fg(ctx, t, lt) {
    museum(ctx, 'Tambora visto do espaço, 1988', 'NASA · ÔNIBUS ESPACIAL DISCOVERY (STS-26)', sstep(SCN.fecho.t0 + 0.3, SCN.fecho.t0 + 0.8, t));
    tag(ctx, 'A CRATERA: 6 km DE LARGURA', 470, win(t, SCN.fecho.t0 + 0.6, Wt('fecho', 11), 0.3, 0.3));
    tag(ctx, 'A LIGAÇÃO COM 1816 SÓ FOI FEITA NO SÉCULO XX', 470, win(t, Wt('fecho', 12), SCN.cta.t0 + 0.2, 0.3, 0.3), { size: 21 });
  },
};
S.cta = { async bg(ctx, t, lt) { ctaScene(ctx, t, lt); }, fg() {} };

// ---------------------------------------------------------------- composição
const SCENES = [
  { name: 'hook', t0: -1, local0: 0 },
  { name: 'tambora', t0: REW[1] - 0.02, tr: 'cut' },
  { name: 'som', t0: L.som.start - 0.35, tr: 'burn' },
  { name: 'verao', t0: L.verao.start - 0.35, tr: 'burn' },
  { name: 'suica', t0: L.suica.start - 0.4, tr: 'burn' },
  { name: 'mary', t0: L.mary.start - 0.35, tr: 'burn' },
  { name: 'vampiro', t0: L.vampiro.start - 0.4, tr: 'burn' },
  { name: 'bike', t0: L.bike.start - 0.4, tr: 'burn' },
  { name: 'fecho', t0: L.fecho.start - 0.4, tr: 'burn' },
  { name: 'cta', t0: L.cta.start - 0.45, tr: 'dissolve' },
  { name: 'hook', t0: TL.total - 0.5, local0: TL.total, tr: 'dissolve' },
];
const SCN = {}; SCENES.forEach(s => { if (!SCN[s.name]) SCN[s.name] = s; });
const TR = { cut: 0, burn: 0.55, dissolve: 0.6 };
const vignette = (() => { const c = createCanvas(W, H), x = c.getContext('2d'); const g = x.createRadialGradient(W / 2, H * 0.47, H * 0.2, W / 2, H * 0.5, H * 0.75); g.addColorStop(0, 'rgba(0,0,0,0)'); g.addColorStop(1, 'rgba(0,0,0,0.78)'); x.fillStyle = g; x.fillRect(0, 0, W, H); return c; })();
const topVeil = (() => { const c = createCanvas(W, 700), x = c.getContext('2d'); const g = x.createLinearGradient(0, 0, 0, 700); g.addColorStop(0, 'rgba(0,0,0,0.6)'); g.addColorStop(1, 'rgba(0,0,0,0)'); x.fillStyle = g; x.fillRect(0, 0, W, 700); return c; })();
const botVeil = (() => { const c = createCanvas(W, 760), x = c.getContext('2d'); const g = x.createLinearGradient(0, 0, 0, 760); g.addColorStop(0, 'rgba(0,0,0,0)'); g.addColorStop(1, 'rgba(0,0,0,0.7)'); x.fillStyle = g; x.fillRect(0, 0, W, 760); return c; })();
const GRAIN = Array.from({ length: 4 }, (_, k) => { const c = createCanvas(540, 960), x = c.getContext('2d'), im = x.createImageData(540, 960), r = rng(60 + k); for (let q = 0; q < im.data.length; q += 4) { const v = r() * 255; im.data[q] = im.data[q + 1] = im.data[q + 2] = v; im.data[q + 3] = 15; } x.putImageData(im, 0, 0); return c; });
const canvas = createCanvas(W, H), ctx = canvas.getContext('2d');
const bufA = createCanvas(W, H), ctxA = bufA.getContext('2d');
const bufB = createCanvas(W, H), ctxB = bufB.getContext('2d');
const scratch = createCanvas(W, H), sctx = scratch.getContext('2d');
const lt = (sc, t) => t - (sc.local0 !== undefined ? sc.local0 : sc.t0);
async function renderBg(target, sc, t) {
  target.save(); target.setTransform(1, 0, 0, 1, 0, 0); target.globalAlpha = 1; target.globalCompositeOperation = 'source-over';
  target.fillStyle = '#000'; target.fillRect(0, 0, W, H);
  await S[sc.name].bg(target, t, lt(sc, t)); target.restore();
}
const SHAKES = [[M.boom, 18], [M.trovao + 0.1, 5], [M.frank, 6]];
function shakeAt(t) {
  let dx = 0, dy = 0;
  for (const [t0, A] of SHAKES) { if (t < t0 || t > t0 + 1.4) continue; const e = A * Math.exp(-(t - t0) * 3.5); dx += e * noise3(t * 14, 1.3, t0); dy += e * noise3(4.1, t * 14, t0); }
  return [dx, dy];
}
// película antiga: poeira, riscos, tremulação
function filmLook(i, t, amount = 1) {
  const r = rng(i * 7919 + 13);
  ctx.save(); ctx.globalCompositeOperation = 'soft-light'; ctx.fillStyle = rgba(SEPIA, 0.32 * amount); ctx.fillRect(0, 0, W, H); ctx.restore();
  const fl = 0.035 * noise3(t * 9, 0.3, 0.7); ctx.fillStyle = fl > 0 ? `rgba(255,240,220,${fl})` : `rgba(0,0,0,${-fl})`; ctx.fillRect(0, 0, W, H);
  ctx.save(); ctx.globalAlpha = amount;
  for (let k = 0; k < 10; k++) { const x = r() * W, y = r() * H, s = 0.8 + r() * r() * 4; ctx.fillStyle = r() < 0.7 ? 'rgba(20,12,6,0.5)' : 'rgba(255,245,225,0.45)'; ctx.beginPath(); ctx.arc(x, y, s, 0, 6.283); ctx.fill(); }
  const sr = rng(Math.floor(t * 2.3) * 31 + 7); if (sr() < 0.55) { const x = sr() * W; ctx.strokeStyle = 'rgba(255,245,225,0.16)'; ctx.lineWidth = 1 + sr(); ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x + (sr() - 0.5) * 30, H); ctx.stroke(); }
  ctx.restore();
}
async function frame(i, opts = {}) {
  const t = i / FPS;
  let cur = 0; for (let k = 0; k < SCENES.length; k++) if (t >= SCENES[k].t0) cur = k;
  const sc = SCENES[cur], into = t - sc.t0, trd = TR[sc.tr || 'cut'] || 0, inTr = cur > 0 && into < trd;
  ctx.save(); ctx.fillStyle = '#000'; ctx.fillRect(0, 0, W, H);
  const [sx, sy] = shakeAt(t), wx = 1.2 * noise3(t * 3, 9.1, 0), wy = 1.2 * noise3(2.2, t * 3, 0); // tremor + balanço de quadro
  ctx.translate(sx + wx, sy + wy); if (sx || sy) { ctx.translate(W / 2, H / 2); ctx.scale(1.03, 1.03); ctx.translate(-W / 2, -H / 2); }
  if (inTr) {
    const p = easeInOutCubic(into / trd), prev = SCENES[cur - 1];
    await renderBg(ctxA, prev, t); await renderBg(ctxB, sc, t);
    ctx.drawImage(bufA, 0, 0); ctx.globalAlpha = p; ctx.drawImage(bufB, 0, 0); ctx.globalAlpha = 1;
    if (sc.tr === 'burn') { ctx.save(); ctx.globalCompositeOperation = 'screen'; const g = ctx.createRadialGradient(W * 0.7, H * 0.3, 50, W * 0.6, H * 0.4, 1400); const a = Math.sin(Math.PI * p) * 0.75; g.addColorStop(0, `rgba(255,200,120,${a})`); g.addColorStop(0.5, `rgba(255,120,40,${a * 0.5})`); g.addColorStop(1, 'rgba(0,0,0,0)'); ctx.fillStyle = g; ctx.fillRect(0, 0, W, H); ctx.restore(); }
  } else { await renderBg(ctxA, sc, t); ctx.drawImage(bufA, 0, 0); }
  ctx.restore();
  // rebobinar (assinatura da série)
  const ra = win(t, REW[0] - 0.05, REW[1] + 0.05, 0.08, 0.1);
  if (ra > 0) {
    sctx.clearRect(0, 0, W, H); sctx.drawImage(canvas, 0, 0);
    const r = rng(Math.floor(t * 60));
    for (let k = 0; k < 8; k++) { const yy = r() * H, hh = 20 + r() * 120, dx = (r() - 0.5) * 90 * ra; ctx.drawImage(scratch, 0, yy, W, hh, dx, yy, W, hh); }
    ctx.save(); ctx.globalAlpha = 0.18 * ra; ctx.fillStyle = '#000'; for (let yy = (t * 400) % 6; yy < H; yy += 6) ctx.fillRect(0, yy, W, 2); ctx.restore();
    text(ctx, '◀◀', 90, 560, { font: `900 72px ${FONT}`, color: '#fff', alpha: ra * (0.6 + 0.4 * Math.sin(t * 20)), stroke: 8 });
  }
  if (sc.name !== 'cta' || inTr) filmLook(i, t, sc.name === 'cta' ? 1 - clamp(into / trd) : 1);
  ctx.save(); ctx.globalCompositeOperation = 'overlay'; ctx.drawImage(GRAIN[i % 4], 0, 0, W, H); ctx.restore();
  ctx.drawImage(vignette, 0, 0); ctx.drawImage(topVeil, 0, 0); ctx.drawImage(botVeil, 0, H - 760);
  if (inTr) { ctx.save(); ctx.globalAlpha = 1 - clamp(into / trd); S[SCENES[cur - 1].name].fg(ctx, t, lt(SCENES[cur - 1], t)); ctx.restore(); ctx.save(); ctx.globalAlpha = clamp(into / trd); S[sc.name].fg(ctx, t, lt(sc, t)); ctx.restore(); }
  else S[sc.name].fg(ctx, t, lt(sc, t));
  if (!opts.noCaptions) drawCaptions(ctx, t);
}

// ---------------------------------------------------------------- main
(async () => {
  await loadImages();
  const argv = process.argv.slice(2), pi = argv.indexOf('--preview');
  if (argv.includes('--capa')) {
    kb(ctx, IMG.frankenstein_1831_gravura, 0, { x: 0.33, y: 0.42, z: 1.25 }, { x: 0.33, y: 0.42, z: 1.25 });
    filmLook(3, 1.3);
    ctx.drawImage(vignette, 0, 0);
    const g = ctx.createLinearGradient(0, 1050, 0, H); g.addColorStop(0, 'rgba(0,0,0,0)'); g.addColorStop(0.45, 'rgba(0,0,0,0.85)'); g.addColorStop(1, 'rgba(0,0,0,0.96)');
    ctx.fillStyle = g; ctx.fillRect(0, 1050, W, H - 1050);
    text(ctx, 'TAMBORA, 1815', W / 2, 1300, { font: `26px ${MONO_M}`, color: 'rgba(255,214,170,0.95)', align: 'center', spacing: 10 });
    text(ctx, 'O vulcão que criou', W / 2, 1430, { font: `italic 400 104px ${SERIF_I}`, color: '#fff3e0', align: 'center', shadow: 30 });
    text(ctx, 'o Frankenstein', W / 2, 1545, { font: `italic 400 104px ${SERIF_I}`, color: '#fff3e0', align: 'center', shadow: 30 });
    text(ctx, 'Gravura de Theodor von Holst, 1831 · Internet Archive', W - 60, 1780, { font: `500 18px ${FONT}`, color: 'rgba(240,228,205,0.6)', align: 'right' });
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
      '-c:v', 'libx264', '-preset', 'slow', '-crf', '23', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', out], { stdio: ['pipe', 'inherit', 'inherit'] });
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
