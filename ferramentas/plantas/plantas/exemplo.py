"""Planta de exemplo com áreas conhecidas — base dos testes e para ver o programa funcionando.

Casa térrea num lote 12 × 25 m. Inclui de propósito situações reais para testar as conferências:
- SALA com hachura por cima da polilinha (não pode contar duas vezes);
- COZINHA com área escrita errada no desenho (12,00 m² escrito; real 11,70 m²) e PD=2,60;
- BANHEIRO desenhado com LINEs soltas (sem polilinha);
- dois QUARTOs (nome repetido);
- VARANDA com arco (polilinha com bulge), fora da projeção da área construída;
- um DEPÓSITO sem texto de nome;
- blocos de portas e janelas.
"""
from __future__ import annotations

import math
from pathlib import Path

import ezdxf

# nome, (x0, y0, x1, y1) em metros
RETANGULOS = {
    "SALA": (2.15, 5.15, 6.15, 10.15),        # 20,00
    "COZINHA": (6.25, 5.15, 10.15, 8.15),     # 11,70
    "BANHEIRO": (6.25, 8.25, 8.25, 10.15),    # 3,80  (linhas soltas)
    "QUARTO": (2.15, 10.25, 6.15, 15.15),     # 19,60
    "QUARTO ": (6.25, 10.25, 10.15, 15.15),   # 19,11  (mesmo nome)
    "": (8.35, 8.25, 10.15, 10.15),           # 3,42  sem nome
}
VARANDA_AREA = 4 * 1.55 + math.pi * 2 ** 2 / 2          # 12,4832
VARANDA_PERIMETRO = 2 * 1.55 + 4 + math.pi * 2           # 13,3832

ESPERADO = {
    "SALA": 20.00, "COZINHA": 11.70, "BANHEIRO": 3.80, "QUARTO (1)": 19.60, "QUARTO (2)": 19.11,
    "VARANDA": VARANDA_AREA, "AMBIENTE": 3.42,
    "_terreno": 300.0, "_construida": 8.3 * 10.3, "_permeavel": 1.5 * 25,
}
ESPERADO["_util"] = sum(v for k, v in ESPERADO.items() if not k.startswith("_"))


