"""Leitura de PDF VETORIAL (exportado do CAD). PDF escaneado (imagem) não é suportado.

Diferenças em relação ao DXF:
- o PDF guarda medidas do PAPEL (pontos, 1 pt = 1/72 pol). É preciso a escala da
  prancha (1:50, 1:100...). Ela é informada com --escala ou lida do próprio desenho
  (texto "ESC. 1:50", "ESCALA 1/100"); se houver mais de uma, use --escala;
- só há camadas se o CAD exportou camadas de PDF (OCG). Sem elas, os ambientes são
  achados pelos textos: cada nome de ambiente marca a menor área fechada que o contém.
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from pathlib import Path

from shapely.geometry import LineString, Polygon
from shapely.ops import polygonize, unary_union

from .modelo import Alerta, Desenho, Poligono, Texto

MM_POR_PT = 25.4 / 72
RE_ESCALA = re.compile(r"ESC(?:ALA)?\.?\s*:?\s*1\s*[:/]\s*(\d{1,4})\b", re.I)


class ErroLeitura(Exception):
    pass


def ler_escala(texto: str | None) -> int | None:
    if not texto:
        return None
    m = re.fullmatch(r"\s*1\s*[:/]\s*(\d{1,5})\s*", str(texto))
    if m:
        return int(m.group(1))
    if str(texto).isdigit():
        return int(texto)
    raise ValueError(f"Escala inválida: {texto!r}. Use o formato 1:50")


def _bezier(p0, p1, p2, p3, n=8):
    out = []
    for i in range(1, n + 1):
        t = i / n
        a, b, c, d = (1 - t) ** 3, 3 * t * (1 - t) ** 2, 3 * t * t * (1 - t), t ** 3
        out.append((a * p0.x + b * p1.x + c * p2.x + d * p3.x, a * p0.y + b * p1.y + c * p2.y + d * p3.y))
    return out


def _subcaminhos(itens):
    """Converte os itens de um caminho do PyMuPDF em listas de pontos contínuas."""
    subs, atual = [], []
    fechados = []
    for it in itens:
        op = it[0]
        if op == "re":
            r = it[1]
            fechados.append([(r.x0, r.y0), (r.x1, r.y0), (r.x1, r.y1), (r.x0, r.y1), (r.x0, r.y0)])
            continue
        if op == "qu":
            q = it[1]
            fechados.append([(q.ul.x, q.ul.y), (q.ur.x, q.ur.y), (q.lr.x, q.lr.y), (q.ll.x, q.ll.y), (q.ul.x, q.ul.y)])
            continue
        ini = it[1]
        if not atual or abs(atual[-1][0] - ini.x) > 1e-3 or abs(atual[-1][1] - ini.y) > 1e-3:
            if len(atual) >= 2:
                subs.append(atual)
            atual = [(ini.x, ini.y)]
        if op == "l":
            atual.append((it[2].x, it[2].y))
        elif op == "c":
            atual.extend(_bezier(it[1], it[2], it[3], it[4]))
    if len(atual) >= 2:
        subs.append(atual)
    return subs, fechados


def ler(caminho: str | Path, cfg: dict, escala: str | None = None, pagina: int = 1) -> Desenho:
    try:
        import pymupdf as fitz
    except ImportError as exc:
        raise ErroLeitura("Para ler PDF instale o PyMuPDF: pip install pymupdf") from exc

    caminho = Path(caminho)
    doc = fitz.open(str(caminho))
    if not 1 <= pagina <= doc.page_count:
        raise ErroLeitura(f"O PDF tem {doc.page_count} página(s); pedida a {pagina}.")
    pg = doc[pagina - 1]
    alertas: list[Alerta] = []

    # ---- textos (em pontos)
    textos_pt = []
    for bl in pg.get_text("dict")["blocks"]:
        for ln in bl.get("lines", []):
            txt = "".join(s["text"] for s in ln["spans"]).strip()
            if not txt:
                continue
            x0, y0, x1, y1 = ln["bbox"]
            textos_pt.append((txt, (x0 + x1) / 2, (y0 + y1) / 2, abs(y1 - y0)))

    # ---- escala
    den = ler_escala(escala)
    if den is None:
        achadas = Counter(int(m.group(1)) for t, *_ in textos_pt for m in [RE_ESCALA.search(t)] if m)
        if not achadas:
            raise ErroLeitura("Não achei a escala da prancha no PDF. Informe com --escala 1:50 (ou 1:100...).")
        den = achadas.most_common(1)[0][0]
        if len(achadas) > 1:
            alertas.append(Alerta("atencao", f"Há mais de uma escala na prancha ({', '.join(f'1:{k}' for k in achadas)}). "
                                             f"Usei 1:{den}. Se o desenho for de outra, rode com --escala."))
        else:
            alertas.append(Alerta("info", f"Escala lida do desenho: 1:{den}."))
    fator = MM_POR_PT / 1000 * den  # metros reais por ponto do PDF

    def m(x, y):  # pontos do PDF (y para baixo) -> metros (y para cima)
        return (x * fator, -y * fator)

    if not pg.get_drawings():
        raise ErroLeitura("Esta página do PDF não tem desenho vetorial (provavelmente é imagem escaneada). "
                          "Use o DXF/DWG original ou um PDF exportado direto do CAD.")

    # ---- caminhos
    poligonos: list[Poligono] = []
    linhas_por_camada = defaultdict(list)
    camadas = defaultdict(lambda: {"fechados": 0, "abertos": 0, "textos": 0, "blocos": 0})
    tem_ocg = False
    for i, d in enumerate(pg.get_drawings()):
        camada = d.get("layer") or ""
        tem_ocg = tem_ocg or bool(camada)
        subs, fechados = _subcaminhos(d["items"])
        fecha = bool(d.get("closePath")) or d.get("fill") is not None
        for pts in fechados + (subs if fecha else []):
            pts = [m(*p) for p in pts]
            if len(pts) >= 3:
                g = Polygon(pts)
                if not g.is_valid:
                    g = g.buffer(0)
                    if g.geom_type == "MultiPolygon":
                        g = max(g.geoms, key=lambda q: q.area)
                if g.area >= cfg["area_minima_m2"]:
                    poligonos.append(Poligono(g, camada, "pdf-caminho", f"caminho {i}"))
                    camadas[camada]["fechados"] += 1
        if not fecha:
            for pts in subs:
                linhas_por_camada[camada].append(LineString([m(*p) for p in pts]))
                camadas[camada]["abertos"] += 1
        # contornos fechados (ex.: paredes como retângulos) também delimitam os ambientes vizinhos
        if fecha or fechados:
            for pts in fechados + (subs if fecha else []):
                if len(pts) >= 2:
                    linhas_por_camada[camada].append(LineString([m(*p) for p in pts]))

    # faces formadas por linhas soltas (paredes desenhadas com linhas)
    for camada, lins in linhas_por_camada.items():
        if len(lins) > 20000:
            alertas.append(Alerta("info", f"Camada '{camada or '(sem camada)'}': {len(lins)} linhas, muitas para "
                                          f"montar áreas; só os caminhos fechados foram usados."))
            continue
        for f in polygonize(unary_union(lins)):
            if f.area >= cfg["area_minima_m2"]:
                poligonos.append(Poligono(f, camada, "pdf-linhas", ""))

    textos = []
    for t, x, y, h in textos_pt:
        xm, ym = m(x, y)
        textos.append(Texto(t, xm, ym, h * fator, ""))
        camadas[""]["textos"] += 1

    if not tem_ocg:
        alertas.append(Alerta("info", "O PDF não tem camadas; os ambientes foram achados pelos nomes escritos "
                                      "dentro deles. Confira o desenho de conferência (SVG)."))

    return Desenho(arquivo=str(caminho), formato="pdf", unidade=f"PDF, escala 1:{den}", fator_m=fator,
                   poligonos=poligonos, textos=textos, blocos=Counter(),
                   camadas={k: dict(v) for k, v in camadas.items()}, alertas=alertas, tem_camadas=tem_ocg)
