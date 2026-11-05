// Gera a foto de perfil "Curiosidades Aleatórias" (1080x1080) em duas variações
//   node gerar-perfil.js  -> output/*.png  (+ build/ com prévias recortadas em círculo)
const { createCanvas } = require('@napi-rs/canvas');
const fs = require('fs');
const path = require('path');

const S = 1080, C = S / 2;
const FONT = '"Inter Display"';
const COL = { yellow: '#FFD23F', cyan: '#4FD1FF', white: '#FFFFFF', bg0: '#1d2d5c', bg1: '#060a17' };
const OUT = path.join(__dirname, 'output'), BUILD = path.join(__dirname, 'build');
fs.mkdirSync(OUT, { recursive: true }); fs.mkdirSync(BUILD, { recursive: true });

function rng(seed) { return () => { seed |= 0; seed = seed + 0x6D2B79F5 | 0; let t = Math.imul(seed ^ seed >>> 15, 1 | seed); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }

function fundo(ctx) {
  const g = ctx.createRadialGradient(C, C * 0.85, 40, C, C, S * 0.72);
  g.addColorStop(0, COL.bg0); g.addColorStop(1, COL.bg1);
  ctx.fillStyle = g; ctx.fillRect(0, 0, S, S);
  const r = rng(9);
  for (let i = 0; i < 140; i++) {
    const x = r() * S, y = r() * S, rad = 0.8 + r() * r() * 2.6;
    ctx.globalAlpha = 0.25 + r() * 0.6; ctx.fillStyle = '#fff';
    ctx.beginPath(); ctx.arc(x, y, rad, 0, 6.283); ctx.fill();
  }
  ctx.globalAlpha = 1;
}

// "?" amarelo com um anel orbital (metade de trás atrás do glifo, metade da frente na frente)
function icone(ctx, cx, cy, size) {
  const ringRx = size * 0.62, ringRy = size * 0.17, tilt = -0.32, lw = size * 0.045;
  const anel = (a0, a1) => {
    ctx.save(); ctx.translate(cx, cy); ctx.rotate(tilt);
    ctx.shadowColor = 'rgba(79,209,255,0.8)'; ctx.shadowBlur = size * 0.06;
    ctx.strokeStyle = COL.cyan; ctx.lineWidth = lw; ctx.lineCap = 'round';
    ctx.beginPath(); ctx.ellipse(0, 0, ringRx, ringRy, 0, a0, a1); ctx.stroke(); ctx.restore();
  };
  // brilho atrás
  const halo = ctx.createRadialGradient(cx, cy, 0, cx, cy, size * 0.75);
  halo.addColorStop(0, 'rgba(255,210,63,0.30)'); halo.addColorStop(1, 'rgba(255,210,63,0)');
  ctx.fillStyle = halo; ctx.beginPath(); ctx.arc(cx, cy, size * 0.75, 0, 6.283); ctx.fill();
  anel(Math.PI, Math.PI * 2);                 // metade de trás
  ctx.save();
  ctx.font = `900 ${size}px ${FONT}`; ctx.textAlign = 'center'; ctx.textBaseline = 'alphabetic';
  const m = ctx.measureText('?');
  const base = cy + (m.actualBoundingBoxAscent - m.actualBoundingBoxDescent) / 2;
  ctx.shadowColor = 'rgba(0,0,0,0.45)'; ctx.shadowBlur = size * 0.05; ctx.shadowOffsetY = size * 0.02;
  const g = ctx.createLinearGradient(0, cy - size * 0.4, 0, cy + size * 0.4);
  g.addColorStop(0, '#FFE27A'); g.addColorStop(1, '#FFB81F');
  ctx.fillStyle = g; ctx.fillText('?', cx, base);
  ctx.restore();
  anel(0, Math.PI);                           // metade da frente
  // "elétron" no anel
  ctx.save(); ctx.translate(cx, cy); ctx.rotate(tilt);
  const a = 0.35 * Math.PI, ex = ringRx * Math.cos(a), ey = ringRy * Math.sin(a);
  ctx.shadowColor = 'rgba(255,255,255,0.9)'; ctx.shadowBlur = size * 0.05;
  ctx.fillStyle = '#fff'; ctx.beginPath(); ctx.arc(ex, ey, size * 0.05, 0, 6.283); ctx.fill();
  ctx.restore();
}

function texto(ctx, s, x, y, { size, color, spacing = 0 }) {
  ctx.save(); ctx.font = `900 ${size}px ${FONT}`; ctx.textAlign = 'center'; ctx.textBaseline = 'alphabetic';
  ctx.letterSpacing = spacing + 'px';
  ctx.lineJoin = 'round'; ctx.lineWidth = size * 0.12; ctx.strokeStyle = 'rgba(4,7,16,0.85)';
  ctx.strokeText(s, x, y); ctx.fillStyle = color; ctx.fillText(s, x, y); ctx.restore();
}
function caberLargura(ctx, s, maxW, size, spacing) {
  ctx.letterSpacing = spacing + 'px';
  while (size > 20) { ctx.font = `900 ${size}px ${FONT}`; if (ctx.measureText(s).width <= maxW) break; size -= 2; }
  ctx.letterSpacing = '0px';
  return size;
}

function borda(ctx) {
  ctx.save(); ctx.strokeStyle = 'rgba(255,210,63,0.9)'; ctx.lineWidth = 14;
  ctx.beginPath(); ctx.arc(C, C, C - 30, 0, 6.283); ctx.stroke();
  ctx.strokeStyle = 'rgba(255,255,255,0.12)'; ctx.lineWidth = 3;
  ctx.beginPath(); ctx.arc(C, C, C - 52, 0, 6.283); ctx.stroke(); ctx.restore();
}

// A) ícone em cima + nome empilhado (recomendada: lê bem pequena)
function variacaoA() {
  const cv = createCanvas(S, S), ctx = cv.getContext('2d');
  fundo(ctx); borda(ctx);
  icone(ctx, C, 385, 400);
  const s1 = caberLargura(ctx, 'CURIOSIDADES', 820, 150, 2);
  texto(ctx, 'CURIOSIDADES', C, 735, { size: s1, color: COL.white, spacing: 2 });
  const s2 = caberLargura(ctx, 'ALEATÓRIAS', 700, s1, 2);
  texto(ctx, 'ALEATÓRIAS', C, 735 + s2 * 1.02, { size: s2, color: COL.yellow, spacing: 2 });
  return cv;
}

// B) selo: nome em arco ao redor + ícone grande no centro
function arco(ctx, s, r, centro, cima, { size, color, spacing }) {
  ctx.save(); ctx.font = `900 ${size}px ${FONT}`; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
  const ws = [...s].map(ch => ctx.measureText(ch).width + spacing);
  const total = ws.reduce((a, b) => a + b, 0);
  let ang = centro - (cima ? 1 : -1) * (total / r) / 2;
  [...s].forEach((ch, i) => {
    const da = ws[i] / r, a = ang + (cima ? 1 : -1) * da / 2;
    ctx.save(); ctx.translate(C + r * Math.cos(a), C + r * Math.sin(a));
    ctx.rotate(cima ? a + Math.PI / 2 : a - Math.PI / 2);
    ctx.lineJoin = 'round'; ctx.lineWidth = size * 0.12; ctx.strokeStyle = 'rgba(4,7,16,0.85)';
    ctx.strokeText(ch, 0, 0); ctx.fillStyle = color; ctx.fillText(ch, 0, 0); ctx.restore();
    ang += (cima ? 1 : -1) * da;
  });
  ctx.restore();
}
function variacaoB() {
  const cv = createCanvas(S, S), ctx = cv.getContext('2d');
  fundo(ctx);
  ctx.save(); ctx.fillStyle = 'rgba(4,7,16,0.55)'; ctx.beginPath(); ctx.arc(C, C, C - 30, 0, 6.283); ctx.fill(); ctx.restore();
  const g = ctx.createRadialGradient(C, C * 0.9, 20, C, C, 330);
  g.addColorStop(0, COL.bg0); g.addColorStop(1, '#0a1230');
  ctx.fillStyle = g; ctx.beginPath(); ctx.arc(C, C, 330, 0, 6.283); ctx.fill();
  ctx.strokeStyle = 'rgba(255,210,63,0.9)'; ctx.lineWidth = 10; ctx.beginPath(); ctx.arc(C, C, 330, 0, 6.283); ctx.stroke();
  borda(ctx);
  icone(ctx, C, C + 10, 430);
  arco(ctx, 'CURIOSIDADES', 410, -Math.PI / 2, true, { size: 96, color: COL.white, spacing: 6 });
  arco(ctx, 'ALEATÓRIAS', 425, Math.PI / 2, false, { size: 96, color: COL.yellow, spacing: 6 });
  for (const a of [Math.PI, 0]) { ctx.fillStyle = COL.yellow; ctx.beginPath(); ctx.arc(C + 418 * Math.cos(a), C + 418 * Math.sin(a), 12, 0, 6.283); ctx.fill(); }
  return cv;
}

// prévia: recorte circular (como o TikTok mostra) em tamanho grande e em ~110 px
function previa(cv, nome) {
  const big = createCanvas(S, S), b = big.getContext('2d');
  b.fillStyle = '#fff'; b.fillRect(0, 0, S, S);
  b.save(); b.beginPath(); b.arc(C, C, C, 0, 6.283); b.clip(); b.drawImage(cv, 0, 0); b.restore();
  const sm = createCanvas(S, S), s = sm.getContext('2d');
  s.fillStyle = '#fff'; s.fillRect(0, 0, S, S);
  for (const [px, x] of [[110, 120], [64, 420], [40, 640]]) {
    s.save(); s.beginPath(); s.arc(x + px / 2, 300 + px / 2, px / 2, 0, 6.283); s.clip(); s.drawImage(cv, x, 300, px, px); s.restore();
  }
  fs.writeFileSync(path.join(BUILD, `${nome}-circulo.png`), big.toBuffer('image/png'));
  fs.writeFileSync(path.join(BUILD, `${nome}-pequena.png`), sm.toBuffer('image/png'));
}

for (const [nome, fn] of [['perfil-curiosidades-aleatorias', variacaoA], ['perfil-curiosidades-aleatorias-selo', variacaoB]]) {
  const cv = fn();
  fs.writeFileSync(path.join(OUT, `${nome}.png`), cv.toBuffer('image/png'));
  previa(cv, nome);
  console.log(path.join(OUT, `${nome}.png`));
}
