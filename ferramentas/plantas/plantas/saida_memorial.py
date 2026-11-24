"""Memorial (.docx).

Dois jeitos:
1. Sem modelo: gera um memorial padrão (identificação, quadro de áreas, ambientes,
   descrição, esquadrias, metodologia/conferência, assinatura).
2. Com modelo (--modelo seu.docx): abre o seu Word e troca os marcadores:
   - campos {{OBRA}}, {{ENDERECO}}, {{PROPRIETARIO}}, {{RESPONSAVEL}}, {{REGISTRO}},
     {{MUNICIPIO}}, {{DATA}}, {{ARQUIVO}}, {{AREA_TERRENO}}, {{AREA_CONSTRUIDA}},
     {{AREA_UTIL}}, {{AREA_PERMEAVEL}}, {{TAXA_OCUPACAO}}, {{TAXA_PERMEABILIDADE}},
     {{N_AMBIENTES}} e qualquer outra chave do projeto.json em maiúsculas;
   - um parágrafo só com {{TABELA_RESUMO}}, {{TABELA_AMBIENTES}}, {{DESCRICAO_AMBIENTES}},
     {{TABELA_BLOCOS}} ou {{ALERTAS}} é substituído pelo conteúdo correspondente.
"""
from __future__ import annotations

import copy
import datetime as dt
import re
from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

from .formatos import m, m2, num, pct
from .modelo import Resultado

A_PREENCHER = "[a preencher]"


def _campos(res: Resultado, dados: dict) -> dict:
    s = res.resumo
    c = {k.upper(): str(v) for k, v in dados.items() if not isinstance(v, (dict, list))}
    c.setdefault("OBRA", A_PREENCHER)
    c.setdefault("ENDERECO", A_PREENCHER)
    c.setdefault("PROPRIETARIO", A_PREENCHER)
    c.setdefault("RESPONSAVEL", A_PREENCHER)
    c.setdefault("REGISTRO", "")
    c.setdefault("MUNICIPIO", "")
    c.setdefault("DATA", dt.date.today().strftime("%d/%m/%Y"))
    c.update({
        "ARQUIVO": Path(res.desenho.arquivo).name,
        "AREA_TERRENO": m2(s["area_terreno"]),
        "AREA_CONSTRUIDA": m2(s["area_construida"]),
        "AREA_UTIL": m2(s["area_util"]),
        "AREA_PERMEAVEL": m2(s["area_permeavel"]),
        "TAXA_OCUPACAO": pct(s["taxa_ocupacao"]),
        "TAXA_PERMEABILIDADE": pct(s["taxa_permeabilidade"]),
        "N_AMBIENTES": str(s["n_ambientes"]),
    })
    return c


# ------------------------------------------------------------ peças reutilizadas
def _sombrear(cel, cor="D9E1F2"):
    tcPr = cel._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), cor)
    tcPr.append(shd)


def _tabela(doc, titulos, linhas, total=None, alinhar_dir=(), larguras_cm=None):
    t = doc.add_table(rows=1, cols=len(titulos))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, tt in enumerate(titulos):
        cel = t.rows[0].cells[i]
        cel.text = ""
        run = cel.paragraphs[0].add_run(tt)
        run.bold = True
        run.font.size = Pt(9)
        cel.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
        _sombrear(cel)
    for ln in linhas + ([total] if total else []):
        cels = t.add_row().cells
        for i, v in enumerate(ln):
            cels[i].text = ""
            run = cels[i].paragraphs[0].add_run(str(v))
            run.font.size = Pt(9)
            if ln is total:
                run.bold = True
                _sombrear(cels[i], "F2F2F2")
            if i in alinhar_dir:
                cels[i].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT
    if larguras_cm:
        t.autofit = False
        for col, w in zip(t.columns, larguras_cm):
            col.width = Cm(w)  # grade da tabela (LibreOffice usa esta)
        for row in t.rows:
            for cel, w in zip(row.cells, larguras_cm):
                cel.width = Cm(w)
    return t


def _tabela_resumo(doc, res):
    s = res.resumo
    linhas = [["Área do terreno", m2(s["area_terreno"])],
              ["Área construída", m2(s["area_construida"])],
              ["Área útil (soma dos ambientes, sem paredes)", m2(s["area_util"])],
              ["Área permeável", m2(s["area_permeavel"])],
              ["Taxa de ocupação", pct(s["taxa_ocupacao"])],
              ["Taxa de permeabilidade", pct(s["taxa_permeabilidade"])],
              ["Número de ambientes", str(s["n_ambientes"])]]
    return _tabela(doc, ["Item", "Valor"], linhas, alinhar_dir=(1,), larguras_cm=[11, 5])


