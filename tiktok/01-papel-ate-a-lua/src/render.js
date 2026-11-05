// Renderiza o vídeo quadro a quadro (1080x1920, 30 fps) e envia para o ffmpeg.
//   node src/render.js                      -> build/video.mp4 (sem áudio)
//   node src/render.js --preview 1.2,3.8    -> build/preview/*.png
const { createCanvas } = require('@napi-rs/canvas');
const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');

const ROOT = path.resolve(__dirname, '..');
const TL = JSON.parse(fs.readFileSync(path.join(ROOT, 'build/timeline.json'), 'utf8'));
const W = 1080, H = 1920, FPS = TL.fps;
const G = 1400;            // linha do chão (y)
let SX = 330;              // centro da pilha (x) — muda por quadro
const VIEW = 880;          // px de "céu" visíveis acima do chão
const TOP_TARGET = 760;    // altura em px que a pilha ocupa quando a câmera acompanha
const PAPEL = 1e-4;
const FONT = '"Inter Display"';
const MONO = '"JetBrains Mono"';

// ---------- utilidades ----------
const clamp = (x, a = 0, b = 1) => Math.max(a, Math.min(b, x));
const lerp = (a, b, t) => a + (b - a) * t;
const sstep = (a, b, x) => { const t = clamp((x - a) / (b - a)); return t * t * (3 - 2 * t); };
const easeOutCubic = p => 1 - Math.pow(1 - clamp(p), 3);
const easeInOutCubic = p => (p = clamp(p), p < 0.5 ? 4 * p * p * p : 1 - Math.pow(-2 * p + 2, 3) / 2);
const easeOutBack = p => { p = clamp(p); const c1 = 1.70158, c3 = c1 + 1; return 1 + c3 * Math.pow(p - 1, 3) + c1 * Math.pow(p - 1, 2); };
const win = (t, a, b, fi = 0.2, fo = 0.2) => Math.min(sstep(a, a + fi, t), 1 - sstep(b - fo, b, t));
function rng(seed) { return () => { seed |= 0; seed = seed + 0x6D2B79F5 | 0; let t = Math.imul(seed ^ seed >>> 15, 1 | seed); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
const hex = h => [parseInt(h.slice(1, 3), 16), parseInt(h.slice(3, 5), 16), parseInt(h.slice(5, 7), 16)];
const mixc = (a, b, t) => a.map((v, i) => v + (b[i] - v) * t);
const rgba = (c, a = 1) => `rgba(${c[0] | 0},${c[1] | 0},${c[2] | 0},${a})`;

const C = {
  yellow: '#FFD23F', cyan: '#4FD1FF', red: '#FF3B4E', gold: '#FFC23C', ink: '#070A14',
  paper: '#F7F3EA', label: '#8FA3C8',
};

// ---------- linha do tempo ----------
const L = TL.lines;
const Wt = (line, i, k = 't0') => L[line].words[i][k];
const N = TL.frames;
const F = TL.fold, CNT = TL.count;
// câmera: dobra suavizada (gaussiana centrada) => zoom sem atraso e sem tremor
const FC = new Float64Array(N);
{
  const sig = 1.6, R = 5;
  for (let i = 0; i < N; i++) {
    let s = 0, ws = 0;
    for (let k = -R; k <= R; k++) {
      const j = clamp(i + k, 0, N - 1); const w = Math.exp(-(k * k) / (2 * sig * sig));
      s += F[j] * w; ws += w;
    }
    FC[i] = s / ws;
  }
}
const camM = i => Math.max(PAPEL * Math.pow(2, FC[clamp(i, 0, N - 1)]) / TOP_TARGET, PAPEL / 45);

const MORPH0 = Wt('hook', 7);             // folha de frente -> vista lateral
const MORPH1 = MORPH0 + 0.28;
const LOOP0 = TL.total - 0.42;              // volta para a folha de frente (loop)
const REW1 = [L.hook.end + 0.25, L.hook.end + 0.95];
const REW2 = [Wt('mito', 0), Wt('mito', 0) + 1.0];
const MOON_HITS = TL.cross.lua;
const SUN_HIT = TL.cross.sol[0];
const UNI_HIT = TL.cross.universo[0];
const ERRADO = Wt('errado', 0);
const EXPLODE = Wt('licao', 8);
const TWIST0 = Wt('mito', 0);

const firstFrameCount = (v, after) => { for (let i = Math.ceil(after * FPS); i < N; i++) if (CNT[i] >= v) return i / FPS; return 1e9; };

// marcos (etiquetas)
const MARCOS = [
  { f: 7, title: 'CADERNO', sub: '≈ 1,3 cm de espessura', h: 0.013 },
  { f: 10, title: 'XÍCARA', sub: '≈ 10 cm', h: 0.095 },
  { f: 14, title: 'PESSOA', sub: '≈ 1,70 m', h: 1.7 },
  { f: 17, title: 'PRÉDIO DE 4 ANDARES', sub: '≈ 13 m', h: 13 },
  { f: 23, title: 'BURJ KHALIFA', sub: '828 m · o mais alto do mundo', h: 828 },
  { f: 27, title: 'MONTE EVEREST', sub: '8.849 m', h: 8849 },
  { f: 30, title: 'ESPAÇO', sub: 'começa a 100 km', h: 1e5 },
  { f: 32, title: 'ESTAÇÃO ESPACIAL', sub: '≈ 400 km de altitude', h: 4.08e5 },
  { f: 42, title: 'LUA', sub: '384.400 km', h: 3.844e8 },
  { f: 51, title: 'SOL', sub: '150 milhões de km', h: 1.496e11 },
  { f: 103, title: 'UNIVERSO OBSERVÁVEL', sub: '93 bilhões de anos-luz', h: 8.8e26 },
];
for (const m of MARCOS) m.at = firstFrameCount(m.f, L.mentira.start);
MARCOS.forEach((m, i) => { m.until = i + 1 < MARCOS.length ? MARCOS[i + 1].at : TWIST0; });
MARCOS.find(m => m.f === 42).at = MOON_HITS[1];
MARCOS.find(m => m.f === 51).at = SUN_HIT;
MARCOS.find(m => m.f === 103).at = UNI_HIT;
MARCOS.find(m => m.f === 32).until = MOON_HITS[1] - 0.6;
MARCOS.find(m => m.f === 103).until = TWIST0 + 0.1;
const HOOK_MOON = { ...MARCOS.find(m => m.f === 42), at: MOON_HITS[0], until: REW1[0] + 0.1 };

// ---------- formatação ----------
const nf = (x, d) => x.toLocaleString('pt-BR', { minimumFractionDigits: d, maximumFractionDigits: d });
function fmtLen(m) {
  if (m < 0.01) return nf(m * 1000, 1) + ' mm';
  if (m < 1) return nf(m * 100, 1) + ' cm';
  if (m < 10) return nf(m, 2) + ' m';
  if (m < 1000) return nf(m, 1) + ' m';
  const km = m / 1000;
  if (km < 100) return nf(km, 1) + ' km';
  if (km < 1e6) return nf(Math.round(km), 0) + ' km';
  if (km < 1e9) { const v = km / 1e6; return nf(v, v < 10 ? 1 : 0) + (v < 2 ? ' milhão de km' : ' milhões de km'); }
  const ly = m / 9.4607e15;
  if (ly < 0.1) { const v = km / 1e9; return nf(v, v < 10 ? 1 : 0) + (v < 2 ? ' bilhão de km' : ' bilhões de km'); }
  if (ly < 1000) return nf(ly, ly < 10 ? 1 : 0) + ' anos-luz';
  if (ly < 1e6) return nf(ly / 1e3, 0) + ' mil anos-luz';
  if (ly < 1e9) { const v = ly / 1e6; return nf(v, 0) + (v < 2 ? ' milhão' : ' milhões') + ' de anos-luz'; }
  const v = ly / 1e9; return nf(v, 0) + (v < 2 ? ' bilhão' : ' bilhões') + ' de anos-luz';
}
function fmtTick(m) {
  const t = (v, u) => `${nf(v, v < 10 && v % 1 ? 1 : 0)} ${u}`;
  if (m < 0.01) return t(m * 1000, 'mm');
  if (m < 1) return t(m * 100, 'cm');
  if (m < 1000) return t(m, 'm');
  const km = m / 1000;
  if (km < 1000) return t(km, 'km');
  if (km < 1e6) return t(km / 1e3, 'mil km');
  if (km < 1e9) return t(km / 1e6, 'mi km');
  const ly = m / 9.4607e15;
  if (ly < 0.1) return t(km / 1e9, 'bi km');
  if (ly < 1000) return t(ly, 'a.l.');
  if (ly < 1e6) return t(ly / 1e3, 'mil a.l.');
  if (ly < 1e9) return t(ly / 1e6, 'mi a.l.');
  return t(ly / 1e9, 'bi a.l.');
}
const SUP = '⁰¹²³⁴⁵⁶⁷⁸⁹';
const sup = n => String(n).split('').map(d => SUP[+d]).join('');

// ---------- recursos pré-desenhados ----------
const R0 = rng(7);
const STAR_LAYERS = [];
for (let k = 4; k <= 28; k++) {
  const stars = [];
  const n = k >= 19 ? 40 : 110;
  for (let i = 0; i < n; i++) stars.push({ u: R0() * 2 - 1, v: -R0() * 1.7 + 0.5, r: 0.6 + R0() * R0() * 2.2, a: 0.35 + R0() * 0.65, gal: k >= 19 && R0() < 0.6, rot: R0() * Math.PI, hue: R0() });
  STAR_LAYERS.push({ k, stars });
}
const BG_STARS = Array.from({ length: 260 }, () => ({ x: R0() * W, y: R0() * H, r: 0.4 + R0() * 1.1, a: 0.2 + R0() * 0.6, tw: R0() * 6.28 }));
const SPEED = Array.from({ length: 46 }, () => ({ x: R0() * W, y: R0() * H, len: 90 + R0() * 320, a: 0.12 + R0() * 0.3, sp: 0.6 + R0() * 0.8 }));
// silhuetas de cidade (m)
const CITY = [];
{
  const r = rng(11);
  for (let i = 0; i < 70; i++) {
    const dx = -900 + r() * 3600;
    if (Math.abs(dx) < 90) continue;
    CITY.push({ dx, w: 18 + r() * 45, h: 25 + Math.pow(r(), 2.2) * 330, layer: r() < 0.5 ? 0 : 1 });
  }
  CITY.sort((a, b) => a.layer - b.layer);
}
const RANGE = [];
{
  const r = rng(5);
  for (let i = 0; i < 16; i++) RANGE.push({ dx: -40000 + r() * 90000, h: 2500 + r() * 4500, w: 9000 + r() * 16000, layer: r() < 0.5 ? 0 : 1 });
}
const CLOUDS = [];
{
  const r = rng(3);
  for (let i = 0; i < 22; i++) CLOUDS.push({ dx: -30000 + r() * 60000, alt: 1200 + r() * 2500, w: 1500 + r() * 4500, h: 250 + r() * 500 });
}

const vignette = (() => {
  const c = createCanvas(W, H), x = c.getContext('2d');
  const g = x.createRadialGradient(W / 2, H * 0.48, H * 0.28, W / 2, H * 0.5, H * 0.75);
  g.addColorStop(0, 'rgba(0,0,0,0)'); g.addColorStop(1, 'rgba(0,0,0,0.55)');
  x.fillStyle = g; x.fillRect(0, 0, W, H);
  return c;
})();
const nebula = (() => {
  const c = createCanvas(W, H), x = c.getContext('2d');
  const blobs = [[200, 500, 520, '120,60,200'], [880, 900, 600, '30,120,200'], [400, 1300, 500, '200,60,140'], [800, 300, 420, '60,90,220']];
  for (const [bx, by, br, col] of blobs) {
    const g = x.createRadialGradient(bx, by, 0, bx, by, br);
    g.addColorStop(0, `rgba(${col},0.22)`); g.addColorStop(1, `rgba(${col},0)`);
    x.fillStyle = g; x.fillRect(0, 0, W, H);
  }
  return c;
})();

// ---------- desenho ----------
const canvas = createCanvas(W, H);
const ctx = canvas.getContext('2d');
const scratch = createCanvas(W, H);
const sctx = scratch.getContext('2d');

function rr(x, y, w, h, r) {
  ctx.beginPath(); ctx.moveTo(x + r, y); ctx.arcTo(x + w, y, x + w, y + h, r); ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r); ctx.arcTo(x, y, x + w, y, r); ctx.closePath();
}
function text(s, x, y, { font, color = '#fff', align = 'left', base = 'alphabetic', stroke = 0, strokeColor = 'rgba(0,0,0,0.9)', spacing = 0, alpha = 1 } = {}) {
  ctx.save(); ctx.globalAlpha *= alpha; ctx.font = font; ctx.textAlign = align; ctx.textBaseline = base;
  ctx.letterSpacing = spacing + 'px';
  if (stroke) { ctx.lineJoin = 'round'; ctx.lineWidth = stroke; ctx.strokeStyle = strokeColor; ctx.strokeText(s, x, y); }
  ctx.fillStyle = color; ctx.fillText(s, x, y); ctx.restore();
}

const SKY = [
  { lv: -9, top: '#0b1122', mid: '#111a33', bot: '#1b2747' },
  { lv: -0.3, top: '#0b1122', mid: '#111a33', bot: '#1b2747' },
  { lv: 0.9, top: '#0c1838', mid: '#2a3d78', bot: '#e0875f' },
  { lv: 2.6, top: '#0b1a44', mid: '#2d5aa8', bot: '#f0a774' },
  { lv: 3.6, top: '#071233', mid: '#1f4f9c', bot: '#7fb4e3' },
  { lv: 4.6, top: '#030716', mid: '#0b1d4a', bot: '#2c5fa8' },
  { lv: 5.4, top: '#010208', mid: '#03050f', bot: '#0a1430' },
  { lv: 40, top: '#010208', mid: '#03050f', bot: '#060b1e' },
].map(k => ({ lv: k.lv, top: hex(k.top), mid: hex(k.mid), bot: hex(k.bot) }));
function skyAt(lv) {
  for (let i = 0; i < SKY.length - 1; i++) {
    const a = SKY[i], b = SKY[i + 1];
    if (lv <= b.lv) { const t = sstep(a.lv, b.lv, lv); return { top: mixc(a.top, b.top, t), mid: mixc(a.mid, b.mid, t), bot: mixc(a.bot, b.bot, t) }; }
  }
  return SKY[SKY.length - 1];
}

function drawBackground(t, m, lv) {
  const s = skyAt(lv);
  const g = ctx.createLinearGradient(0, 0, 0, G);
  g.addColorStop(0, rgba(s.top)); g.addColorStop(0.62, rgba(s.mid)); g.addColorStop(1, rgba(s.bot));
  ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
  // estúdio: luz suave atrás da pilha
  const studio = 1 - sstep(-0.6, 0.4, lv);
  if (studio > 0) {
    const rg = ctx.createRadialGradient(SX + 120, G - 380, 20, SX + 120, G - 380, 900);
    rg.addColorStop(0, `rgba(80,110,190,${0.32 * studio})`); rg.addColorStop(1, 'rgba(80,110,190,0)');
    ctx.fillStyle = rg; ctx.fillRect(0, 0, W, H);
    ctx.save(); ctx.globalAlpha = 0.07 * studio; ctx.strokeStyle = '#9fb6ff'; ctx.lineWidth = 1;
    for (let x = 0; x < W; x += 60) { ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, G); ctx.stroke(); }
    for (let y = G; y > 0; y -= 60) { ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke(); }
    ctx.restore();
  }
  // espaço: estrelas fixas + nebulosa
  const space = sstep(4.5, 5.6, lv);
  if (space > 0) {
    for (const st of BG_STARS) {
      ctx.globalAlpha = space * st.a * (0.75 + 0.25 * Math.sin(t * 2 + st.tw));
      ctx.fillStyle = '#fff'; ctx.beginPath(); ctx.arc(st.x, st.y, st.r, 0, 6.283); ctx.fill();
    }
    ctx.globalAlpha = 1;
    const neb = sstep(10.5, 14, lv);
    if (neb > 0) { ctx.globalAlpha = neb; ctx.drawImage(nebula, 0, 0); ctx.globalAlpha = 1; }
    // camadas de estrelas com zoom infinito
    const V = m * VIEW;
    for (const layer of STAR_LAYERS) {
      const sc = Math.pow(10, layer.k) / V; const ls = Math.log10(sc);
      const a = space * sstep(-1.7, -1.0, ls) * (1 - sstep(0.1, 0.6, ls));
      if (a < 0.01) continue;
      for (const st of layer.stars) {
        const x = SX + st.u * 1150 * sc, y = G + st.v * 1250 * sc;
        if (x < -20 || x > W + 20 || y < -20 || y > H + 20) continue;
        ctx.globalAlpha = a * st.a;
        if (st.gal) {
          ctx.save(); ctx.translate(x, y); ctx.rotate(st.rot); ctx.scale(1, 0.45);
          const rr2 = 4 + st.r * 5;
          const gg = ctx.createRadialGradient(0, 0, 0, 0, 0, rr2);
          const col = st.hue < 0.5 ? '170,190,255' : '255,210,170';
          gg.addColorStop(0, `rgba(255,255,255,0.95)`); gg.addColorStop(0.3, `rgba(${col},0.55)`); gg.addColorStop(1, `rgba(${col},0)`);
          ctx.fillStyle = gg; ctx.beginPath(); ctx.arc(0, 0, rr2, 0, 6.283); ctx.fill(); ctx.restore();
        } else {
          ctx.fillStyle = '#fff'; ctx.beginPath(); ctx.arc(x, y, st.r, 0, 6.283); ctx.fill();
        }
      }
    }
    ctx.globalAlpha = 1;
  }
}

