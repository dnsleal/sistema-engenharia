-- =====================================================================
-- Quantidades com todas as casas decimais (como no Excel).
-- numeric(16,4) cortava quantidades como 56,99564365… e mudava o total do item.
-- As views dependem dessas colunas, por isso são recriadas iguais.
-- =====================================================================
drop view if exists public.v_etapas;
drop view if exists public.v_obras_resumo;
drop view if exists public.v_medicoes_resumo;
drop view if exists public.v_itens_saldo;

alter table public.itens         alter column quantidade type numeric;
alter table public.medicao_itens alter column quantidade type numeric;

create view public.v_itens_saldo with (security_invoker = on) as
select
  i.id as item_id, i.user_id, p.obra_id,
  p.id as planilha_id, p.tipo as planilha_tipo, p.numero as planilha_numero,
  i.ordem, i.nivel, i.item, i.tipo, i.etapa_id, i.codigo, i.banco, i.descricao, i.unidade,
  i.quantidade as qtd_contratada, i.pu_sem_bdi, i.pu_com_bdi,
  round(i.quantidade * coalesce(i.pu_com_bdi, 0), 2)                                       as valor_contratado,
  coalesce(sum(mi.quantidade), 0)                                                          as qtd_executada,
  i.quantidade - coalesce(sum(mi.quantidade), 0)                                           as qtd_saldo,
  round(coalesce(sum(mi.quantidade), 0) * coalesce(i.pu_com_bdi, 0), 2)                    as valor_executado,
  round((i.quantidade - coalesce(sum(mi.quantidade), 0)) * coalesce(i.pu_com_bdi, 0), 2)   as valor_saldo,
  case when i.quantidade > 0 then round(coalesce(sum(mi.quantidade), 0) / i.quantidade * 100, 2) end as pct_executado
from public.itens i
join public.planilhas p on p.id = i.planilha_id
left join public.medicao_itens mi on mi.item_id = i.id
group by i.id, p.id;

-- Valor do BM: bruto (preços da planilha) → desconto do contrato → reajuste
create view public.v_medicoes_resumo with (security_invoker = on) as
with b as (
  select m.id, m.user_id, m.obra_id, m.numero, m.periodo_inicio, m.periodo_fim,
         m.reajuste_pct, m.fechada, m.fechada_em, coalesce(o.desconto_pct, 0) as desconto_pct,
         coalesce(round(sum(mi.quantidade * coalesce(i.pu_com_bdi, 0)), 2), 0) as bruto
    from public.medicoes m
    join public.obras o on o.id = m.obra_id
    left join public.medicao_itens mi on mi.medicao_id = m.id
    left join public.itens i on i.id = mi.item_id
   group by m.id, o.desconto_pct
)
select
  b.id as medicao_id, b.user_id, b.obra_id, b.numero, b.periodo_inicio, b.periodo_fim,
  b.reajuste_pct, b.fechada, b.fechada_em, b.desconto_pct,
  b.bruto                                                                      as valor_bruto,
  round(b.bruto * b.desconto_pct / 100, 2)                                     as valor_desconto,
  b.bruto - round(b.bruto * b.desconto_pct / 100, 2)                           as valor_medido,
  round((b.bruto - round(b.bruto * b.desconto_pct / 100, 2)) * b.reajuste_pct / 100, 2) as valor_reajuste,
  (b.bruto - round(b.bruto * b.desconto_pct / 100, 2))
    + round((b.bruto - round(b.bruto * b.desconto_pct / 100, 2)) * b.reajuste_pct / 100, 2) as valor_total
from b;

