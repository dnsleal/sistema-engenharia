# Plantas → áreas, perímetros e memorial

Lê plantas **DXF**, **DWG** (convertido para DXF) e **PDF vetorial**, calcula a área e o perímetro de cada
ambiente e gera:

| Arquivo | O que é |
| --- | --- |
| `*_quadro_areas.xlsx` | Resumo (terreno, construída, útil, permeável, taxas), Ambientes, Blocos (portas, janelas…), Alertas. Totais com fórmula `SOMA` |
| `*_memorial.docx` | Memorial descritivo: identificação, quadro de áreas, ambientes, descrição, esquadrias, metodologia e pontos a conferir |
| `*_conferencia.svg` | Desenho do que o programa entendeu (abra no navegador e compare com a planta) |
| `*_resultado.json` | Tudo em JSON, para integrar depois com o sistema web/Supabase |

## Instalar

```bash
cd ferramentas/plantas
pip install -r requirements.txt
```

## Usar

```bash
# 1. ver a planta de exemplo funcionando
python -m plantas processar exemplos/casa_exemplo.dxf --dados exemplos/projeto.json

# 2. num arquivo real: primeiro veja o que ele tem
python -m plantas camadas minha_planta.dxf

# 3. processe, dizendo a camada dos ambientes se não for o padrão
python -m plantas processar minha_planta.dxf --camada-ambientes "ARQ-AREA" --dados projeto.json

# PDF vetorial (exportado do CAD): informe a escala se ela não estiver escrita na prancha
python -m plantas processar prancha.pdf --escala 1:50 --pagina 2

# memorial no SEU modelo do Word
python -m plantas processar minha_planta.dxf --dados projeto.json --modelo exemplos/modelo_memorial.docx
```

Outras opções: `--unidade m|cm|mm` (DXF sem unidade), `--pe-direito 3.0`, `--saida pasta`,
`--camada-terreno`, `--camada-construida`, `--camada-permeavel`, `--camada-nomes`, `--config meu.json`, `--detalhes`.

## Como desenhar para o resultado sair certo

O programa faz o que um bom desenhista faria com o comando ÁREA do CAD, só que em todos os ambientes de uma
vez. Para isso a planta precisa seguir um padrão mínimo:

1. **Uma polilinha fechada por ambiente**, numa camada própria (padrão: `AMBIENTE*`, `AREA-AMB*`).
   O contorno é o **interno** das paredes (área útil). Arcos podem (bulge), círculos também.
2. **O nome do ambiente escrito dentro** dele (TEXT, MTEXT ou atributo de bloco). Se no mesmo texto ou em
   outro dentro do ambiente tiver `12,50 m²`, o programa confere com a área calculada; `PD=3,00` muda o pé-direito.
3. Opcional: polilinha do **terreno** (`TERRENO*`, `LOTE*`), da **projeção / área construída**
   (`CONSTRUIDA*`, `PROJECAO*`) e das **áreas permeáveis** (`PERMEAVEL*`). Com elas saem as taxas de ocupação
   e permeabilidade.

Nomes de camada são configuráveis em `config_padrao.json` ou num `config.json` seu (`--config`).
`exemplos/config_arq.json` é o padrão de camadas `ARQ-` (testado no projeto da USF Jardim Fortaleza/Santa Laura):
ambientes = hachura `ARQ-HACH-SETOR`, nomes em `ARQ-TEXTOS`, áreas em `ARQ-AREAS`, números em `ARQ-NUMEROS`,
lote em `ARQ-LOTE`, projeção em `ARQ-PROJECAO`. Nesse padrão, a planta existente e a nova estão nas mesmas
coordenadas; por isso as camadas de nome precisam ser informadas (senão os textos da existente se misturam).

```bash
python -m plantas processar USF_..._ARQ_R00.dxf --config exemplos/config_arq.json --dados projeto.json
```
Se nenhuma camada de ambientes for achada, o programa entra no **modo textos**: cada nome escrito marca a menor
área fechada que o contém. Funciona, mas é menos confiável — o aviso aparece no resultado.

