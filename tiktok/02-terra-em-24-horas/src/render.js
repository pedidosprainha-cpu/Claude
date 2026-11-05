// Vídeo 02 — "A história da Terra em 24 horas"
// Renderiza quadro a quadro (1080x1920, 30 fps) e envia para o ffmpeg.
//   node src/render.js                   -> build/video.mp4
//   node src/render.js --preview 3,20    -> build/preview/*.png
//   node src/render.js --capa            -> output/capa.png
const { createCanvas, loadImage } = require('@napi-rs/canvas');
const { getIconData, iconToSVG, iconToHTML, replaceIDs } = require('@iconify/utils');
const FLUENT = require('@iconify-json/fluent-emoji/icons.json');
const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');

const ROOT = path.resolve(__dirname, '..');
const TL = JSON.parse(fs.readFileSync(path.join(ROOT, 'build/timeline.json'), 'utf8'));
const W = 1080, H = 1920, FPS = TL.fps, N = TL.frames;
const DIA = 86400, IDADE = 4.54e9, HR = 3600;
const FONT = '"Inter Display"', MONO = '"JetBrains Mono"';
const C = { yellow: '#FFD23F', cyan: '#4FD1FF', red: '#FF3B4E', ink: '#070A14', label: '#8FA3C8' };

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

// ---------------------------------------------------------------- linha do tempo
const L = TL.lines;
const Wt = (line, i, k = 't0') => L[line].words[i][k];
const CLOCK = TL.clock;
const clockAt = i => { const c = CLOCK[clamp(i, 0, N - 1)]; return c >= DIA - 1e-9 ? 0 : c; };
const ERAS = [
  { c1: 2.8546 * HR, col: hex('#ff6a3d'), nome: 'HADEANO' },
  { c1: 10.784 * HR, col: hex('#a46bff'), nome: 'ARQUEANO' },
  { c1: 21.151 * HR, col: hex('#3fc1c9'), nome: 'PROTEROZOICO' },
  { c1: DIA, col: hex('#7bd65b'), nome: 'FANEROZOICO' },
];
const eraCol = c => ERAS.find(e => c < e.c1 + 1e-9) || ERAS[3];

const SCENES = [
  { name: 'space', t0: -1, local0: 0 },
  { name: 'ocean', t0: L.vida.start - 0.35 },
  { name: 'reef', t0: L.animais.start - 0.4 },
  { name: 'jurassic', t0: L.dinos.start - 0.3 },
  { name: 'cenozoic', t0: L.mamiferos.start - 0.4 },
  { name: 'sunset', t0: L.humanos.start - 0.35 },
  { name: 'ringzoom', t0: L.vidahum.start - 0.35 },
  { name: 'cta', t0: L.cta.start - 0.35 },
  { name: 'space', t0: TL.total - 0.5, local0: TL.total, fade: true },
];
const TR = 0.42; // duração da transição

// ---------------------------------------------------------------- ilustrações (Fluent Emoji, MIT)
const SPRITES = {};
const SPRITE_NAMES = ['volcano', 'comet', 'microbe', 'sleeping-face', 'jellyfish', 'shrimp', 'squid', 'coral', 'spiral-shell', 'tropical-fish',
  'sauropod', 't-rex', 'palm-tree', 'herb', 'evergreen-tree', 'mammoth', 'monkey', 'deer', 'deciduous-tree', 'person-standing', 'fire', 'camel',
  'bubbles', 'rock', 'cactus', 'seedling'];
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

// ---------------------------------------------------------------- planetas (texturas procedurais + render esférico)
const TW = 1024, TH = 512;
function makeTexture(kind) {
  const rgb = new Uint8ClampedArray(TW * TH * 3), emit = new Uint8ClampedArray(TW * TH), cloud = new Uint8ClampedArray(TW * TH);
  for (let j = 0; j < TH; j++) {
    const lat = (0.5 - (j + 0.5) / TH) * Math.PI, cl = Math.cos(lat), sl = Math.sin(lat);
    for (let i = 0; i < TW; i++) {
      const lon = ((i + 0.5) / TW) * 2 * Math.PI;
      const px = cl * Math.cos(lon), py = sl, pz = cl * Math.sin(lon);
      const k = j * TW + i; let c = [0, 0, 0], e = 0, cd = 0;
      const n = fbm3(px * 1.8 + 3, py * 1.8, pz * 1.8, 5);
      if (kind === 'molten') {
        const rid = 1 - Math.abs(fbm3(px * 3.2, py * 3.2 + 9, pz * 3.2, 4));
        const crust = mixc([22, 12, 10], [62, 34, 26], clamp(n * 1.6 + 0.5));
        const lava = Math.max(sstep(0.87, 0.97, rid), 0.85 * sstep(-0.3, -0.42, n));
        c = mixc(crust, [200, 70, 20], lava * 0.5); e = lava * 255;
      } else if (kind === 'theia') {
        c = mixc([80, 68, 60], [140, 124, 108], clamp(n * 1.5 + 0.5));
        const cr = fbm3(px * 7, py * 7, pz * 7, 2); if (cr > 0.28) c = mixc(c, [60, 50, 44], 0.6);
      } else if (kind === 'moon') {
        const m = fbm3(px * 2.2 + 11, py * 2.2, pz * 2.2, 4);
        c = mixc([175, 175, 172], [205, 205, 200], clamp(n + 0.5));
        if (m > 0.12) c = mixc(c, [92, 94, 104], sstep(0.12, 0.25, m));
        const cr = fbm3(px * 9, py * 9 + 4, pz * 9, 2); if (cr > 0.3) c = mixc(c, [120, 120, 124], 0.5);
      } else {
        const seed = kind === 'archean' ? 20 : kind === 'proto' ? 40 : 60;
        const land = fbm3(px * 1.6 + seed, py * 1.6, pz * 1.6 - seed, 6);
        const thr = kind === 'archean' ? 0.32 : kind === 'proto' ? 0.08 : 0.06;
        const ocean0 = kind === 'archean' ? [8, 52, 70] : [8, 44, 100], ocean1 = kind === 'archean' ? [22, 98, 112] : [30, 104, 178];
        c = mixc(ocean0, ocean1, clamp((land - thr + 0.5) * 1.2));
        if (land > thr) {
          const d = fbm3(px * 4 + seed, py * 4, pz * 4, 4);
          if (kind === 'archean') c = mixc([52, 46, 44], [92, 80, 70], clamp(d + 0.5));
          else if (kind === 'proto') c = mixc([120, 92, 64], [190, 160, 118], clamp(d + 0.5));
          else c = d > 0.18 ? mixc([170, 140, 90], [200, 170, 110], clamp(d)) : mixc([48, 104, 50], [104, 150, 66], clamp(d + 0.5));
          if (land < thr + 0.025) c = mixc(c, [210, 200, 160], 0.35);
        }
        if (kind !== 'archean' && Math.abs(lat) > 1.15 + 0.08 * fbm3(px * 5, py * 5, pz * 5, 2)) c = [236, 242, 248];
        cd = sstep(0.04, 0.32, fbm3(px * 2.6 - 7, py * 4.2, pz * 2.6, 5)) * 255 * (kind === 'archean' ? 0.7 : 0.9);
      }
      rgb[k * 3] = c[0]; rgb[k * 3 + 1] = c[1]; rgb[k * 3 + 2] = c[2]; emit[k] = e; cloud[k] = cd;
    }
  }
  return { rgb, emit, cloud };
}
let TEX = {};
const LIGHT = (() => { const v = [-0.62, 0.42, 0.66], n = Math.hypot(...v); return v.map(x => x / n); })();
const globeCache = {};
// desenha um planeta (raio R) num canvas próprio. texB/mix permitem transição entre eras.
function globe(texA, R, rot, o = {}) {
  const { texB = null, mix = 0, cloudRot = rot * 1.25, atm = [120, 180, 255], emitBoost = 1, light = 1 } = o;
  const S = Math.ceil(R * 2 + 4), key = S;
  if (!globeCache[key]) { const cv = createCanvas(S, S); globeCache[key] = { cv, ctx: cv.getContext('2d'), img: cv.getContext('2d').createImageData(S, S) }; }
  const g = globeCache[key], d = g.img.data; d.fill(0);
  const c0 = S / 2;
  for (let y = 0; y < S; y++) {
    const ny = -(y + 0.5 - c0) / R;
    if (Math.abs(ny) > 1.01) continue;
    for (let x = 0; x < S; x++) {
      const nx = (x + 0.5 - c0) / R, r2 = nx * nx + ny * ny;
      if (r2 > 1.0 + 2 / R) continue;
      const r = Math.sqrt(r2), aa = clamp((1 - r) * R + 0.5);
      if (aa <= 0) continue;
      const nz = Math.sqrt(Math.max(0, 1 - r2));
      const lat = Math.asin(clamp(ny, -1, 1));
      const lon = Math.atan2(nx, nz) + rot;
      const u = ((lon / (2 * Math.PI)) % 1 + 1) % 1, v = 0.5 - lat / Math.PI;
      const ti = Math.min(TH - 1, Math.max(0, (v * TH) | 0)) * TW + ((u * TW) | 0) % TW;
      let cr = texA.rgb[ti * 3], cg = texA.rgb[ti * 3 + 1], cb = texA.rgb[ti * 3 + 2], em = texA.emit[ti], cl = texA.cloud[ti];
      if (texB && mix > 0) {
        cr = lerp(cr, texB.rgb[ti * 3], mix); cg = lerp(cg, texB.rgb[ti * 3 + 1], mix); cb = lerp(cb, texB.rgb[ti * 3 + 2], mix);
        em = lerp(em, texB.emit[ti], mix); cl = lerp(cl, texB.cloud[ti], mix);
      }
      // nuvens giram um pouco mais rápido
      if (cl > 0 || (texB && mix > 0)) {
        const lon2 = Math.atan2(nx, nz) + cloudRot, u2 = ((lon2 / (2 * Math.PI)) % 1 + 1) % 1;
        const t2 = Math.min(TH - 1, (v * TH) | 0) * TW + ((u2 * TW) | 0) % TW;
        cl = texB && mix > 0 ? lerp(texA.cloud[t2], texB.cloud[t2], mix) : texA.cloud[t2];
      }
      const dif = Math.max(0, nx * LIGHT[0] + ny * LIGHT[1] + nz * LIGHT[2]);
      const lit = (0.06 + 1.02 * Math.pow(dif, 0.85)) * light;
      const ca = cl / 255;
      cr = lerp(cr, 245, ca) * lit; cg = lerp(cg, 248, ca) * lit; cb = lerp(cb, 252, ca) * lit;
      // brilho especular no oceano
      const spec = Math.pow(Math.max(0, dif), 40) * 90 * (1 - ca) * (em > 0 ? 0 : 1);
      // lava emite luz própria (inclusive no lado noturno)
      const e = em / 255 * emitBoost * (1 - ca * 0.7);
      cr += e * 235; cg += e * 92; cb += e * 18;
      // borda atmosférica
      const rim = Math.pow(1 - nz, 2.5) * (0.25 + 0.75 * dif);
      cr = cr + atm[0] * rim * 0.7 + spec; cg = cg + atm[1] * rim * 0.7 + spec; cb = cb + atm[2] * rim * 0.7 + spec;
      const k = (y * S + x) * 4;
      d[k] = cr; d[k + 1] = cg; d[k + 2] = cb; d[k + 3] = aa * 255;
    }
  }
  g.ctx.putImageData(g.img, 0, 0);
  return g.cv;
}
function drawGlobe(ctx, tex, cx, cy, R, rot, o = {}) {
  const atm = o.atm || [120, 180, 255];
  // halo atmosférico
  const hg = ctx.createRadialGradient(cx, cy, R * 0.9, cx, cy, R * 1.28);
  hg.addColorStop(0, rgba(atm, 0.5 * (o.halo ?? 1))); hg.addColorStop(1, rgba(atm, 0));
  ctx.fillStyle = hg; ctx.beginPath(); ctx.arc(cx, cy, R * 1.28, 0, 6.283); ctx.fill();
  const cv = globe(tex, R, rot, o);
  ctx.drawImage(cv, cx - cv.width / 2, cy - cv.height / 2);
}

