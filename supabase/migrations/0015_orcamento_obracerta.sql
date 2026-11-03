-- =====================================================================
-- Fase 4b: app de orçamento ObraCerta dentro do sistema.
-- - orcamentos.app separa os orçamentos do ObraCerta ('obracerta') dos do
--   app anterior ('offline'), que continua em orcamento/classico.html
-- - composições próprias por usuário (orc_proprias)
-- - bases de preço importadas (ORSE, SEINFRA, SINAPI de outro mês…):
--   todos os usuários logados leem; só quem importou altera ou exclui
-- - importação em duas fases: as linhas entram numa "versão" nova, que só
--   passa a valer quando orc_base_publicar troca a versão ativa, numa única
--   transação. Se a importação cair no meio, a base antiga continua inteira.
-- =====================================================================

-- ---------- orçamentos: qual app gravou ----------
alter table public.orcamentos add column app text not null default 'offline'
  check (app in ('offline', 'obracerta'));
create index orcamentos_app_idx on public.orcamentos(user_id, app, updated_at desc);

-- ---------- COMPOSIÇÕES PRÓPRIAS ----------
create table public.orc_proprias (
  id          text primary key,
  user_id     uuid not null default auth.uid() references auth.users(id) on delete cascade,
  codigo      text not null,
  dados       jsonb not null,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);
create index orc_proprias_user_idx on public.orc_proprias(user_id, codigo);
create trigger orc_proprias_updated before update on public.orc_proprias
  for each row execute function public.tg_updated_at();

alter table public.orc_proprias enable row level security;
create policy orc_proprias_select on public.orc_proprias for select to authenticated
  using (user_id = (select auth.uid()));
create policy orc_proprias_insert on public.orc_proprias for insert to authenticated
  with check (user_id = (select auth.uid()));
create policy orc_proprias_update on public.orc_proprias for update to authenticated
  using (user_id = (select auth.uid())) with check (user_id = (select auth.uid()));
create policy orc_proprias_delete on public.orc_proprias for delete to authenticated
  using (user_id = (select auth.uid()));

-- ---------- BASES DE PREÇO IMPORTADAS ----------
create table public.orc_bases (
  id            text primary key,              -- ex.: ORSE-SE-2026-04
  user_id       uuid not null default auth.uid() references auth.users(id) on delete cascade,
  fonte         text not null,                 -- ORSE, SINAPI, SEINFRA…
  uf            text,
  referencia    text,                          -- AAAA-MM
  descricao     text,
  meta          jsonb not null default '{}'::jsonb,   -- nI, nC, nA, encargos…
  versao_itens  uuid,                          -- versão publicada dos preços (null = ainda não publicada)
  versao_anal   uuid,                          -- versão publicada do analítico
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now()
);
create index orc_bases_user_idx on public.orc_bases(user_id);
create trigger orc_bases_updated before update on public.orc_bases
  for each row execute function public.tg_updated_at();

create table public.orc_base_itens (
  id         bigint generated always as identity primary key,
  user_id    uuid not null default auth.uid() references auth.users(id) on delete cascade,
  base_id    text not null references public.orc_bases(id) on delete cascade,
  versao     uuid not null,
  tipo       text not null check (tipo in ('I', 'C')),
  codigo     text not null,
  descricao  text,
  unidade    text,
  grupo      text,
  preco_nd   numeric,
  preco_d    numeric,
  extra      jsonb
);
create index orc_base_itens_base_idx on public.orc_base_itens(base_id, versao);
create index orc_base_itens_user_idx on public.orc_base_itens(user_id);

create table public.orc_base_analitico (
  id           bigint generated always as identity primary key,
  user_id      uuid not null default auth.uid() references auth.users(id) on delete cascade,
  base_id      text not null references public.orc_bases(id) on delete cascade,
  versao       uuid not null,
  comp_codigo  text not null,
  item_tipo    text not null check (item_tipo in ('I', 'C')),
  item_codigo  text not null,
  coef         numeric not null
);
create index orc_base_analitico_base_idx on public.orc_base_analitico(base_id, versao);
create index orc_base_analitico_user_idx on public.orc_base_analitico(user_id);

alter table public.orc_bases          enable row level security;
alter table public.orc_base_itens     enable row level security;
alter table public.orc_base_analitico enable row level security;

