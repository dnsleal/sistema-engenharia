# Sistema Integrado de Engenharia

Sistema web para fiscalização de obras públicas, orçamentos e laudos, feito em HTML + JavaScript puro, com banco de dados, login e fotos no Supabase.

Desenvolvido por Eng. Civil Diego Leal, CREA-MT 37420.

## Módulos

| Fase | Módulo | Situação |
| --- | --- | --- |
| 0 | Login, Central de Monitoramento, cadastro de obras | pronto |
| 1 | Importar planilha orçamentária, aditivos, cronograma; página da obra | pronto |
| 2 | Medições (BM): lançamento, fechamento, boletim em PDF | pronto |
| 3 | Relatório fotográfico por BM (4 fotos por página, PDF) | pronto |
| 4 | Orçamento (ObraCerta): SINAPI-MT 09/2026 pronta, ORSE e outras bases importadas, composições próprias, curva ABC, cronograma, relatórios Excel/PDF, grava na obra como planilha original ou aditivo | pronto |
| 5 | Laudos de avaliação (locação SMECEL e terreno) salvos no sistema | pronto |
| 6 | Proposta Geoflora e relatório de vistoria (clientes) salvos no sistema | pronto |
| 7 | Acompanhamento de processos SIGED (prazos, histórico, alertas) | pronto |
| 8 | Simulador de armaduras | a fazer |

## Estrutura

```
index.html            Central de Monitoramento (exige login)
obras/obra.html       Página da obra: etapas × cronograma, planilhas com saldo
obras/importar.html   Importa planilha original/aditivo e cronograma do Excel
obras/medicao.html    Lançamento do BM: anterior, este BM, acumulado, saldo; fechar/reabrir
obras/boletim.html    Boletim de medição para imprimir ou salvar em PDF
obras/fotos.html      Fotos do BM: enviar (câmera ou arquivos), legenda, item, ordem
obras/relatorio-fotos.html  Relatório fotográfico do BM para imprimir ou salvar em PDF
login.html            Entrar, criar conta, recuperar senha
processos/index.html  Processos do SIGED: prazos (corridos/úteis), situação, histórico de movimentações
laudos/index.html     Documentos salvos (laudos, propostas, relatórios) e modelos para começar um novo
laudos/locacao.html   Laudo de locação (PVG, CUB, Ross-Heidecke) — formulário original + salvar no sistema
laudos/terreno.html   Laudo de terreno (comparativo direto, homogeneização) — idem
laudos/proposta.html  Proposta técnica Geoflora (timbre, imposto por dentro) — idem
laudos/relatorio.html Relatório de vistoria para clientes (logo editável, fotos, PDF/Word) — idem
orcamento/index.html  App de orçamento (ObraCerta): planilha, BDI, curva ABC, cronograma, relatórios,
                      composições próprias, bancos de preços; "Gravar na obra" leva a planilha para a obra
                      (?id=<orçamento> abre direto; ?obra=<obra> lista e cria orçamentos daquela obra)
orcamento/classico.html  App de orçamento anterior (Orçamento Offline), mantido para os orçamentos já feitos nele
orcamento/nuvem.js    Ligação do app anterior com o sistema
orcamento/bases/      Bases prontas: obracerta.json lista as do app atual (arquivos .json.gz, só MT);
                      index.json e sinapi-mt-AAAA-MM.json servem ao app anterior e à Auditoria
comum/
  config.js           Endereço e chave pública do Supabase
  supabase.js         Conexão e controle de login
  formatos.js         R$, %, datas e números no padrão brasileiro
  prazos.js           Data-limite com prorrogação para o próximo dia útil; feriados nacionais, de Cuiabá e pontos facultativos
  estilo.css          Visual único do sistema
  importar.js         Leitura da planilha orçamentária e do cronograma
  medicao.js          Cálculo do BM por item e por etapa (desconto e reajuste)
  laudo-nuvem.js      Salva/reabre documentos: formulário (campos/fotos), página editável (html) ou estado do navegador (local)
supabase/migrations/  SQL que cria o banco, em ordem (0001, 0002…)
```

## Como o banco funciona

- Cada linha tem um dono (`user_id`). As regras de RLS fazem cada usuário enxergar e alterar só os próprios dados, e impedem pendurar dados na obra de outra pessoa.
- Quem não fez login não consulta nenhuma tabela.
- Saldo, % executado, valor de cada BM, % de aditivo e prazo vencido **não são gravados**: são calculados pelas views `v_itens_saldo`, `v_medicoes_resumo` e `v_obras_resumo`.
- Um BM fechado não aceita alteração nas quantidades até ser reaberto.
- As fotos ficam no bucket privado `fotos`, na pasta `<user_id>/<obra_id>/`.
- Orçamentos (`orcamentos`, coluna `app`) e composições próprias (`orc_proprias`) são de cada usuário.
- Bases de preço importadas (`orc_bases`, `orc_base_itens`, `orc_base_analitico`) são lidas por todos os usuários logados e só quem importou altera ou exclui. A importação grava uma versão nova e só no fim a função `orc_base_publicar` troca a versão ativa: se cair no meio, a base anterior continua inteira.
- A medição é uma só: os BMs da obra. O orçamento, depois de gravado na obra, mostra na aba Medição os BMs lançados nela.

## Instalar uma cópia nova (para outra pessoa)

1. Crie uma conta e um projeto no [Supabase](https://supabase.com) (plano gratuito, região São Paulo).
2. No projeto, abra **SQL Editor** e rode os arquivos de `supabase/migrations/` na ordem dos números.
3. Em **Project Settings → API Keys**, copie a *Project URL* e a *publishable key* e cole em `comum/config.js`.
4. Em **Authentication → URL Configuration**, informe o endereço onde o site vai ficar (Site URL).
5. Publique os arquivos (Vercel, Netlify ou GitHub Pages) e crie a sua conta pela tela de login.

Nunca coloque no código a chave secreta (`service_role` / `sb_secret_…`).

## Bases SINAPI prontas

O app de orçamento usa os arquivos listados em `orcamento/bases/obracerta.json` (ex.: `sinapi-mt-2026-09.obracerta.json.gz`, JSON comprimido com insumos, composições nos dois regimes e analítico). A base mais recente de cada fonte é a usada nos orçamentos novos. Para um mês novo, gere os arquivos com `ferramentas/sinapi_orcamento.py` e `ferramentas/sinapi_auditoria.py` e acrescente uma linha no `obracerta.json` e no `index.json`; ou importe a planilha em Bancos de preços (fica no banco, para todos os usuários).

Os padrões dos orçamentos novos (órgão, município, responsável técnico, taxa de administração) ficam em `comum/config.js`, no bloco `ORCAMENTO`.

`orcamento/bases/sinapi-mt-AAAA-MM.json` (app anterior e Auditoria) traz, só para MT: insumos e composições nos dois regimes (desonerado e não desonerado), a composição analítica, o % de mão de obra e o preço de SP (%AS) dos insumos sem preço em MT. Composições com custo zero em MT ficam fora da busca.

Para incluir um mês novo, gere o arquivo a partir dos relatórios da CAIXA (SINAPI_Referência e SINAPI_mão_de_obra) e acrescente uma linha em `orcamento/bases/index.json`. Também é possível importar o mês direto no app (Bancos de dados → Importar planilha); nesse caso a base fica só no navegador onde foi importada.
