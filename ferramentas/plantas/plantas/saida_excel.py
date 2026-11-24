"""Planilha de áreas (.xlsx): Resumo, Ambientes, Blocos (esquadrias etc.), Alertas.

Os totais são fórmulas (SOMA), para a planilha continuar certa se alguém editar uma linha.
"""
from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from .modelo import Resultado

AZUL = PatternFill("solid", fgColor="1F4E79")
CINZA = PatternFill("solid", fgColor="D9E1F2")
AMARELO = PatternFill("solid", fgColor="FFF2CC")
VERMELHO = PatternFill("solid", fgColor="F8CBAD")
BRANCO_NEGRITO = Font(bold=True, color="FFFFFF")
NEGRITO = Font(bold=True)
FINA = Side(style="thin", color="999999")
BORDA = Border(left=FINA, right=FINA, top=FINA, bottom=FINA)
F2 = '#,##0.00'
PCT = '0.00%'


def _cabecalho(ws, linha, titulos, larguras=None):
    for c, t in enumerate(titulos, 1):
        cel = ws.cell(linha, c, t)
        cel.fill, cel.font, cel.border = AZUL, BRANCO_NEGRITO, BORDA
        cel.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    if larguras:
        for c, w in enumerate(larguras, 1):
            ws.column_dimensions[get_column_letter(c)].width = w