const yAlt = (alt, m) => G - alt / m;
const visBy = (h, V, lo = 0.012, hi = 1.25) => Math.min(sstep(lo, lo * 3, h / V), 1 - sstep(hi, hi * 1.35, h / V));

function drawFar(t, m, lv) {
  const V = m * VIEW;
  // nuvens
  const cv = Math.min(sstep(2.4, 2.9, lv), 1 - sstep(4.0, 4.5, lv));
  if (cv > 0) {
    for (const c of CLOUDS) {
      const x = SX + c.dx / m, y = yAlt(c.alt, m), w = c.w / m, h = c.h / m;
      if (x + w < 0 || x - w > W) continue;
      ctx.globalAlpha = cv * 0.22;
      ctx.fillStyle = '#e8eefc';
      ctx.beginPath(); ctx.ellipse(x, y, w / 2, Math.max(h / 2, 1), 0, 0, 6.283); ctx.fill();
      ctx.beginPath(); ctx.ellipse(x + w * 0.18, y - h * 0.3, w / 3, Math.max(h / 2, 1), 0, 0, 6.283); ctx.fill();
    }
    ctx.globalAlpha = 1;
  }
  // linha de Kármán
  const kv = Math.min(sstep(4.55, 4.85, lv), 1 - sstep(6.3, 6.7, lv));
  if (kv > 0) {
    const y = yAlt(1e5, m);
    ctx.save(); ctx.globalAlpha = kv * 0.7; ctx.strokeStyle = C.cyan; ctx.lineWidth = 2; ctx.setLineDash([14, 12]);
    ctx.beginPath(); ctx.moveTo(150, y); ctx.lineTo(W, y); ctx.stroke(); ctx.restore();
    text('LINHA DE KÁRMÁN · 100 km', W - 150, y - 14, { font: `700 24px ${FONT}`, color: C.cyan, align: 'right', alpha: kv * 0.9, spacing: 2 });
  }
  // ISS
  const iv = Math.min(sstep(5.15, 5.45, lv), 1 - sstep(6.8, 7.3, lv));
  if (iv > 0) drawISS(SX + 210, yAlt(4.08e5, m), iv);
  // Lua
  const mv = Math.min(sstep(7.6, 8.1, lv), 1 - sstep(10.6, 11.2, lv));
  if (mv > 0) {
    const r = Math.max(1.737e6 / m, lerp(58, 22, sstep(9, 11, lv)));
    drawMoon(SX + 18 + r, yAlt(3.844e8, m), r, mv);
  }
  // Sol
  const sv = Math.min(sstep(10.4, 10.9, lv), 1 - sstep(13.2, 14, lv));
  if (sv > 0) {
    const r = Math.max(6.96e8 / m, lerp(80, 30, sstep(12, 14, lv)));
    drawSun(SX + 26 + r, yAlt(1.496e11, m), r, sv, t);
  }
  // universo observável (esfera centrada na Terra)
  const uv = sstep(25.2, 26.0, lv);
  if (uv > 0) {
    const r = 4.4e26 / m;
    const gg = ctx.createRadialGradient(SX, G, r * 0.2, SX, G, r);
    gg.addColorStop(0, 'rgba(90,110,255,0.05)'); gg.addColorStop(0.85, 'rgba(120,120,255,0.16)'); gg.addColorStop(1, 'rgba(160,190,255,0.35)');
    ctx.save(); ctx.globalAlpha = uv; ctx.fillStyle = gg; ctx.beginPath(); ctx.arc(SX, G, r, 0, 6.283); ctx.fill();
    ctx.shadowColor = 'rgba(150,180,255,0.9)'; ctx.shadowBlur = 24; ctx.strokeStyle = 'rgba(190,210,255,0.85)'; ctx.lineWidth = 3;
    ctx.beginPath(); ctx.arc(SX, G, r, 0, 6.283); ctx.stroke(); ctx.restore();
  }
  // cordilheira
  const rv = Math.min(sstep(3.0, 3.5, lv), 1 - sstep(5.0, 5.5, lv));
  if (rv > 0) {
    for (const p of RANGE) {
      const x = SX + p.dx / m, w = p.w / m, h = p.h / m;
      if (x + w < 0 || x - w > W) continue;
      ctx.globalAlpha = rv;
      ctx.fillStyle = p.layer ? '#1a2d55' : '#13234a';
      ctx.beginPath(); ctx.moveTo(x - w / 2, G); ctx.lineTo(x - w * 0.08, G - h * 0.92); ctx.lineTo(x, G - h); ctx.lineTo(x + w * 0.12, G - h * 0.88); ctx.lineTo(x + w / 2, G); ctx.fill();
    }
    ctx.globalAlpha = 1;
  }
  // cidade
  const cityv = Math.min(sstep(1.25, 1.8, lv), 1 - sstep(3.4, 3.9, lv));
  if (cityv > 0) {
    for (const b of CITY) {
      const x = SX + b.dx / m, w = b.w / m, h = b.h / m;
      if (x + w < 0 || x > W) continue;
      ctx.globalAlpha = cityv;
      ctx.fillStyle = b.layer ? '#141c38' : '#0f1630';
      ctx.fillRect(x, G - h, w, h);
      if (w > 10 && h > 20) {
        ctx.fillStyle = 'rgba(255,214,140,0.35)';
        const cols = Math.max(1, Math.floor(w / 9)), rows = Math.floor(h / 12);
        for (let r = 1; r < rows; r += 2) for (let c = 0; c < cols; c += 2) if (((r * 7 + c * 13 + (b.dx | 0)) % 5) < 2) ctx.fillRect(x + 3 + c * (w - 6) / cols, G - h + r * 12, Math.max(1, (w - 6) / cols - 2), 4);
      }
    }
    ctx.globalAlpha = 1;
  }
}

