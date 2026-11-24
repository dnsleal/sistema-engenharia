"""Desenho de conferência (.svg): mostra o que o programa entendeu de cada área.

Abra no navegador e compare com a planta: ambientes em azul com nome e área,
terreno em cinza, área construída tracejada, permeável em verde e alertas em vermelho.
"""
from __future__ import annotations

from html import escape
from pathlib import Path

from .formatos import num
from .modelo import Resultado

ESTILO = {
    "terreno": ('fill="none" stroke="#666" stroke-width="2"', None),
    "construida": ('fill="none" stroke="#c55a11" stroke-width="2" stroke-dasharray="8 4"', None),
    "permeavel": ('fill="#a9d18e" fill-opacity="0.45" stroke="#548235" stroke-width="1"', None),
    "ambientes": ('fill="#9dc3e6" fill-opacity="0.55" stroke="#1f4e79" stroke-width="1.2"', None),
}


def gerar(res: Resultado, destino: str | Path, largura_px: int = 1400) -> Path:
    geoms = [a.geom for a in res.ambientes] + [a.geom for v in res.outras.values() for a in v]
    destino = Path(destino)
    if not geoms:
        destino.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="400" height="60">'
                           '<text x="10" y="35">Nenhuma área encontrada.</text></svg>', encoding="utf-8")
        return destino
    # enquadra no prédio (ambientes + construída); o lote costuma ser bem maior e fica cortado
    foco = [a.geom for a in res.ambientes] + [a.geom for a in res.outras.get("construida", [])] or geoms
    minx = min(g.bounds[0] for g in foco)
    miny = min(g.bounds[1] for g in foco)
    maxx = max(g.bounds[2] for g in foco)
    maxy = max(g.bounds[3] for g in foco)
    folga = 0.04 * max(maxx - minx, maxy - miny)
    minx, miny, maxx, maxy = minx - folga, miny - folga, maxx + folga, maxy + folga
    w, h = (maxx - minx) or 1, (maxy - miny) or 1
    marg = 30
    esc = (largura_px - 2 * marg) / w
    altura_px = int(h * esc + 2 * marg)
    linha_leg = 17
    n_col = 3
    linhas_lista = -(-len(res.ambientes) // n_col)
    altura_total = altura_px + 40 + (linhas_lista + 2) * linha_leg

    def X(x):
        return marg + (x - minx) * esc

    def Y(y):
        return marg + (maxy - y) * esc

    def caminho(g):
        partes = []
        for anel in [g.exterior, *g.interiors]:
            cs = list(anel.coords)
            partes.append("M" + " L".join(f"{X(x):.1f},{Y(y):.1f}" for x, y in cs) + " Z")
        return " ".join(partes)

    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {largura_px} {altura_total}" '
           f'width="{largura_px}" height="{altura_total}" font-family="Arial, sans-serif">',
           '<rect width="100%" height="100%" fill="#ffffff"/>',
           f'<clipPath id="quadro"><rect x="0" y="0" width="{largura_px}" height="{altura_px}"/></clipPath>',
           '<g clip-path="url(#quadro)">']
    for cat in ("terreno", "permeavel", "construida"):
        for a in res.outras.get(cat, []):
            out.append(f'<path d="{caminho(a.geom)}" fill-rule="evenodd" {ESTILO[cat][0]}><title>'
                       f'{escape(a.nome)}: {num(a.area)} m²</title></path>')
    fonte = max(9, min(16, 0.35 * esc))
    for a in res.ambientes:
        sem_nome = "SEM NOME" in a.nome
        estilo = ESTILO["ambientes"][0]
        if sem_nome:
            estilo = estilo.replace("#9dc3e6", "#ffd966")
        out.append(f'<path d="{caminho(a.geom)}" fill-rule="evenodd" {estilo}><title>{a.numero} - '
                   f'{escape(a.nome)}: {num(a.area)} m², perímetro {num(a.perimetro)} m</title></path>')
    for a in res.ambientes:
        c = a.geom.representative_point()
        larg_amb = (a.geom.bounds[2] - a.geom.bounds[0]) * esc
        rotulo = f"{a.numero}. {a.nome}"
        if 0.6 * fonte * len(rotulo) > 0.95 * larg_amb:
            rotulo = str(a.numero)  # ambiente estreito: só o número; o nome está na lista abaixo
        out.append(f'<text x="{X(c.x):.1f}" y="{Y(c.y):.1f}" font-size="{fonte:.0f}" text-anchor="middle" '
                   f'fill="#0b2545"><tspan font-weight="bold">{escape(rotulo)}</tspan>'
                   f'<tspan x="{X(c.x):.1f}" dy="{fonte * 1.2:.0f}">{num(a.area)} m²</tspan></text>')
    for al in res.alertas:
        if al.x is not None and al.nivel in ("erro", "atencao"):
            # um pouco acima do ponto, para não cobrir o nome do ambiente
            out.append(f'<circle cx="{X(al.x):.1f}" cy="{Y(al.y) - 2.2 * fonte:.1f}" r="7" fill="none" stroke="#c00000" '
                       f'stroke-width="2.5"><title>{escape(al.mensagem)}</title></circle>')
    out.append("</g>")
    s = res.resumo
    larg_col = (largura_px - 2 * marg) / n_col
    for i, a in enumerate(res.ambientes):
        col, lin = i // linhas_lista, i % linhas_lista
        out.append(f'<text x="{marg + col * larg_col:.0f}" y="{altura_px + 40 + (lin + 1) * linha_leg}" '
                   f'font-size="12" fill="#0b2545">{a.numero}. {escape(a.nome)} — {num(a.area)} m²</text>')
    legenda = (f"Área útil {num(s['area_util'])} m²  |  Ambientes {s['n_ambientes']}  |  "
               f"Terreno {num(s['area_terreno'])} m²  |  Construída {num(s['area_construida'])} m²  |  "
               f"Círculos vermelhos = alertas (passe o mouse)")
    out.append(f'<text x="{marg}" y="{altura_px + 22}" font-size="13" font-weight="bold" fill="#333">'
               f'{escape(legenda)}</text>')
    out.append("</svg>")
    destino.write_text("\n".join(out), encoding="utf-8")
    return destino
