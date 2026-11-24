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

from shapely.geometry import Point, box
from shapely.ops import unary_union
from shapely.strtree import STRtree

from . import config as cfgmod
from .formatos import num
from shapely.geometry import LineString, Polygon

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

    def __init__(self, t, ignorar: list[re.Pattern], camadas_numeros: list[str] = ()):
        self.x, self.y, self.altura, self.camada = t.x, t.y, t.altura, t.camada
        self.area = self.pd = self.numero = None
        self.texto = t.texto
        if camadas_numeros and cfgmod.casa_camada(t.camada, camadas_numeros):
            if re.fullmatch(r"\s*\d{1,4}\s*", t.texto):
                self.numero = int(t.texto)
            self.nome = ""
            self.ponto = Point(self.x, self.y)
            return
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

    @property
    def util(self) -> bool:
        return bool(self.nome) or self.area is not None or self.pd is not None or self.numero is not None

    @property
    def largura(self) -> float:
        return 0.6 * self.altura * max(len(self.texto), 1)


def _juntar_nome(nomes: list[_Rotulo]) -> tuple[str, list[_Rotulo]]:
    """Junta nomes escritos em várias linhas (TEXTs separados, um embaixo do outro).

    Parte do maior texto e agrega os de altura parecida, alinhados e logo acima/abaixo.
    Devolve o nome e os textos que sobraram (não fazem parte do nome)."""
    if not nomes:
        return "", []
    resto = sorted(nomes, key=lambda r: -r.altura)
    grupo = [resto.pop(0)]
    h = grupo[0].altura
    mudou = True
    while mudou:
        mudou = False
        for r in list(resto):
            if abs(r.altura - h) > 0.2 * h:
                continue
            x_ok = any(abs(r.x - g.x) <= max(r.largura, g.largura) / 2 + h for g in grupo)
            y_ok = any(abs(r.y - g.y) <= 1.8 * h for g in grupo)
            if x_ok and y_ok:
                grupo.append(r)
                resto.remove(r)
                mudou = True
    grupo.sort(key=lambda r: (-r.y, r.x))
    return " ".join(r.nome for r in grupo), resto


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


def _tampa_vao(a, b, paredes):
    """Retângulo que fecha o vão entre os batentes a e b na espessura da parede.

    Mede a espessura 1 cm para dentro de cada batente, na perpendicular à linha da esquadria;
    assim o ambiente é cortado no alinhamento da face da parede, não na linha do peitoril."""
    import math
    comp = math.dist(a, b)
    ux, uy = (b[0] - a[0]) / comp, (b[1] - a[1]) / comp
    nx, ny = -uy, ux
    faixas = []
    for p, sinal in ((a, -1), (b, 1)):
        q = (p[0] + sinal * ux * 0.01, p[1] + sinal * uy * 0.01)
        sonda = LineString([(q[0] - nx * 0.6, q[1] - ny * 0.6), (q[0] + nx * 0.6, q[1] + ny * 0.6)])
        corte = sonda.intersection(paredes)
        pedacos = [g for g in getattr(corte, "geoms", [corte]) if g.geom_type == "LineString" and not g.is_empty]
        if not pedacos:
            return None
        pq = Point(q)
        pedaco = min(pedacos, key=lambda g: g.distance(pq))
        if pedaco.distance(pq) > 0.02:
            return None
        ts = [(x - q[0]) * nx + (y - q[1]) * ny for x, y in pedaco.coords]
        faixas.append((min(ts), max(ts)))
    t0, t1 = min(f[0] for f in faixas), max(f[1] for f in faixas)
    if not 0.03 <= t1 - t0 <= 0.6:
        return None
    return Polygon([(a[0] + nx * t0, a[1] + ny * t0), (b[0] + nx * t0, b[1] + ny * t0),
                    (b[0] + nx * t1, b[1] + ny * t1), (a[0] + nx * t1, a[1] + ny * t1)])