function drawGround(t, m, lv) {
  const Rpx = 6.371e6 / m;
  const earth = sstep(4.6, 5.8, lv);
  if (Rpx > 40000) {
    const g = ctx.createLinearGradient(0, G, 0, H);
    const studio = 1 - sstep(-0.6, 0.4, lv);
    const c0 = mixc(mixc(hex('#0e1426'), hex('#0b0f1d'), studio), hex('#123a73'), earth);
    const c1 = mixc(hex('#05070e'), hex('#061a3a'), earth);
    g.addColorStop(0, rgba(c0)); g.addColorStop(1, rgba(c1));
    ctx.fillStyle = g; ctx.fillRect(0, G, W, H - G);
    ctx.fillStyle = `rgba(160,190,255,${0.25 + 0.3 * earth})`; ctx.fillRect(0, G, W, 2);
  } else {
    const r = Math.max(Rpx, 16), cy = G + r;
    // atmosfera
    const ag = ctx.createRadialGradient(SX, cy, r * 0.96, SX, cy, r * 1.12 + 6);
    ag.addColorStop(0, 'rgba(90,170,255,0.55)'); ag.addColorStop(1, 'rgba(90,170,255,0)');
    ctx.fillStyle = ag; ctx.beginPath(); ctx.arc(SX, cy, r * 1.12 + 6, 0, 6.283); ctx.fill();
    const eg = ctx.createRadialGradient(SX - r * 0.35, cy - r * 0.45, r * 0.1, SX, cy, r);
    eg.addColorStop(0, '#3d8fe0'); eg.addColorStop(0.6, '#164f99'); eg.addColorStop(1, '#071d45');
    ctx.fillStyle = eg; ctx.beginPath(); ctx.arc(SX, cy, r, 0, 6.283); ctx.fill();
    if (r > 30) {
      ctx.save(); ctx.beginPath(); ctx.arc(SX, cy, r, 0, 6.283); ctx.clip();
      ctx.fillStyle = 'rgba(70,140,80,0.55)';
      ctx.beginPath(); ctx.ellipse(SX - r * 0.3, cy - r * 0.5, r * 0.32, r * 0.2, 0.6, 0, 6.283); ctx.fill();
      ctx.beginPath(); ctx.ellipse(SX + r * 0.35, cy - r * 0.2, r * 0.22, r * 0.35, -0.3, 0, 6.283); ctx.fill();
      ctx.fillStyle = 'rgba(255,255,255,0.35)';
      ctx.beginPath(); ctx.ellipse(SX, cy - r * 0.75, r * 0.6, r * 0.08, 0.1, 0, 6.283); ctx.fill();
      ctx.restore();
    }
  }
}

function drawISS(x, y, a) {
  ctx.save(); ctx.globalAlpha = a; ctx.translate(x, y);
  ctx.fillStyle = '#c9d3e6'; ctx.fillRect(-70, -3, 140, 6);
  for (const px of [-62, -40, 40, 62]) {
    ctx.fillStyle = '#2b4f9e'; ctx.fillRect(px - 9, -34, 18, 28); ctx.fillRect(px - 9, 6, 18, 28);
    ctx.strokeStyle = '#d9b45a'; ctx.lineWidth = 1.5; ctx.strokeRect(px - 9, -34, 18, 28); ctx.strokeRect(px - 9, 6, 18, 28);
  }
  ctx.fillStyle = '#e9edf5'; rr(-22, -9, 44, 18, 5); ctx.fill();
  ctx.restore();
}
function drawMoon(x, y, r, a) {
  ctx.save(); ctx.globalAlpha = a;
  const glow = ctx.createRadialGradient(x, y, r * 0.8, x, y, r * 1.9);
  glow.addColorStop(0, 'rgba(220,225,240,0.35)'); glow.addColorStop(1, 'rgba(220,225,240,0)');
  ctx.fillStyle = glow; ctx.beginPath(); ctx.arc(x, y, r * 1.9, 0, 6.283); ctx.fill();
  const g = ctx.createRadialGradient(x - r * 0.4, y - r * 0.4, r * 0.1, x, y, r);
  g.addColorStop(0, '#f4f4f0'); g.addColorStop(0.7, '#b9bcc4'); g.addColorStop(1, '#7c8090');
  ctx.fillStyle = g; ctx.beginPath(); ctx.arc(x, y, r, 0, 6.283); ctx.fill();
  ctx.fillStyle = 'rgba(90,95,110,0.35)';
  for (const [cx, cy, cr] of [[-0.3, -0.2, 0.22], [0.25, 0.1, 0.16], [0.05, 0.45, 0.12], [-0.45, 0.3, 0.1], [0.4, -0.4, 0.09]]) {
    ctx.beginPath(); ctx.arc(x + cx * r, y + cy * r, cr * r, 0, 6.283); ctx.fill();
  }
  ctx.restore();
}
function drawSun(x, y, r, a, t) {
  ctx.save(); ctx.globalAlpha = a;
  const glow = ctx.createRadialGradient(x, y, r * 0.6, x, y, r * 3.2);
  glow.addColorStop(0, 'rgba(255,190,80,0.6)'); glow.addColorStop(1, 'rgba(255,120,40,0)');
  ctx.fillStyle = glow; ctx.beginPath(); ctx.arc(x, y, r * 3.2, 0, 6.283); ctx.fill();
  const g = ctx.createRadialGradient(x, y, 0, x, y, r);
  g.addColorStop(0, '#fffbe6'); g.addColorStop(0.55, '#ffd25a'); g.addColorStop(1, '#ff8a1f');
  ctx.fillStyle = g; ctx.beginPath(); ctx.arc(x, y, r, 0, 6.283); ctx.fill();
  ctx.restore();
}