// ---------------------------------------------------------------- recursos de cena
const R0 = rng(77);
const STARS = Array.from({ length: 420 }, () => ({ x: R0() * W, y: R0() * H, r: 0.4 + R0() * R0() * 2.2, a: 0.25 + R0() * 0.75, tw: R0() * 6.28 }));
const DUST = Array.from({ length: 90 }, () => ({ x: R0(), y: R0(), r: 1 + R0() * 3.5, s: 0.2 + R0() * 0.8, ph: R0() * 6.28 }));
const DEBRIS = Array.from({ length: 300 }, () => ({ a: R0() * 6.283, rr: 0.8 + R0() * 0.5, sp: 0.6 + R0() * 0.9, sz: 1.5 + R0() * 3.5, ej: (R0() - 0.5) * 1.6, ph: R0() }));
const vignette = (() => {
  const c = createCanvas(W, H), x = c.getContext('2d');
  const g = x.createRadialGradient(W / 2, H * 0.48, H * 0.25, W / 2, H * 0.5, H * 0.78);
  g.addColorStop(0, 'rgba(0,0,0,0)'); g.addColorStop(1, 'rgba(0,0,0,0.6)');
  x.fillStyle = g; x.fillRect(0, 0, W, H); return c;
})();
const nebula = (() => {
  const c = createCanvas(W, H), x = c.getContext('2d');
  for (const [bx, by, br, col] of [[160, 620, 560, '120,60,200'], [940, 1050, 620, '30,120,210'], [380, 1500, 520, '200,60,120'], [880, 420, 420, '70,90,230']]) {
    const g = x.createRadialGradient(bx, by, 0, bx, by, br); g.addColorStop(0, `rgba(${col},0.2)`); g.addColorStop(1, `rgba(${col},0)`);
    x.fillStyle = g; x.fillRect(0, 0, W, H);
  }
  return c;
})();

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
function bubbles(ctx, t, n, x0, x1, alpha, label = false, seed = 3) {
  const r = rng(seed);
  for (let i = 0; i < n; i++) {
    const bx = lerp(x0, x1, r()), sp = 90 + r() * 140, ph = r() * 10, sz = 6 + r() * (label ? 26 : 14);
    const y = 1500 - ((t * sp + ph * 150) % 1150);
    const x = bx + Math.sin(t * 2 + ph) * 12;
    ctx.save(); ctx.globalAlpha = alpha * clamp((1500 - y) / 120) * clamp((y - 380) / 120);
    ctx.strokeStyle = 'rgba(220,245,255,0.9)'; ctx.lineWidth = 2.5; ctx.fillStyle = 'rgba(200,240,255,0.15)';
    ctx.beginPath(); ctx.arc(x, y, sz, 0, 6.283); ctx.fill(); ctx.stroke();
    ctx.fillStyle = 'rgba(255,255,255,0.8)'; ctx.beginPath(); ctx.arc(x - sz * 0.35, y - sz * 0.35, sz * 0.22, 0, 6.283); ctx.fill();
    if (label && sz > 18) text(ctx, 'O₂', x, y + sz * 0.3, { font: `800 ${sz * 0.85}px ${FONT}`, color: '#eaffff', align: 'center' });
    ctx.restore();
  }
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

// ---------------------------------------------------------------- cenas
// cada cena recebe (ctx, t global, lt = tempo local da cena, i = quadro)
const GX = 540, GY = 930; // centro do planeta

function ringDial(ctx, cx, cy, R, w, c, alpha = 1, ticks = true) {
  if (alpha <= 0) return;
  ctx.save(); ctx.globalAlpha *= alpha;
  ctx.strokeStyle = 'rgba(255,255,255,0.08)'; ctx.lineWidth = w; ctx.beginPath(); ctx.arc(cx, cy, R, 0, 6.283); ctx.stroke();
  let prev = 0;
  for (const e of ERAS) {
    const a0 = prev, a1 = Math.min(c, e.c1);
    if (a1 > a0) {
      ctx.strokeStyle = rgba(e.col); ctx.lineWidth = w; ctx.lineCap = 'butt';
      ctx.beginPath(); ctx.arc(cx, cy, R, -Math.PI / 2 + a0 / DIA * 6.2832, -Math.PI / 2 + a1 / DIA * 6.2832); ctx.stroke();
    }
    prev = e.c1; if (c <= e.c1) break;
  }
  if (ticks) for (let h = 0; h < 24; h++) {
    const a = -Math.PI / 2 + h / 24 * 6.2832, big = h % 6 === 0;
    ctx.strokeStyle = big ? 'rgba(255,255,255,0.7)' : 'rgba(255,255,255,0.3)'; ctx.lineWidth = big ? 4 : 2;
    ctx.beginPath(); ctx.moveTo(cx + Math.cos(a) * (R + w / 2 + 6), cy + Math.sin(a) * (R + w / 2 + 6));
    ctx.lineTo(cx + Math.cos(a) * (R + w / 2 + (big ? 24 : 14)), cy + Math.sin(a) * (R + w / 2 + (big ? 24 : 14))); ctx.stroke();
    if (big) text(ctx, `${String(h).padStart(2, '0')}h`, cx + Math.cos(a) * (R + w / 2 + 56), cy + Math.sin(a) * (R + w / 2 + 56) + 11, { font: `700 30px ${FONT}`, color: 'rgba(220,230,255,0.75)', align: 'center' });
  }
  const a = -Math.PI / 2 + c / DIA * 6.2832, col = eraCol(c).col;
  ctx.shadowColor = rgba(col, 0.9); ctx.shadowBlur = 24;
  ctx.fillStyle = '#fff'; ctx.beginPath(); ctx.arc(cx + Math.cos(a) * R, cy + Math.sin(a) * R, w * 0.62, 0, 6.283); ctx.fill();
  ctx.restore();
}

function sceneSpace(ctx, t, lt, i) {
  ctx.fillStyle = '#03040b'; ctx.fillRect(0, 0, W, H);
  ctx.drawImage(nebula, 0, 0);
  for (const s of STARS) { ctx.globalAlpha = s.a * (0.7 + 0.3 * Math.sin(lt * 2 + s.tw)); ctx.fillStyle = '#fff'; ctx.beginPath(); ctx.arc(s.x, s.y, s.r, 0, 6.283); ctx.fill(); }
  ctx.globalAlpha = 1;
  const c = clockAt(i);
  // textura conforme a era do relógio (no gancho a Terra evolui enquanto o relógio gira)
  const eras = [['molten', 0], ['archean', 3.6 * HR], ['proto', 11.5 * HR], ['modern', 21.4 * HR]];
  let k = 0; while (k < 3 && c >= eras[k + 1][1]) k++;
  const next = eras[Math.min(k + 1, 3)], blendW = 1.6 * HR;
  const mix = k < 3 ? sstep(next[1] - blendW, next[1], c) : 0;
  const texA = TEX[eras[k][0]], texB = TEX[next[0]];
  const atm = k === 0 ? mixc([255, 120, 50], [255, 170, 90], mix) : k === 1 ? mixc([255, 170, 90], [120, 180, 255], mix) : [120, 180, 255];
  // câmera: aproxima no "nasce" e durante a colisão
  const zoom = 1 + 0.12 * win(t, L.nasce.start - 0.3, L.lua.start + 0.6, 0.8, 0.6);
  const lua0 = Wt('lua', 3), TI = Wt('lua', 11), lua1 = L.lua.end + 0.5;
  const R = 285 * zoom;
  const rot = 0.6 + lt * 0.11;
  // anel do relógio de 24h
  const ringA = 1 - 0.8 * win(t, lua0 - 0.3, lua1, 0.4, 0.5);
  ringDial(ctx, GX, GY, R + 92, 22, c, ringA);
  // Theia (planeta do tamanho de Marte) vindo do alto à direita
  const inLua = t > lua0 - 0.2 && t < lua1 + 1;
  if (inLua && t < TI) {
    const p = Math.pow(clamp((t - lua0) / (TI - lua0)), 1.7);
    const ang = -0.38, dist = lerp(R * 2.25, R * 1.38, p);
    const tx = GX + Math.cos(ang) * dist, ty = GY + Math.sin(ang) * dist;
    // rastro de velocidade
    ctx.save(); ctx.globalAlpha = 0.35 * p; ctx.strokeStyle = 'rgba(255,190,140,0.8)'; ctx.lineWidth = 2;
    for (let s = -3; s <= 3; s++) { ctx.beginPath(); ctx.moveTo(tx + Math.cos(ang) * 60 + s * 18 * Math.sin(ang), ty + Math.sin(ang) * 60 - s * 18 * Math.cos(ang)); ctx.lineTo(tx + Math.cos(ang) * (220 + 200 * p), ty + Math.sin(ang) * (220 + 200 * p)); ctx.stroke(); }
    ctx.restore();
    drawGlobe(ctx, TEX.theia, tx, ty, R * 0.53, lt * 0.3, { atm: [255, 150, 90], halo: 0.4 });
  }
  const glowBoost = 1 + 1.4 * (t > TI ? Math.exp(-(t - TI) / 1.6) : 0);
  drawGlobe(ctx, texA, GX, GY, R, rot, { texB, mix, atm, emitBoost: (k === 0 ? 1.15 : 1) * glowBoost });
  if (inLua && t >= TI) {
    // detritos: ejetados do ponto de impacto, entram em órbita e se juntam na Lua
    const ang = -0.38, ix = GX + Math.cos(ang) * R * 0.95, iy = GY + Math.sin(ang) * R * 0.95;
    const tMoon = Wt('lua', 17), tEnd = Wt('lua', 19, 't1');
    const mx = GX - R * 1.22, my = GY - R * 1.12;
    const s1 = easeOutCubic((t - TI) / 1.1), s2 = easeInOutCubic((t - tMoon) / (tEnd - tMoon + 0.2));
    ctx.save(); ctx.globalCompositeOperation = 'lighter';
    for (const d of DEBRIS) {
      const oa = d.a + (t - TI) * d.sp * 0.9;
      const ox = GX + Math.cos(oa) * R * 1.75 * d.rr, oy = GY + Math.sin(oa) * R * 0.42 * d.rr - R * 0.12;
      const ex = ix + Math.cos(ang + d.ej) * R * 0.9 * d.rr * s1, ey = iy + Math.sin(ang + d.ej) * R * 0.9 * d.rr * s1;
      const blend = sstep(0.25, 1.0, (t - TI) / 1.3);
      let x = lerp(ex, ox, blend), y = lerp(ey, oy, blend);
      x = lerp(x, mx + (d.ph - 0.5) * 30, s2); y = lerp(y, my + (d.rr - 1) * 30, s2);
      const heat = Math.exp(-(t - TI) / 1.4);
      const col = mixc([150, 140, 130], [255, 170, 70], heat);
      const behind = Math.sin(oa) < -0.2 && blend > 0.5 && s2 < 0.5;
      ctx.globalAlpha = (behind ? 0.35 : 0.9) * (1 - s2 * 0.9);
      const rad = d.sz * (1 + heat);
      ctx.fillStyle = rgba(col, 0.12); ctx.beginPath(); ctx.arc(x, y, rad * 3.2, 0, 6.283); ctx.fill();
      ctx.fillStyle = rgba(mixc(col, [255, 255, 255], 0.3)); ctx.beginPath(); ctx.arc(x, y, rad * 0.8, 0, 6.283); ctx.fill();
    }
    ctx.restore();
    // clarão do impacto
    const fl = Math.exp(-(t - TI) / 0.35);
    glowAt(ctx, ix, iy, R * (0.6 + 2.2 * (1 - fl)), [255, 220, 160], 0.95 * fl);
    // a Lua se forma
    const mr = R * 0.27 * easeOutBack((t - tMoon - 0.1) / 0.9);
    if (mr > 1) drawGlobe(ctx, TEX.moon, mx, my, mr, lt * 0.05, { atm: [200, 200, 210], halo: 0.35 });
    if (t > Wt('lua', 19) - 0.1) {
      const la = win(t, Wt('lua', 19) - 0.1, lua1 + 0.6, 0.25, 0.3);
      text(ctx, 'LUA', mx, my - mr - 26, { font: `900 44px ${FONT}`, color: '#fff', align: 'center', alpha: la, stroke: 8 });
    }
  }
  // nasce: brasas e calor
  const nasceA = win(t, L.nasce.start - 0.2, L.lua.end, 0.4, 0.6);
  if (nasceA > 0) embers(ctx, lt, 0.6 * nasceA, 70, 21);
  // "1 hora = 189 milhões de anos"
  const ac0 = Wt('acelera', 4), ac1 = L.acelera.end + 0.35;
  const aa = win(t, ac0 - 0.1, ac1, 0.2, 0.25);
  if (aa > 0) {
    const p = easeOutBack((t - ac0 + 0.1) / 0.35);
    ctx.save(); ctx.globalAlpha = aa; ctx.translate(GX, GY); ctx.scale(0.8 + 0.2 * p, 0.8 + 0.2 * p);
    ctx.fillStyle = 'rgba(5,8,20,0.82)'; rr(ctx, -420, -170, 840, 330, 40); ctx.fill();
    ctx.strokeStyle = 'rgba(255,210,63,0.6)'; ctx.lineWidth = 3; rr(ctx, -420, -170, 840, 330, 40); ctx.stroke();
    text(ctx, '1 HORA NO RELÓGIO', 0, -85, { font: `800 40px ${FONT}`, color: C.label, align: 'center', spacing: 4 });
    text(ctx, '=', 0, -20, { font: `900 54px ${FONT}`, color: '#fff', align: 'center' });
    text(ctx, '189 milhões', 0, 75, { font: `900 104px ${FONT}`, color: C.yellow, align: 'center' });
    text(ctx, 'de anos', 0, 135, { font: `800 46px ${FONT}`, color: '#fff', align: 'center' });
    ctx.restore();
  }
}

// ---- fundo do oceano primitivo (vida / tédio / oxigênio)
const MICROBES = Array.from({ length: 26 }, (_, k) => { const r = rng(300 + k); return { x: 80 + r() * 920, y: 560 + r() * 760, s: 46 + r() * 110, ph: r() * 6.28, rot: r() * 6.28, sp: 0.4 + r() * 0.8, tAt: k < 6 ? k * 0.16 : 1.2 + (k - 6) * 0.2, depth: r() }; });
function sceneOcean(ctx, t, lt, i) {
  const shallow = sstep(L.oxigenio.start - 0.6, L.oxigenio.start + 0.8, t);
  gradSky(ctx, [[0, mixc(hex('#0b4c6e'), hex('#3fb7d9'), shallow)], [0.45, mixc(hex('#06263d'), hex('#167a9c'), shallow)], [1, mixc(hex('#020a14'), hex('#0a3b4f'), shallow)]]);
  // superfície da água com céu (oxigênio)
  if (shallow > 0) {
    const sy = 470;
    ctx.save(); ctx.globalAlpha = shallow;
    const g = ctx.createLinearGradient(0, 0, 0, sy); g.addColorStop(0, '#f2b77a'); g.addColorStop(1, '#ffe2b0');
    ctx.fillStyle = g; ctx.beginPath(); ctx.moveTo(0, 0); ctx.lineTo(W, 0);
    for (let x = W; x >= 0; x -= 10) ctx.lineTo(x, sy + Math.sin(x * 0.02 + lt * 2) * 8);
    ctx.fill();
    glowAt(ctx, 760, sy - 40, 220, [255, 240, 200], 0.8);
    ctx.restore();
  }
  godRays(ctx, lt, 0.8 + 0.8 * shallow);
  marineSnow(ctx, lt, 0.7);
  // relevo do fundo
  terrain(ctx, { seed: 2, base: 1330, amp: 160, freq: 0.0032, color: rgba(mixc(hex('#0a2235'), hex('#1f5b6a'), shallow)), scroll: lt * 6 });
  // fontes hidrotermais (somem quando a cena fica rasa)
  const vent = 1 - shallow;
  if (vent > 0) {
    ctx.save(); ctx.globalAlpha = vent;
    for (const [vx, vh, vw] of [[200, 330, 70], [300, 220, 50], [860, 280, 64]]) {
      smoke(ctx, lt, vx, 1430 - vh, 1, 0.9, '120,135,150', vx);
      const g = ctx.createLinearGradient(vx - vw, 0, vx + vw, 0); g.addColorStop(0, '#0b1d2c'); g.addColorStop(0.5, '#1d3a4c'); g.addColorStop(1, '#081520');
      ctx.fillStyle = g; ctx.beginPath(); ctx.moveTo(vx - vw, 1440);
      for (let k = 0; k <= 6; k++) ctx.lineTo(vx - vw * (1 - k / 6 * 0.62) + Math.sin(k * 3.1 + vx) * 8, 1440 - vh * k / 6);
      for (let k = 6; k >= 0; k--) ctx.lineTo(vx + vw * (1 - k / 6 * 0.62) + Math.cos(k * 2.7 + vx) * 8, 1440 - vh * k / 6);
      ctx.fill();
      glowAt(ctx, vx, 1440 - vh, 70, [255, 150, 70], 0.45 + 0.1 * Math.sin(lt * 5 + vx));
    }
    for (const [rx, rs] of [[90, 150], [470, 120], [700, 170], [1010, 140]]) sprite(ctx, 'rock', rx, 1450, rs, { tint: [8, 30, 50, 0.6] });
    ctx.restore();
  }
  // estromatólitos (tapetes de bactérias) quando raso
  if (shallow > 0) {
    ctx.save(); ctx.globalAlpha = shallow;
    for (const [sx, sw, sh] of [[150, 240, 150], [430, 300, 190], [760, 260, 160], [990, 220, 130]]) {
      const g = ctx.createLinearGradient(0, 1420 - sh, 0, 1420); g.addColorStop(0, '#5f8f55'); g.addColorStop(1, '#2f4a35');
      ctx.fillStyle = g; ctx.beginPath(); ctx.ellipse(sx, 1420, sw / 2, sh, 0, Math.PI, 0); ctx.fill();
      ctx.strokeStyle = 'rgba(200,230,170,0.25)'; ctx.lineWidth = 3;
      for (let k = 1; k < 5; k++) { ctx.beginPath(); ctx.ellipse(sx, 1420, sw / 2 * (1 - k * 0.16), sh * (1 - k * 0.16), 0, Math.PI, 0); ctx.stroke(); }
    }
    ctx.restore();
    bubbles(ctx, lt, 22, 100, 1000, shallow, true, 8);
  }
  // micróbio em destaque no "surge a primeira vida"
  const hv = popIn(t, Wt('vida', 6) - 0.05, 0.5) * (1 - sstep(Wt('vida', 7) + 0.6, Wt('vida', 8) + 0.4, t));
  if (hv > 0) {
    glowAt(ctx, 540, 930, 330, [120, 255, 200], 0.28 * hv);
    sprite(ctx, 'microbe', 540, 930 + Math.sin(lt * 1.6) * 14, 330 * hv, { anchor: 'center', rot: Math.sin(lt * 0.9) * 0.2, glow: 'rgba(120,255,200,0.7)' });
  }
  // micróbios: aparecem e se multiplicam no "tédio"
  const v0 = Wt('vida', 7), te0 = L.tedio.start;
  for (const [k, m] of MICROBES.entries()) {
    const at = k < 6 ? v0 - 0.1 + m.tAt : te0 + 0.6 + (k - 6) * 0.22;
    const s = popIn(t, at, 0.4);
    if (s <= 0) continue;
    const x = m.x + Math.sin(lt * m.sp + m.ph) * 26, y = m.y + Math.cos(lt * m.sp * 0.8 + m.ph) * 20;
    const fog = 0.25 + 0.45 * m.depth;
    sprite(ctx, 'microbe', x, y, m.s * s * (1 + 0.05 * Math.sin(lt * 3 + m.ph)), { anchor: 'center', rot: m.rot + Math.sin(lt * 0.7 + m.ph) * 0.4, tint: [...mixc(hex('#0a3550'), hex('#3a8fa8'), shallow), fog * (1 - shallow * 0.5)], alpha: 1 - shallow * 0.55 });
  }
  // "quase nada muda": avanço rápido + carinha dormindo
  const ffA = win(t, Wt('tedio', 2), L.tedio.end + 0.2, 0.2, 0.3);
  if (ffA > 0) {
    text(ctx, '▶▶', 100, 560, { font: `900 64px ${FONT}`, color: '#fff', alpha: ffA * (0.6 + 0.4 * Math.sin(lt * 10)), stroke: 8 });
    const z = popIn(t, Wt('tedio', 7), 0.45);
    if (z > 0) sprite(ctx, 'sleeping-face', 860, 640 + Math.sin(lt * 2) * 10, 190 * z, { anchor: 'center', alpha: ffA, rot: Math.sin(lt * 1.5) * 0.08 });
  }
  const ox = win(t, Wt('oxigenio', 10) - 0.2, L.oxigenio.end + 0.6, 0.2, 0.3);
  if (ox > 0) text(ctx, 'O₂', 540, 1000, { font: `900 ${180 + 20 * Math.sin(lt * 4)}px ${FONT}`, color: '#bff4ff', align: 'center', alpha: ox * 0.9, stroke: 14, strokeColor: 'rgba(5,40,60,0.85)' });
}

// ---- recife cambriano (animais)
function seaweed(ctx, lt, x, h, col, ph) {
  ctx.save(); ctx.strokeStyle = col; ctx.lineCap = 'round';
  for (let k = 0; k < 3; k++) {
    ctx.lineWidth = 14 - k * 3; ctx.beginPath(); ctx.moveTo(x + k * 18, 1430);
    for (let s = 1; s <= 8; s++) { const yy = 1430 - s * h / 8; ctx.lineTo(x + k * 18 + Math.sin(lt * 1.3 + s * 0.6 + ph + k) * s * 4, yy); }
    ctx.stroke();
  }
  ctx.restore();
}
function sceneReef(ctx, t, lt, i) {
  gradSky(ctx, [[0, '#2aa5d8'], [0.45, '#0f5f8f'], [1, '#042238']]);
  godRays(ctx, lt, 1.3);
  marineSnow(ctx, lt, 0.5);
  terrain(ctx, { seed: 5, base: 1250, amp: 120, freq: 0.003, color: '#0b4a66', scroll: lt * 8 });
  terrain(ctx, { seed: 8, base: 1390, amp: 70, freq: 0.004, color: ['#a8925f', '#2a2a2c'], rim: 'rgba(255,240,200,0.35)', scroll: lt * 16 });
  for (const [rx, rs] of [[400, 90], [690, 120], [960, 80]]) sprite(ctx, 'rock', rx, 1440, rs, { tint: [20, 70, 110, 0.35] });
  seaweed(ctx, lt, 70, 380, '#2f8f5a', 0); seaweed(ctx, lt, 990, 330, '#3a9f68', 2);
  const a0 = Wt('animais', 3) - 0.1, a1 = Wt('animais', 5), a2 = Wt('animais', 7);
  const tintW = [20, 90, 140, 0.18];
  sprite(ctx, 'coral', 230, 1440, 260 * popIn(t, a1 - 0.2), { shadow: 0.5, tint: tintW });
  sprite(ctx, 'coral', 820, 1450, 330 * popIn(t, a1), { shadow: 0.5, flip: true, tint: tintW });
  sprite(ctx, 'spiral-shell', 520, 1455, 120 * popIn(t, a2), { shadow: 0.6, tint: tintW, rot: -0.2 });
  // águas-vivas pulsando
  for (const [k, [jx, jy, js, at]] of [[0, [300, 760, 230, a0]], [1, [760, 640, 170, a0 + 0.25]], [2, [560, 900, 120, a1 + 0.2]]].map(x => x)) {
    const s = popIn(t, at, 0.5); if (s <= 0) continue;
    const pulse = 1 + 0.07 * Math.sin(lt * 3 + k);
    sprite(ctx, 'jellyfish', jx + Math.sin(lt * 0.6 + k) * 30, jy + Math.sin(lt * 1.2 + k) * 24, js * s, { anchor: 'center', sx: 1 / pulse, sy: pulse, tint: [40, 120, 200, 0.15], glow: 'rgba(160,140,255,0.6)' });
  }
  // camarão e lula nadando
  const sh = popIn(t, a1 + 0.1, 0.45);
  if (sh > 0) sprite(ctx, 'shrimp', 1180 - (t - a1) * 120, 1110 + Math.sin(lt * 3) * 12, 170 * sh, { anchor: 'center', tint: tintW, rot: Math.sin(lt * 3) * 0.06 });
  const sq = popIn(t, a2 - 0.05, 0.45);
  if (sq > 0) sprite(ctx, 'squid', 160 + (t - a2) * 70, 560 + Math.sin(lt * 1.8) * 30, 180 * sq, { anchor: 'center', tint: tintW, rot: 0.5 });
  const fi = popIn(t, a2 + 0.25, 0.45);
  if (fi > 0) for (let k = 0; k < 4; k++) sprite(ctx, 'tropical-fish', 900 - (t - a2) * 90 - k * 70, 560 + k * 35 + Math.sin(lt * 2 + k) * 10, 80 * fi, { anchor: 'center', tint: tintW, flip: true, alpha: 0.85 });
  bubbles(ctx, lt, 10, 150, 950, 0.7, false, 12);
}

// ---- era dos dinossauros + asteroide
function sceneJurassic(ctx, t, lt, i) {
  const TA = Wt('asteroide', 7), TI = Wt('asteroide', 12, 't1') - 0.05;
  const doom = sstep(TI, TI + 1.4, t);           // céu escurece depois do impacto
  const pre = sstep(TA, TI, t);                    // céu esquenta com o asteroide chegando
  gradSky(ctx, [[0, mixc(mixc(hex('#4b8fd6'), hex('#5a3a7a'), pre * 0.6), hex('#1a0a0a'), doom)], [0.5, mixc(mixc(hex('#f2c48a'), hex('#ff9a5a'), pre), hex('#7a1e0e'), doom)], [0.72, mixc(hex('#ffe3b0'), hex('#ff5a1e'), Math.max(pre * 0.7, doom))], [1, '#2a3a1f']], 0, 1450);
  // sol
  glowAt(ctx, 300, 620, 260, mixc([255, 240, 200], [255, 120, 60], doom), 0.7 * (1 - doom * 0.6));
  ctx.fillStyle = rgba(mixc([255, 248, 225], [255, 150, 90], doom)); ctx.beginPath(); ctx.arc(300, 620, 70, 0, 6.283); ctx.fill();
  // pterossauros (silhuetas)
  for (let k = 0; k < 3; k++) {
    const px = ((lt * 60 + k * 300) % 1300) - 100, py = 560 + k * 60 + Math.sin(lt + k) * 20, fl = Math.sin(lt * 6 + k) * 14;
    ctx.save(); ctx.globalAlpha = 0.55 * (1 - doom); ctx.strokeStyle = '#3a2a3a'; ctx.lineWidth = 4; ctx.lineCap = 'round';
    ctx.beginPath(); ctx.moveTo(px - 28, py - fl); ctx.quadraticCurveTo(px - 10, py - 6, px, py); ctx.quadraticCurveTo(px + 10, py - 6, px + 28, py - fl); ctx.stroke(); ctx.restore();
  }
  const sc = lt * 10;
  // vulcão distante com fumaça
  terrain(ctx, { seed: 11, base: 1110, amp: 170, freq: 0.0022, color: rgba(mixc(hex('#7f8fb8'), hex('#3a1d1d'), doom)), scroll: sc * 0.2 });
  sprite(ctx, 'volcano', 860, 1060, 260, { tint: [...mixc([120, 140, 190], [80, 20, 20], doom), 0.55] });
  smoke(ctx, lt, 860, 830, 0.8, 0.7, '60,50,60', 4);
  terrain(ctx, { seed: 13, base: 1230, amp: 140, freq: 0.003, color: rgba(mixc(hex('#3f6b3f'), hex('#2a1410'), doom)), rim: 'rgba(255,230,160,0.25)', scroll: sc * 0.5 });
  // asteroide
  if (t > TA - 0.1 && t < TI + 0.05) {
    const p = easeInCubic((t - TA) / (TI - TA));
    const x = lerp(1300, 760, p), y = lerp(300, 1130, p), s = lerp(80, 220, p);
    ctx.save(); ctx.globalCompositeOperation = 'lighter';
    const g = ctx.createLinearGradient(x, y, x + 500, y - 420); g.addColorStop(0, 'rgba(255,200,120,0.9)'); g.addColorStop(1, 'rgba(255,120,40,0)');
    ctx.strokeStyle = g; ctx.lineWidth = s * 0.5; ctx.lineCap = 'round'; ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x + 500, y - 420); ctx.stroke();
    ctx.restore();
    sprite(ctx, 'comet', x + s * 0.2, y - s * 0.2, s * 1.6, { anchor: 'center', rot: 0.12, glow: 'rgba(255,150,60,0.9)' });
  }
  // bola de fogo + onda de choque no horizonte
  if (t >= TI) {
    const q = t - TI;
    const fr = 120 + q * 900, fa = Math.exp(-q / 1.6);
    glowAt(ctx, 760, 1170, fr * 1.6, [255, 200, 120], 0.9 * fa);
    ctx.save(); ctx.globalAlpha = 0.85 * fa; ctx.fillStyle = '#fff1c2'; ctx.beginPath(); ctx.ellipse(760, 1170, fr * 0.7, fr * 0.5, 0, Math.PI, 0); ctx.fill(); ctx.restore();
    ctx.save(); ctx.strokeStyle = `rgba(255,240,210,${0.7 * fa})`; ctx.lineWidth = 10; ctx.beginPath(); ctx.ellipse(760, 1170, fr * 1.4, fr * 0.35, 0, 0, 6.283); ctx.stroke(); ctx.restore();
  }
  // primeiro plano
  const fg = { seed: 17, base: 1400, amp: 90, freq: 0.004, scroll: sc };
  terrain(ctx, { ...fg, color: [rgba(mixc(hex('#3c7d36'), hex('#1a0d08'), doom)), rgba(mixc(hex('#1d3d1b'), hex('#0a0504'), doom))], rim: `rgba(255,240,170,${0.35 * (1 - doom)})` });
  const d0 = Wt('dinos', 3), d1 = Wt('dinos', 5);
  const tint = [...mixc([255, 220, 160], [40, 10, 5], doom), 0.12 + 0.75 * doom];
  sprite(ctx, 'palm-tree', 120, terrainY(120, fg) + 10, 430, { tint, shadow: 0.4, rot: Math.sin(lt) * 0.02 });
  sprite(ctx, 'palm-tree', 1000, terrainY(1000, fg) + 10, 360, { tint, shadow: 0.4, flip: true, rot: Math.sin(lt + 1) * 0.02 });
  const sp = popIn(t, d0 - 0.1, 0.5);
  const sx = 700 - (t - d0) * 28;
  if (sp > 0) sprite(ctx, 'sauropod', sx, terrainY(sx, fg) + 8 + Math.abs(Math.sin(lt * 3)) * -6, 470 * sp, { tint, shadow: 0.6 });
  const tr = popIn(t, d1, 0.45);
  const tx = 340 - (t - d1) * 20;
  if (tr > 0) sprite(ctx, 't-rex', tx, terrainY(tx, fg) + 14 + Math.abs(Math.sin(lt * 4)) * -8, 330 * tr, { tint, shadow: 0.6 });
  sprite(ctx, 'herb', 520, terrainY(520, fg) + 18, 150, { tint, rot: Math.sin(lt * 1.3) * 0.05 });
  sprite(ctx, 'herb', 880, terrainY(880, fg) + 18, 130, { tint, flip: true, rot: Math.sin(lt * 1.1) * 0.05 });
  if (doom > 0) { embers(ctx, lt, doom, 90, 33, [255, 120, 50]); ctx.fillStyle = `rgba(40,10,5,${0.35 * doom})`; ctx.fillRect(0, 0, W, H); }
}

