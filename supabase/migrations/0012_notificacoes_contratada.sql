-- =====================================================================
-- Notificações à contratada: estrutura de documento formal de fiscalização.
-- Constatação → evidência → fundamento (contrato/norma) → determinação →
-- prazo (contado da ciência) → acompanhamento do atendimento.
-- =====================================================================
alter table public.notificacoes
  add column categoria       text,                       -- prazo, qualidade, segurança, documentação…
  add column data_constatacao date,                      -- quando o fato foi verificado em campo
  add column constatacao     text,                       -- o que foi verificado (fato objetivo)
  add column evidencia       text,                       -- fotos, diário de obra, ensaio, medição…
  add column fundamento      text,                       -- cláusula contratual, norma, projeto
  add column determinacao    text,                       -- o que a contratada deve fazer
  add column data_ciencia    date,                       -- ciência da contratada (início do prazo)
  add column prazo_dias      integer check (prazo_dias is null or prazo_dias >= 0),
  add column contagem        text not null default 'corridos' check (contagem in ('corridos','uteis')),
  add column situacao        text not null default 'aberta'
                             check (situacao in ('rascunho','aberta','respondida','atendida','nao_atendida','cancelada')),
  add column resposta        text,                       -- resumo da resposta / providências da contratada
  add column processo_id     uuid references public.processos(id) on delete set null,
  add column destinatario    text,                       -- preposto / responsável técnico da contratada
  add column signatario      text,                       -- quem assina (fiscal)
  add column cargo           text,
  add column updated_at      timestamptz not null default now();

create index notificacoes_processo_idx on public.notificacoes(processo_id);
create trigger notificacoes_updated before update on public.notificacoes
  for each row execute function public.tg_updated_at();

-- coerência do campo antigo
update public.notificacoes set situacao = 'respondida' where respondida and situacao = 'aberta';

-- o processo vinculado também precisa ser do usuário
drop policy notificacoes_insert on public.notificacoes;
drop policy notificacoes_update on public.notificacoes;
create policy notificacoes_insert on public.notificacoes for insert to authenticated
  with check (user_id = (select auth.uid())
    and exists (select 1 from public.obras o where o.id = obra_id and o.user_id = (select auth.uid()))
    and (processo_id is null or exists (select 1 from public.processos p where p.id = processo_id and p.user_id = (select auth.uid()))));
create policy notificacoes_update on public.notificacoes for update to authenticated
  using (user_id = (select auth.uid()))
  with check (user_id = (select auth.uid())
    and exists (select 1 from public.obras o where o.id = obra_id and o.user_id = (select auth.uid()))
    and (processo_id is null or exists (select 1 from public.processos p where p.id = processo_id and p.user_id = (select auth.uid()))));
