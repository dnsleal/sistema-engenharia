-- =====================================================================
-- Fase 7: acompanhamento de processos do SIGED.
-- O SIGED não tem integração aberta: número e movimentações são lançados
-- à mão; o sistema cuida de prazos, situação e histórico.
-- A data-limite é calculada na tela (dias corridos ou úteis, com feriados)
-- e gravada, para ordenar e filtrar no banco.
-- =====================================================================
create table public.processos (
  id            uuid primary key default gen_random_uuid(),
  user_id       uuid not null default auth.uid() references auth.users(id) on delete cascade,
  numero        text not null,                         -- nº do processo no SIGED
  assunto       text not null,
  interessado   text,                                  -- interessado / órgão de origem
  tipo          text,                                  -- ofício, notificação, pedido de aditivo…
  obra_id       uuid references public.obras(id) on delete set null,
  data_entrada  date not null default current_date,
  prazo_dias    integer check (prazo_dias is null or prazo_dias >= 0),
  contagem      text not null default 'corridos' check (contagem in ('corridos','uteis')),
  data_limite   date,
  status        text not null default 'recebido'
                check (status in ('recebido','em_analise','aguardando','respondido','arquivado')),
  respondido_em date,
  responsavel   text,
  link          text,
  observacoes   text,
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now()
);
create index processos_user_idx on public.processos(user_id, data_limite);
create index processos_obra_idx on public.processos(obra_id);
create trigger processos_updated before update on public.processos
  for each row execute function public.tg_updated_at();

create table public.processo_movimentos (
  id           uuid primary key default gen_random_uuid(),
  user_id      uuid not null default auth.uid() references auth.users(id) on delete cascade,
  processo_id  uuid not null references public.processos(id) on delete cascade,
  data         date not null default current_date,
  descricao    text not null,                          -- o que aconteceu
  destino      text,                                   -- para onde foi tramitado
  documento    text,                                   -- nº do despacho / ofício / parecer
  created_at   timestamptz not null default now()
);
create index processo_movimentos_proc_idx on public.processo_movimentos(processo_id, data);
create index processo_movimentos_user_idx on public.processo_movimentos(user_id);

alter table public.processos enable row level security;
alter table public.processo_movimentos enable row level security;

create policy processos_select on public.processos for select to authenticated using (user_id = (select auth.uid()));
create policy processos_insert on public.processos for insert to authenticated
  with check (user_id = (select auth.uid())
    and (obra_id is null or exists (select 1 from public.obras o where o.id = obra_id and o.user_id = (select auth.uid()))));
create policy processos_update on public.processos for update to authenticated
  using (user_id = (select auth.uid()))
  with check (user_id = (select auth.uid())
    and (obra_id is null or exists (select 1 from public.obras o where o.id = obra_id and o.user_id = (select auth.uid()))));
create policy processos_delete on public.processos for delete to authenticated using (user_id = (select auth.uid()));

create policy movimentos_select on public.processo_movimentos for select to authenticated using (user_id = (select auth.uid()));
create policy movimentos_insert on public.processo_movimentos for insert to authenticated
  with check (user_id = (select auth.uid())
    and exists (select 1 from public.processos p where p.id = processo_id and p.user_id = (select auth.uid())));
create policy movimentos_update on public.processo_movimentos for update to authenticated
  using (user_id = (select auth.uid()))
  with check (user_id = (select auth.uid())
    and exists (select 1 from public.processos p where p.id = processo_id and p.user_id = (select auth.uid())));
create policy movimentos_delete on public.processo_movimentos for delete to authenticated using (user_id = (select auth.uid()));

revoke all on public.processos, public.processo_movimentos from anon;