// ---- mamíferos assumem
function sceneCenozoic(ctx, t, lt, i) {
  const m0 = Wt('mamiferos', 1), m1 = Wt('mamiferos', 2), m2 = Wt('mamiferos', 4);
  gradSky(ctx, [[0, '#5aa3e0'], [0.55, '#bfe0f2'], [0.75, '#f3ecd0'], [1, '#6f8f4a']], 0, 1450);
  for (const [cx, cy, cw] of [[220, 560, 200], [760, 640, 260], [520, 500, 150]]) {
    const x = cx + lt * 12; ctx.fillStyle = 'rgba(255,255,255,0.85)';
    ctx.beginPath(); ctx.ellipse(x, cy, cw, cw * 0.28, 0, 0, 6.283); ctx.fill();
    ctx.beginPath(); ctx.ellipse(x - cw * 0.3, cy - cw * 0.15, cw * 0.45, cw * 0.3, 0, 0, 6.283); ctx.fill();
    ctx.beginPath(); ctx.ellipse(x + cw * 0.25, cy - cw * 0.2, cw * 0.38, cw * 0.32, 0, 0, 6.283); ctx.fill();
  }
  const sc = lt * 10;
  terrain(ctx, { seed: 21, base: 1080, amp: 200, freq: 0.0022, color: '#8fb0c8', scroll: sc * 0.2, sharp: 0.4 });
  terrain(ctx, { seed: 23, base: 1210, amp: 120, freq: 0.003, color: '#6e9a4e', rim: 'rgba(255,255,220,0.3)', scroll: sc * 0.5 });
  const fg = { seed: 27, base: 1400, amp: 70, freq: 0.004, scroll: sc };
  terrain(ctx, { ...fg, color: ['#7fb04a', '#3f6a2a'], rim: 'rgba(255,255,220,0.4)' });
  const tint = [255, 240, 210, 0.06];
  sprite(ctx, 'deciduous-tree', 160, terrainY(160, fg) + 12, 470, { tint, shadow: 0.5, rot: Math.sin(lt) * 0.015 });
  sprite(ctx, 'evergreen-tree', 1010, terrainY(1010, fg) + 12, 360, { tint, shadow: 0.5 });
  const a = popIn(t, m0, 0.5), mx = 640 - (t - m0) * 30;
  if (a > 0) sprite(ctx, 'mammoth', mx, terrainY(mx, fg) + 10 + Math.abs(Math.sin(lt * 3)) * -6, 400 * a, { tint, shadow: 0.6 });
  const b = popIn(t, m1, 0.45);
  if (b > 0) sprite(ctx, 'monkey', 250, terrainY(250, fg) + 8, 200 * b, { tint, shadow: 0.5 });
  const d = popIn(t, m2, 0.45), dx = 930 - (t - m2) * 40;
  if (d > 0) sprite(ctx, 'deer', dx, terrainY(dx, fg) + 10, 230 * d, { tint, shadow: 0.5, flip: false });
}

