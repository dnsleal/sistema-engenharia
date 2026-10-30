# Sistema de Engenharia

Sistema web para fiscalização de obras públicas, orçamentos e laudos, feito em HTML + JavaScript puro, com banco de dados, login e fotos no Supabase.

Desenvolvido por Eng. Civil Diego Leal, CREA-MT 37420.

## Módulos

| Fase | Módulo | Situação |
| --- | --- | --- |
| 0 | Login, Central de Monitoramento, cadastro de obras | pronto |
| 1 | Importar planilha orçamentária, aditivos, cronograma; página da obra | pronto |
| 2 | Medições (BM): lançamento, fechamento, boletim em PDF | pronto |
| 3 | Relatório fotográfico por BM (4 fotos por página, PDF) | pronto |
| 4 | Orçamento SINAPI-MT (base pronta 09/2026, analítico, salvo no sistema, vira planilha da obra) | pronto |
| 5 | Laudos de avaliação (locação e terreno) | a fazer |
| 6 | Propostas e ferramentas de cálculo | a fazer |

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
orcamento/index.html  App de orçamento (Orçamento Offline) ligado ao sistema
orcamento/nuvem.js    Login, orçamentos no banco, base pronta, analítico, virar planilha da obra
orcamento/bases/      Bases SINAPI prontas (só MT) em JSON; index.json lista as disponíveis
comum/
  config.js           Endereço e chave pública do Supabase
  supabase.js         Conexão e controle de login
  formatos.js         R$, %, datas e números no padrão brasileiro
  estilo.css          Visual único do sistema
  importar.js         Leitura da planilha orçamentária e do cronograma
  medicao.js          Cálculo do BM por item e por etapa (desconto e reajuste)
supabase/migrations/  SQL que cria o banco, em ordem (0001, 0002…)
```

## Como o banco funciona

- Cada linha tem um dono (`user_id`). As regras de RLS fazem cada usuário enxergar e alterar só os próprios dados, e impedem pendurar dados na obra de outra pessoa.
- Quem não fez login não consulta nenhuma tabela.
- Saldo, % executado, valor de cada BM, % de aditivo e prazo vencido **não são gravados**: são calculados pelas views `v_itens_saldo`, `v_medicoes_resumo` e `v_obras_resumo`.
- Um BM fechado não aceita alteração nas quantidades até ser reaberto.
- As fotos ficam no bucket privado `fotos`, na pasta `<user_id>/<obra_id>/`.

## Instalar uma cópia nova (para outra pessoa)

1. Crie uma conta e um projeto no [Supabase](https://supabase.com) (plano gratuito, região São Paulo).
2. No projeto, abra **SQL Editor** e rode os arquivos de `supabase/migrations/` na ordem dos números.
3. Em **Project Settings → API Keys**, copie a *Project URL* e a *publishable key* e cole em `comum/config.js`.
4. Em **Authentication → URL Configuration**, informe o endereço onde o site vai ficar (Site URL).
5. Publique os arquivos (Vercel, Netlify ou GitHub Pages) e crie a sua conta pela tela de login.

Nunca coloque no código a chave secreta (`service_role` / `sb_secret_…`).

## Bases SINAPI prontas

`orcamento/bases/sinapi-mt-AAAA-MM.json` traz, só para MT: insumos e composições nos dois regimes (desonerado e não desonerado), a composição analítica, o % de mão de obra e o preço de SP (%AS) dos insumos sem preço em MT. Composições com custo zero em MT ficam fora da busca.

Para incluir um mês novo, gere o arquivo a partir dos relatórios da CAIXA (SINAPI_Referência e SINAPI_mão_de_obra) e acrescente uma linha em `orcamento/bases/index.json`. Também é possível importar o mês direto no app (Bancos de dados → Importar planilha); nesse caso a base fica só no navegador onde foi importada.
