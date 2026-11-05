-- =====================================================================
-- Acompanhamento das propostas no SISMOB (Ministério da Saúde/FNS).
-- O SISMOB não tem integração aberta: os dados são lançados à mão.
-- O sistema controla duas coisas por proposta:
--   1) a próxima atualização obrigatória no SISMOB (última + intervalo);
--   2) pendências/alertas/diligências com prazo de resposta (como no SIGED).
-- As datas são calculadas na tela e gravadas, para ordenar e filtrar no banco.
-- =====================================================================
create table public.sismob_propostas (
  id                    uuid primary key default gen_random_uuid(),
  user_id               uuid not null default auth.uid() references auth.users(id) on delete cascade,
  numero_proposta       text not null,                    -- nº da proposta no SISMOB / FNS
  estabelecimento       text not null,                    -- nome da unidade (ex.: UBS São João Del Rei)
  componente            text,                             -- UBS, Academia da Saúde, CAPS, UPA…
  tipo_obra             text check (tipo_obra is null or tipo_obra in ('construcao','ampliacao','reforma')),
  municipio             text,
  obra_id               uuid references public.obras(id) on delete set null,
  valor_proposta        numeric(14,2),
  valor_recebido        numeric(14,2),
  etapa                 text not null default 'acao_preparatoria'
                        check (etapa in ('acao_preparatoria','ordem_inicio','em_execucao','concluida','em_funcionamento','cancelada')),
  percentual_executado  numeric(5,2) check (percentual_executado is null or (percentual_executado >= 0 and percentual_executado <= 100)),
  ultima_atualizacao    date,
  intervalo_atualizacao integer not null default 60 check (intervalo_atualizacao > 0),
  proxima_atualizacao   date,
  -- pendência / alerta / diligência em aberto
  pendencia             text,
  pendencia_entrada     date,
  prazo_dias            integer check (prazo_dias is null or prazo_dias >= 0),
  contagem              text not null default 'corridos' check (contagem in ('corridos','uteis')),
  data_limite           date,
  pendencia_status      text not null default 'sem' check (pendencia_status in ('sem','pendente','respondida')),
  respondido_em         date,
  documento_resposta    text,
  responsavel           text,
  link                  text,
  observacoes           text,
  created_at            timestamptz not null default now(),
  updated_at            timestamptz not null default now()
);
create index sismob_user_idx on public.sismob_propostas(user_id, proxima_atualizacao);
create index sismob_limite_idx on public.sismob_propostas(user_id, data_limite);
create index sismob_obra_idx on public.sismob_propostas(obra_id);
create trigger sismob_updated before update on public.sismob_propostas
  for each row execute function public.tg_updated_at();

create table public.sismob_movimentos (
  id           uuid primary key default gen_random_uuid(),
  user_id      uuid not null default auth.uid() references auth.users(id) on delete cascade,
  proposta_id  uuid not null references public.sismob_propostas(id) on delete cascade,
  data         date not null default current_date,
  descricao    text not null,                          -- o que aconteceu (atualização, alerta, parcela…)
  documento    text,                                   -- ofício, nota técnica, comprovante
  created_at   timestamptz not null default now()
);
create index sismob_mov_prop_idx on public.sismob_movimentos(proposta_id, data);
create index sismob_mov_user_idx on public.sismob_movimentos(user_id);

alter table public.sismob_propostas enable row level security;
alter table public.sismob_movimentos enable row level security;

create policy sismob_select on public.sismob_propostas for select to authenticated using (user_id = (select auth.uid()));
create policy sismob_insert on public.sismob_propostas for insert to authenticated
  with check (user_id = (select auth.uid())
    and (obra_id is null or exists (select 1 from public.obras o where o.id = obra_id and o.user_id = (select auth.uid()))));
create policy sismob_update on public.sismob_propostas for update to authenticated
  using (user_id = (select auth.uid()))
  with check (user_id = (select auth.uid())
    and (obra_id is null or exists (select 1 from public.obras o where o.id = obra_id and o.user_id = (select auth.uid()))));
create policy sismob_delete on public.sismob_propostas for delete to authenticated using (user_id = (select auth.uid()));

create policy sismob_mov_select on public.sismob_movimentos for select to authenticated using (user_id = (select auth.uid()));
create policy sismob_mov_insert on public.sismob_movimentos for insert to authenticated
  with check (user_id = (select auth.uid())
    and exists (select 1 from public.sismob_propostas p where p.id = proposta_id and p.user_id = (select auth.uid())));
create policy sismob_mov_delete on public.sismob_movimentos for delete to authenticated using (user_id = (select auth.uid()));

revoke all on public.sismob_propostas, public.sismob_movimentos from anon;
