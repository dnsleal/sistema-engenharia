-- =====================================================================
-- Fase 4: orçamentos salvos no banco (o projeto inteiro do app de orçamento
-- fica em "dados", como no arquivo .json), ligados opcionalmente a uma obra.
-- =====================================================================
create table public.orcamentos (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null default auth.uid() references auth.users(id) on delete cascade,
  titulo      text not null default 'Sem título',
  obra_id     uuid references public.obras(id) on delete set null,
  total       numeric(16,2),
  dados       jsonb not null,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);
create index orcamentos_user_idx on public.orcamentos(user_id, updated_at desc);
create index orcamentos_obra_idx on public.orcamentos(obra_id);
create trigger orcamentos_updated before update on public.orcamentos
  for each row execute function public.tg_updated_at();

alter table public.orcamentos enable row level security;
create policy orcamentos_select on public.orcamentos for select to authenticated
  using (user_id = (select auth.uid()));
create policy orcamentos_insert on public.orcamentos for insert to authenticated
  with check (user_id = (select auth.uid())
    and (obra_id is null or exists (select 1 from public.obras o where o.id = obra_id and o.user_id = (select auth.uid()))));
create policy orcamentos_update on public.orcamentos for update to authenticated
  using (user_id = (select auth.uid()))
  with check (user_id = (select auth.uid())
    and (obra_id is null or exists (select 1 from public.obras o where o.id = obra_id and o.user_id = (select auth.uid()))));
create policy orcamentos_delete on public.orcamentos for delete to authenticated
  using (user_id = (select auth.uid()));

revoke all on public.orcamentos from anon;