// objetos de referência em escala real (altura); largura estilizada
function drawObjects(t, m, lv, stackW) {
  const V = m * VIEW;
  const right = SX + stackW / 2;
  // caderno (deitado, sai da tela à direita)
  {
    const h = 0.013, a = visBy(h, V);
    if (a > 0) {
      const hp = h / m, x0 = right + 0.0025 / m, w = 0.21 / m, cv = hp * 0.11;
      ctx.save(); ctx.globalAlpha *= a;
      ctx.fillStyle = '#2f6fd6'; rr(x0, G - hp, w, hp, hp * 0.14); ctx.fill();
      const pg = ctx.createLinearGradient(0, G - hp + cv, 0, G - cv);
      pg.addColorStop(0, '#fbf8ef'); pg.addColorStop(1, '#e6dfcf');
      ctx.fillStyle = pg; ctx.fillRect(x0 + hp * 0.16, G - hp + cv, w, hp - 2 * cv);
      ctx.strokeStyle = 'rgba(150,140,120,0.45)'; ctx.lineWidth = Math.max(1, hp * 0.006);
      for (let k = 1; k < 18; k++) { const yy = G - hp + cv + k * (hp - 2 * cv) / 18; ctx.beginPath(); ctx.moveTo(x0 + hp * 0.16, yy); ctx.lineTo(x0 + w, yy); ctx.stroke(); }
      ctx.strokeStyle = '#c3cad8'; ctx.lineWidth = Math.max(2, hp * 0.018);
      for (let k = 0; k < 9; k++) { const yy = G - hp * (0.1 + k * 0.1); ctx.beginPath(); ctx.ellipse(x0 + hp * 0.05, yy, hp * 0.075, hp * 0.042, -0.25, 0, 6.283); ctx.stroke(); }
      ctx.fillStyle = 'rgba(255,255,255,0.18)'; ctx.fillRect(x0 + hp * 0.5, G - hp, w, cv * 0.35);
      ctx.fillStyle = '#e8463c'; ctx.fillRect(x0 + hp * 0.9, G - hp * 0.12, hp * 0.1, hp * 0.6);
      ctx.restore();
    }
  }
  // xícara
  {
    const h = 0.095, a = visBy(h, V);
    if (a > 0) {
      const hp = h / m, bw = 0.082 / m, x0 = right + 0.025 / m;
      ctx.save(); ctx.globalAlpha *= a;
      ctx.strokeStyle = '#d94f45'; ctx.lineWidth = bw * 0.1;
      ctx.beginPath(); ctx.ellipse(x0 + bw + bw * 0.06, G - hp * 0.52, bw * 0.24, hp * 0.24, 0, -1.4, 1.4); ctx.stroke();
      const g = ctx.createLinearGradient(x0, 0, x0 + bw, 0);
      g.addColorStop(0, '#b8392f'); g.addColorStop(0.45, '#ec6a5d'); g.addColorStop(1, '#a3322a');
      ctx.fillStyle = g; rr(x0, G - hp, bw, hp, bw * 0.12); ctx.fill();
      ctx.fillStyle = '#5a2a1c'; ctx.beginPath(); ctx.ellipse(x0 + bw / 2, G - hp + bw * 0.03, bw * 0.46, bw * 0.05, 0, 0, 6.283); ctx.fill();
      ctx.strokeStyle = 'rgba(255,255,255,0.35)'; ctx.lineWidth = bw * 0.03; ctx.lineCap = 'round';
      for (let k = 0; k < 3; k++) {
        const sx = x0 + bw * (0.3 + k * 0.2), ph = t * 2 + k;
        ctx.beginPath(); ctx.moveTo(sx, G - hp - bw * 0.08);
        ctx.bezierCurveTo(sx + Math.sin(ph) * bw * 0.08, G - hp - bw * 0.25, sx - Math.sin(ph) * bw * 0.08, G - hp - bw * 0.4, sx, G - hp - bw * 0.45); ctx.stroke();
      }
      ctx.restore();
    }
  }
  // pessoa
  {
    const h = 1.7, a = visBy(h, V);
    if (a > 0) {
      const hp = h / m, cx = right + 0.45 / m;
      ctx.save(); ctx.globalAlpha *= a; ctx.fillStyle = '#9fb4dc'; ctx.strokeStyle = '#9fb4dc';
      ctx.translate(cx, G); ctx.scale(hp / 170, hp / 170); ctx.lineCap = 'round'; ctx.lineJoin = 'round';
      ctx.beginPath(); ctx.arc(0, -157, 13, 0, 6.283); ctx.fill();
      ctx.lineWidth = 9; ctx.beginPath(); ctx.moveTo(0, -146); ctx.lineTo(0, -136); ctx.stroke();
      rr(-19, -141, 38, 62, 13); ctx.fill();
      ctx.lineWidth = 11;
      ctx.beginPath(); ctx.moveTo(-20, -134); ctx.lineTo(-28, -102); ctx.lineTo(-27, -74); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(20, -134); ctx.lineTo(28, -102); ctx.lineTo(27, -74); ctx.stroke();
      ctx.lineWidth = 15;
      ctx.beginPath(); ctx.moveTo(-9, -86); ctx.lineTo(-10, -8); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(9, -86); ctx.lineTo(10, -8); ctx.stroke();
      ctx.beginPath(); ctx.ellipse(-13, -4, 10, 5, 0, 0, 6.283); ctx.fill();
      ctx.beginPath(); ctx.ellipse(13, -4, 10, 5, 0, 0, 6.283); ctx.fill();
      ctx.restore();
    }
  }
  // prédio de 4 andares
  {
    const h = 13, a = visBy(h, V);
    if (a > 0) {
      const hp = h / m, w = 11 / m, x0 = right + 2.2 / m;
      ctx.save(); ctx.globalAlpha *= a;
      ctx.fillStyle = '#c56d4a'; ctx.fillRect(x0, G - hp, w, hp);
      ctx.fillStyle = '#9b4f33'; ctx.fillRect(x0 - w * 0.03, G - hp, w * 1.06, hp * 0.04);
      const fh = hp * 0.96 / 4;
      for (let fl = 0; fl < 4; fl++) for (let c = 0; c < 4; c++) {
        ctx.fillStyle = ((fl + c) % 3 === 0) ? '#ffd98a' : '#3a4f78';
        ctx.fillRect(x0 + w * (0.08 + c * 0.235), G - (fl + 1) * fh + fh * 0.22, w * 0.15, fh * 0.48);
      }
      ctx.fillStyle = '#3a2a22'; ctx.fillRect(x0 + w * 0.42, G - fh * 0.62, w * 0.16, fh * 0.62);
      ctx.restore();
    }
  }
  // Burj Khalifa
  {
    const h = 828, a = visBy(h, V, 0.02, 1.25);
    if (a > 0) {
      const hp = h / m, cx = right + 120 / m, bw = 140 / m;
      ctx.save(); ctx.globalAlpha *= a;
      const g = ctx.createLinearGradient(cx - bw / 2, 0, cx + bw / 2, 0);
      g.addColorStop(0, '#7f93b8'); g.addColorStop(0.5, '#dfe8f7'); g.addColorStop(1, '#6d81a6');
      ctx.fillStyle = g;
      const segs = [[1.0, 0.0], [0.8, 0.22], [0.62, 0.42], [0.45, 0.6], [0.3, 0.74], [0.18, 0.84]];
      for (const [wf, y0] of segs) ctx.fillRect(cx - bw * wf / 2, G - hp * (y0 === 0 ? 0.3 : y0 + 0.08) - 0, bw * wf, hp * (y0 === 0 ? 0.3 : 0.08) + (y0 === 0 ? 0 : 0));
      for (const [wf, y0] of segs) ctx.fillRect(cx - bw * wf / 2, G - hp * (y0 + 0.24), bw * wf, hp * 0.24 + 0.5);
      ctx.beginPath(); ctx.moveTo(cx - bw * 0.06, G - hp * 0.95); ctx.lineTo(cx, G - hp); ctx.lineTo(cx + bw * 0.06, G - hp * 0.95); ctx.fill();
      ctx.fillRect(cx - bw * 0.06, G - hp * 0.95, bw * 0.12, hp * 0.1);
      ctx.restore();
    }
  }
  // Everest
  {
    const h = 8849, a = visBy(h, V, 0.02, 1.3);
    if (a > 0) {
      const hp = h / m, cx = right + 8000 / m, w = 21000 / m;
      ctx.save(); ctx.globalAlpha *= a;
      const g = ctx.createLinearGradient(0, G - hp, 0, G);
      g.addColorStop(0, '#6b7fa8'); g.addColorStop(1, '#22325a');
      ctx.fillStyle = g;
      ctx.beginPath(); ctx.moveTo(cx - w / 2, G); ctx.lineTo(cx - w * 0.22, G - hp * 0.55); ctx.lineTo(cx - w * 0.12, G - hp * 0.62);
      ctx.lineTo(cx, G - hp); ctx.lineTo(cx + w * 0.1, G - hp * 0.78); ctx.lineTo(cx + w * 0.2, G - hp * 0.7); ctx.lineTo(cx + w / 2, G); ctx.fill();
      ctx.fillStyle = '#f2f6ff';
      ctx.beginPath(); ctx.moveTo(cx - w * 0.085, G - hp * 0.8); ctx.lineTo(cx, G - hp); ctx.lineTo(cx + w * 0.065, G - hp * 0.85);
      ctx.lineTo(cx + w * 0.03, G - hp * 0.8); ctx.lineTo(cx - w * 0.01, G - hp * 0.86); ctx.lineTo(cx - w * 0.04, G - hp * 0.78); ctx.fill();
      ctx.restore();
    }
  }
}

function stackWidth(f) {
  if (f <= 8) return Math.max(120, 340 / Math.pow(2, f / 2));
  if (f <= 27) return lerp(120, 56, (f - 8) / 19);
  if (f <= 40) return lerp(56, 26, (f - 27) / 13);
  return 26;
}

