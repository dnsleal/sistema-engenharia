"""Linha de comando.

    python -m plantas processar planta.dxf --dados projeto.json
    python -m plantas processar prancha.pdf --escala 1:50
    python -m plantas camadas planta.dxf          (diagnóstico: o que o arquivo tem)
    python -m plantas exemplo                     (gera uma planta de teste)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import analise, config as cfgmod
from . import saida_excel, saida_memorial, saida_svg
from .formatos import m2, pct


def ler_desenho(arquivo: Path, cfg: dict, args):
    ext = arquivo.suffix.lower()
    if ext in (".dxf", ".dwg"):
        from . import leitor_dxf
        return leitor_dxf.ler(arquivo, cfg, unidade=getattr(args, "unidade", None))
    if ext == ".pdf":
        from . import leitor_pdf
        return leitor_pdf.ler(arquivo, cfg, escala=getattr(args, "escala", None), pagina=getattr(args, "pagina", 1))
    raise SystemExit(f"Formato não suportado: {ext} (use .dxf, .dwg ou .pdf)")


def _cfg(args) -> dict:
    cfg = cfgmod.carregar(args.config)
    if getattr(args, "camada_ambientes", None):
        cfg["camadas"]["ambientes"] = args.camada_ambientes
    if getattr(args, "modo", None):
        cfg["modo"] = args.modo
    if getattr(args, "vao", None):
        cfg["fechamento_vaos_m"] = args.vao / 2
    for chave in ("terreno", "construida", "permeavel", "nomes", "numeros", "paredes", "esquadrias"):
        v = getattr(args, f"camada_{chave}", None)
        if v:
            cfg["camadas"][chave] = v
    return cfg


def para_json(res) -> dict:
    return {
        "arquivo": res.desenho.arquivo, "unidade": res.desenho.unidade, "modo": res.modo,
        "resumo": res.resumo,
        "ambientes": [{"numero": a.numero, "nome": a.nome, "camada": a.camada, "area_m2": round(a.area, 4),
                       "perimetro_m": round(a.perimetro, 4), "pe_direito_m": a.pe_direito,
                       "area_paredes_m2": None if a.area_parede is None else round(a.area_parede, 4),
                       "area_declarada_m2": a.area_declarada, "origem": a.origem,
                       "vertices": [[round(x, 4), round(y, 4)] for x, y in a.geom.exterior.coords]}
                      for a in res.ambientes],
        "outras_areas": {cat: [{"nome": a.nome, "camada": a.camada, "area_m2": round(a.area, 4),
                                "perimetro_m": round(a.perimetro, 4)} for a in lst]
                         for cat, lst in res.outras.items()},
        "blocos": [{"bloco": n, "camada": c, "quantidade": q} for (n, c), q in sorted(res.desenho.blocos.items())],
        "alertas": [{"nivel": a.nivel, "mensagem": a.mensagem, "x": a.x, "y": a.y} for a in res.alertas],
    }


def cmd_processar(args) -> int:
    arq = Path(args.arquivo)
    if not arq.exists():
        print(f"Arquivo não encontrado: {arq}", file=sys.stderr)
        return 2
    cfg = _cfg(args)
    dados = json.loads(Path(args.dados).read_text(encoding="utf-8")) if args.dados else {}
    try:
        des = ler_desenho(arq, cfg, args)
    except Exception as exc:  # noqa: BLE001
        print(f"ERRO: {exc}", file=sys.stderr)
        return 1
    res = analise.analisar(des, cfg, pe_direito=args.pe_direito)

    saida = Path(args.saida) if args.saida else arq.parent / f"{arq.stem}_areas"
    saida.mkdir(parents=True, exist_ok=True)
    base = saida / arq.stem
    arquivos = [saida_excel.gerar(res, f"{base}_quadro_areas.xlsx", dados),
                saida_memorial.gerar(res, f"{base}_memorial.docx", dados, args.modelo),
                saida_svg.gerar(res, f"{base}_conferencia.svg")]
    jp = Path(f"{base}_resultado.json")
    jp.write_text(json.dumps(para_json(res), ensure_ascii=False, indent=1), encoding="utf-8")
    arquivos.append(jp)

    s = res.resumo
    print(f"\n{arq.name}  —  unidade: {des.unidade}  —  ambientes por {res.modo}")
    print(f"{'Nº':>3}  {'Ambiente':<28} {'Área (m²)':>10} {'Perím. (m)':>11}")
    for a in res.ambientes:
        print(f"{a.numero:>3}  {a.nome[:28]:<28} {a.area:>10.2f} {a.perimetro:>11.2f}")
    print(f"     {'ÁREA ÚTIL':<28} {s['area_util']:>10.2f}")
    print(f"\nTerreno {m2(s['area_terreno'])} | Construída {m2(s['area_construida'])} | "
          f"Permeável {m2(s['area_permeavel'])} | Ocupação {pct(s['taxa_ocupacao'])} | "
          f"Permeabilidade {pct(s['taxa_permeabilidade'])}")
    n_err = sum(a.nivel == "erro" for a in res.alertas)
    n_at = sum(a.nivel == "atencao" for a in res.alertas)
    if res.alertas:
        print(f"\nAlertas: {n_err} erro(s), {n_at} atenção, {len(res.alertas) - n_err - n_at} info")
        for a in res.alertas:
            if a.nivel != "info" or args.detalhes:
                print("  " + str(a))
    print("\nArquivos gerados:")
    for f in arquivos:
        print(f"  {f}")
    return 0


def cmd_camadas(args) -> int:
    cfg = _cfg(args)
    des = ler_desenho(Path(args.arquivo), cfg, args)
    print(f"{Path(args.arquivo).name} — unidade: {des.unidade}\n")
    print(f"{'Camada':<32} {'Categoria':<11} {'Fechados':>8} {'Abertos':>8} {'Textos':>7} {'Blocos':>7}")
    for camada, info in des.camadas.items():
        cat = cfgmod.categoria_da_camada(camada, cfg) or ""
        print(f"{(camada or '(sem camada)')[:32]:<32} {cat:<11} {info.get('fechados', 0):>8} "
              f"{info.get('abertos', 0):>8} {info.get('textos', 0):>7} {info.get('blocos', 0):>7}")
    print("\n'Categoria' vazia = camada não reconhecida. Para usar uma camada como ambientes:\n"
          "  python -m plantas processar ARQUIVO --camada-ambientes \"NOME DA CAMADA\"\n"
          "ou ajuste config_padrao.json / um config.json próprio (--config).")
    if des.blocos:
        print("\nBlocos mais usados:")
        for (n, c), q in des.blocos.most_common(15):
            print(f"  {q:>4} × {n}  ({c})")
    for a in des.alertas:
        print("  " + str(a))
    return 0


def cmd_exemplo(args) -> int:
    from . import exemplo
    if args.pdf:
        p = exemplo.gerar_pdf(args.saida or "exemplo_casa.pdf")
    else:
        p = exemplo.gerar_dxf(args.saida or "exemplo_casa.dxf", unidade=args.unidade or "m")
    print(f"Gerado: {p}\nAgora rode:  python -m plantas processar {p}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="plantas", description="Áreas, perímetros e memorial a partir de plantas DXF/DWG/PDF.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def comuns(p):
        p.add_argument("arquivo")
        p.add_argument("--config", help="config.json com camadas/tolerâncias próprias")
        p.add_argument("--unidade", choices=["m", "cm", "mm"], help="unidade do DXF (quando o arquivo não informa)")
        p.add_argument("--escala", help="escala da prancha PDF, ex.: 1:50")
        p.add_argument("--pagina", type=int, default=1, help="página do PDF (padrão 1)")
        p.add_argument("--camada-ambientes", nargs="+", metavar="CAMADA", help="camada(s) dos ambientes (aceita *)")
        p.add_argument("--camada-terreno", nargs="+", metavar="CAMADA")
        p.add_argument("--camada-construida", nargs="+", metavar="CAMADA")
        p.add_argument("--camada-permeavel", nargs="+", metavar="CAMADA")
        p.add_argument("--camada-nomes", nargs="+", metavar="CAMADA", help="camada(s) dos textos de nome dos ambientes")
        p.add_argument("--camada-numeros", nargs="+", metavar="CAMADA", help="camada(s) com o número de cada ambiente")
        p.add_argument("--camada-paredes", nargs="+", metavar="CAMADA", help="camada(s) das paredes (modo paredes)")
        p.add_argument("--camada-esquadrias", nargs="+", metavar="CAMADA", help="camada(s) de portas/janelas")
        p.add_argument("--modo", choices=["auto", "camadas", "paredes", "textos"],
                       help="como achar os ambientes (padrão auto: camada de ambientes > paredes > textos)")
        p.add_argument("--vao", type=float, help="modo paredes: maior vão de porta fechado automaticamente, em m (padrão 0,90)")

    p = sub.add_parser("processar", help="calcula áreas e gera planilha, memorial, SVG e JSON")
    comuns(p)
    p.add_argument("--dados", help="projeto.json com obra, endereço, responsável, descrições...")
    p.add_argument("--modelo", help="memorial .docx com marcadores {{...}} para preencher")
    p.add_argument("--saida", help="pasta de saída (padrão: <arquivo>_areas ao lado do arquivo)")
    p.add_argument("--pe-direito", type=float, help="pé-direito padrão em m (padrão do config: 2,80)")
    p.add_argument("--detalhes", action="store_true", help="mostra também os alertas de nível info")
    p.set_defaults(func=cmd_processar)

    p = sub.add_parser("camadas", help="lista camadas, polígonos, textos e blocos do arquivo")
    comuns(p)
    p.set_defaults(func=cmd_camadas)

    p = sub.add_parser("exemplo", help="gera uma planta de exemplo para teste")
    p.add_argument("--saida")
    p.add_argument("--unidade", choices=["m", "cm", "mm"])
    p.add_argument("--pdf", action="store_true", help="gera PDF vetorial em vez de DXF")
    p.set_defaults(func=cmd_exemplo)

    args = ap.parse_args(argv)
    return args.func(args)
