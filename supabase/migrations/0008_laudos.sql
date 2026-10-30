-- =====================================================================
-- Fase 5: laudos de avaliação (locação SMECEL e terreno urbano).
-- O formulário inteiro (campos, fotos e logo comprimidos) fica em "dados".
-- =====================================================================
create table public.laudos (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null default auth.uid() references auth.users(id) on delete cascade,
  tipo        text not null check (tipo in ('locacao','terreno')),
  titulo      text not null default 'Sem título',
  valor       numeric(16,2),
  dados       jsonb not null,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);
create index laudos_user_idx on public.laudos(user_id, updated_at desc);
create trigger laudos_updated before update on public.laudos
  for each row execute function public.tg_updated_at();

alter table public.laudos enable row level security;
create policy laudos_select on public.laudos for select to authenticated using (user_id = (select auth.uid()));
create policy laudos_insert on public.laudos for insert to authenticated with check (user_id = (select auth.uid()));
create policy laudos_update on public.laudos for update to authenticated
  using (user_id = (select auth.uid())) with check (user_id = (select auth.uid()));
create policy laudos_delete on public.laudos for delete to authenticated using (user_id = (select auth.uid()));

revoke all on public.laudos from anon;