function drawStack(t, f, m, lv, alpha = 1) {
  const Hm = PAPEL * Math.pow(2, f);
  const hp = Hm / m, w = stackWidth(f);
  const x0 = SX - w / 2, top = Math.max(G - hp, -40);
  ctx.save(); ctx.globalAlpha = alpha;
  // sombra de contato
  const sh = ctx.createRadialGradient(SX, G, 0, SX, G, w * 0.9);
  sh.addColorStop(0, 'rgba(0,0,0,0.5)'); sh.addColorStop(1, 'rgba(0,0,0,0)');
  ctx.fillStyle = sh; ctx.beginPath(); ctx.ellipse(SX, G + 4, w * 0.9, 14, 0, 0, 6.283); ctx.fill();
  const beam = sstep(3.5, 6, lv);
  if (beam > 0) { ctx.shadowColor = `rgba(255,236,190,${0.85 * beam})`; ctx.shadowBlur = 36 * beam; }
  const g = ctx.createLinearGradient(x0, 0, x0 + w, 0);
  g.addColorStop(0, '#d6d0c2'); g.addColorStop(0.35, '#fffdf7'); g.addColorStop(0.7, '#f1ece0'); g.addColorStop(1, '#c4bdae');
  ctx.fillStyle = g; ctx.fillRect(x0, top, w, G - top);
  ctx.shadowBlur = 0;
  // camadas
  const sp = PAPEL / m;
  if (sp >= 2.4 && hp < 4000) {
    const a = sstep(2.4, 7, sp) * 0.45;
    ctx.strokeStyle = `rgba(110,100,85,${a})`; ctx.lineWidth = 1;
    const n = Math.ceil(Hm / PAPEL);
    for (let k = 1; k < n; k++) { const y = G - k * sp; if (y < top) break; ctx.beginPath(); ctx.moveTo(x0 + 2, y); ctx.lineTo(x0 + w - 2, y); ctx.stroke(); }
    // dobras arredondadas alternadas nas bordas
    ctx.strokeStyle = `rgba(150,140,120,${a})`;
    for (let k = 0; k < n; k += 2) {
      const y = G - (k + 1) * sp; if (y < top) break;
      ctx.beginPath(); ctx.arc((k / 2) % 2 ? x0 + w : x0, y, sp * 0.5, 0, 6.283); ctx.stroke();
    }
  }
  // topo
  ctx.fillStyle = 'rgba(255,255,255,0.9)'; ctx.fillRect(x0, top, w, Math.min(3, G - top));
  if (beam > 0 && top > -30) {
    const tg = ctx.createRadialGradient(SX, top, 0, SX, top, 60);
    tg.addColorStop(0, `rgba(255,250,230,${0.9 * beam})`); tg.addColorStop(1, 'rgba(255,250,230,0)');
    ctx.fillStyle = tg; ctx.beginPath(); ctx.arc(SX, top, 60, 0, 6.283); ctx.fill();
  }
  ctx.restore();
  return { w, top };
}

function drawRuler(m, stackTop, alpha) {
  if (alpha <= 0) return;
  const V = m * VIEW;
  const x = 150, yTop = 470;
  ctx.save(); ctx.globalAlpha = alpha;
  const bg = ctx.createLinearGradient(0, 0, 170, 0);
  bg.addColorStop(0, 'rgba(5,8,18,0.55)'); bg.addColorStop(1, 'rgba(5,8,18,0)');
  ctx.fillStyle = bg; ctx.fillRect(0, yTop - 20, 170, G - yTop + 20);
  ctx.strokeStyle = 'rgba(200,215,255,0.55)'; ctx.lineWidth = 2;
  ctx.beginPath(); ctx.moveTo(x, G); ctx.lineTo(x, yTop); ctx.stroke();
  // passos 1-2-5
  const target = V / 5;
  const e = Math.floor(Math.log10(target));
  const seq = [1, 2, 5, 10].map(v => v * Math.pow(10, e));
  let i = 0; while (i < 3 && seq[i + 1] <= target) i++;
  const s0 = seq[i], s1 = seq[i + 1];
  const fr = Math.log(target / s0) / Math.log(s1 / s0);
  const ticks = (step, a, major) => {
    for (let k = 1; k * step < V * 1.02; k++) {
      const y = G - (k * step) / m; if (y < yTop) break;
      const onMajor = Math.abs((k * step) / s1 - Math.round((k * step) / s1)) < 1e-6;
      const aa = onMajor ? 1 : a;
      if (aa < 0.02) continue;
      ctx.globalAlpha = alpha * aa;
      ctx.strokeStyle = 'rgba(200,215,255,0.8)'; ctx.lineWidth = 2;
      ctx.beginPath(); ctx.moveTo(x - (onMajor ? 18 : 11), y); ctx.lineTo(x, y); ctx.stroke();
      if (major) text(fmtTick(k * step), x - 26, y + 8, { font: `600 22px ${FONT}`, color: '#b8c6e6', align: 'right', alpha: 1 });
    }
  };
  ticks(s0, 1 - fr, true);
  ctx.globalAlpha = alpha;
  // marcador do topo
  const ty = clamp(stackTop, yTop, G);
  ctx.fillStyle = C.yellow; ctx.beginPath(); ctx.moveTo(x + 4, ty); ctx.lineTo(x + 20, ty - 10); ctx.lineTo(x + 20, ty + 10); ctx.closePath(); ctx.fill();
  ctx.restore();
}

function drawTag(t, m, stack) {
  let mk = null;
  if (t >= HOOK_MOON.at && t < HOOK_MOON.until) mk = HOOK_MOON;
  for (const k of MARCOS) if (t >= k.at && t < k.until) mk = k;
  if (!mk) return;
  const a = win(t, mk.at, mk.until, 0.18, 0.2);
  const p = easeOutBack((t - mk.at) / 0.35);
  const x = 560 + (1 - p) * 80, y = 500, w = 380, h = 118;
  const ay = clamp(G - mk.h / m, 470, G - 6);
  const ax = SX + stack.w / 2 + 8;
  ctx.save(); ctx.globalAlpha = a;
  ctx.strokeStyle = 'rgba(255,210,63,0.85)'; ctx.lineWidth = 2.5; ctx.setLineDash([8, 7]);
  ctx.beginPath(); ctx.moveTo(ax, ay); ctx.lineTo(x - 14, ay); ctx.lineTo(x, y + h / 2); ctx.stroke(); ctx.setLineDash([]);
  ctx.fillStyle = C.yellow; ctx.beginPath(); ctx.arc(ax, ay, 6, 0, 6.283); ctx.fill();
  ctx.fillStyle = 'rgba(8,12,26,0.82)'; rr(x, y, w, h, 22); ctx.fill();
  ctx.strokeStyle = 'rgba(255,210,63,0.6)'; ctx.lineWidth = 2; rr(x, y, w, h, 22); ctx.stroke();
  ctx.fillStyle = C.yellow; rr(x, y, 10, h, 5); ctx.fill();
  let fs = 40; ctx.font = `900 ${fs}px ${FONT}`; while (ctx.measureText(mk.title).width > w - 50 && fs > 26) { fs -= 2; ctx.font = `900 ${fs}px ${FONT}`; }
  text(mk.title, x + 30, y + 54, { font: `900 ${fs}px ${FONT}`, color: '#fff' });
  text(mk.sub, x + 30, y + 94, { font: `600 26px ${FONT}`, color: '#c9d4ee' });
  ctx.restore();
}

function drawCounter(t, fi, f, cnt, accent) {
  const x = 60, y = 186, w = 960, h = 236;
  ctx.save();
  ctx.fillStyle = 'rgba(6,10,22,0.62)'; rr(x, y, w, h, 34); ctx.fill();
  ctx.strokeStyle = 'rgba(255,255,255,0.09)'; ctx.lineWidth = 2; rr(x, y, w, h, 34); ctx.stroke();
  text('DOBRAS', x + 52, y + 62, { font: `700 28px ${FONT}`, color: C.label, spacing: 5 });
  // pop quando o número muda
  let last = fi; while (last > 0 && CNT[last - 1] === cnt) last--;
  const since = (fi - last) / FPS;
  const pop = fi > 0 && last > 0 ? 1 + 0.16 * (1 - easeOutCubic(since / 0.22)) : 1;
  const col = accent || (since < 0.25 && last > 0 ? mixc(hex(C.yellow), [255, 255, 255], easeOutCubic(since / 0.25)) : [255, 255, 255]);
  ctx.save(); ctx.translate(x + 52, y + 196); ctx.scale(pop, pop);
  text(String(cnt), 0, 0, { font: `900 150px ${FONT}`, color: rgba(col) });
  ctx.restore();
  ctx.fillStyle = 'rgba(255,255,255,0.1)'; ctx.fillRect(x + 380, y + 40, 2, h - 80);
  text('ESPESSURA', x + 420, y + 62, { font: `700 28px ${FONT}`, color: C.label, spacing: 5 });
  const Hm = PAPEL * Math.pow(2, f);
  const s = fmtLen(Hm);
  let fs = 60; ctx.font = `800 ${fs}px ${MONO}`; while (ctx.measureText(s).width > 500 && fs > 30) { fs -= 2; ctx.font = `800 ${fs}px ${MONO}`; }
  text(s, x + 420, y + 140, { font: `800 ${fs}px ${MONO}`, color: C.yellow });
  text(`= 0,1 mm × 2${sup(cnt)}`, x + 420, y + 196, { font: `600 32px ${FONT}`, color: '#7f8fb3' });
  ctx.restore();
}

// ---------- legendas ----------
let NO_CAPTIONS = false;
function drawCaptions(t) {
  if (NO_CAPTIONS) return;
  const pg = TL.pages.find(p => t >= p.t0 && t < p.t1);
  if (!pg) return;
  const special = pg.line === 'errado';
  const fs0 = special ? 130 : 84;
  let fs = fs0;
  const gap = 0.26;
  ctx.font = `900 ${fs}px ${FONT}`;
  const widths = () => pg.toks.map(k => ctx.measureText(k.txt).width);
  let ws = widths(), sp = fs * 0.3;
  let total = ws.reduce((a, b) => a + b, 0) + sp * (ws.length - 1);
  while (total > 900 && fs > 50) { fs -= 4; ctx.font = `900 ${fs}px ${FONT}`; ws = widths(); sp = fs * 0.3; total = ws.reduce((a, b) => a + b, 0) + sp * (ws.length - 1); }
  const age = t - pg.t0;
  const pin = easeOutBack(age / 0.2);
  const alpha = clamp(age / 0.08) * (1 - sstep(pg.t1 - 0.08, pg.t1, t));
  const cy = 1545;
  ctx.save(); ctx.globalAlpha = alpha;
  ctx.translate(W / 2, cy); ctx.scale(0.86 + 0.14 * pin, 0.86 + 0.14 * pin); ctx.translate(-W / 2, -cy);
  let x = W / 2 - total / 2;
  pg.toks.forEach((k, i) => {
    const active = t >= k.t0 - 0.03 && (i === pg.toks.length - 1 || t < pg.toks[i + 1].t0 - 0.03);
    const said = t >= k.t0 - 0.03;
    let color = special ? C.red : (active ? C.yellow : (said ? '#fff' : 'rgba(255,255,255,0.92)'));
    const s = active ? 1 + 0.07 * (1 - easeOutCubic((t - k.t0) / 0.18)) + 0.02 : 1;
    const cx = x + ws[i] / 2;
    ctx.save(); ctx.translate(cx, cy); ctx.scale(s, s);
    ctx.font = `900 ${fs}px ${FONT}`; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    ctx.lineJoin = 'round'; ctx.lineWidth = fs * 0.2; ctx.strokeStyle = 'rgba(0,0,0,0.92)';
    ctx.shadowColor = 'rgba(0,0,0,0.6)'; ctx.shadowBlur = 18; ctx.shadowOffsetY = 6;
    ctx.strokeText(k.txt, 0, 0); ctx.shadowBlur = 0; ctx.shadowOffsetY = 0;
    ctx.fillStyle = color; ctx.fillText(k.txt, 0, 0);
    ctx.restore();
    x += ws[i] + sp;
  });
  ctx.restore();
}