def _tabela_ambientes(doc, res):
    linhas = [[a.numero, a.nome, num(a.area), num(a.perimetro),
               num(a.pe_direito) if a.pe_direito else "—",
               num(a.area_parede) if a.area_parede else "—"] for a in res.ambientes]
    s = res.resumo
    total = ["", "TOTAL", num(s["area_util"]), num(s["perimetro_total"]), "",
             num(s["area_paredes_total"]) if s["area_paredes_total"] else "—"]
    return _tabela(doc, ["Nº", "Ambiente", "Área (m²)", "Perímetro (m)", "Pé-direito (m)", "Paredes (m²)*"],
                   linhas, total if linhas else None, alinhar_dir=(2, 3, 4, 5),
                   larguras_cm=[1.1, 6.4, 2.3, 2.6, 2.5, 2.5])


def _tabela_blocos(doc, res):
    linhas = [[nome, camada, n] for (nome, camada), n in sorted(res.desenho.blocos.items())]
    return _tabela(doc, ["Bloco", "Camada", "Quantidade"], linhas, alinhar_dir=(2,), larguras_cm=[8, 5.5, 3])


def _paragrafos_descricao(res, dados) -> list[str]:
    desc = {k.upper(): v for k, v in (dados.get("descricoes") or {}).items()}
    out = []
    for a in res.ambientes:
        base = re.sub(r"\s*\(\d+\)$", "", a.nome)
        txt = (f"{a.numero}. {a.nome}: área de piso de {m2(a.area)} e perímetro de {m(a.perimetro)}"
               + (f", pé-direito de {m(a.pe_direito)}" if a.pe_direito else "") + ".")
        extra = desc.get(a.nome) or desc.get(base)
        if extra:
            txt += " " + extra.strip()
        out.append(txt)
    return out


def _texto_metodologia(res) -> str:
    d = res.desenho
    modo = ("polígonos fechados das camadas de ambientes" if res.modo == "camadas"
            else "áreas fechadas identificadas pelos nomes escritos no desenho")
    return (f"As áreas e perímetros foram calculados diretamente da geometria do arquivo {Path(d.arquivo).name} "
            f"({d.formato.upper()}, unidade/escala: {d.unidade}), a partir de {modo}, pela fórmula de Gauss "
            f"(área de polígono) — arcos aproximados por segmentos com erro desprezível. A área útil corresponde "
            f"à soma das áreas internas dos ambientes e não inclui paredes. *A área de paredes é bruta "
            f"(perímetro × pé-direito), sem desconto de vãos de portas e janelas. Os valores devem ser "
            f"conferidos pelo responsável técnico antes de uso oficial.")


# ------------------------------------------------------------ memorial padrão
def _padrao(res: Resultado, dados: dict) -> Document:
    c = _campos(res, dados)
    doc = Document()
    st = doc.styles["Normal"]
    st.font.name = "Arial"
    st.font.size = Pt(10.5)

    t = doc.add_paragraph()
    t.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = t.add_run(dados.get("titulo", "MEMORIAL DESCRITIVO"))
    r.bold, r.font.size = True, Pt(15)
    sub = doc.add_paragraph()
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    rs = sub.add_run(dados.get("subtitulo", "Quadro de áreas e descrição dos ambientes"))
    rs.font.size, rs.font.color.rgb = Pt(11), RGBColor(0x55, 0x55, 0x55)

    def titulo(txt):
        h = doc.add_paragraph()
        h.paragraph_format.space_before = Pt(12)
        rr = h.add_run(txt)
        rr.bold, rr.font.size, rr.font.color.rgb = True, Pt(11.5), RGBColor(0x1F, 0x4E, 0x79)

    titulo("1. IDENTIFICAÇÃO")
    _tabela(doc, ["Campo", "Dado"], [["Obra / projeto", c["OBRA"]], ["Endereço", c["ENDERECO"]],
                                    ["Proprietário / interessado", c["PROPRIETARIO"]],
                                    ["Responsável técnico", (c["RESPONSAVEL"] + (f" — {c['REGISTRO']}" if c["REGISTRO"] else ""))],
                                    ["Arquivo de origem", c["ARQUIVO"]], ["Data", c["DATA"]]],
           larguras_cm=[5, 11])

    titulo("2. OBJETO")
    doc.add_paragraph(dados.get("objeto") or
                      f"O presente memorial apresenta o quadro de áreas e a descrição dos ambientes do projeto "
                      f"{c['OBRA']}, com áreas e perímetros obtidos do desenho {c['ARQUIVO']}.")

    titulo("3. QUADRO DE ÁREAS")
    _tabela_resumo(doc, res)

    titulo("4. AMBIENTES")
    _tabela_ambientes(doc, res)

    titulo("5. DESCRIÇÃO DOS AMBIENTES")
    for p in _paragrafos_descricao(res, dados):
        doc.add_paragraph(p)

    n = 6
    if res.desenho.blocos:
        titulo(f"{n}. ESQUADRIAS E ELEMENTOS (BLOCOS DO DESENHO)")
        _tabela_blocos(doc, res)
        n += 1

    titulo(f"{n}. METODOLOGIA E CONFERÊNCIA")
    doc.add_paragraph(_texto_metodologia(res))
    pend = [a for a in res.alertas if a.nivel in ("erro", "atencao")]
    if pend:
        p = doc.add_paragraph()
        rr = p.add_run(f"Pontos a conferir no desenho ({len(pend)}):")
        rr.bold = True
        for a in pend:
            doc.add_paragraph(a.mensagem, style="List Bullet")

    doc.add_paragraph()
    loc = doc.add_paragraph(f"{c['MUNICIPIO'] + ', ' if c['MUNICIPIO'] else ''}{c['DATA']}.")
    loc.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    for _ in range(2):
        doc.add_paragraph()
    for txt in ("_______________________________________", c["RESPONSAVEL"], c["REGISTRO"]):
        if txt:
            p = doc.add_paragraph(txt)
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.space_after = Pt(0)
    return doc


