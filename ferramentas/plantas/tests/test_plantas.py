"""Testes com a planta de exemplo (áreas conhecidas). Rodar: cd ferramentas/plantas && pytest"""
import json
import math

import pytest
from docx import Document
from openpyxl import load_workbook

from plantas import analise, cli, config, exemplo, leitor_dxf, leitor_pdf, saida_excel, saida_memorial
from plantas.modelo import Desenho, Poligono, Texto
from shapely.geometry import box

CFG = config.carregar()


def _processar_dxf(tmp_path, **kw):
    arq = exemplo.gerar_dxf(tmp_path / "casa.dxf", **kw)
    des = leitor_dxf.ler(arq, CFG)
    return analise.analisar(des, CFG)


def _por_nome(res):
    return {a.nome: a for a in res.ambientes}


def _confere_areas(res):
    amb = _por_nome(res)
    for nome, area in exemplo.ESPERADO.items():
        if nome.startswith("_"):
            continue
        chave = next(k for k in amb if k.startswith(nome))
        assert amb[chave].area == pytest.approx(area, abs=1e-3), nome


@pytest.mark.parametrize("unidade", ["m", "cm", "mm"])
def test_areas_dxf_em_qualquer_unidade(tmp_path, unidade):
    res = _processar_dxf(tmp_path, unidade=unidade)
    assert res.modo == "camadas"
    assert len(res.ambientes) == 7
    _confere_areas(res)
    s = res.resumo
    assert s["area_util"] == pytest.approx(exemplo.ESPERADO["_util"], abs=1e-3)
    assert s["area_terreno"] == pytest.approx(300, abs=1e-6)
    assert s["area_construida"] == pytest.approx(exemplo.ESPERADO["_construida"], abs=1e-6)
    assert s["area_permeavel"] == pytest.approx(37.5, abs=1e-6)
    assert s["taxa_ocupacao"] == pytest.approx(85.49 / 300, abs=1e-6)


def test_unidade_deduzida_quando_arquivo_nao_informa(tmp_path):
    arq = exemplo.gerar_dxf(tmp_path / "casa.dxf", unidade="cm", informar_unidade=False)
    des = leitor_dxf.ler(arq, CFG)
    assert des.fator_m == 0.01
    assert any("não informa a unidade" in a.mensagem for a in des.alertas)
    _confere_areas(analise.analisar(des, CFG))


def test_unidade_informada_vence(tmp_path):
    arq = exemplo.gerar_dxf(tmp_path / "casa.dxf", unidade="cm", informar_unidade=False)
    des = leitor_dxf.ler(arq, CFG, unidade="mm")
    assert des.fator_m == 0.001


def test_arco_da_varanda(tmp_path):
    v = _por_nome(_processar_dxf(tmp_path))["VARANDA"]
    assert v.area == pytest.approx(exemplo.VARANDA_AREA, abs=1e-3)
    assert v.perimetro == pytest.approx(exemplo.VARANDA_PERIMETRO, abs=1e-3)


def test_hachura_nao_conta_duas_vezes(tmp_path):
    res = _processar_dxf(tmp_path)
    assert sum(a.nome.startswith("SALA") for a in res.ambientes) == 1


def test_linhas_soltas_viram_ambiente(tmp_path):
    amb = _por_nome(_processar_dxf(tmp_path))
    assert amb["BANHEIRO"].origem == "linhas"


def test_conferencias(tmp_path):
    res = _processar_dxf(tmp_path)
    amb = _por_nome(res)
    msgs = " | ".join(a.mensagem for a in res.alertas)
    assert "QUARTO (1)" in amb and "QUARTO (2)" in amb
    assert any("SEM NOME" in n for n in amb)
    assert amb["COZINHA"].area_declarada == 12.0
    assert amb["COZINHA"].pe_direito == 2.6
    assert amb["SALA"].pe_direito == CFG["pe_direito_padrao"]
    assert "COZINHA: área escrita no desenho 12,00" in msgs
    assert "VARANDA" in msgs and "fora da projeção" in msgs
    assert not any(a.nivel == "erro" for a in res.alertas)


def test_blocos_contados(tmp_path):
    res = _processar_dxf(tmp_path)
    assert res.desenho.blocos[("PORTA 80", "ESQUADRIAS")] == 5
    assert res.desenho.blocos[("JANELA 120", "ESQUADRIAS")] == 4