// ---------- folha de frente (gancho e loop) ----------
function drawFrontSheet(t, f, alpha, push = 1, tip = 0, target = null) {
  if (alpha <= 0) return;
  const w0 = 560, h0 = 792, q = easeInOutCubic(tip);
  // no fim da transição a folha (já dobrada 2x: 280x396) assume a forma exata da pilha lateral
  const tw = target ? target.w / 280 : 1, th = target ? Math.max(target.h, 2) / 396 : 1;
  const cx = lerp(540, SX, q), cy = lerp(850, target ? G - Math.max(target.h, 2) / 2 : 850, q);
  ctx.save(); ctx.globalAlpha = alpha;
  ctx.translate(cx, cy); ctx.scale(push * lerp(1, tw, q), push * lerp(1, th, q));
  // sombra
  const p1 = clamp(f), p2 = clamp(f - 1);
  const fh = h0 * (1 - 0.5 * easeInOutCubic(p1)), fw = w0 * (1 - 0.5 * easeInOutCubic(p2));
  ctx.save(); ctx.shadowColor = 'rgba(0,0,0,0.55)'; ctx.shadowBlur = 50; ctx.shadowOffsetY = 24;
  ctx.fillStyle = C.paper; ctx.fillRect(-fw / 2, -fh / 2, fw, fh); ctx.restore();
  const paper = (x, y, w, h, shade) => {
    const g = ctx.createLinearGradient(x, y, x + w, y + h);
    g.addColorStop(0, rgba(mixc(hex('#fffdf8'), [150, 150, 165], shade)));
    g.addColorStop(1, rgba(mixc(hex('#ece6d8'), [120, 120, 140], shade)));
    ctx.fillStyle = g; ctx.fillRect(x, y, w, h);
    ctx.strokeStyle = 'rgba(160,150,130,0.35)'; ctx.lineWidth = 1.5; ctx.strokeRect(x, y, w, h);
  };
  if (f < 1) {
    // dobra 1: metade de cima vira para baixo
    const p = easeInOutCubic(p1), s = Math.cos(Math.PI * p);
    paper(-w0 / 2, 0 - (h0 / 2) * 0 , w0, h0 / 2, 0);
    // linhas de caderno na metade de baixo
    ctx.strokeStyle = 'rgba(80,130,220,0.18)'; ctx.lineWidth = 2;
    for (let k = 1; k < 9; k++) { ctx.beginPath(); ctx.moveTo(-w0 / 2 + 30, k * h0 / 18); ctx.lineTo(w0 / 2 - 30, k * h0 / 18); ctx.stroke(); }
    const hh = (h0 / 2) * s;
    if (hh > 0) {
      paper(-w0 / 2, -hh, w0, hh, 0.25 * p);
      ctx.strokeStyle = `rgba(80,130,220,${0.18 * s})`;
      for (let k = 1; k < 9; k++) { ctx.beginPath(); ctx.moveTo(-w0 / 2 + 30, -k * hh / 9); ctx.lineTo(w0 / 2 - 30, -k * hh / 9); ctx.stroke(); }
    } else paper(-w0 / 2, 0, w0, -hh, 0.3 * (1 - p) + 0.05);
    ctx.translate(0, -h0 / 4 * easeInOutCubic(p1));
  } else {
    // dobra 2: metade direita vira para a esquerda
    const p = easeInOutCubic(p2), s = Math.cos(Math.PI * p);
    const hh = h0 / 2, y0 = -hh / 2;
    ctx.translate(w0 / 4 * p, 0);
    paper(-w0 / 2, y0, w0 / 2, hh, 0.05);
    const ww = (w0 / 2) * s;
    if (ww > 0) paper(0, y0, ww, hh, 0.05 + 0.25 * p);
    else paper(ww, y0, -ww, hh, 0.3 * (1 - p) + 0.08);
  }
  ctx.restore();
}

// ---------- sobreposições ----------
function drawFormula(t) {
  const a0 = Wt('mentira', 4), a1 = L.espessura.start + 0.2;
  const a = win(t, a0 - 0.05, a1, 0.15, 0.25);
  if (a <= 0) return;
  const p = easeOutBack((t - a0 + 0.05) / 0.3);
  ctx.save(); ctx.globalAlpha = a; ctx.translate(540, 860); ctx.scale(0.8 + 0.2 * p, 0.8 + 0.2 * p);
  ctx.fillStyle = 'rgba(6,10,22,0.75)'; rr(-400, -150, 800, 290, 36); ctx.fill();
  ctx.strokeStyle = 'rgba(79,209,255,0.5)'; ctx.lineWidth = 2; rr(-400, -150, 800, 290, 36); ctx.stroke();
  text('ESPESSURA =', 0, -70, { font: `700 34px ${FONT}`, color: C.label, align: 'center', spacing: 4 });
  text('0,1 mm × 2ⁿ', 0, 50, { font: `900 120px ${FONT}`, color: '#fff', align: 'center' });
  text('n = número de dobras', 0, 112, { font: `600 32px ${FONT}`, color: C.cyan, align: 'center' });
  ctx.restore();
}

function drawThickness(t, m) {
  const a = win(t, Wt('espessura', 5) - 0.2, L.dobra.start + 0.1, 0.2, 0.25);
  if (a <= 0) return;
  const hp = PAPEL / m, x = SX + 190, y0 = G - hp;
  ctx.save(); ctx.globalAlpha = a; ctx.strokeStyle = C.yellow; ctx.fillStyle = C.yellow; ctx.lineWidth = 3;
  ctx.beginPath(); ctx.moveTo(x - 10, y0); ctx.lineTo(x + 10, y0); ctx.moveTo(x - 10, G); ctx.lineTo(x + 10, G); ctx.moveTo(x, y0); ctx.lineTo(x, G); ctx.stroke();
  ctx.restore();
  text('0,1 mm', x + 24, G - hp / 2 + 16, { font: `900 50px ${FONT}`, color: C.yellow, alpha: a });
}

function drawMyth(t) {
  const a0 = Wt('mito', 4) - 0.1, a1 = L.britney.start + 0.35;
  const a = win(t, a0, a1, 0.2, 0.3);
  if (a <= 0) return;
  const p = easeOutBack((t - a0) / 0.35);
  ctx.save(); ctx.globalAlpha = a;
  ctx.fillStyle = 'rgba(3,5,12,0.84)'; ctx.fillRect(-40, -40, W + 80, H + 80);
  ctx.translate(540, 900); ctx.scale(0.7 + 0.3 * p, 0.7 + 0.3 * p);
  ctx.fillStyle = 'rgba(8,12,26,0.85)'; ctx.beginPath(); ctx.arc(0, 0, 250, 0, 6.283); ctx.fill();
  ctx.strokeStyle = 'rgba(255,255,255,0.25)'; ctx.lineWidth = 4; ctx.beginPath(); ctx.arc(0, 0, 250, 0, 6.283); ctx.stroke();
  text('7', 0, 95, { font: `900 300px ${FONT}`, color: '#fff', align: 'center' });
  text('DOBRAS NO MÁXIMO?', 0, -150, { font: `800 30px ${FONT}`, color: C.label, align: 'center', spacing: 3 });
  if (t >= ERRADO - 0.02) {
    const q = clamp((t - ERRADO + 0.02) / 0.16);
    const s = lerp(2.4, 1, easeOutCubic(q));
    ctx.strokeStyle = C.red; ctx.lineWidth = 22; ctx.lineCap = 'round';
    ctx.globalAlpha = a * q;
    ctx.beginPath(); ctx.moveTo(-170, 170); ctx.lineTo(170, -170); ctx.stroke();
    ctx.save(); ctx.rotate(-0.2); ctx.scale(s, s);
    ctx.strokeStyle = C.red; ctx.lineWidth = 12; rr(-250, -95, 500, 190, 26); ctx.stroke();
    ctx.fillStyle = 'rgba(255,59,78,0.12)'; rr(-250, -95, 500, 190, 26); ctx.fill();
    text('MITO', 0, 60, { font: `900 165px ${FONT}`, color: C.red, align: 'center' });
    ctx.restore();
  }
  ctx.restore();
}

