"""Baixa as imagens/vídeo de arquivo (Wikimedia Commons, licenças livres) e gera assets/CREDITOS.md.

Usa os metadados de build/commons_meta.json (consulta à API do Commons) e baixa direto do servidor de mídia,
com espera progressiva quando o servidor pede para desacelerar (HTTP 429) e validação do arquivo baixado.
"""
import json, re, sys, time, urllib.request, urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
A = ROOT / "assets"
UA = "CuriosidadesVideoBot/1.0 (https://github.com/pedidosprainha-cpu; educational video)"
ITENS = [
    ("carapintadas_planalto.jpg", "Cara pintadas.jpg"),
    ("carapintadas_senado.jpg", "Caras-pintadas (4987269067).jpg"),
    ("esplanada_impeachment.jpg", "Manifestantes na Esplanada dos Ministérios pedem o impeachment de Fernando Collor de Mello (4987870444).jpg"),
    ("collor_deixa_presidencia.jpg", "Fernando Collor deixa a presidência.jpg"),
    ("collor_retrato_1992.jpg", "Fernando Collor 1992 B&W.jpg"),
    ("collor_corrida.jpg", "Collor corre nas proximidades da casa da Dinda.jpg"),
    ("collor_carro_aberto.jpg", "Presidente Collor em carro aberto..jpg"),
    ("gabriel_2003.jpg", "Gabriel o Pensador.jpg"),
    ("fita_cassete.jpg", "Noname blank compact cassette, loose tape (1).jpg"),
    ("confisco_1990.webm", "Anúncio do confisco das poupanças pelo governo Collor.webm"),
]
MAGIC = {".jpg": b"\xff\xd8", ".webm": b"\x1a\x45\xdf\xa3"}


def valid(p):
    return p.exists() and p.stat().st_size > 5000 and p.read_bytes()[:2 if p.suffix == ".jpg" else 4] == MAGIC[p.suffix]


def get(url, tries=10):
    for k in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=90) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code not in (429, 503):
                raise
            wait = 90 * (k + 1)
            print(f"  {e.code}, aguardando {wait}s", flush=True)
            time.sleep(wait)
    raise RuntimeError("falhou: " + url)


strip = lambda s: re.sub("<[^>]+>", "", s or "").strip()


def main():
    meta = json.loads((ROOT / "build" / "commons_meta.json").read_text())
    pages = {p["title"].replace("_", " "): p for p in meta["query"]["pages"].values()}
    rows = []
    for local, title in ITENS:
        ii = pages["File:" + title]["imageinfo"][0]; m = ii["extmetadata"]
        g = lambda k: strip(m.get(k, {}).get("value"))
        url = ii["url"] if local.endswith(".webm") else (ii.get("thumburl") or ii["url"])
        dest = A / local
        if not valid(dest):
            dest.write_bytes(get(url))
            time.sleep(6)
        print(("ok " if valid(dest) else "INVÁLIDO ") + local, dest.stat().st_size, flush=True)
        rows.append((local, g("Artist"), g("Credit"), g("LicenseShortName"), g("DateTimeOriginal"), ii["descriptionurl"]))
    with open(A / "CREDITOS.md", "w") as f:
        f.write("# Créditos das imagens e do vídeo de arquivo\n\n")
        f.write("Todos os arquivos vêm do Wikimedia Commons, com licenças livres que permitem uso comercial com atribuição.\n\n")
        f.write("| Arquivo | Autor | Fonte / acervo | Licença | Data | Página |\n|---|---|---|---|---|---|\n")
        for r in rows:
            f.write(f"| `{r[0]}` | {r[1]} | {r[2][:90]} | {r[3]} | {r[4][:24]} | {r[5]} |\n")
    print("créditos gravados")


if __name__ == "__main__":
    main()