// ---- pôr do sol: humanos e pirâmides
function pyramid(ctx, x, base, w, h, lit, shade) {
  ctx.fillStyle = shade; ctx.beginPath(); ctx.moveTo(x - w / 2, base); ctx.lineTo(x, base - h); ctx.lineTo(x + w / 2, base); ctx.fill();
  ctx.fillStyle = lit; ctx.beginPath(); ctx.moveTo(x - w / 2, base); ctx.lineTo(x, base - h); ctx.lineTo(x + w * 0.08, base); ctx.fill();
  ctx.strokeStyle = 'rgba(80,40,20,0.18)'; ctx.lineWidth = 2;
  for (let k = 1; k < 10; k++) { const yy = base - h * k / 10, hw = (w / 2) * (1 - k / 10); ctx.beginPath(); ctx.moveTo(x - hw, yy); ctx.lineTo(x + hw, yy); ctx.stroke(); }
}
function sceneSunset(ctx, t, lt, i) {
  const pan = easeInOutCubic((t - (L.piramides.start - 0.4)) / 1.2); // câmera desliza para as pirâmides
  const off = pan * 900;
  const dusk = sstep(L.piramides.start, L.piramides.end + 1, t);
  gradSky(ctx, [[0, mixc(hex('#2a1f5c'), hex('#1a1440'), dusk)], [0.45, '#b4507a'], [0.62, '#ff8a4c'], [0.72, '#ffd08a'], [1, '#3a1f2a']], 0, 1450);
  for (const s of STARS.slice(0, 120)) { if (s.y > 900) continue; ctx.globalAlpha = s.a * 0.5 * dusk; ctx.fillStyle = '#fff'; ctx.beginPath(); ctx.arc(s.x, s.y, s.r, 0, 6.283); ctx.fill(); }
  ctx.globalAlpha = 1;
  const sunY = 1060 + dusk * 60;
  glowAt(ctx, 640 - off * 0.15, sunY, 420, [255, 200, 120], 0.75);
  ctx.fillStyle = '#ffe9b8'; ctx.beginPath(); ctx.arc(640 - off * 0.15, sunY, 110, 0, 6.283); ctx.fill();
  terrain(ctx, { seed: 31, base: 1150, amp: 90, freq: 0.0025, color: '#7a3a4a', scroll: off * 0.3 + lt * 4 });
  // pirâmides (entram com o pan)
  const px = 1500 - off;
  pyramid(ctx, px - 230, 1230, 320, 210, '#e7a865', '#9a5a3a');
  pyramid(ctx, px + 120, 1235, 460, 300, '#f0b46e', '#a3613e');
  pyramid(ctx, px + 470, 1240, 260, 170, '#e0a060', '#93553a');
  const fg = { seed: 33, base: 1390, amp: 80, freq: 0.0035, scroll: off * 0.9 };
  terrain(ctx, { ...fg, color: ['#2a1426', '#140a14'], rim: 'rgba(255,170,110,0.45)' });
  // humano + fogueira no alto da colina
  const h0 = Wt('humanos', 1), hx = 380 - off * 0.9, hy = terrainY(380, fg) + 8;
  const hp = popIn(t, h0, 0.5);
  if (hx > -200) {
    glowAt(ctx, hx + 150, hy - 60, 260, [255, 150, 60], 0.45 * hp * (0.85 + 0.15 * Math.sin(lt * 9)));
    sprite(ctx, 'fire', hx + 150, hy + 4, 120 * hp * (1 + 0.06 * Math.sin(lt * 11)), { glow: 'rgba(255,140,40,0.9)' });
    embers(ctx, lt, 0.5 * hp, 20, 41);
    sprite(ctx, 'person-standing', hx, hy, 300 * hp, { tint: [60, 20, 40, 0.28], shadow: 0.5 });
  }
  const cm = popIn(t, Wt('piramides', 3), 0.45);
  if (cm > 0) { const cx = 1180 - off * 0.9 - (t - Wt('piramides', 3)) * 50; sprite(ctx, 'camel', cx, terrainY(cx + off * 0.9, { ...fg, scroll: 0 }) + 10, 240 * cm, { tint: [70, 30, 40, 0.45], shadow: 0.5 }); }
  sprite(ctx, 'palm-tree', 1250 - off * 0.9 + 200, 1400, 380, { tint: [40, 15, 30, 0.75] });
}