-- Resumo por obra: valores já com o desconto do contrato
create view public.v_obras_resumo with (security_invoker = on) as
with valores as (
  select s.obra_id,
         coalesce(sum(s.valor_contratado) filter (where s.planilha_tipo = 'original' and s.tipo = 'servico'), 0) as bruto_original,
         coalesce(sum(s.valor_contratado) filter (where s.planilha_tipo = 'aditivo'  and s.tipo = 'servico'), 0) as bruto_aditivos,
         coalesce(sum(s.valor_executado)  filter (where s.tipo = 'servico'), 0)                                  as bruto_executado
    from public.v_itens_saldo s
   group by s.obra_id
), bms as (
  select r.obra_id, count(*) as n_bms, max(r.numero) as ultimo_bm, sum(r.valor_reajuste) as total_reajuste
    from public.v_medicoes_resumo r
   group by r.obra_id
), x as (
  select o.*, (1 - coalesce(o.desconto_pct, 0) / 100) as fator,
         coalesce(v.bruto_original, 0) as bruto_original, coalesce(v.bruto_aditivos, 0) as bruto_aditivos,
         coalesce(v.bruto_executado, 0) as bruto_executado,
         coalesce(b.n_bms, 0) as n_bms, b.ultimo_bm, coalesce(b.total_reajuste, 0) as total_reajuste
    from public.obras o
    left join valores v on v.obra_id = o.id
    left join bms b on b.obra_id = o.id
)
select
  x.id as obra_id, x.user_id, x.nome, x.contratada, x.num_contrato, x.processo_siged,
  x.status, x.tipo_obra, x.data_inicio, x.termino_vigente, x.desconto_pct,
  x.bruto_original + x.bruto_aditivos                                         as valor_total_bruto,
  round(x.bruto_original * x.fator, 2)                                        as valor_original,
  round(x.bruto_aditivos * x.fator, 2)                                        as valor_aditivos,
  round((x.bruto_original + x.bruto_aditivos) * x.fator, 2)                   as valor_total,
  round(x.bruto_executado * x.fator, 2)                                       as valor_executado,
  round((x.bruto_original + x.bruto_aditivos - x.bruto_executado) * x.fator, 2) as valor_saldo,
  case when x.bruto_original + x.bruto_aditivos > 0
       then round(x.bruto_executado / (x.bruto_original + x.bruto_aditivos) * 100, 2) end as pct_executado,
  case when x.bruto_original > 0 then round(x.bruto_aditivos / x.bruto_original * 100, 2) end as pct_aditivo,
  case when x.tipo_obra = 'reforma' then 50 else 25 end                       as limite_aditivo_pct,
  x.n_bms, x.ultimo_bm, x.total_reajuste,
  (x.termino_vigente - current_date)                                          as dias_restantes,
  (x.termino_vigente < current_date and x.status not in ('concluida','encerrada')) as prazo_vencido
from x;

-- Etapas: contratado x executado x previsto no cronograma até hoje (sem tolerância)
create view public.v_etapas with (security_invoker = on) as
with serv as (
  select s.etapa_id, sum(s.valor_contratado) as contratado, sum(s.valor_executado) as executado
    from public.v_itens_saldo s
   where s.tipo = 'servico' and s.etapa_id is not null
   group by s.etapa_id
), crono as (
  select c.item_id,
         sum(c.pct_previsto) as pct_total,
         sum(c.pct_previsto) filter (where o.data_inicio is not null
                                       and c.dias is not null
                                       and o.data_inicio + c.dias <= current_date) as pct_previsto_hoje,
         max(c.dias) as dias_total
    from public.cronograma c
    join public.obras o on o.id = c.obra_id
   group by c.item_id
)
select
  e.id as etapa_id, e.user_id, p.obra_id, p.tipo as planilha_tipo, p.numero as planilha_numero,
  e.ordem, e.item, e.descricao,
  coalesce(s.contratado, 0) as valor_contratado,
  coalesce(s.executado, 0)  as valor_executado,
  case when coalesce(s.contratado, 0) > 0 then round(s.executado / s.contratado * 100, 2) end as pct_executado,
  c.pct_total               as pct_cronograma,
  coalesce(c.pct_previsto_hoje, 0) as pct_previsto_hoje,
  c.dias_total,
  (c.item_id is not null
     and coalesce(c.pct_previsto_hoje, 0) > 0
     and coalesce(s.executado, 0) / nullif(s.contratado, 0) * 100 < c.pct_previsto_hoje) as atrasada
from public.itens e
join public.planilhas p on p.id = e.planilha_id
left join serv s  on s.etapa_id = e.id
left join crono c on c.item_id = e.id
where e.tipo = 'etapa' and e.nivel = 1;

revoke all on public.v_itens_saldo, public.v_medicoes_resumo, public.v_obras_resumo, public.v_etapas from anon;