-- leitura: qualquer usuário logado (são tabelas de referência de preço)
create policy orc_bases_select on public.orc_bases for select to authenticated using (true);
create policy orc_base_itens_select on public.orc_base_itens for select to authenticated using (true);
create policy orc_base_analitico_select on public.orc_base_analitico for select to authenticated using (true);

-- gravação: só o dono da base
create policy orc_bases_insert on public.orc_bases for insert to authenticated
  with check (user_id = (select auth.uid()));
create policy orc_bases_update on public.orc_bases for update to authenticated
  using (user_id = (select auth.uid())) with check (user_id = (select auth.uid()));
create policy orc_bases_delete on public.orc_bases for delete to authenticated
  using (user_id = (select auth.uid()));

create policy orc_base_itens_insert on public.orc_base_itens for insert to authenticated
  with check (user_id = (select auth.uid())
    and exists (select 1 from public.orc_bases b where b.id = base_id and b.user_id = (select auth.uid())));
create policy orc_base_itens_delete on public.orc_base_itens for delete to authenticated
  using (user_id = (select auth.uid()));

create policy orc_base_analitico_insert on public.orc_base_analitico for insert to authenticated
  with check (user_id = (select auth.uid())
    and exists (select 1 from public.orc_bases b where b.id = base_id and b.user_id = (select auth.uid())));
create policy orc_base_analitico_delete on public.orc_base_analitico for delete to authenticated
  using (user_id = (select auth.uid()));

revoke all on public.orc_proprias, public.orc_bases, public.orc_base_itens, public.orc_base_analitico from anon;

-- ---------- publicar a versão importada (tudo ou nada) ----------
-- Troca a versão ativa e apaga as versões antigas e as importações abandonadas.
create or replace function public.orc_base_publicar(
  p_base text, p_versao_itens uuid default null, p_versao_anal uuid default null,
  p_meta jsonb default '{}'::jsonb
) returns jsonb
language plpgsql security invoker set search_path = '' as $$
declare v_itens int; v_anal int;
begin
  if p_versao_itens is null and p_versao_anal is null then
    raise exception 'Nada para publicar.';
  end if;
  update public.orc_bases
     set versao_itens = coalesce(p_versao_itens, versao_itens),
         versao_anal  = coalesce(p_versao_anal, versao_anal),
         meta = meta || coalesce(p_meta, '{}'::jsonb)
   where id = p_base and user_id = (select auth.uid());
  if not found then
    raise exception 'Base % não encontrada ou de outro usuário.', p_base;
  end if;
  if p_versao_itens is not null then
    select count(*) into v_itens from public.orc_base_itens where base_id = p_base and versao = p_versao_itens;
    if v_itens = 0 then raise exception 'A versão importada não tem nenhum item.'; end if;
    delete from public.orc_base_itens where base_id = p_base and versao <> p_versao_itens;
  end if;
  if p_versao_anal is not null then
    select count(*) into v_anal from public.orc_base_analitico where base_id = p_base and versao = p_versao_anal;
    if v_anal = 0 then raise exception 'A versão importada não tem nenhuma linha do analítico.'; end if;
    delete from public.orc_base_analitico where base_id = p_base and versao <> p_versao_anal;
  end if;
  return jsonb_build_object('itens', v_itens, 'analitico', v_anal);
end $$;

-- Descarta uma importação que falhou no meio (a versão ativa não é tocada).
create or replace function public.orc_base_descartar(p_base text, p_versao uuid)
returns void
language plpgsql security invoker set search_path = '' as $$
begin
  delete from public.orc_base_itens i using public.orc_bases b
   where i.base_id = p_base and i.versao = p_versao and b.id = i.base_id
     and i.versao is distinct from b.versao_itens;
  delete from public.orc_base_analitico a using public.orc_bases b
   where a.base_id = p_base and a.versao = p_versao and b.id = a.base_id
     and a.versao is distinct from b.versao_anal;
  -- base criada agora e nunca publicada: some junto
  delete from public.orc_bases
   where id = p_base and user_id = (select auth.uid()) and versao_itens is null and versao_anal is null;
end $$;

revoke execute on function public.orc_base_publicar(text, uuid, uuid, jsonb) from public, anon;
grant execute on function public.orc_base_publicar(text, uuid, uuid, jsonb) to authenticated;
revoke execute on function public.orc_base_descartar(text, uuid) from public, anon;
grant execute on function public.orc_base_descartar(text, uuid) to authenticated;