def test_sobreposicao_e_polilinha_quase_fechada():
    # dois ambientes que se sobrepõem 1 m²
    d = Desenho("x.dxf", "dxf", "m", 1.0,
                poligonos=[Poligono(box(0, 0, 3, 3), "AMBIENTES", "polilinha"),
                           Poligono(box(2, 2, 5, 5), "AMBIENTES", "polilinha")],
                textos=[Texto("SALA", 1, 1, 0.2, "T"), Texto("COPA", 4, 4, 0.2, "T")])
    res = analise.analisar(d, CFG)
    assert any(a.nivel == "erro" and "sobrepõem em 1,00" in a.mensagem for a in res.alertas)


def test_polilinha_com_folga_e_fechada(tmp_path):
    import ezdxf
    doc = ezdxf.new()
    doc.header["$INSUNITS"] = 6
    msp = doc.modelspace()
    msp.add_lwpolyline([(0, 0), (4, 0), (4, 3), (0, 3), (0, 0.01)], dxfattribs={"layer": "AMBIENTES"})
    msp.add_text("ESCRITORIO", height=0.2, dxfattribs={"layer": "0", "insert": (1, 1.5)})
    doc.saveas(tmp_path / "f.dxf")
    res = analise.analisar(leitor_dxf.ler(tmp_path / "f.dxf", CFG), CFG)
    assert len(res.ambientes) == 1
    assert res.ambientes[0].area == pytest.approx(12, abs=0.05)
    assert res.ambientes[0].nome == "ESCRITORIO"
    assert any("fechei" in a.mensagem for a in res.alertas)


def test_modo_textos_sem_camada_de_ambientes(tmp_path):
    arq = exemplo.gerar_dxf(tmp_path / "casa.dxf")
    cfg = config.carregar()
    cfg["camadas"]["ambientes"] = ["NAO-EXISTE"]
    res = analise.analisar(leitor_dxf.ler(arq, cfg), cfg)
    assert res.modo == "textos"
    amb = _por_nome(res)
    assert amb["SALA"].area == pytest.approx(20, abs=1e-6)
    assert any("Nenhuma camada de ambientes" in a.mensagem for a in res.alertas)


def test_pdf_vetorial(tmp_path):
    arq = exemplo.gerar_pdf(tmp_path / "casa.pdf", escala=100)
    des = leitor_pdf.ler(arq, CFG)              # escala lida do texto "ESC. 1:100"
    res = analise.analisar(des, CFG)
    amb = _por_nome(res)
    assert res.modo == "textos"
    assert amb["SALA"].area == pytest.approx(20, abs=0.01)
    assert amb["COZINHA"].area == pytest.approx(11.70, abs=0.01)
    assert amb["QUARTO (1)"].area == pytest.approx(19.60, abs=0.01)
    assert amb["BANHEIRO"].perimetro == pytest.approx(7.80, abs=0.01)


def test_pdf_escala_errada_muda_area(tmp_path):
    arq = exemplo.gerar_pdf(tmp_path / "casa.pdf", escala=100)
    res = analise.analisar(leitor_pdf.ler(arq, CFG, escala="1:50"), CFG)
    assert _por_nome(res)["SALA"].area == pytest.approx(5, abs=0.01)   # metade do lado = 1/4 da área


def test_escala_invalida():
    with pytest.raises(ValueError):
        leitor_pdf.ler_escala("cinquenta")
    assert leitor_pdf.ler_escala("1/75") == 75


def test_saidas(tmp_path):
    res = _processar_dxf(tmp_path)
    xl = saida_excel.gerar(res, tmp_path / "q.xlsx", {"obra": "Casa teste"})
    wb = load_workbook(xl)
    assert wb.sheetnames == ["Resumo", "Ambientes", "Blocos", "Alertas"]
    ws = wb["Ambientes"]
    assert ws.cell(ws.max_row, 4).value == "=SUM(D2:D8)"
    assert ws["G2"].value == "=E2*F2"

    doc = saida_memorial.gerar(res, tmp_path / "m.docx", {"obra": "Casa teste", "responsavel": "Fulano"})
    texto = "\n".join(p.text for p in Document(doc).paragraphs)
    assert "MEMORIAL DESCRITIVO" in texto and "COZINHA: área de piso de 11,70 m²" in texto