# ------------------------------------------------------------ memorial com modelo
def _todos_paragrafos(doc):
    yield from doc.paragraphs
    for t in doc.tables:
        for row in t.rows:
            for cel in row.cells:
                yield from cel.paragraphs
    for sec in doc.sections:
        for parte in (sec.header, sec.footer):
            yield from parte.paragraphs
            for t in parte.tables:
                for row in t.rows:
                    for cel in row.cells:
                        yield from cel.paragraphs


def _trocar_campos(par, campos):
    txt = "".join(r.text for r in par.runs)
    if "{{" not in txt:
        return
    novo = re.sub(r"\{\{\s*([A-Z0-9_]+)\s*\}\}", lambda mm: campos.get(mm.group(1), mm.group(0)), txt)
    if novo != txt and par.runs:
        par.runs[0].text = novo
        for r in par.runs[1:]:
            r.text = ""


def _paragrafo_como(p, texto: str):
    """Novo parágrafo com o mesmo estilo/formatação do parágrafo-marcador do modelo."""
    novo = OxmlElement("w:p")
    if p._p.pPr is not None:
        novo.append(copy.deepcopy(p._p.pPr))
    r = OxmlElement("w:r")
    if p.runs and p.runs[0]._r.rPr is not None:
        r.append(copy.deepcopy(p.runs[0]._r.rPr))
    t = OxmlElement("w:t")
    t.text = texto
    t.set(qn("xml:space"), "preserve")
    r.append(t)
    novo.append(r)
    return novo


def _com_modelo(res: Resultado, dados: dict, modelo: Path) -> Document:
    doc = Document(str(modelo))
    campos = _campos(res, dados)
    blocos = {"TABELA_RESUMO", "TABELA_AMBIENTES", "TABELA_BLOCOS", "DESCRICAO_AMBIENTES", "ALERTAS"}
    alvos = []
    for p in list(doc.paragraphs):
        chave = re.fullmatch(r"\s*\{\{\s*([A-Z_]+)\s*\}\}\s*", p.text or "")
        if chave and chave.group(1) in blocos:
            alvos.append((p, chave.group(1)))
    for p, chave in alvos:
        ancora = p._p
        elems = []
        if chave == "TABELA_RESUMO":
            elems = [_tabela_resumo(doc, res)._tbl]
        elif chave == "TABELA_AMBIENTES":
            elems = [_tabela_ambientes(doc, res)._tbl]
        elif chave == "TABELA_BLOCOS":
            elems = [_tabela_blocos(doc, res)._tbl]
        elif chave in ("DESCRICAO_AMBIENTES", "ALERTAS"):
            textos = (_paragrafos_descricao(res, dados) if chave == "DESCRICAO_AMBIENTES"
                      else [a.mensagem for a in res.alertas if a.nivel in ("erro", "atencao")] or ["Nenhum ponto a conferir."])
            for t in textos:
                elems.append(_paragrafo_como(p, t))
        for e in elems:
            ancora.addnext(e)
            ancora = e
        p._p.getparent().remove(p._p)
    for par in _todos_paragrafos(doc):
        _trocar_campos(par, campos)
    return doc


def gerar(res: Resultado, destino: str | Path, dados: dict | None = None, modelo: str | Path | None = None) -> Path:
    dados = dados or {}
    doc = _com_modelo(res, dados, Path(modelo)) if modelo else _padrao(res, dados)
    destino = Path(destino)
    doc.save(str(destino))
    return destino