def gerar(res: Resultado, destino: str | Path, dados: dict | None = None) -> Path:
    dados = dados or {}
    wb = Workbook()

    # ---------------- Ambientes
    wa = wb.active
    wa.title = "Ambientes"
    _cabecalho(wa, 1, ["Nº", "Ambiente", "Camada", "Área (m²)", "Perímetro (m)", "Pé-direito (m)",
                       "Área de paredes bruta (m²)", "Área escrita no desenho (m²)", "Diferença (m²)", "Origem"],
               [6, 32, 18, 12, 14, 13, 16, 16, 13, 12])
    wa.row_dimensions[1].height = 32
    lin = 2
    for a in res.ambientes:
        wa.cell(lin, 1, a.numero)
        wa.cell(lin, 2, a.nome)
        wa.cell(lin, 3, a.camada)
        wa.cell(lin, 4, round(a.area, 4)).number_format = F2
        wa.cell(lin, 5, round(a.perimetro, 4)).number_format = F2
        if a.pe_direito is not None:
            wa.cell(lin, 6, a.pe_direito).number_format = F2
            wa.cell(lin, 7, f"=E{lin}*F{lin}").number_format = F2
        if a.area_declarada is not None:
            wa.cell(lin, 8, a.area_declarada).number_format = F2
            c = wa.cell(lin, 9, f"=D{lin}-H{lin}")
            c.number_format = F2
            if abs(a.area - a.area_declarada) > 0.05:
                c.fill = VERMELHO
        wa.cell(lin, 10, a.origem)
        if "SEM NOME" in a.nome:
            wa.cell(lin, 2).fill = AMARELO
        for col in range(1, 11):
            wa.cell(lin, col).border = BORDA
        lin += 1
    ult = lin - 1
    wa.cell(lin, 2, "TOTAL").font = NEGRITO
    if res.ambientes:
        for col, L in ((4, "D"), (5, "E"), (7, "G")):
            c = wa.cell(lin, col, f"=SUM({L}2:{L}{ult})")
            c.number_format, c.font = F2, NEGRITO
    for col in range(1, 11):
        wa.cell(lin, col).fill = CINZA
        wa.cell(lin, col).border = BORDA
    wa.freeze_panes = "A2"
    linha_total_amb = lin

    # ---------------- Resumo (primeira aba)
    wr = wb.create_sheet("Resumo", 0)
    wr.column_dimensions["A"].width = 38
    wr.column_dimensions["B"].width = 18
    wr.column_dimensions["C"].width = 48
    wr["A1"] = "QUADRO DE ÁREAS"
    wr["A1"].font = Font(bold=True, size=14)
    info = [("Obra", dados.get("obra", "")), ("Endereço", dados.get("endereco", "")),
            ("Arquivo", Path(res.desenho.arquivo).name), ("Unidade / escala", res.desenho.unidade),
            ("Ambientes achados por", "camadas" if res.modo == "camadas" else "textos (sem camada de ambientes)")]
    r = 3
    for k, v in info:
        wr.cell(r, 1, k).font = NEGRITO
        wr.cell(r, 2, v)
        r += 1
    r += 1
    _cabecalho(wr, r, ["Item", "Valor", "Observação"])
    r += 1
    s = res.resumo

    def linha(nome, valor, fmt=F2, obs=""):
        nonlocal r
        wr.cell(r, 1, nome).border = BORDA
        c = wr.cell(r, 2, valor if valor is not None else "—")
        c.border = BORDA
        if valor is not None:
            c.number_format = fmt
        wr.cell(r, 3, obs).border = BORDA
        r += 1
        return r - 1

    lt = linha("Área do terreno (m²)", s["area_terreno"])
    lc = linha("Área construída (m²)", s["area_construida"], obs=s["fonte_area_construida"] or "sem polígono de área construída")
    linha("Área útil — soma dos ambientes (m²)", f"=Ambientes!D{linha_total_amb}" if res.ambientes else 0,
          obs="não inclui paredes")
    lp = linha("Área permeável (m²)", s["area_permeavel"])
    linha("Taxa de ocupação", f"=B{lc}/B{lt}" if (s["area_terreno"] and s["area_construida"]) else None, PCT,
          "área construída ÷ terreno (confira se a lei usa projeção)")
    linha("Taxa de permeabilidade", f"=B{lp}/B{lt}" if (s["area_terreno"] and s["area_permeavel"] is not None) else None,
          PCT, "área permeável ÷ terreno")
    linha("Nº de ambientes", s["n_ambientes"], "0")
    linha("Perímetro total dos ambientes (m)", f"=Ambientes!E{linha_total_amb}" if res.ambientes else 0)
    linha("Área de paredes bruta (m²)", f"=Ambientes!G{linha_total_amb}" if res.ambientes else 0,
          obs=f"perímetro × pé-direito, sem descontar vãos (PD padrão {s['pe_direito_padrao']} m)")

    for cat, titulo in (("terreno", "Terreno"), ("construida", "Área construída"), ("permeavel", "Área permeável")):
        lst = res.outras.get(cat) or []
        if len(lst) > 1:
            r += 1
            wr.cell(r, 1, f"{titulo} — polígonos").font = NEGRITO
            r += 1
            for a in lst:
                wr.cell(r, 1, f"{a.nome} (camada {a.camada})")
                wr.cell(r, 2, round(a.area, 4)).number_format = F2
                r += 1

    # ---------------- Blocos
    wb_ = wb.create_sheet("Blocos")
    _cabecalho(wb_, 1, ["Bloco", "Camada", "Quantidade"], [36, 22, 12])
    r = 2
    for (nome, camada), n in sorted(res.desenho.blocos.items(), key=lambda x: (x[0][1], x[0][0])):
        for col, v in enumerate((nome, camada, n), 1):
            wb_.cell(r, col, v).border = BORDA
        r += 1
    if r == 2:
        wb_.cell(2, 1, "Nenhum bloco inserido no desenho (ou PDF).")

    # ---------------- Alertas
    wl = wb.create_sheet("Alertas")
    _cabecalho(wl, 1, ["Nível", "Mensagem", "X (m)", "Y (m)"], [10, 110, 12, 12])
    for r, al in enumerate(res.alertas, 2):
        wl.cell(r, 1, al.nivel)
        wl.cell(r, 2, al.mensagem).alignment = Alignment(wrap_text=True)
        if al.x is not None:
            wl.cell(r, 3, round(al.x, 3))
            wl.cell(r, 4, round(al.y, 3))
        if al.nivel == "erro":
            wl.cell(r, 1).fill = VERMELHO
        elif al.nivel == "atencao":
            wl.cell(r, 1).fill = AMARELO
    if not res.alertas:
        wl.cell(2, 2, "Nenhum alerta.")

    destino = Path(destino)
    wb.save(destino)
    return destino
