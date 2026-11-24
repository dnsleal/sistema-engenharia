"""Leitura de DXF (e DWG, convertido antes para DXF pelo ODA File Converter).

O que é lido do espaço do modelo (model space):
- polilinhas (LWPOLYLINE/POLYLINE), com arcos (bulge) — fechadas viram polígonos;
- círculos, elipses e splines fechadas;
- hachuras (o contorno externo vira polígono);
- LINEs e polilinhas abertas nas camadas de área: o programa tenta fechar
  ambientes desenhados com linhas soltas;
- TEXT, MTEXT e atributos de blocos (nomes dos ambientes, áreas escritas, PD);
- blocos inseridos (INSERT), contados por nome — portas, janelas, pontos etc.
  O conteúdo dos blocos também é lido (até 3 níveis), caso o ambiente esteja dentro de um bloco.
"""
from __future__ import annotations

import math
import os
import shutil
from collections import Counter, defaultdict
from pathlib import Path

import ezdxf
from ezdxf import recover
from ezdxf import path as ezpath
from ezdxf import bbox as ezbbox
from shapely.geometry import LineString, Polygon
from shapely.ops import polygonize, unary_union

from . import config as cfgmod
from .modelo import Alerta, Desenho, Poligono, Texto

# $INSUNITS -> (nome, metros por unidade)
UNIDADES = {1: ("polegada", 0.0254), 2: ("pé", 0.3048), 4: ("mm", 0.001),
            5: ("cm", 0.01), 6: ("m", 1.0), 14: ("dm", 0.1)}
UNIDADE_NOME = {"m": 1.0, "cm": 0.01, "mm": 0.001, "dm": 0.1}


class ErroLeitura(Exception):
    pass


# ---------------------------------------------------------------- DWG
def abrir_dwg(caminho: str | Path):
    """Converte DWG -> DXF com o ODA File Converter (gratuito) e abre."""
    from ezdxf.addons import odafc
    exe = os.environ.get("ODA_CONVERTER")
    if exe:
        ezdxf.options.set("odafc-addon", "win_exec_path", exe)
        ezdxf.options.set("odafc-addon", "unix_exec_path", exe)
    if not odafc.is_installed():
        if shutil.which("dwg2dxf"):
            raise ErroLeitura(
                "Para DWG, converta antes para DXF: dwg2dxf arquivo.dwg  (LibreDWG) "
                "e rode o programa no .dxf gerado.")
        raise ErroLeitura(
            "Arquivo DWG: instale o ODA File Converter (gratuito, opendesign.com/guestfiles/oda_file_converter) "
            "ou informe o caminho do executável na variável ODA_CONVERTER. "
            "Alternativa: no AutoCAD/LibreCAD, 'Salvar como' DXF e use o .dxf.")
    return odafc.readfile(str(caminho))


# ---------------------------------------------------------------- texto
def _centro_texto(e) -> tuple[float, float]:
    """Centro do retângulo do texto (considera alinhamento, rotação e MTEXT de várias linhas)."""
    try:
        bb = ezbbox.extents([e], fast=True)
        if bb.has_data:
            c = bb.center
            return (c.x, c.y)
    except Exception:  # noqa: BLE001
        pass
    p = e.dxf.insert
    return (p.x, p.y)


# ---------------------------------------------------------------- leitura bruta
class _Bruto:
    def __init__(self):
        self.fechados = []   # (pontos, camada, origem, ref)
        self.abertos = []    # (pontos, camada, ref)
        self.textos = []     # (texto, x, y, altura, camada)
        self.blocos = Counter()
        self.camadas = defaultdict(lambda: {"fechados": 0, "abertos": 0, "textos": 0, "blocos": 0})


def _pontos_de_path(p, fechar: bool):
    bb = p.control_vertices()
    if len(bb) < 2:
        return []
    xs = [v.x for v in bb]
    ys = [v.y for v in bb]
    diag = math.hypot(max(xs) - min(xs), max(ys) - min(ys)) or 1.0
    pts = [(v.x, v.y) for v in p.flattening(distance=diag * 2e-5, segments=8)]
    if fechar and pts and pts[0] != pts[-1]:
        pts.append(pts[0])
    return pts


PASSO_ARCO = math.radians(0.25)  # pontos a cada 0,25° nos arcos: erro de área < 0,0002 %