def test_memorial_com_modelo(tmp_path):
    modelo = Document()
    modelo.add_paragraph("Obra: {{OBRA}} — área útil {{AREA_UTIL}}")
    modelo.add_paragraph("{{TABELA_AMBIENTES}}")
    modelo.add_paragraph("{{DESCRICAO_AMBIENTES}}")
    modelo.add_paragraph("Resp.: {{RESPONSAVEL}}")
    modelo.save(tmp_path / "modelo.docx")
    res = _processar_dxf(tmp_path)
    out = saida_memorial.gerar(res, tmp_path / "m.docx", {"obra": "Casa X", "responsavel": "Fulano"},
                               modelo=tmp_path / "modelo.docx")
    d = Document(out)
    texto = "\n".join(p.text for p in d.paragraphs)
    assert "Obra: Casa X — área útil 90,11 m²" in texto
    assert "Resp.: Fulano" in texto
    assert "{{" not in texto
    assert len(d.tables) == 1 and len(d.tables[0].rows) == 1 + 7 + 1
    assert "SALA: área de piso de 20,00 m²" in texto


def test_cli_ponta_a_ponta(tmp_path, capsys):
    arq = exemplo.gerar_dxf(tmp_path / "casa.dxf")
    dados = tmp_path / "p.json"
    dados.write_text(json.dumps({"obra": "Casa", "descricoes": {"SALA": "Piso porcelanato."}}), encoding="utf-8")
    assert cli.main(["processar", str(arq), "--dados", str(dados), "--saida", str(tmp_path / "out")]) == 0
    r = json.loads((tmp_path / "out" / "casa_resultado.json").read_text(encoding="utf-8"))
    assert r["resumo"]["area_util"] == pytest.approx(exemplo.ESPERADO["_util"], abs=1e-3)
    assert (tmp_path / "out" / "casa_conferencia.svg").exists()
    texto = "\n".join(p.text for p in Document(tmp_path / "out" / "casa_memorial.docx").paragraphs)
    assert "Piso porcelanato." in texto
    assert cli.main(["camadas", str(arq)]) == 0
    assert "AMBIENTES" in capsys.readouterr().out


def _dxf_um(tmp_path, monta):
    import ezdxf
    doc = ezdxf.new()
    doc.header["$INSUNITS"] = 6
    monta(doc, doc.modelspace())
    doc.saveas(tmp_path / "t.dxf")
    return analise.analisar(leitor_dxf.ler(tmp_path / "t.dxf", CFG), CFG)


def test_bulge_negativo_e_circulo(tmp_path):
    def monta(doc, msp):
        # semicírculo PARA FORA pelo lado de cima, percorrido no sentido horário (bulge -1)
        msp.add_lwpolyline([(0, 0, 0), (0, 2, -1), (4, 2, 0), (4, 0, 0)], format="xyb", close=True,
                           dxfattribs={"layer": "AMBIENTES"})
        msp.add_text("HALL", height=0.2, dxfattribs={"insert": (1.5, 1)})
        msp.add_circle((10, 10), 1.5, dxfattribs={"layer": "AMBIENTES"})
        msp.add_text("LAVABO", height=0.2, dxfattribs={"insert": (9.6, 10)})
    amb = _por_nome(_dxf_um(tmp_path, monta))
    assert amb["HALL"].area == pytest.approx(8 + math.pi * 2, rel=1e-5)
    assert amb["LAVABO"].area == pytest.approx(math.pi * 1.5 ** 2, rel=1e-5)
    assert amb["LAVABO"].perimetro == pytest.approx(2 * math.pi * 1.5, rel=1e-5)


def test_polilinha_espelhada_ocs(tmp_path):
    def monta(doc, msp):
        msp.add_lwpolyline([(1, 1), (4, 1), (4, 3), (1, 3)], close=True,
                           dxfattribs={"layer": "AMBIENTES", "extrusion": (0, 0, -1)})
        # em WCS o retângulo fica em x = -4..-1
        msp.add_text("DEPOSITO", height=0.2, dxfattribs={"insert": (-3, 2)})
    amb = _por_nome(_dxf_um(tmp_path, monta))
    assert amb["DEPOSITO"].area == pytest.approx(6, abs=1e-9)


def test_ambiente_dentro_de_bloco_escalado(tmp_path):
    def monta(doc, msp):
        blk = doc.blocks.new("MODULO")
        blk.add_lwpolyline([(0, 0), (1, 0), (1, 1), (0, 1)], close=True, dxfattribs={"layer": "AMBIENTES"})
        msp.add_blockref("MODULO", (10, 0), dxfattribs={"xscale": 3, "yscale": 2, "layer": "0"})
        msp.add_text("GUARITA", height=0.2, dxfattribs={"insert": (11, 1)})
    res = _dxf_um(tmp_path, monta)
    assert _por_nome(res)["GUARITA"].area == pytest.approx(6, abs=1e-9)
    assert res.desenho.blocos[("MODULO", "0")] == 1
