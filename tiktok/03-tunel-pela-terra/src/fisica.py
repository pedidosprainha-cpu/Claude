"""Simula a queda num túnel (sem ar) que passa pelo centro da Terra.

Modelo de densidade em camadas (simplificação do PREM). Ignora rotação da Terra e atrito.
Saída: build/queda.json com tempo, profundidade, velocidade e temperatura amostrados.
"""
import json, math
from pathlib import Path

G = 6.674e-11
R = 6.371e6
# (raio externo da camada em m, densidade kg/m3)
CAMADAS = [(1.221e6, 12900), (3.480e6, 10900), (5.701e6, 4900), (6.346e6, 3600), (6.371e6, 2800)]
# temperatura (°C) por profundidade (km)
TEMP = [(0, 15), (35, 500), (100, 1300), (660, 1900), (2890, 3700), (5150, 5000), (6371, 5400)]


def massa_interna(r):
    m, r0 = 0.0, 0.0
    for (r1, rho) in CAMADAS:
        a, b = r0, min(r, r1)
        if b > a:
            m += 4 / 3 * math.pi * (b ** 3 - a ** 3) * rho
        r0 = r1
        if r <= r1:
            break
    return m


def g(r):
    return 0.0 if r <= 0 else G * massa_interna(r) / r ** 2


def temp(prof_km):
    p = min(prof_km, 6371)
    for (d0, t0), (d1, t1) in zip(TEMP, TEMP[1:]):
        if p <= d1:
            return t0 + (t1 - t0) * (p - d0) / (d1 - d0)
    return TEMP[-1][1]


def main():
    print(f"massa total: {massa_interna(R):.3e} kg (real: 5,972e24)   g na superfície: {g(R):.2f} m/s²")
    # posição x ao longo do túnel: +R (Brasil) -> 0 (centro) -> -R (outro lado)
    x, v, t, dt = R, 0.0, 0.0, 0.05
    amostras = []
    cruz = {}
    while True:
        prof = (R - x) / 1000
        amostras.append({"t": round(t, 2), "prof": round(prof, 3), "v": round(abs(v) * 3.6, 1), "temp": round(temp(R / 1000 - abs(x) / 1000), 1)})
        for nome, d in [("crosta", 35), ("manto", 2890), ("nucleo_int", 5150), ("centro", 6371), ("sai_nucleo_int", 7592), ("sai_nucleo", 9852), ("sai_manto", 12707)]:
            if nome not in cruz and prof >= d:
                cruz[nome] = round(t, 1)
        a = -math.copysign(g(abs(x)), x)
        # Velocity Verlet
        x_new = x + v * dt + 0.5 * a * dt * dt
        a_new = -math.copysign(g(abs(x_new)), x_new)
        v = v + 0.5 * (a + a_new) * dt
        x = x_new
        t += dt
        if v > 0 and t > 100:  # parou do outro lado (velocidade inverteu)
            break
    vmax = max(s["v"] for s in amostras)
    print(f"tempo até o outro lado: {t:.0f} s = {t / 60:.1f} min   velocidade máxima: {vmax:,.0f} km/h")
    for k, tt in cruz.items():
        print(f"  {k:15s} {tt:7.1f} s  ({tt / 60:5.2f} min)")
    out = Path(__file__).resolve().parent.parent / "build" / "queda.json"
    out.write_text(json.dumps({"total": round(t, 1), "vmax": vmax, "cruz": cruz, "amostras": amostras[::10]}))


if __name__ == "__main__":
    main()