## O que ele confere sozinho (alertas)

- polilinha quase fechada (folga até 2 cm): fecha e avisa; ambiente feito com linhas soltas: monta e avisa;
- polígono com laço (autointerseção); hachura repetindo a polilinha (não conta em dobro);
- nome escrito em várias linhas (TEXTs separados, um embaixo do outro): junta ("HALL DOS" + "SANITÁRIOS");
- ambiente pequeno com o rótulo do lado de fora: associa ao ambiente sem nome mais próximo (até 1 m) e avisa;
- numeração dos ambientes do próprio desenho (camada `numeros`), se completa e sem repetição;
- ambiente sem nome, nome repetido (numera), texto de nome fora de qualquer ambiente;
- **área escrita no desenho diferente da calculada**;
- **ambientes sobrepostos** (área útil contada em dobro) — nível erro;
- ambiente fora da projeção da área construída (varanda descoberta?);
- DXF sem unidade (deduz m/cm/mm pelo tamanho típico dos ambientes e avisa);
- PDF sem escala, com mais de uma escala, sem camadas, ou escaneado (recusa).

## Limitações atuais (próximos passos)

- **DWG** precisa do [ODA File Converter](https://www.opendesign.com/guestfiles/oda_file_converter) instalado
  (gratuito) ou ser salvo como DXF no CAD. Variável `ODA_CONVERTER` aponta o executável, se não estiver no PATH.
- **PDF**: só vetorial. Sem camadas, móveis e hachuras podem subdividir ambientes; confira no SVG.
  Escala por calibração (medir uma cota conhecida) ainda não existe.
- Área de paredes é **bruta** (perímetro × pé-direito): ainda não desconta vãos de portas/janelas pelos blocos.
- Um pavimento por arquivo (ou por página). Vários pavimentos no mesmo DXF ainda não são separados.
- Rodapé, área de forro e de piso por tipo de acabamento: próximos passos naturais a partir do JSON.

## Estrutura

```
plantas/
  leitor_dxf.py      DXF/DWG -> polígonos (m), textos, blocos. Arcos exatos pelo bulge, unidades, OCS, blocos
  leitor_pdf.py      PDF vetorial -> idem, com escala da prancha
  analise.py         nomes dos ambientes, classificação por camada, quadro de áreas, alertas
  saida_excel.py     planilha
  saida_memorial.py  memorial Word (padrão ou modelo com {{MARCADORES}})
  saida_svg.py       desenho de conferência
  exemplo.py         planta de exemplo com áreas conhecidas (base dos testes)
  cli.py             linha de comando
config_padrao.json   nomes de camada, pé-direito padrão, tolerâncias, textos ignorados
exemplos/            casa_exemplo.dxf/.pdf, projeto.json, modelo_memorial.docx
tests/               pytest (rodar: cd ferramentas/plantas && pytest)
```

### Marcadores do modelo de memorial

Campos: `{{OBRA}}`, `{{ENDERECO}}`, `{{PROPRIETARIO}}`, `{{RESPONSAVEL}}`, `{{REGISTRO}}`, `{{MUNICIPIO}}`,
`{{DATA}}`, `{{ARQUIVO}}`, `{{AREA_TERRENO}}`, `{{AREA_CONSTRUIDA}}`, `{{AREA_UTIL}}`, `{{AREA_PERMEAVEL}}`,
`{{TAXA_OCUPACAO}}`, `{{TAXA_PERMEABILIDADE}}`, `{{N_AMBIENTES}}` e qualquer outra chave do `projeto.json`
em maiúsculas.

Parágrafo sozinho com `{{TABELA_RESUMO}}`, `{{TABELA_AMBIENTES}}`, `{{TABELA_BLOCOS}}`,
`{{DESCRICAO_AMBIENTES}}` ou `{{ALERTAS}}` vira a tabela/lista correspondente (com o estilo do parágrafo).
As descrições por ambiente vêm de `descricoes` no `projeto.json` (a chave `QUARTO` vale para `QUARTO (1)`, `QUARTO (2)`).