def _pontos_arco(p1, p2, bulge):
    """Pontos sobre o arco VERDADEIRO entre p1 e p2 (sem p1, com p2)."""
    teta = 4 * math.atan(bulge)                      # ângulo central, com sinal (+ = anti-horário)
    corda = math.dist(p1, p2)
    if corda == 0:
        return [p2]
    r = corda / (2 * math.sin(abs(teta) / 2))
    mx, my = (p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2
    d = r * math.cos(teta / 2)                       # distância do centro à corda
    ux, uy = (p2[0] - p1[0]) / corda, (p2[1] - p1[1]) / corda
    cx, cy = mx - uy * d, my + ux * d                # centro à esquerda da corda quando bulge > 0
    a0 = math.atan2(p1[1] - cy, p1[0] - cx)
    n = max(2, math.ceil(abs(teta) / PASSO_ARCO))
    pts = [(cx + r * math.cos(a0 + teta * i / n), cy + r * math.sin(a0 + teta * i / n)) for i in range(1, n)]
    return pts + [p2]


def _pontos_polilinha(e) -> tuple[list, bool]:
    """Vértices de LWPOLYLINE/POLYLINE 2D com arcos (bulge) exatos, em coordenadas do mundo (WCS)."""
    if e.dxftype() == "LWPOLYLINE":
        brutos = [(x, y, b) for x, y, b in e.get_points("xyb")]
        fechada = e.closed
    else:
        brutos = [(v.dxf.location.x, v.dxf.location.y, v.dxf.get("bulge", 0)) for v in e.vertices]
        fechada = e.is_closed
    if len(brutos) < 2:
        return [], fechada
    pts = [brutos[0][:2]]
    pares = list(zip(brutos, brutos[1:] + ([brutos[0]] if fechada else [])))
    for (x1, y1, b), (x2, y2, _) in pares:
        if abs(b) > 1e-12:
            pts.extend(_pontos_arco((x1, y1), (x2, y2), b))
        else:
            pts.append((x2, y2))
    ocs = e.ocs()
    if ocs.transform:  # polilinha espelhada / em outro plano
        pts = [(v.x, v.y) for v in ocs.points_to_wcs([(x, y, e.dxf.get("elevation", 0) if e.dxftype() == "LWPOLYLINE" else 0) for x, y in pts])]
    if fechada and pts[0] != pts[-1]:
        pts.append(pts[0])
    return pts, fechada


def _pontos_curva(e, fechar: bool):
    """CIRCLE/ARC/ELLIPSE/SPLINE: pontos sobre a curva verdadeira (não Bézier)."""
    t = e.dxftype()
    if t in ("CIRCLE", "ARC"):
        r = e.dxf.radius
        pts = [(v.x, v.y) for v in e.flattening(sagitta=max(r * 1e-6, 1e-9))]
    else:
        ext = list(e.flattening(1.0)) if t == "SPLINE" else None
        tam = 1.0
        if ext:
            xs, ys = [v.x for v in ext], [v.y for v in ext]
            tam = math.hypot(max(xs) - min(xs), max(ys) - min(ys)) or 1.0
        elif t == "ELLIPSE":
            tam = e.dxf.major_axis.magnitude
        pts = [(v.x, v.y) for v in e.flattening(distance=tam * 1e-6)]
    if fechar and pts and pts[0] != pts[-1]:
        pts.append(pts[0])
    return pts


def _camada_efetiva(e, camada_pai: str | None) -> str:
    c = e.dxf.get("layer", "0")
    if c == "0" and camada_pai:
        return camada_pai  # entidade na camada 0 dentro de bloco herda a camada do INSERT
    return c


def _ler_entidade(e, b: _Bruto, camadas_area: list[str], nivel: int, camada_pai: str | None):
    t = e.dxftype()
    camada = _camada_efetiva(e, camada_pai)
    ref = e.dxf.get("handle", "") or ""
    try:
        if t in ("LWPOLYLINE", "POLYLINE"):
            if t == "POLYLINE" and (e.is_3d_polyline is False and e.is_2d_polyline is False):
                return  # malhas 3D
            pts, fechada = _pontos_polilinha(e)
            if len(pts) < 2:
                return
            if fechada or (len(pts) > 3 and pts[0] == pts[-1]):
                b.fechados.append((pts, camada, "polilinha", ref))
                b.camadas[camada]["fechados"] += 1
            else:
                b.abertos.append((pts, camada, ref))
                b.camadas[camada]["abertos"] += 1
        elif t in ("CIRCLE", "ELLIPSE", "SPLINE"):
            fechada = t == "CIRCLE" or (t == "SPLINE" and e.closed) or (
                t == "ELLIPSE" and abs(abs(e.dxf.end_param - e.dxf.start_param) - 2 * math.pi) < 1e-9)
            pts = _pontos_curva(e, fechada)
            if t == "SPLINE" and not fechada and len(pts) > 3 and math.dist(pts[0], pts[-1]) < 1e-9:
                fechada = True
            if fechada and len(pts) > 3:
                b.fechados.append((pts, camada, "circulo" if t == "CIRCLE" else "curva", ref))
                b.camadas[camada]["fechados"] += 1
            elif len(pts) >= 2:
                b.abertos.append((pts, camada, ref))
                b.camadas[camada]["abertos"] += 1
        elif t == "ARC":
            if cfgmod.casa_camada(camada, camadas_area):
                pts = _pontos_curva(e, False)
                b.abertos.append((pts, camada, ref))
                b.camadas[camada]["abertos"] += 1
        elif t == "LINE":
            if cfgmod.casa_camada(camada, camadas_area):
                s, f = e.dxf.start, e.dxf.end
                b.abertos.append(([(s.x, s.y), (f.x, f.y)], camada, ref))
                b.camadas[camada]["abertos"] += 1
        elif t == "HATCH":
            # só o maior contorno de cada hachura; furos viram interiores
            caminhos = list(ezpath.from_hatch(e))
            aneis = [pp for pp in (_pontos_de_path(c, True) for c in caminhos) if len(pp) > 3]
            if aneis:
                aneis.sort(key=lambda r: abs(Polygon(r).area), reverse=True)
                b.fechados.append((aneis[0], camada, "hachura", ref, aneis[1:]))
                b.camadas[camada]["fechados"] += 1
        elif t == "TEXT":
            txt = e.plain_text().strip()
            if txt:
                x, y = _centro_texto(e)
                b.textos.append((txt, x, y, e.dxf.get("height", 1.0), camada))
                b.camadas[camada]["textos"] += 1
        elif t == "MTEXT":
            txt = e.plain_text().strip()
            if txt:
                x, y = _centro_texto(e)
                b.textos.append((txt, x, y, e.dxf.get("char_height", 1.0), camada))
                b.camadas[camada]["textos"] += 1
        elif t == "INSERT":
            nome = e.dxf.name
            if not nome.startswith("*"):  # *D cotas, *U anônimos
                b.blocos[(nome, camada)] += 1
                b.camadas[camada]["blocos"] += 1
            for a in e.attribs:
                txt = a.plain_text().strip() if hasattr(a, "plain_text") else (a.dxf.text or "").strip()
                if txt and not a.is_invisible:
                    x, y = _centro_texto(a)
                    b.textos.append((txt, x, y, a.dxf.get("height", 1.0), _camada_efetiva(a, camada)))
            if nivel < 3:
                try:
                    for v in e.virtual_entities():
                        _ler_entidade(v, b, camadas_area, nivel + 1, camada)
                except Exception:  # noqa: BLE001  blocos com escala não uniforme etc.
                    pass
    except Exception as exc:  # noqa: BLE001
        b.camadas[camada].setdefault("falhas", 0)
        b.camadas[camada]["falhas"] += 1
        b.camadas[camada]["ultima_falha"] = f"{t} {ref}: {exc}"


# ---------------------------------------------------------------- unidades
def _adivinhar_fator(areas_brutas: list[float]) -> tuple[float, str]:
    """Sem $INSUNITS: escolhe m/cm/mm que deixa a área típica entre 2 e 300 m²."""
    if not areas_brutas:
        return 1.0, "m (sem unidade no arquivo, assumido)"
    areas_brutas = sorted(areas_brutas)
    mediana = areas_brutas[len(areas_brutas) // 2]
    for nome, f in (("m", 1.0), ("cm", 0.01), ("mm", 0.001)):
        if 2 <= mediana * f * f <= 300:
            return f, f"{nome} (sem unidade no arquivo, deduzida pelo tamanho dos ambientes)"
    return 1.0, "m (sem unidade no arquivo, assumido)"


# ---------------------------------------------------------------- principal
def ler(caminho: str | Path, cfg: dict, unidade: str | None = None) -> Desenho:
    caminho = Path(caminho)
    formato = caminho.suffix.lower().lstrip(".")
    try:
        if formato == "dwg":
            doc = abrir_dwg(caminho)
        else:
            doc, auditor = recover.readfile(str(caminho))
    except ErroLeitura:
        raise
    except Exception as exc:  # noqa: BLE001
        raise ErroLeitura(f"Não consegui abrir {caminho.name}: {exc}") from exc

    camadas_area = cfgmod.camadas_de_area(cfg)
    camadas_leitura = camadas_area + cfg["camadas"].get("paredes", []) + cfg["camadas"].get("esquadrias", [])
    b = _Bruto()
    for e in doc.modelspace():
        _ler_entidade(e, b, camadas_leitura, 0, None)

    alertas: list[Alerta] = []

    # ---- unidade
    insunits = doc.header.get("$INSUNITS", 0)
    if unidade:
        fator, desc = UNIDADE_NOME[unidade], f"{unidade} (informada)"
    elif insunits in UNIDADES:
        nome, fator = UNIDADES[insunits]
        desc = f"{nome} ($INSUNITS={insunits})"
    else:
        amostra = [abs(Polygon(f[0]).area) for f in b.fechados
                   if cfgmod.casa_camada(f[1], cfg["camadas"]["ambientes"]) and len(f[0]) > 3]
        if not amostra:
            amostra = [abs(Polygon(f[0]).area) for f in b.fechados if len(f[0]) > 3]
        fator, desc = _adivinhar_fator(amostra)
        alertas.append(Alerta("atencao", f"O arquivo não informa a unidade do desenho. Usei {desc}. "
                                         f"Se estiver errado, rode de novo com --unidade m|cm|mm."))

    def escalar(pts):
        return [(x * fator, y * fator) for x, y in pts]

    # ---- polígonos fechados
    poligonos: list[Poligono] = []
    for item in b.fechados:
        pts, camada, origem, ref = item[:4]
        furos = item[4] if len(item) > 4 else []
        if len(pts) < 4:
            continue
        g = Polygon(escalar(pts), [escalar(f) for f in furos])
        if not g.is_valid:
            g2 = g.buffer(0)
            if g2.geom_type == "MultiPolygon":
                g2 = max(g2.geoms, key=lambda q: q.area)
            if cfgmod.casa_camada(camada, camadas_area):
                c = g.representative_point()
                alertas.append(Alerta("atencao", f"Polígono com laço/autointerseção na camada {camada} "
                                                 f"(handle {ref}); corrigido automaticamente — confira.", c.x, c.y))
            g = g2
        if g.is_empty or g.area <= 0:
            continue
        poligonos.append(Poligono(g, camada, origem, ref))

    # ---- polilinhas quase fechadas e linhas soltas nas camadas de área
    tol = cfg["tolerancia_fechamento_m"]
    por_camada = defaultdict(list)
    linhas_paredes, linhas_esq = [], []
    for pts, camada, ref in b.abertos:
        if cfgmod.camada_parede(camada, cfg):
            linhas_paredes.append(LineString(escalar(pts)))
        elif cfgmod.camada_esquadria(camada, cfg):
            linhas_esq.append(LineString(escalar(pts)))
        if not cfgmod.casa_camada(camada, camadas_area):
            continue
        pts = escalar(pts)
        if len(pts) >= 3 and math.dist(pts[0], pts[-1]) <= tol:
            g = Polygon(pts + [pts[0]])
            if g.is_valid and g.area > 0:
                poligonos.append(Poligono(g, camada, "polilinha", ref))
                alertas.append(Alerta("atencao", f"Polilinha aberta (handle {ref}, camada {camada}) com "
                                                 f"folga de {math.dist(pts[0], pts[-1]) * 100:.1f} cm; fechei "
                                                 f"automaticamente. Feche no CAD.", pts[0][0], pts[0][1]))
                continue
        por_camada[camada].append((LineString(pts), ref))

    for camada, itens in por_camada.items():
        # junta pontas próximas arredondando à tolerância e monta faces fechadas
        rede = unary_union([ls for ls, _ in itens])
        faces = [f for f in polygonize(rede) if f.area > cfg["area_minima_m2"]]
        sobra = len(itens)
        for f in faces:
            poligonos.append(Poligono(f, camada, "linhas", ""))
        if faces:
            c = faces[0].representative_point()
            alertas.append(Alerta("atencao", f"Camada {camada}: {len(faces)} área(s) montada(s) a partir de "
                                             f"linhas soltas/abertas. Prefira polilinha fechada.", c.x, c.y))
        else:
            alertas.append(Alerta("atencao", f"Camada {camada}: {sobra} linha(s)/polilinha(s) aberta(s) "
                                             f"que não fecham nenhuma área — foram ignoradas."))

    textos = [Texto(t, x * fator, y * fator, h * fator, c) for t, x, y, h, c in b.textos]
    paredes = [p.geom for p in poligonos if cfgmod.camada_parede(p.camada, cfg)]
    for p in poligonos:  # contorno de esquadrias fechadas (caixilhos) também pode fechar vão
        if cfgmod.camada_esquadria(p.camada, cfg):
            linhas_esq.append(LineString(p.geom.exterior.coords))

    for camada, info in b.camadas.items():
        if info.get("falhas"):
            alertas.append(Alerta("info", f"Camada {camada}: {info['falhas']} entidade(s) não lida(s) "
                                          f"(ex.: {info['ultima_falha']})."))

    return Desenho(arquivo=str(caminho), formato=formato, unidade=desc, fator_m=fator,
                   poligonos=poligonos, textos=textos, blocos=b.blocos,
                   camadas={k: dict(v) for k, v in sorted(b.camadas.items())}, alertas=alertas,
                   paredes=paredes, linhas_paredes=linhas_paredes, linhas_esquadrias=linhas_esq)