function drawRecord(t, cnt) {
  const a0 = L.britney.start, a1 = L.rolo.start + 0.25;
  const a = win(t, a0 + 0.2, a1, 0.25, 0.3);
  if (a <= 0) return;
  const p = easeOutBack((t - a0 - 0.2) / 0.4);
  ctx.save(); ctx.globalAlpha = a;
  ctx.fillStyle = 'rgba(3,5,12,0.84)'; ctx.fillRect(-40, -40, W + 80, H + 80);
  ctx.translate(540, 880); ctx.scale(0.8 + 0.2 * p, 0.8 + 0.2 * p);
  ctx.fillStyle = 'rgba(14,12,6,0.88)'; rr(-420, -260, 840, 500, 44); ctx.fill();
  ctx.strokeStyle = 'rgba(255,194,60,0.7)'; ctx.lineWidth = 3; rr(-420, -260, 840, 500, 44); ctx.stroke();
  text('★ RECORDE ★', 0, -180, { font: `900 44px ${FONT}`, color: C.gold, align: 'center', spacing: 6 });
  const n = Math.max(7, cnt);
  const flash = n === 12 ? 1 - easeOutCubic((t - Wt('britney', 10)) / 0.4) : 0;
  text(String(n), -40, 90, { font: `900 270px ${FONT}`, color: rgba(mixc(hex(C.gold), [255, 255, 255], clamp(flash))), align: 'right' });
  text('DOBRAS', -10, 40, { font: `900 72px ${FONT}`, color: '#fff' });
  text('de verdade', -6, 92, { font: `600 36px ${FONT}`, color: '#d8cfb4' });
  const na = sstep(Wt('britney', 1), Wt('britney', 1) + 0.3, t);
  text('Britney Gallivan · 2002', 0, 190, { font: `700 44px ${FONT}`, color: '#fff', align: 'center', alpha: na });
  ctx.restore();
}

function drawRoll(t) {
  const a0 = L.rolo.start, a1 = L.licao.start + 0.15;
  const a = win(t, a0 - 0.1, a1, 0.2, 0.3);
  if (a <= 0) return;
  const p = easeInOutCubic((t - Wt('rolo', 2)) / (Wt('rolo', 10, 't1') - Wt('rolo', 2)));
  ctx.save(); ctx.globalAlpha = a;
  ctx.fillStyle = 'rgba(3,5,12,0.84)'; ctx.fillRect(-40, -40, W + 80, H + 80);
  const rx = 190, ry = 900, r = 110;
  // tira desenrolando
  const len = p * (W + 300);
  const sy = ry + r - 6;
  const sg = ctx.createLinearGradient(0, sy - 40, 0, sy + 40);
  sg.addColorStop(0, '#fbf8f0'); sg.addColorStop(1, '#ddd6c6');
  ctx.fillStyle = sg; ctx.beginPath();
  ctx.moveTo(rx, sy - 6); ctx.lineTo(rx + len, sy - 6 + Math.sin(len * 0.01) * 4); ctx.lineTo(rx + len, sy + 70); ctx.lineTo(rx, sy + 70); ctx.fill();
  ctx.strokeStyle = 'rgba(150,140,120,0.5)'; ctx.setLineDash([6, 6]); ctx.lineWidth = 2;
  for (let x = rx + 90; x < rx + len; x += 90) { ctx.beginPath(); ctx.moveTo(x, sy - 4); ctx.lineTo(x, sy + 68); ctx.stroke(); }
  ctx.setLineDash([]);
  // rolo
  const rg = ctx.createLinearGradient(rx - r, 0, rx + r, 0);
  rg.addColorStop(0, '#cfc8b8'); rg.addColorStop(0.5, '#fffdf6'); rg.addColorStop(1, '#bdb6a6');
  ctx.fillStyle = rg; ctx.beginPath(); ctx.arc(rx, ry, r, 0, 6.283); ctx.fill();
  ctx.strokeStyle = 'rgba(160,150,130,0.4)'; ctx.lineWidth = 2;
  for (let k = 1; k < 6; k++) { ctx.beginPath(); ctx.arc(rx, ry, r * (0.35 + k * 0.11), 0, 6.283); ctx.stroke(); }
  ctx.fillStyle = '#8a6a45'; ctx.beginPath(); ctx.arc(rx, ry, r * 0.3, 0, 6.283); ctx.fill();
  ctx.fillStyle = '#2a1c10'; ctx.beginPath(); ctx.arc(rx, ry, r * 0.22, 0, 6.283); ctx.fill();
  // cota
  const la = sstep(Wt('rolo', 9) - 0.1, Wt('rolo', 9) + 0.2, t);
  ctx.globalAlpha = a * la;
  ctx.strokeStyle = C.yellow; ctx.lineWidth = 4;
  ctx.beginPath(); ctx.moveTo(rx, ry - 170); ctx.lineTo(W - 30, ry - 170); ctx.moveTo(rx, ry - 190); ctx.lineTo(rx, ry - 150); ctx.stroke();
  ctx.fillStyle = C.yellow; ctx.beginPath(); ctx.moveTo(W - 10, ry - 170); ctx.lineTo(W - 40, ry - 186); ctx.lineTo(W - 40, ry - 154); ctx.fill();
  text('+ de 1 km', 600, ry - 200, { font: `900 96px ${FONT}`, color: C.yellow, align: 'center', stroke: 10 });
  ctx.globalAlpha = a;
  text('PAPEL HIGIÊNICO', 600, ry + 300, { font: `800 40px ${FONT}`, color: '#d8deee', align: 'center', spacing: 5 });
  ctx.restore();
}

function drawChart(t) {
  const a0 = L.licao.start - 0.1, a1 = L.cta.start + 0.1;
  const a = win(t, a0, a1, 0.25, 0.3);
  if (a <= 0) return;
  ctx.save(); ctx.globalAlpha = a;
  ctx.fillStyle = 'rgba(3,5,12,0.84)'; ctx.fillRect(-40, -40, W + 80, H + 80);
  const x0 = 170, y0 = 1250, w = 760, h = 680;
  ctx.fillStyle = 'rgba(8,12,26,0.85)'; rr(x0 - 90, y0 - h - 90, w + 140, h + 170, 40); ctx.fill();
  const ta = sstep(Wt('licao', 2), Wt('licao', 3, 't1'), t);
  text('CRESCIMENTO', x0 + w / 2 - 20, y0 - h - 20, { font: `900 54px ${FONT}`, color: '#fff', align: 'center', alpha: ta });
  text('EXPONENCIAL', x0 + w / 2 - 20, y0 - h + 40, { font: `900 54px ${FONT}`, color: C.cyan, align: 'center', alpha: ta });
  ctx.strokeStyle = 'rgba(200,215,255,0.6)'; ctx.lineWidth = 3;
  ctx.beginPath(); ctx.moveTo(x0, y0 - h + 80); ctx.lineTo(x0, y0); ctx.lineTo(x0 + w, y0); ctx.stroke();
  text('dobras →', x0 + w, y0 + 48, { font: `600 30px ${FONT}`, color: C.label, align: 'right' });
  ctx.save(); ctx.translate(x0 - 24, y0); ctx.rotate(-Math.PI / 2);
  text('espessura →', 0, 0, { font: `600 30px ${FONT}`, color: C.label }); ctx.restore();
  // curva 2^x (x de 0 a 42), escala linear => fica no chão e depois explode
  const tA = Wt('licao', 4), tB = Wt('licao', 5, 't1'), tC = EXPLODE;
  let prog;
  if (t < tA) prog = 0;
  else if (t < tB) prog = 0.8 * (t - tA) / (tB - tA);
  else if (t < tC) prog = 0.8 + 0.03 * (t - tB) / (tC - tB);
  else prog = 0.83 + 0.17 * easeOutCubic((t - tC) / 0.35);
  const xmax = 42;
  ctx.save(); ctx.beginPath(); ctx.rect(x0 - 20, 452, w + 60, y0 - 448); ctx.clip();
  ctx.strokeStyle = C.yellow; ctx.lineWidth = 9; ctx.lineCap = 'round'; ctx.lineJoin = 'round';
  ctx.shadowColor = 'rgba(255,210,63,0.7)'; ctx.shadowBlur = 20;
  ctx.beginPath();
  const top = Math.pow(2, xmax * 0.93);
  let lastX = x0, lastY = y0;
  for (let k = 0; k <= 400 * prog; k++) {
    const u = k / 400, xv = u * xmax;
    const yv = Math.pow(2, xv) / top;
    const X = x0 + u * w, Y = y0 - 4 - yv * (h - 80);
    if (k === 0) ctx.moveTo(X, Y); else ctx.lineTo(X, Y);
    lastX = X; lastY = Y;
    if (Y < 452) break;
  }
  ctx.stroke(); ctx.restore();
  ctx.fillStyle = '#fff'; ctx.beginPath(); ctx.arc(lastX, Math.max(lastY, 462), 10, 0, 6.283); ctx.fill();
  const da = win(t, tA, tC, 0.2, 0.2);
  text('devagar...', x0 + 200, y0 - 60, { font: `800 44px ${FONT}`, color: '#c9d4ee', alpha: da });
  if (t > tC) {
    const q = clamp((t - tC) / 0.25);
    ctx.save(); ctx.translate(x0 + w - 150, y0 - h + 230); ctx.rotate(-0.12); ctx.scale(lerp(1.8, 1, easeOutCubic(q)), lerp(1.8, 1, easeOutCubic(q)));
    text('BOOM!', 0, 0, { font: `900 96px ${FONT}`, color: C.red, align: 'center', alpha: q, stroke: 12 });
    ctx.restore();
  }
  ctx.restore();
}

