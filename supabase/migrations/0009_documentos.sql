-- =====================================================================
-- Fase 6: a tabela de laudos passa a guardar também propostas e
-- relatórios de vistoria (documentos do mesmo tipo: formulário salvo).
-- =====================================================================
alter table public.laudos drop constraint laudos_tipo_check;
alter table public.laudos add constraint laudos_tipo_check
  check (tipo in ('locacao','terreno','proposta','relatorio'));
comment on table public.laudos is 'Documentos salvos: laudos (locação, terreno), propostas e relatórios de vistoria';
