"""Interpretação do desenho: quais polígonos são ambientes, qual o nome de cada um,
quadro de áreas e conferências (alertas).

Dois modos:
- 'camadas': os ambientes são os polígonos fechados nas camadas de ambientes
  (config: camadas.ambientes). É o modo recomendado.
- 'textos': quando não há nenhuma camada de ambientes (ou PDF sem camadas), cada
  nome de ambiente escrito no desenho marca a menor área fechada que o contém.
"""
from __future__ import annotations

import re

from shapely.geometry import Point
from shapely.strtree import STRtree

from . import config as cfgmod
from .formatos import num
from .modelo import Alerta, Area, Desenho, Poligono, Resultado

RE_AREA = re.compile(r"(?:A\s*[=:]\s*)?(\d{1,6}(?:[.,]\d{1,3})?)\s*m(?:²|2)\b", re.I)
RE_PD = re.compile(r"\b(?:PD|P\.D\.|PE[- ]DIREITO|H)\s*[=:]?\s*(\d+(?:[.,]\d{1,3})?)\s*m?\b", re.I)

NOMES_CATEGORIA = {"terreno": "Terreno", "construida": "Área construída", "permeavel": "Área permeável"}


def _num(s: str) -> float:
    s = s.strip()
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    return float(s)


class _Rotulo:
    """Um texto do desenho já separado em nome / área escrita / pé-direito."""

    def __init__(self, t, ignorar: list[re.Pattern]):
        self.x, self.y, self.altura, self.camada = t.x, t.y, t.altura, t.camada
        self.area = self.pd = None
        nomes = []
        for linha in re.split(r"[\n\r]+|\\P", t.texto):
            linha = " ".join(linha.split())
            if not linha:
                continue
            ma, mp = RE_AREA.search(linha), RE_PD.search(linha)
            if ma and self.area is None:
                self.area = _num(ma.group(1))
            if mp and self.pd is None:
                v = _num(mp.group(1))
                if 1.5 <= v <= 15:
                    self.pd = v
            if ma or mp or any(r.search(linha) for r in ignorar):
                continue
            nomes.append(linha)
        self.nome = " ".join(nomes).upper()
        self.ponto = Point(self.x, self.y)


def _sem_duplicados(polys: list[Poligono]) -> list[Poligono]:
    """Remove polígonos repetidos (ex.: polilinha + hachura com o mesmo contorno)."""
    polys = sorted(polys, key=lambda p: {"polilinha": 0, "circulo": 1, "curva": 1}.get(p.origem, 2))
    fica: list[Poligono] = []
    for p in polys:
        dup = False
        for q in fica:
            a, b = p.geom.area, q.geom.area
            if abs(a - b) <= 0.005 * max(a, b) and p.geom.intersection(q.geom).area >= 0.995 * max(a, b):
                dup = True
                break
        if not dup:
            fica.append(p)
    return fica


def _menor_que_contem(pt: Point, polys: list[Poligono], arvore: STRtree):
    melhor = None
    for i in arvore.query(pt):
        p = polys[int(i)]
        if p.geom.covers(pt) and (melhor is None or p.geom.area < melhor.geom.area):
            melhor = p
    return melhor


def _ordem_leitura(a: Area):
    c = a.geom.centroid
    return (-round(c.y), c.x)  # de cima para baixo, faixas de 1 m; depois da esquerda para a direita