function drawCTA(t) {
  const a0 = L.cta.start - 0.1, a1 = LOOP0 + 0.05;
  const a = win(t, a0, a1, 0.25, 0.3);
  if (a <= 0) return;
  ctx.save(); ctx.globalAlpha = a;
  ctx.fillStyle = 'rgba(3,5,12,0.86)'; ctx.fillRect(-40, -40, W + 80, H + 80);
  const p = easeOutBack((t - a0) / 0.4);
  ctx.translate(540, 880); ctx.scale(0.85 + 0.15 * p, 0.85 + 0.15 * p);
  text('CURIOSIDADES', 0, -230, { font: `800 40px ${FONT}`, color: C.label, align: 'center', spacing: 8 });
  text('que parecem', 0, -150, { font: `700 64px ${FONT}`, color: '#fff', align: 'center' });
  text('MENTIRA', 0, -40, { font: `900 130px ${FONT}`, color: C.yellow, align: 'center' });
  text('(mas são ciência)', 0, 30, { font: `600 44px ${FONT}`, color: '#c9d4ee', align: 'center' });
  // botão seguir com toque
  const tap = Wt('cta', 0) + 0.55;
  const pressed = t > tap;
  const bp = pressed ? 1 - 0.08 * Math.sin(clamp((t - tap) / 0.18) * Math.PI) : 1 + 0.04 * Math.sin(t * 9);
  ctx.save(); ctx.translate(0, 190); ctx.scale(bp, bp);
  ctx.fillStyle = pressed ? 'rgba(255,255,255,0.12)' : C.yellow; rr(-230, -60, 460, 120, 60); ctx.fill();
  if (pressed) { ctx.strokeStyle = 'rgba(255,255,255,0.5)'; ctx.lineWidth = 3; rr(-230, -60, 460, 120, 60); ctx.stroke(); }
  text(pressed ? '✓ SEGUINDO' : '+ SEGUIR', 0, 20, { font: `900 56px ${FONT}`, color: pressed ? '#fff' : C.ink, align: 'center' });
  ctx.restore();
  // "dedo" (círculo de toque)
  const hp = clamp((t - (tap - 0.45)) / 0.45);
  if (hp > 0 && t < tap + 0.6) {
    const ha = t < tap ? hp : 1 - clamp((t - tap) / 0.6);
    ctx.globalAlpha = a * ha;
    ctx.fillStyle = 'rgba(255,255,255,0.9)'; ctx.beginPath(); ctx.arc(lerp(260, 120, easeOutCubic(hp)), lerp(360, 210, easeOutCubic(hp)), 30, 0, 6.283); ctx.fill();
    if (pressed) { ctx.strokeStyle = 'rgba(255,255,255,0.8)'; ctx.lineWidth = 4; ctx.beginPath(); ctx.arc(120, 210, 30 + (t - tap) * 160, 0, 6.283); ctx.stroke(); }
  }
  ctx.restore();
}

function drawSpeedLines(t, speed) {
  const a = sstep(5, 14, speed);
  if (a <= 0) return;
  ctx.save(); ctx.strokeStyle = '#fff'; ctx.lineCap = 'round';
  for (const s of SPEED) {
    const y = ((s.y + t * 2600 * s.sp) % (H + s.len)) - s.len;
    ctx.globalAlpha = a * s.a * 0.55; ctx.lineWidth = 2;
    ctx.beginPath(); ctx.moveTo(s.x, y); ctx.lineTo(s.x, y + s.len); ctx.stroke();
  }
  ctx.restore();
}

function rewindFx(t, range) {
  const a = win(t, range[0] - 0.05, range[1] + 0.05, 0.08, 0.12);
  if (a <= 0) return;
  sctx.clearRect(0, 0, W, H); sctx.drawImage(canvas, 0, 0);
  const r = rng(Math.floor(t * 60));
  for (let i = 0; i < 7; i++) {
    const y = r() * H, h = 20 + r() * 120, dx = (r() - 0.5) * 80 * a;
    ctx.drawImage(scratch, 0, y, W, h, dx, y, W, h);
  }
  ctx.save(); ctx.globalAlpha = 0.18 * a; ctx.fillStyle = '#000';
  for (let y = (t * 400) % 6; y < H; y += 6) ctx.fillRect(0, y, W, 2);
  ctx.globalAlpha = 0.12 * a; ctx.fillStyle = '#4fd1ff'; ctx.fillRect(0, 0, W, H);
  ctx.restore();
  text('◀◀', 90, 560, { font: `900 72px ${FONT}`, color: '#fff', alpha: a * (0.6 + 0.4 * Math.sin(t * 20)), stroke: 8 });
}

function flashes(t) {
  let a = 0;
  for (const h of MOON_HITS) a = Math.max(a, 0.62 * (1 - easeOutCubic((t - h) / 0.4)) * (t >= h ? 1 : 0));
  for (const [h, k] of [[SUN_HIT, 0.4], [UNI_HIT, 0.6], [EXPLODE, 0.5], [ERRADO, 0.25]]) a = Math.max(a, k * (1 - easeOutCubic((t - h) / 0.35)) * (t >= h ? 1 : 0));
  if (a > 0.01) { ctx.fillStyle = `rgba(255,255,255,${a})`; ctx.fillRect(0, 0, W, H); }
}
function shakeAt(t) {
  let amp = 0;
  for (const [h, k, d] of [[MOON_HITS[0], 12, 0.4], [MOON_HITS[1], 16, 0.5], [UNI_HIT, 10, 0.5], [ERRADO, 20, 0.4], [EXPLODE, 16, 0.45]]) {
    if (t >= h && t < h + d) amp = Math.max(amp, k * (1 - (t - h) / d));
  }
  if (!amp) return [0, 0];
  return [Math.sin(t * 91) * amp, Math.cos(t * 77) * amp];
}

// ---------- quadro ----------
function frame(i) {
  const t = i / FPS;
  const f = F[i], cnt = CNT[i];
  const m = camM(i);
  const lv = Math.log10(m * VIEW);
  const speed = Math.abs(FC[Math.min(i + 1, N - 1)] - FC[Math.max(i - 1, 0)]) * FPS / 2;
  SX = lerp(540, 330, sstep(4.6, 6.6, FC[i]));
  const [sx, sy] = shakeAt(t);
  ctx.save(); ctx.translate(sx, sy);
  ctx.fillStyle = '#05070e'; ctx.fillRect(-40, -40, W + 80, H + 80);
  drawBackground(t, m, lv);
  drawFar(t, m, lv);
  drawGround(t, m, lv);
  // folha de frente vs pilha lateral
  const frontA = t < MORPH1 ? 1 - sstep(MORPH1 - 0.08, MORPH1, t) : sstep(LOOP0, LOOP0 + 0.3, t);
  const sideA = 1 - frontA;
  const stack = { w: stackWidth(f), top: G - PAPEL * Math.pow(2, f) / m };
  ctx.save(); ctx.beginPath(); ctx.rect(-40, 422, W + 80, H); ctx.clip();
  ctx.globalAlpha = 1 - win(t, Wt('mito', 4) - 0.1, LOOP0, 0.3, 0.3);
  drawObjects(t, m, lv, stack.w);
  ctx.restore();
  if (sideA > 0) Object.assign(stack, drawStack(t, f, m, lv, sideA));
  drawRuler(m, stack.top, sideA * (1 - win(t, TWIST0 + 1.0, L.cta.end + 1, 0.3, 0.3) * 0.7));
  drawThickness(t, m);
  if (t > L.mentira.start - 0.5 || (t >= HOOK_MOON.at && t < HOOK_MOON.until)) drawTag(t, m, stack);
  drawSpeedLines(t, speed);
  if (frontA > 0) drawFrontSheet(t, t < MORPH1 ? Math.min(f, 2) : 0, frontA, t < MORPH1 ? 1 + 0.06 * easeInOutCubic(t / MORPH0) : 1, t < MORPH1 ? clamp((t - MORPH0) / (MORPH1 - MORPH0)) : 0, { w: stack.w, h: G - stack.top });
  drawFormula(t);
  drawMyth(t);
  drawRecord(t, cnt);
  drawRoll(t);
  drawChart(t);
  drawCTA(t);
  rewindFx(t, REW1);
  rewindFx(t, REW2);
  ctx.drawImage(vignette, 0, 0);
  drawCounter(t, i, f, cnt, t > L.britney.start && t < L.rolo.start + 0.3 && cnt >= 8 ? hex(C.gold) : null);
  drawCaptions(t);
  flashes(t);
  ctx.restore();
}

// ---------- main ----------
const argv = process.argv.slice(2);
const pi = argv.indexOf('--preview');
if (argv.includes('--capa')) {
  NO_CAPTIONS = true;
  const i = Math.round((MOON_HITS[1] + 0.75) * FPS);
  frame(i);
  const g = ctx.createLinearGradient(0, 900, 0, 1700);
  g.addColorStop(0, 'rgba(3,5,12,0)'); g.addColorStop(0.3, 'rgba(3,5,12,0.82)'); g.addColorStop(1, 'rgba(3,5,12,0.92)');
  ctx.fillStyle = g; ctx.fillRect(0, 900, W, 1020);
  text('DOBRE UMA FOLHA', W / 2, 1150, { font: `900 84px ${FONT}`, color: '#fff', align: 'center', stroke: 14 });
  text('42 VEZES', W / 2, 1340, { font: `900 196px ${FONT}`, color: C.yellow, align: 'center', stroke: 18 });
  text('...e ela chega na Lua', W / 2, 1450, { font: `800 66px ${FONT}`, color: '#fff', align: 'center', stroke: 12 });
  const out = path.join(ROOT, 'output/capa.png');
  fs.mkdirSync(path.dirname(out), { recursive: true });
  fs.writeFileSync(out, canvas.toBuffer('image/png'));
  console.log(out);
} else if (pi >= 0) {
  const dir = path.join(ROOT, 'build/preview');
  fs.mkdirSync(dir, { recursive: true });
  for (const s of argv[pi + 1].split(',')) {
    const i = clamp(Math.round(parseFloat(s) * FPS), 0, N - 1);
    for (let j = Math.max(0, i - 12); j < i; j++) camM(j); // (câmera sem estado; nada a aquecer)
    frame(i);
    const out = path.join(dir, `t${(i / FPS).toFixed(2).padStart(6, '0')}.png`);
    fs.writeFileSync(out, canvas.toBuffer('image/png'));
    console.log(out);
  }
} else {
  const out = path.join(ROOT, 'build/video.mp4');
  const ff = spawn('ffmpeg', ['-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgba', '-s', `${W}x${H}`, '-r', String(FPS), '-i', '-',
    '-c:v', 'libx264', '-preset', 'slow', '-crf', '16', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', out], { stdio: ['pipe', 'inherit', 'inherit'] });
  let i = 0;
  const t0 = Date.now();
  const write = () => {
    while (i < N) {
      frame(i);
      const ok = ff.stdin.write(Buffer.from(canvas.data()));
      i++;
      if (i % 150 === 0) console.log(`  quadro ${i}/${N}  (${((Date.now() - t0) / 1000).toFixed(0)}s)`);
      if (!ok) { ff.stdin.once('drain', write); return; }
    }
    ff.stdin.end();
  };
  ff.on('close', code => { console.log('ffmpeg terminou:', code, out); process.exit(code); });
  write();
}