def _faces_por_paredes(d: Desenho, cfg: dict) -> list[Poligono]:
    """Ambientes = espaço livre entre as paredes.

    1. barreira = paredes (polígonos e linhas) + linhas de esquadria que vão de uma parede à outra
       (peitoril/caixilho de janela; folha e arco de porta encostam só num lado e ficam de fora);
    2. fecha os vãos de porta: engorda a barreira em d (cantos retos), pega o espaço livre que
       sobrou fechado (o que encosta na borda é o lado de fora) e devolve os d — a sala volta
       exatamente à face das paredes, com o vão da porta cortado no alinhamento da parede.
    """
    fino = 1e-4  # 0,1 mm: espessura dada às linhas, sem efeito prático na área
    pecas = list(d.paredes) + [l.buffer(fino, cap_style=2) for l in d.linhas_paredes if l.length > 0]
    if not pecas:
        return []
    paredes = unary_union(pecas)
    tol, minimo = 0.03, 0.20
    barreiras = [paredes]
    for linha in d.linhas_esquadrias:
        cs = list(linha.coords)
        for a, b in zip(cs, cs[1:]):
            seg_pa, seg_pb = Point(a), Point(b)
            if (seg_pa.distance(seg_pb) >= minimo and paredes.distance(seg_pa) <= tol
                    and paredes.distance(seg_pb) <= tol):
                tampa = _tampa_vao(a, b, paredes)
                barreiras.append(tampa if tampa is not None else LineString([a, b]).buffer(fino, cap_style=2))
    barreira = unary_union(barreiras)
    dd = cfg.get("fechamento_vaos_m", 0.45)
    moldura = box(*barreira.bounds).buffer(1.0, join_style=2)
    livre = moldura.difference(barreira)
    fechado = barreira.buffer(dd, join_style=2, cap_style=3)
    sobra = moldura.difference(fechado)
    faces = []
    for f in getattr(sobra, "geoms", [sobra]):
        if f.is_empty or f.exterior.distance(moldura.exterior) < 1e-6:
            continue  # encosta na borda: é o lado de fora do prédio
        sala = f.buffer(dd, join_style=2).intersection(livre)
        if sala.geom_type != "Polygon":
            partes = [g for g in getattr(sala, "geoms", []) if g.geom_type == "Polygon"]
            if not partes:
                continue
            sala = max(partes, key=lambda g: g.intersection(f).area)
        if sala.area >= cfg.get("area_minima_m2", 0.2):
            faces.append(Poligono(sala, "(paredes)", "paredes"))
    return faces


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
    camadas_numeros = cfg["camadas"].get("numeros") or []
    dist_rotulo = cfg.get("distancia_rotulo_m", 1.0)

    rotulos = [_Rotulo(t, ignorar, camadas_numeros) for t in d.textos
               if not camadas_nomes or cfgmod.casa_camada(t.camada, camadas_nomes)
               or (camadas_numeros and cfgmod.casa_camada(t.camada, camadas_numeros))]
    rotulos = [r for r in rotulos if r.util]

    # ---- separa polígonos por categoria de camada
    por_cat = {"ambientes": [], "terreno": [], "construida": [], "permeavel": []}
    soltos = []
    for p in d.poligonos:
        cat = cfgmod.categoria_da_camada(p.camada, cfg) if d.tem_camadas else None
        (por_cat[cat] if cat else soltos).append(p)
    por_cat = {k: _sem_duplicados(v) for k, v in por_cat.items()}

    modo_pedido = cfg.get("modo", "auto")
    if modo_pedido in ("paredes", "textos"):
        por_cat["ambientes"] = []
    faces_paredes = [] if modo_pedido == "textos" else _faces_por_paredes(d, cfg)
    if modo_pedido == "paredes" and not faces_paredes:
        alertas.append(Alerta("erro", "Modo paredes pedido, mas não achei paredes (padrões: "
                                      + ", ".join(cfg["camadas"].get("paredes", [])) + "). Use --camada-paredes."))
    if por_cat["ambientes"]:
        modo = "camadas"
        candidatos = por_cat["ambientes"]
    elif faces_paredes:
        modo = "paredes"
        candidatos = faces_paredes
        alertas.append(Alerta("info", "Sem camada de ambientes: os ambientes foram montados pelo espaço entre as "
                                      "paredes. Ambientes sem parede de divisa (salas abertas entre si, vãos "
                                      "largos) não são calculados — aparecem nos alertas."))
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
    grupos: dict[int, list[_Rotulo]] = {}
    orfaos = []
    for r in rotulos:
        p = _menor_que_contem(r.ponto, candidatos, arvore) if arvore is not None else None
        if p is None:
            orfaos.append(r)
        else:
            grupos.setdefault(id(p), []).append(r)

    if modo == "textos":
        candidatos = [p for p in candidatos if any(r.nome for r in grupos.get(id(p), []))]

    # ---- rótulo fora do ambiente (ambiente pequeno, texto ao lado): vai para o ambiente
    #      sem aquela informação mais próximo, até distancia_rotulo_m
    adotou: dict[int, float] = {}
    sem_lugar = []
    if modo in ("camadas", "paredes") and candidatos:
        def falta(p, r):
            g = grupos.get(id(p), [])
            if r.nome:
                return id(p) in adotou or not any(x.nome for x in g)
            if r.area is not None:
                return not any(x.area is not None for x in g)
            if r.numero is not None:
                return not any(x.numero is not None for x in g)
            return not any(x.pd is not None for x in g)

        for r in sorted(orfaos, key=lambda r: (not r.nome,)):  # nomes primeiro
            perto = [(p.geom.distance(r.ponto), p) for p in candidatos]
            perto = [(dd, p) for dd, p in perto if dd <= dist_rotulo and falta(p, r)]
            if not perto:
                if r.nome and camadas_nomes:
                    sem_lugar.append(r)
                continue
            # prefere o ambiente que já adotou um texto vizinho (o resto do mesmo rótulo)
            perto.sort(key=lambda t: (id(t[1]) not in adotou, t[0]))
            dd, p = perto[0]
            grupos.setdefault(id(p), []).append(r)
            if r.nome and id(p) not in adotou:
                adotou[id(p)] = dd
    else:
        sem_lugar = [r for r in orfaos if r.nome and camadas_nomes]

    if modo == "paredes":
        candidatos = [p for p in candidatos if any(r.nome for r in grupos.get(id(p), []))]

    ambientes: list[Area] = []
    for p in candidatos:
        g = grupos.get(id(p), [])
        nome, sobra = _juntar_nome([r for r in g if r.nome])
        c = p.geom.representative_point()
        outros = [r.nome for r in sobra if r.nome != nome]
        if outros and modo == "paredes":
            # mais de um ambiente no mesmo espaço: falta parede de divisa. Não calcula para não somar errado.
            todos = [nome] + list(dict.fromkeys(outros))
            alertas.append(Alerta("atencao", f"Sem parede entre {', '.join(todos[:5])}"
                                             f"{'…' if len(todos) > 5 else ''} (espaço único de "
                                             f"{num(p.geom.area)} m²): não calculados. Desenhe a divisa numa "
                                             f"camada de ambientes ou use a hachura/polilinha de área.", c.x, c.y))
            continue
        if outros and modo == "camadas":
            alertas.append(Alerta("info", f"Ambiente {nome}: outros textos dentro dele foram ignorados como nome "
                                          f"({', '.join(outros[:4])}{'…' if len(outros) > 4 else ''}).", c.x, c.y))
        if id(p) in adotou:
            alertas.append(Alerta("atencao", f"Ambiente {nome} ({num(p.geom.area)} m²): o nome está escrito FORA "
                                             f"dele (a {num(adotou[id(p)])} m); associado pela proximidade. Confira.",
                                  c.x, c.y))
        area_decl = next((r.area for r in g if r.area is not None), None)
        pd = next((r.pd for r in g if r.pd is not None), pd_padrao)
        a_ = Area("ambientes", nome, p.camada, p.geom, pd, area_decl, p.origem)
        nums = sorted({r.numero for r in g if r.numero is not None})
        a_.numero = nums[0] if len(nums) == 1 else 0
        ambientes.append(a_)

    # numeração: a do desenho, se completa e sem repetição; senão, ordem de leitura
    nums = [a.numero for a in ambientes]
    usar_desenho = bool(camadas_numeros) and ambientes and all(nums) and len(set(nums)) == len(nums)
    if usar_desenho:
        ambientes.sort(key=lambda a: a.numero)
    else:
        if camadas_numeros and any(nums):
            alertas.append(Alerta("atencao", f"Numeração dos ambientes no desenho incompleta ou repetida "
                                             f"({sum(1 for n in nums if n)} de {len(nums)} com número); "
                                             f"usei a ordem de leitura."))
        ambientes.sort(key=_ordem_leitura)
        for i, a in enumerate(ambientes, 1):
            a.numero = i
    for a in ambientes:
        if not a.nome:
            a.nome = f"AMBIENTE {a.numero} (SEM NOME)"
            c = a.geom.representative_point()
            alertas.append(Alerta("atencao", f"Ambiente nº {a.numero} ({num(a.area)} m²) sem texto de nome dentro.",
                                  c.x, c.y))

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

    if modo == "paredes":
        # junta as linhas de cada nome e explica: o espaço não fecha (vão largo ou aberto para fora)
        resto = list(sem_lugar)
        vao = 2 * cfg.get("fechamento_vaos_m", 0.45)
        while resto:
            nome, sobra = _juntar_nome(resto)
            usados = [r for r in resto if r not in sobra]
            r0 = usados[0]
            alertas.append(Alerta("atencao", f"{nome}: não calculado — o espaço não fecha só com paredes (comunica "
                                             f"com o lado de fora ou com outro ambiente por vão maior que "
                                             f"{num(vao)} m, ou não há parede de divisa).", r0.x, r0.y))
            resto = sobra
    else:
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

    if modo == "camadas" and faces_paredes:
        tol_p = cfg.get("diferenca_paredes_m2", 0.02)
        arv_f = STRtree([f.geom for f in faces_paredes])
        for a in ambientes:
            for j in arv_f.query(a.geom):
                f = faces_paredes[int(j)].geom
                inter = a.geom.intersection(f).area
                if inter >= 0.9 * max(a.area, f.area):        # é o mesmo ambiente
                    if abs(f.area - a.area) > tol_p:
                        c = a.geom.representative_point()
                        alertas.append(Alerta("atencao", f"{a.nome}: a área desenhada ({num(a.area)} m²) não encosta "
                                                         f"nas paredes — pelas faces das paredes dá {num(f.area)} m² "
                                                         f"(diferença {num(f.area - a.area)} m²).", c.x, c.y))
                    break

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
