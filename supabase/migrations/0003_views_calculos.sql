-- =====================================================================
-- Cálculos por consulta: saldo, % executado, valor medido, aditivos.
-- Nada disso é gravado — é recalculado sempre, então nunca desatualiza.
-- security_invoker = on: a view respeita o RLS de quem consulta.
-- =====================================================================

-- ---------- Saldo por item ----------
create view public.v_itens_saldo with (security_invoker = on) as
select
  i.id                                   as item_id,
  i.user_id,
  p.obra_id,
  p.id                                   as planilha_id,
  p.tipo                                 as planilha_tipo,
  p.numero                               as planilha_numero,
  i.ordem, i.item, i.tipo, i.codigo, i.banco, i.descricao, i.unidade,
  i.quantidade                           as qtd_contratada,
  i.pu_com_bdi,
  round(i.quantidade * coalesce(i.pu_com_bdi, 0), 2)                          as valor_contratado,
  coalesce(sum(mi.quantidade), 0)                                             as qtd_executada,
  i.quantidade - coalesce(sum(mi.quantidade), 0)                              as qtd_saldo,
  round(coalesce(sum(mi.quantidade), 0) * coalesce(i.pu_com_bdi, 0), 2)       as valor_executado,
  round((i.quantidade - coalesce(sum(mi.quantidade), 0)) * coalesce(i.pu_com_bdi, 0), 2) as valor_saldo,
  case when i.quantidade > 0
       then round(coalesce(sum(mi.quantidade), 0) / i.quantidade * 100, 2) end as pct_executado
from public.itens i
join public.planilhas p      on p.id = i.planilha_id
left join public.medicao_itens mi on mi.item_id = i.id
group by i.id, p.id;

-- ---------- Valor de cada BM ----------
create view public.v_medicoes_resumo with (security_invoker = on) as
select
  m.id as medicao_id, m.user_id, m.obra_id, m.numero,
  m.periodo_inicio, m.periodo_fim, m.reajuste_pct, m.fechada, m.fechada_em,
  coalesce(round(sum(mi.quantidade * coalesce(i.pu_com_bdi, 0)), 2), 0)                         as valor_medido,
  coalesce(round(sum(mi.quantidade * coalesce(i.pu_com_bdi, 0)) * m.reajuste_pct / 100, 2), 0)  as valor_reajuste,
  coalesce(round(sum(mi.quantidade * coalesce(i.pu_com_bdi, 0)) * (1 + m.reajuste_pct / 100), 2), 0) as valor_total
from public.medicoes m
left join public.medicao_itens mi on mi.medicao_id = m.id
left join public.itens i          on i.id = mi.item_id
group by m.id;

-- ---------- Resumo por obra (alimenta a Central de Monitoramento) ----------
create view public.v_obras_resumo with (security_invoker = on) as
with valores as (
  select s.obra_id,
         sum(s.valor_contratado) filter (where s.planilha_tipo = 'original' and s.tipo = 'servico') as valor_original,
         sum(s.valor_contratado) filter (where s.planilha_tipo = 'aditivo'  and s.tipo = 'servico') as valor_aditivos,
         sum(s.valor_executado)  filter (where s.tipo = 'servico')                                  as valor_executado
    from public.v_itens_saldo s
   group by s.obra_id
), bms as (
  select r.obra_id, count(*) as n_bms, max(r.numero) as ultimo_bm,
         sum(r.valor_reajuste) as total_reajuste
    from public.v_medicoes_resumo r
   group by r.obra_id
)
select
  o.id as obra_id, o.user_id, o.nome, o.contratada, o.num_contrato, o.processo_siged,
  o.status, o.tipo_obra, o.data_inicio, o.termino_vigente,
  coalesce(v.valor_original, 0)                                       as valor_original,
  coalesce(v.valor_aditivos, 0)                                       as valor_aditivos,
  coalesce(v.valor_original, 0) + coalesce(v.valor_aditivos, 0)       as valor_total,
  coalesce(v.valor_executado, 0)                                      as valor_executado,
  coalesce(v.valor_original, 0) + coalesce(v.valor_aditivos, 0) - coalesce(v.valor_executado, 0) as valor_saldo,
  case when coalesce(v.valor_original, 0) + coalesce(v.valor_aditivos, 0) > 0
       then round(coalesce(v.valor_executado, 0)
                  / (coalesce(v.valor_original, 0) + coalesce(v.valor_aditivos, 0)) * 100, 2) end as pct_executado,
  case when coalesce(v.valor_original, 0) > 0
       then round(coalesce(v.valor_aditivos, 0) / v.valor_original * 100, 2) end            as pct_aditivo,
  case when o.tipo_obra = 'reforma' then 50 else 25 end                                      as limite_aditivo_pct,
  coalesce(b.n_bms, 0)            as n_bms,
  b.ultimo_bm,
  coalesce(b.total_reajuste, 0)   as total_reajuste,
  (o.termino_vigente - current_date)                                                         as dias_restantes,
  (o.termino_vigente < current_date and o.status not in ('concluida','encerrada'))           as prazo_vencido
from public.obras o
left join valores v on v.obra_id = o.id
left join bms b     on b.obra_id = o.id;