// ---- zoom na régua do tempo (vida humana)
function sceneRingZoom(ctx, t, lt, i) {
  ctx.fillStyle = '#04060f'; ctx.fillRect(0, 0, W, H); ctx.drawImage(nebula, 0, 0);
  for (const s of STARS) { ctx.globalAlpha = s.a * 0.7; ctx.fillStyle = '#fff'; ctx.beginPath(); ctx.arc(s.x, s.y, s.r, 0, 6.283); ctx.fill(); }
  ctx.globalAlpha = 1;
  const z0 = Wt('vidahum', 2), z1 = Wt('vidahum', 11, 't1');
  const p = easeInOutCubic((t - z0) / (z1 - z0));
  const Wsec = Math.exp(lerp(Math.log(DIA), Math.log(0.0032), p)); // janela visível (s antes da meia-noite)
  const x0 = 90, x1 = 990, y = 980, h = 130;
  const X = s => x1 - (s / Wsec) * (x1 - x0); // s = segundos antes da meia-noite
  ctx.save(); rr(ctx, x0, y - h / 2, x1 - x0, h, 24); ctx.clip();
  ctx.fillStyle = 'rgba(255,255,255,0.06)'; ctx.fillRect(x0, y - h / 2, x1 - x0, h);
  let prev = 0;
  for (const e of ERAS) { const a = DIA - e.c1, b = DIA - prev; ctx.fillStyle = rgba(e.col); ctx.fillRect(X(b), y - h / 2, X(a) - X(b), h); prev = e.c1; }
  // humanos (últimos 6 s) e você (últimos 1,5 ms)
  ctx.fillStyle = C.red; ctx.fillRect(X(6.3), y - h / 2, X(0) - X(6.3), h);
  ctx.fillStyle = C.yellow; ctx.shadowColor = 'rgba(255,210,63,0.9)'; ctx.shadowBlur = 30;
  ctx.fillRect(X(80 / IDADE * DIA), y - h / 2, X(0) - X(80 / IDADE * DIA) + 2, h);
  ctx.restore();
  ctx.strokeStyle = 'rgba(255,255,255,0.35)'; ctx.lineWidth = 2; rr(ctx, x0, y - h / 2, x1 - x0, h, 24); ctx.stroke();
  // nome do trecho dominante dentro da barra
  const inBar = (label, sa, sb, col = '#fff') => {
    const xa = Math.max(X(sb), x0), xb = Math.min(X(sa), x1);
    if (xb - xa > 280) text(ctx, label, (xa + xb) / 2, y + 15, { font: `900 44px ${FONT}`, color: col, align: 'center', stroke: 10, strokeColor: 'rgba(0,0,0,0.55)' });
  };
  if (Wsec > 90) { let pv = 0; for (const e of ERAS) { inBar(e.nome, DIA - e.c1, DIA - pv); pv = e.c1; } }
  else if (Wsec > 0.012) inBar('HUMANOS', 0, 6.3);
  // régua (marcações 1-2-5 que se adaptam ao zoom)
  {
    const target = Wsec / 6, e = Math.floor(Math.log10(target)), seq = [1, 2, 5, 10].map(v => v * Math.pow(10, e));
    let k = 0; while (k < 3 && seq[k + 1] <= target) k++;
    const step = seq[k], fr = Math.log(target / seq[k]) / Math.log(seq[k + 1] / seq[k]);
    ctx.save(); ctx.strokeStyle = 'rgba(220,230,255,0.6)'; ctx.lineWidth = 2;
    for (let q = 1; q * step < Wsec; q++) {
      const x = X(q * step); if (x < x0) break;
      const major = Math.abs((q * step) / seq[k + 1] - Math.round((q * step) / seq[k + 1])) < 1e-6;
      ctx.globalAlpha = major ? 0.9 : 0.9 * (1 - fr);
      ctx.beginPath(); ctx.moveTo(x, y + h / 2 + 8); ctx.lineTo(x, y + h / 2 + (major ? 26 : 16)); ctx.stroke();
    }
    ctx.restore();
  }
  // marcadores
  const mark = (s, label, col, up, a = 1) => {
    const x = X(s); if (x < x0 - 2 || x > x1 + 2 || a <= 0) return;
    ctx.save(); ctx.globalAlpha = a; ctx.strokeStyle = col; ctx.lineWidth = 3; ctx.setLineDash([8, 6]);
    ctx.beginPath(); ctx.moveTo(x, y + (up ? -h / 2 : h / 2)); ctx.lineTo(x, y + (up ? -h / 2 - 90 : h / 2 + 90)); ctx.stroke(); ctx.restore();
    text(ctx, label, clamp(x, 200, 880), y + (up ? -h / 2 - 104 : h / 2 + 130), { font: `800 36px ${FONT}`, color: col, align: 'center', alpha: a, stroke: 8 });
  };
  mark(6, 'HUMANOS', C.red, true, sstep(500, 40, Wsec));
  mark(4500 / IDADE * DIA, 'PIRÂMIDES', '#ffb36b', false, sstep(3, 0.4, Wsec) * sstep(0.004, 0.02, Wsec));
  mark(66e6 / IDADE * DIA, 'FIM DOS DINOSSAUROS', '#7bd65b', false, sstep(8000, 2500, Wsec) * sstep(400, 1500, Wsec));
  // rótulos de escala
  const unit = Wsec > 7200 ? [HR, 'h'] : Wsec > 120 ? [60, 'min'] : Wsec > 2 ? [1, 's'] : [0.001, 'ms'];
  const span = Wsec / unit[0];
  text(ctx, `−${nf(span, span < 10 ? 1 : 0)} ${unit[1]}`, x0, y + h / 2 + 50, { font: `700 30px ${FONT}`, color: C.label });
  text(ctx, 'MEIA-NOITE', x1, y + h / 2 + 50, { font: `700 30px ${FONT}`, color: C.label, align: 'right' });
  const zoomX = DIA / Wsec;
  text(ctx, 'ZOOM NO FIM DO DIA', 540, 620, { font: `800 34px ${FONT}`, color: C.label, align: 'center', spacing: 6 });
  text(ctx, `×${nf(Math.round(zoomX), 0)}`, 540, 700, { font: `900 ${zoomX > 1e7 ? 84 : 96}px ${MONO}`, color: '#fff', align: 'center' });
  const ya = sstep(Wt('vidahum', 9) - 0.2, Wt('vidahum', 11), t);
  if (ya > 0) {
    const bx = (X(80 / IDADE * DIA) + x1) / 2;
    text(ctx, 'VOCÊ', bx, y - h / 2 - 40, { font: `900 72px ${FONT}`, color: C.yellow, align: 'center', alpha: ya, stroke: 10 });
    text(ctx, '80 anos de vida', bx, y + h / 2 + 130, { font: `800 40px ${FONT}`, color: '#fff', align: 'center', alpha: ya, stroke: 8 });
  }
  // reflexão: batimento no "VOCÊ"
  const rf = win(t, L.reflexao.start - 0.2, L.cta.start, 0.4, 0.3);
  if (rf > 0) {
    const beat = Math.pow(Math.max(0, Math.sin((t - L.reflexao.start) * Math.PI * 2 * 1.1)), 12);
    glowAt(ctx, (X(80 / IDADE * DIA) + x1) / 2, y, 300 + beat * 120, [255, 210, 63], 0.25 * rf + 0.25 * beat * rf);
  }
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
const SCENE_FN = { space: sceneSpace, ocean: sceneOcean, reef: sceneReef, jurassic: sceneJurassic, cenozoic: sceneCenozoic, sunset: sceneSunset, ringzoom: sceneRingZoom, cta: sceneCTA };

// ---------------------------------------------------------------- HUD (relógio) e legendas
function fmtClock(c) {
  const h = Math.floor(c / HR), m = Math.floor((c - h * HR) / 60), s = c - h * HR - m * 60, si = Math.floor(s);
  const main = `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(si).padStart(2, '0')}`;
  let frac = '';
  if (c > DIA - 0.05) frac = ',' + String(Math.floor((s - si) * 10000)).padStart(4, '0');
  else if (c > DIA - 10) frac = ',' + String(Math.floor((s - si) * 1000)).padStart(3, '0');
  return [main, frac];
}
function fmtAgo(c) {
  const y = IDADE * (1 - c / DIA);
  if (y >= 1e9) { const v = y / 1e9; return `HÁ ${nf(v, 2)} ${v < 2 ? 'BILHÃO' : 'BILHÕES'} DE ANOS`; }
  if (y >= 1e6) { const v = Math.round(y / 1e6); return `HÁ ${nf(v, 0)} ${v < 2 ? 'MILHÃO' : 'MILHÕES'} DE ANOS`; }
  if (y >= 1e3) return `HÁ ${nf(Math.round(y / 1e3), 0)} MIL ANOS`;
  if (y >= 1) return `HÁ ${nf(Math.round(y), 0)} ANOS`;
  return 'AGORA';
}
function drawHUD(ctx, t, i) {
  const c = clockAt(i), x = 60, y = 186, w = 960, h = 236;
  ctx.save();
  ctx.fillStyle = 'rgba(6,10,22,0.66)'; rr(ctx, x, y, w, h, 34); ctx.fill();
  ctx.strokeStyle = 'rgba(255,255,255,0.09)'; ctx.lineWidth = 2; rr(ctx, x, y, w, h, 34); ctx.stroke();
  // mini relógio de 24h
  const dx = x + 118, dy = y + h / 2;
  ctx.lineWidth = 16; ctx.strokeStyle = 'rgba(255,255,255,0.1)'; ctx.beginPath(); ctx.arc(dx, dy, 66, 0, 6.283); ctx.stroke();
  let prev = 0;
  for (const e of ERAS) { const a1 = Math.min(c, e.c1); if (a1 > prev) { ctx.strokeStyle = rgba(e.col); ctx.beginPath(); ctx.arc(dx, dy, 66, -Math.PI / 2 + prev / DIA * 6.2832, -Math.PI / 2 + a1 / DIA * 6.2832); ctx.stroke(); } prev = e.c1; if (c <= e.c1) break; }
  const a = -Math.PI / 2 + c / DIA * 6.2832;
  ctx.strokeStyle = '#fff'; ctx.lineWidth = 5; ctx.lineCap = 'round'; ctx.beginPath(); ctx.moveTo(dx, dy); ctx.lineTo(dx + Math.cos(a) * 46, dy + Math.sin(a) * 46); ctx.stroke();
  ctx.fillStyle = '#fff'; ctx.beginPath(); ctx.arc(dx, dy, 7, 0, 6.283); ctx.fill();
  // horário
  const era = eraCol(c);
  text(ctx, 'RELÓGIO DA TERRA', x + 232, y + 58, { font: `700 26px ${FONT}`, color: C.label, spacing: 5 });
  text(ctx, era.nome, x + w - 40, y + 58, { font: `800 24px ${FONT}`, color: rgba(era.col), align: 'right', spacing: 3 });
  const [main, frac] = fmtClock(c);
  ctx.font = `800 96px ${MONO}`; const mw = ctx.measureText(main).width;
  text(ctx, main, x + 228, y + 150, { font: `800 96px ${MONO}`, color: '#fff' });
  if (frac) text(ctx, frac, x + 232 + mw, y + 150, { font: `800 56px ${MONO}`, color: C.red });
  text(ctx, fmtAgo(c), x + 232, y + 202, { font: `800 34px ${FONT}`, color: C.yellow, spacing: 1 });
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

// ---------------------------------------------------------------- composição
const canvas = createCanvas(W, H), ctx = canvas.getContext('2d');
const bufA = createCanvas(W, H), ctxA = bufA.getContext('2d');
const bufB = createCanvas(W, H), ctxB = bufB.getContext('2d');
const scratch = createCanvas(W, H), sctx = scratch.getContext('2d');
const HITS = () => [Wt('lua', 11), Wt('asteroide', 12, 't1') - 0.05];
function renderScene(target, idx, t, i) {
  const sc = SCENES[idx];
  const lt = t - (sc.local0 !== undefined ? sc.local0 : sc.t0);
  target.save(); target.setTransform(1, 0, 0, 1, 0, 0);
  if (['ocean', 'reef', 'jurassic', 'cenozoic', 'sunset'].includes(sc.name)) { const z = 1 + Math.min(0.07, 0.014 * Math.max(0, lt)); target.translate(W / 2, H * 0.6); target.scale(z, z); target.translate(-W / 2, -H * 0.6); }
  SCENE_FN[sc.name](target, t, lt, i); target.restore();
}
function zoomBlurDraw(src, s, a) {
  for (let k = 0; k < 4; k++) {
    const sk = s * (1 + k * 0.045);
    ctx.globalAlpha = a * (k === 0 ? 1 : 0.35);
    ctx.drawImage(src, W / 2 - W * sk / 2, H / 2 - H * sk / 2, W * sk, H * sk);
  }
  ctx.globalAlpha = 1;
}
function frame(i, opts = {}) {
  const t = i / FPS;
  let cur = 0; for (let k = 0; k < SCENES.length; k++) if (t >= SCENES[k].t0) cur = k;
  // tremor de câmera nos impactos
  let amp = 0; for (const hT of HITS()) if (t >= hT && t < hT + 0.6) amp = Math.max(amp, 18 * (1 - (t - hT) / 0.6));
  ctx.save(); ctx.translate(Math.sin(t * 91) * amp, Math.cos(t * 77) * amp);
  ctx.fillStyle = '#000'; ctx.fillRect(-40, -40, W + 80, H + 80);
  const sc = SCENES[cur];
  const into = t - sc.t0;
  if (cur > 0 && into < TR / 2 && !sc.fade) {
    // transição "zoom-through": a cena anterior acelera para a câmera e a nova chega
    const p = clamp((into + TR / 2) / TR);
    renderScene(ctxA, cur - 1, t, i); renderScene(ctxB, cur, t, i);
    zoomBlurDraw(bufA, 1 + 0.55 * easeInCubic(p), 1 - sstep(0.35, 0.75, p));
    zoomBlurDraw(bufB, lerp(0.82, 1, easeOutCubic(p)), sstep(0.3, 0.8, p));
  } else if (cur + 1 < SCENES.length && SCENES[cur + 1].t0 - t < TR / 2 && !SCENES[cur + 1].fade) {
    const p = clamp((t - (SCENES[cur + 1].t0 - TR / 2)) / TR);
    renderScene(ctxA, cur, t, i);
    zoomBlurDraw(bufA, 1 + 0.55 * easeInCubic(p), 1 - sstep(0.35, 0.75, p));
  } else if (sc.fade) {
    renderScene(ctxA, cur - 1, t, i); renderScene(ctxB, cur, t, i);
    ctx.drawImage(bufA, 0, 0); ctx.globalAlpha = sstep(0, 0.35, into); ctx.drawImage(bufB, 0, 0); ctx.globalAlpha = 1;
  } else {
    renderScene(ctxA, cur, t, i); ctx.drawImage(bufA, 0, 0);
  }
  // rebobinar (assinatura da série)
  const rw = [L.hook.end + 0.25, L.hook.end + 0.95];
  const ra = win(t, rw[0] - 0.05, rw[1] + 0.05, 0.08, 0.12);
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
  // clarões
  let fl = 0;
  const hk = Wt('hook', 16);
  if (t >= hk) fl = Math.max(fl, 0.55 * Math.exp(-(t - hk) / 0.25));
  for (const hT of HITS()) if (t >= hT) fl = Math.max(fl, 0.85 * Math.exp(-(t - hT) / 0.3));
  if (fl > 0.01) { ctx.fillStyle = `rgba(255,250,235,${fl})`; ctx.fillRect(-40, -40, W + 80, H + 80); }
  ctx.restore();
}

// ---------------------------------------------------------------- main
(async () => {
  await loadSprites();
  const t0 = Date.now();
  for (const k of ['molten', 'archean', 'proto', 'modern', 'theia', 'moon']) TEX[k] = makeTexture(k);
  console.log(`texturas prontas (${((Date.now() - t0) / 1000).toFixed(1)}s)`);
  const argv = process.argv.slice(2);
  const pi = argv.indexOf('--preview');
  if (argv.includes('--capa')) {
    const i = Math.round((Wt('hook', 16) + 0.5) * FPS);
    frame(i, { noCaptions: true });
    const g = ctx.createLinearGradient(0, 1150, 0, 1800); g.addColorStop(0, 'rgba(3,5,12,0)'); g.addColorStop(0.35, 'rgba(3,5,12,0.85)'); g.addColorStop(1, 'rgba(3,5,12,0.95)');
    ctx.fillStyle = g; ctx.fillRect(0, 1150, W, 770);
    text(ctx, 'A TERRA EM 24 HORAS', W / 2, 1400, { font: `900 82px ${FONT}`, color: '#fff', align: 'center', stroke: 14 });
    text(ctx, 'NÓS: SÓ 6 SEGUNDOS', W / 2, 1520, { font: `900 92px ${FONT}`, color: C.yellow, align: 'center', stroke: 16 });
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