def _ret(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def gerar_dxf(destino: str | Path, unidade: str = "m", informar_unidade: bool = True) -> Path:
    f = {"m": 1.0, "cm": 100.0, "mm": 1000.0}[unidade]
    S = lambda pts: [(x * f, y * f) for x, y in pts]  # noqa: E731
    doc = ezdxf.new("R2010", setup=True)
    doc.header["$INSUNITS"] = {"m": 6, "cm": 5, "mm": 4}[unidade] if informar_unidade else 0
    for nome, cor in (("TERRENO", 8), ("CONSTRUIDA", 30), ("PERMEAVEL", 3), ("AMBIENTES", 5),
                      ("TEXTOS", 7), ("ESQUADRIAS", 2), ("PAREDES", 7)):
        doc.layers.add(nome, color=cor)
    msp = doc.modelspace()

    msp.add_lwpolyline(S(_ret(0, 0, 12, 25)), close=True, dxfattribs={"layer": "TERRENO"})
    msp.add_lwpolyline(S(_ret(2, 5, 10.3, 15.3)), close=True, dxfattribs={"layer": "CONSTRUIDA"})
    msp.add_lwpolyline(S(_ret(10.5, 0, 12, 25)), close=True, dxfattribs={"layer": "PERMEAVEL"})
    msp.add_lwpolyline(S(_ret(2, 5, 10.3, 15.3)), close=True, dxfattribs={"layer": "PAREDES"})  # ruído

    h = 0.20 * f
    for nome, (x0, y0, x1, y1) in RETANGULOS.items():
        pts = _ret(x0, y0, x1, y1)
        if nome == "BANHEIRO":
            for a, b in zip(pts, pts[1:] + pts[:1]):
                msp.add_line(S([a])[0], S([b])[0], dxfattribs={"layer": "AMBIENTES"})
        else:
            msp.add_lwpolyline(S(pts), close=True, dxfattribs={"layer": "AMBIENTES"})
        cx, cy = (x0 + x1) / 2 * f, (y0 + y1) / 2 * f
        if nome.strip() == "SALA":
            hatch = msp.add_hatch(color=5, dxfattribs={"layer": "AMBIENTES"})
            hatch.paths.add_polyline_path(S(pts), is_closed=True)
            msp.add_mtext("SALA\\P20,00 m²", dxfattribs={"layer": "TEXTOS", "char_height": h,
                                                          "insert": (cx, cy),
                                                          "attachment_point": 5})
        elif nome == "COZINHA":
            msp.add_text("COZINHA", height=h, dxfattribs={"layer": "TEXTOS"}).set_placement(
                (cx, cy + 0.3 * f), align=ezdxf.enums.TextEntityAlignment.MIDDLE_CENTER)
            msp.add_text("A=12,00 m²", height=h * 0.7, dxfattribs={"layer": "TEXTOS"}).set_placement(
                (cx, cy), align=ezdxf.enums.TextEntityAlignment.MIDDLE_CENTER)
            msp.add_text("PD=2,60", height=h * 0.7, dxfattribs={"layer": "TEXTOS"}).set_placement(
                (cx, cy - 0.3 * f), align=ezdxf.enums.TextEntityAlignment.MIDDLE_CENTER)
        elif nome:
            msp.add_text(nome.strip(), height=h, dxfattribs={"layer": "TEXTOS"}).set_placement(
                (cx, cy), align=ezdxf.enums.TextEntityAlignment.MIDDLE_CENTER)

    # VARANDA: retângulo 4 × 1,55 com semicírculo de raio 2 embaixo (bulge = 1)
    x0, x1, yt, yb = 2.15, 6.15, 5.05, 3.5
    msp.add_lwpolyline([(x0 * f, yt * f, 0), (x0 * f, yb * f, 1), (x1 * f, yb * f, 0), (x1 * f, yt * f, 0)],
                       format="xyb", close=True, dxfattribs={"layer": "AMBIENTES"})
    msp.add_text("VARANDA", height=h, dxfattribs={"layer": "TEXTOS"}).set_placement(
        (4.15 * f, 3.6 * f), align=ezdxf.enums.TextEntityAlignment.MIDDLE_CENTER)

    # blocos
    porta = doc.blocks.new("PORTA 80")
    porta.add_line((0, 0), (0.8 * f, 0))
    porta.add_arc((0, 0), 0.8 * f, 0, 90)
    janela = doc.blocks.new("JANELA 120")
    janela.add_lwpolyline(_ret(0, 0, 1.2 * f, 0.15 * f), close=True)
    for x, y in ((3, 5.05), (7, 5.05), (4, 10.15), (8, 10.15), (7, 8.15)):
        msp.add_blockref("PORTA 80", (x * f, y * f), dxfattribs={"layer": "ESQUADRIAS"})
    for x, y in ((3, 15.15), (7.5, 15.15), (2.0, 7), (10.15, 6)):
        msp.add_blockref("JANELA 120", (x * f, y * f), dxfattribs={"layer": "ESQUADRIAS"})

    msp.add_text("PLANTA BAIXA - ESC. 1:100", height=0.35 * f, dxfattribs={"layer": "TEXTOS"}).set_placement(
        (0, -1.5 * f))
    destino = Path(destino)
    doc.saveas(destino)
    return destino


def gerar_pdf(destino: str | Path, escala: int = 100) -> Path:
    """PDF vetorial simples (sem camadas) da mesma casa, só com os ambientes retangulares."""
    import pymupdf as fitz
    pt_por_m = 1000 / escala / (25.4 / 72)
    doc = fitz.open()
    pg = doc.new_page(width=842, height=1191)  # A3 retrato
    ox, oy = 60, 1100

    def P(x, y):
        return fitz.Point(ox + x * pt_por_m, oy - y * pt_por_m)

    sh = pg.new_shape()
    sh.draw_rect(fitz.Rect(P(0, 25), P(12, 0)))           # terreno
    for nome, (x0, y0, x1, y1) in RETANGULOS.items():
        sh.draw_rect(fitz.Rect(P(x0, y1), P(x1, y0)))
    # paredes externas (linhas)
    for a, b in (((2, 5), (10.3, 5)), ((10.3, 5), (10.3, 15.3)), ((10.3, 15.3), (2, 15.3)), ((2, 15.3), (2, 5))):
        sh.draw_line(P(*a), P(*b))
    sh.finish(color=(0, 0, 0), width=0.5)
    sh.commit()
    for nome, (x0, y0, x1, y1) in RETANGULOS.items():
        if nome.strip():
            c = P((x0 + x1) / 2, (y0 + y1) / 2)
            pg.insert_text(fitz.Point(c.x - 3 * len(nome.strip()), c.y), nome.strip(), fontsize=7)
    pg.insert_text(fitz.Point(60, 1150), f"PLANTA BAIXA - ESC. 1:{escala}", fontsize=10)
    destino = Path(destino)
    doc.save(str(destino))
    return destino
