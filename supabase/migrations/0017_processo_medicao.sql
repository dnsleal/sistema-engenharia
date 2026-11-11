-- =====================================================================
-- Processo de medição (fase 1): responsáveis, dados do contrato e do BM
-- usados no checklist, no relatório do fiscal e no relatório do gestor.
-- Cada dado fica num só lugar; os documentos leem daqui.
-- =====================================================================

-- ---------- pessoas: fiscais, gestores… (cadastradas uma vez, usadas em várias obras)
create table public.pessoas (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null default auth.uid() references auth.users(id) on delete cascade,
  nome        text not null,
  cargo       text,                -- ex.: Fiscal Técnico do Contrato, Gestor do Contrato
  unidade     text,                -- ex.: Coordenadoria Técnica de Obras
  matricula   text,
  portaria    text,                -- ex.: Portaria nº 260/DAC/2026/SMS de 28/09/2026
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);
create index pessoas_user_idx on public.pessoas(user_id, nome);
create trigger pessoas_updated before update on public.pessoas
  for each row execute function public.tg_updated_at();
alter table public.pessoas enable row level security;
create policy pessoas_select on public.pessoas for select to authenticated using (user_id = (select auth.uid()));
create policy pessoas_insert on public.pessoas for insert to authenticated with check (user_id = (select auth.uid()));
create policy pessoas_update on public.pessoas for update to authenticated using (user_id = (select auth.uid())) with check (user_id = (select auth.uid()));
create policy pessoas_delete on public.pessoas for delete to authenticated using (user_id = (select auth.uid()));
revoke all on public.pessoas from anon;

-- ---------- obra / contrato
alter table public.obras
  add column codigo_credor   text,                     -- Código/Credor do checklist
  add column termo_aditivo   text,                     -- ex.: 3º Termo Aditivo
  add column empenho_numero  text,
  add column empenho_saldo   numeric(14,2),
  add column fiscal_id       uuid references public.pessoas(id) on delete set null,
  add column gestor_id       uuid references public.pessoas(id) on delete set null,
  add column fiscal_adm_id   uuid references public.pessoas(id) on delete set null;
create index obras_fiscal_idx on public.obras(fiscal_id);
create index obras_gestor_idx on public.obras(gestor_id);
create index obras_fiscal_adm_idx on public.obras(fiscal_adm_id);

-- ---------- BM: dados da nota fiscal e do processo de pagamento
alter table public.medicoes
  add column competencia          text check (competencia is null or competencia ~ '^\d{4}-\d{2}$'),   -- AAAA-MM
  add column processo_pagamento   text,                -- nº do processo do BM no SIGED
  add column nf_numero            text,
  add column nf_data              date,
  add column nf_valor             numeric(14,2),
  add column glosa                text not null default 'nao' check (glosa in ('nao','sim_ajustada','sim_nao_ajustada')),
  add column glosa_valor          numeric(14,2),
  add column imr_pct              numeric(6,2),          -- aferição do IMR (%), quando houver
  add column retencao_vinculada   text,
  add column retencao_terceirizado text,
  add column outras_retencoes     text,
  add column data_relatorio       date,                  -- data dos relatórios do fiscal e do gestor
  add column dados                jsonb not null default '{}'::jsonb;   -- textos e ajustes dos documentos (fases seguintes)