def analisar(d: Desenho, cfg: dict, pe_direito: float | None = None) -> Resultado:
    alertas = list(d.alertas)
    pd_padrao = pe_direito if pe_direito is not None else cfg.get("pe_direito_padrao")
    ignorar = [re.compile(r, re.I) for r in cfg.get("ignorar_textos", [])]
    camadas_nomes = cfg["camadas"].get("nomes") or []

    rotulos = [_Rotulo(t, ignorar) for t in d.textos
               if not camadas_nomes or cfgmod.casa_camada(t.camada, camadas_nomes)]

    # ---- separa polígonos por categoria de camada
    por_cat = {"ambientes": [], "terreno": [], "construida": [], "permeavel": []}
    soltos = []
    for p in d.poligonos:
        cat = cfgmod.categoria_da_camada(p.camada, cfg) if d.tem_camadas else None
        (por_cat[cat] if cat else soltos).append(p)
    por_cat = {k: _sem_duplicados(v) for k, v in por_cat.items()}

    if por_cat["ambientes"]:
        modo = "camadas"
        candidatos = por_cat["ambientes"]
    else:
        modo = "textos"
        candidatos = _sem_duplicados(soltos)
        if d.tem_camadas and d.formato != "pdf":
            alertas.append(Alerta("atencao", "Nenhuma camada de ambientes encontrada (padrões: "
                                             + ", ".join(cfg["camadas"]["ambientes"]) + "). Os ambientes foram "
                                             "achados pelos textos. Para resultado confiável, ponha as polilinhas "
                                             "dos ambientes numa camada própria ou use --camada-ambientes. "
                                             "Rode o comando 'camadas' para ver as camadas do arquivo."))

    arvore = STRtree([p.geom for p in candidatos]) if candidatos else None

    # ---- associa cada texto ao menor polígono que o contém
    nomes_de: dict[int, list[_Rotulo]] = {}
    info_de: dict[int, list[_Rotulo]] = {}
    sem_lugar = []
    for r in rotulos:
        p = _menor_que_contem(r.ponto, candidatos, arvore) if arvore is not None else None
        if p is None:
            if r.nome and camadas_nomes:
                sem_lugar.append(r)
            continue
        if r.nome:
            nomes_de.setdefault(id(p), []).append(r)
        if r.area is not None or r.pd is not None:
            info_de.setdefault(id(p), []).append(r)

    if modo == "textos":
        candidatos = [p for p in candidatos if id(p) in nomes_de]

    ambientes: list[Area] = []
    for p in candidatos:
        nomes = sorted(nomes_de.get(id(p), []), key=lambda r: -r.altura)
        c = p.geom.representative_point()
        if nomes:
            nome = nomes[0].nome
            outros = [r.nome for r in nomes[1:] if r.nome != nome]
            if outros and modo == "camadas":
                alertas.append(Alerta("info", f"Ambiente {nome}: outros textos dentro dele foram ignorados como nome "
                                              f"({', '.join(outros[:4])}{'…' if len(outros) > 4 else ''}).", c.x, c.y))
        else:
            nome = ""
        infos = info_de.get(id(p), [])
        area_decl = next((r.area for r in infos if r.area is not None), None)
        pd = next((r.pd for r in infos if r.pd is not None), pd_padrao)
        ambientes.append(Area("ambientes", nome, p.camada, p.geom, pd, area_decl, p.origem))

    ambientes.sort(key=_ordem_leitura)
    sem_nome = 0
    for i, a in enumerate(ambientes, 1):
        a.numero = i
        if not a.nome:
            sem_nome += 1
            a.nome = f"AMBIENTE {i} (SEM NOME)"
            c = a.geom.representative_point()
            alertas.append(Alerta("atencao", f"Ambiente nº {i} ({num(a.area)} m²) sem texto de nome dentro.", c.x, c.y))

    # nomes repetidos: numera (QUARTO 1, QUARTO 2) só na saída, mantendo o aviso
    vistos: dict[str, int] = {}
    for a in ambientes:
        vistos[a.nome] = vistos.get(a.nome, 0) + 1
    for nome, n in vistos.items():
        if n > 1:
            k = 0
            for a in ambientes:
                if a.nome == nome:
                    k += 1
                    a.nome = f"{nome} ({k})"
            alertas.append(Alerta("info", f"Nome '{nome}' aparece em {n} ambientes; numerados (1)…({n})."))

    for r in sem_lugar:
        alertas.append(Alerta("atencao", f"Texto '{r.nome}' não está dentro de nenhum ambiente.", r.x, r.y))

    # ---- conferências
    tol = cfg.get("diferenca_declarada_m2", 0.05)
    for a in ambientes:
        if a.area_declarada is not None and abs(a.area_declarada - a.area) > tol:
            c = a.geom.representative_point()
            alertas.append(Alerta("atencao", f"{a.nome}: área escrita no desenho {num(a.area_declarada)} m², "
                                             f"calculada {num(a.area)} m² (diferença {num(a.area - a.area_declarada)} m²).",
                                  c.x, c.y))
        if a.area < 1.0:
            c = a.geom.representative_point()
            alertas.append(Alerta("info", f"{a.nome}: área muito pequena ({num(a.area)} m²). É mesmo um ambiente?",
                                  c.x, c.y))

    if len(ambientes) > 1:
        arv = STRtree([a.geom for a in ambientes])
        for i, a in enumerate(ambientes):
            for j in arv.query(a.geom):
                j = int(j)
                if j <= i:
                    continue
                inter = a.geom.intersection(ambientes[j].geom).area
                if inter > 0.01:
                    c = a.geom.intersection(ambientes[j].geom).representative_point()
                    alertas.append(Alerta("erro", f"{a.nome} e {ambientes[j].nome} se sobrepõem em {num(inter)} m² — "
                                                  f"a área útil total fica contada em dobro.", c.x, c.y))

    # ---- terreno, construída, permeável
    outras: dict[str, list[Area]] = {}
    for cat in ("terreno", "construida", "permeavel"):
        lista = []
        polys = por_cat[cat]
        for k, p in enumerate(sorted(polys, key=lambda p: -p.geom.area), 1):
            nome = NOMES_CATEGORIA[cat] + (f" {k}" if len(polys) > 1 else "")
            lista.append(Area(cat, nome, p.camada, p.geom, None, None, p.origem, k))
        outras[cat] = lista
        if len(lista) > 1 and cat == "terreno":
            alertas.append(Alerta("atencao", f"Há {len(lista)} polígonos de terreno; a área do terreno é a soma deles."))

    if outras["construida"]:
        uniao = outras["construida"][0].geom
        for a in outras["construida"][1:]:
            uniao = uniao.union(a.geom)
        for a in ambientes:
            fora = a.geom.difference(uniao).area
            if fora > 0.05:
                c = a.geom.representative_point()
                alertas.append(Alerta("info", f"{a.nome}: {num(fora)} m² fora da projeção da área construída "
                                              f"(varanda descoberta? confira).", c.x, c.y))

    # ---- resumo
    soma = lambda lst: sum(a.area for a in lst)  # noqa: E731
    area_util = soma(ambientes)
    area_terreno = soma(outras["terreno"]) or None
    if outras["construida"]:
        area_constr, fonte_constr = soma(outras["construida"]), "camada de área construída"
    else:
        area_constr, fonte_constr = None, None
        if ambientes:
            alertas.append(Alerta("info", "Sem polígono de área construída: a área construída não foi calculada "
                                          "(a soma dos ambientes é a área ÚTIL, sem paredes)."))
    area_perm = soma(outras["permeavel"]) if outras["permeavel"] else None
    resumo = {
        "area_terreno": area_terreno,
        "area_construida": area_constr,
        "fonte_area_construida": fonte_constr,
        "area_util": area_util,
        "area_permeavel": area_perm,
        "taxa_ocupacao": (area_constr / area_terreno) if (area_constr and area_terreno) else None,
        "taxa_permeabilidade": (area_perm / area_terreno) if (area_perm is not None and area_terreno) else None,
        "n_ambientes": len(ambientes),
        "perimetro_total": sum(a.perimetro for a in ambientes),
        "area_paredes_total": sum(a.area_parede or 0 for a in ambientes) if ambientes else None,
        "pe_direito_padrao": pd_padrao,
    }
    if not ambientes:
        alertas.append(Alerta("erro", "Nenhum ambiente encontrado. Rode o comando 'camadas' para ver o que o "
                                      "arquivo tem e ajuste os nomes de camada (--camada-ambientes)."))

    return Resultado(d, ambientes, outras, resumo, alertas, modo)
