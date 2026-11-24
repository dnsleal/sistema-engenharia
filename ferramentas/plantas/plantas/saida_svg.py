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
    minx = min(g.bounds[0] for g in geoms)
    miny = min(g.bounds[1] for g in geoms)
    maxx = max(g.bounds[2] for g in geoms)
    maxy = max(g.bounds[3] for g in geoms)
    w, h = (maxx - minx) or 1, (maxy - miny) or 1
    marg = 30
    esc = (largura_px - 2 * marg) / w
    altura_px = int(h * esc + 2 * marg)

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

    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {largura_px} {altura_px + 40}" '
           f'width="{largura_px}" height="{altura_px + 40}" font-family="Arial, sans-serif">',
           '<rect width="100%" height="100%" fill="#ffffff"/>']
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
        out.append(f'<text x="{X(c.x):.1f}" y="{Y(c.y):.1f}" font-size="{fonte:.0f}" text-anchor="middle" '
                   f'fill="#0b2545"><tspan font-weight="bold">{a.numero}. {escape(a.nome)}</tspan>'
                   f'<tspan x="{X(c.x):.1f}" dy="{fonte * 1.2:.0f}">{num(a.area)} m²</tspan></text>')
    for al in res.alertas:
        if al.x is not None and al.nivel in ("erro", "atencao"):
            # um pouco acima do ponto, para não cobrir o nome do ambiente
            out.append(f'<circle cx="{X(al.x):.1f}" cy="{Y(al.y) - 2.2 * fonte:.1f}" r="7" fill="none" stroke="#c00000" '
                       f'stroke-width="2.5"><title>{escape(al.mensagem)}</title></circle>')
    s = res.resumo
    legenda = (f"Área útil {num(s['area_util'])} m²  |  Ambientes {s['n_ambientes']}  |  "
               f"Terreno {num(s['area_terreno'])} m²  |  Construída {num(s['area_construida'])} m²  |  "
               f"Círculos vermelhos = alertas (passe o mouse)")
    out.append(f'<text x="{marg}" y="{altura_px + 25}" font-size="13" fill="#333">{escape(legenda)}</text>')
    out.append("</svg>")
    destino.write_text("\n".join(out), encoding="utf-8")
    return destino
