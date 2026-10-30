-- =====================================================================
-- Sistema de Engenharia — Fase 0
-- Núcleo de obras: obras, planilhas (original/aditivos), itens,
-- cronograma, medições (BM), itens medidos, fotos e notificações.
-- Cada linha pertence a um usuário (user_id) e só ele a enxerga (RLS).
-- =====================================================================

-- ---------- utilidades ----------
create or replace function public.tg_updated_at()
returns trigger language plpgsql set search_path = '' as $$
begin
  new.updated_at := now();
  return new;
end $$;

-- ---------- OBRAS ----------
create table public.obras (
  id              uuid primary key default gen_random_uuid(),
  user_id         uuid not null default auth.uid() references auth.users(id) on delete cascade,
  nome            text not null,
  objeto          text,
  endereco        text,
  contratante     text,
  contratada      text,
  cnpj_contratada text,
  num_contrato    text,
  processo_siged  text,
  valor_contrato  numeric(14,2),
  desconto_pct    numeric(7,4) default 0,
  bdi_pct         numeric(7,4),
  data_inicio     date,
  prazo_dias      integer,
  termino_vigente date,
  reajuste_pct    numeric(7,4) default 0,
  tipo_obra       text not null default 'obra' check (tipo_obra in ('obra','reforma')),
  status          text not null default 'em_andamento'
                  check (status in ('em_andamento','paralisada','concluida','encerrada')),
  observacoes     text,
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now()
);
create index obras_user_idx on public.obras(user_id);
create trigger obras_updated before update on public.obras
  for each row execute function public.tg_updated_at();

-- ---------- PLANILHAS (original e aditivos, medidos em separado) ----------
create table public.planilhas (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null default auth.uid() references auth.users(id) on delete cascade,
  obra_id     uuid not null references public.obras(id) on delete cascade,
  tipo        text not null check (tipo in ('original','aditivo')),
  numero      integer not null default 0,          -- 0 = original; 1, 2… = aditivo
  descricao   text,
  data        date,
  created_at  timestamptz not null default now(),
  unique (obra_id, tipo, numero),
  check ((tipo = 'original' and numero = 0) or (tipo = 'aditivo' and numero > 0))
);
create index planilhas_obra_idx on public.planilhas(obra_id);
create index planilhas_user_idx on public.planilhas(user_id);

-- ---------- ITENS da planilha (etapas e serviços) ----------
create table public.itens (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null default auth.uid() references auth.users(id) on delete cascade,
  planilha_id uuid not null references public.planilhas(id) on delete cascade,
  ordem       integer not null default 0,
  item        text,                                 -- numeração: 1, 1.1, 1.1.1
  tipo        text not null default 'servico' check (tipo in ('etapa','servico')),
  codigo      text,
  banco       text,                                 -- SINAPI, SICRO, próprio…
  descricao   text not null,
  unidade     text,
  quantidade  numeric(16,4) not null default 0,
  pu_sem_bdi  numeric(14,2),
  pu_com_bdi  numeric(14,2),
  created_at  timestamptz not null default now()
);
create index itens_planilha_idx on public.itens(planilha_id, ordem);
create index itens_user_idx on public.itens(user_id);

-- ---------- CRONOGRAMA (previsto acumulado por etapa/item e período) ----------
create table public.cronograma (
  id            uuid primary key default gen_random_uuid(),
  user_id       uuid not null default auth.uid() references auth.users(id) on delete cascade,
  obra_id       uuid not null references public.obras(id) on delete cascade,
  item_id       uuid references public.itens(id) on delete cascade,   -- etapa ou serviço
  periodo       integer not null check (periodo > 0),                 -- mês 1, 2, 3…
  data_fim      date,
  pct_previsto  numeric(7,4) not null check (pct_previsto between 0 and 100),
  unique (obra_id, item_id, periodo)
);
create index cronograma_obra_idx on public.cronograma(obra_id);
create index cronograma_item_idx on public.cronograma(item_id);
create index cronograma_user_idx on public.cronograma(user_id);

-- ---------- MEDIÇÕES (Boletins de Medição) ----------
create table public.medicoes (
  id              uuid primary key default gen_random_uuid(),
  user_id         uuid not null default auth.uid() references auth.users(id) on delete cascade,
  obra_id         uuid not null references public.obras(id) on delete cascade,
  numero          integer not null check (numero > 0),
  periodo_inicio  date,
  periodo_fim     date,
  reajuste_pct    numeric(7,4) not null default 0,
  fechada         boolean not null default false,
  fechada_em      timestamptz,
  observacoes     text,
  created_at      timestamptz not null default now(),
  unique (obra_id, numero)
);
create index medicoes_obra_idx on public.medicoes(obra_id);
create index medicoes_user_idx on public.medicoes(user_id);

create table public.medicao_itens (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null default auth.uid() references auth.users(id) on delete cascade,
  medicao_id  uuid not null references public.medicoes(id) on delete cascade,
  item_id     uuid not null references public.itens(id) on delete cascade,
  quantidade  numeric(16,4) not null default 0,     -- executado NO PERÍODO
  unique (medicao_id, item_id)
);
create index medicao_itens_item_idx on public.medicao_itens(item_id);
create index medicao_itens_user_idx on public.medicao_itens(user_id);

-- BM fechado não aceita alteração nas quantidades
create or replace function public.tg_bm_fechado()
returns trigger language plpgsql set search_path = '' as $$
declare v_fechada boolean;
begin
  select m.fechada into v_fechada
    from public.medicoes m
   where m.id = coalesce(new.medicao_id, old.medicao_id);
  if v_fechada then
    raise exception 'Este BM está fechado: reabra-o antes de alterar as quantidades.';
  end if;
  return coalesce(new, old);
end $$;
create trigger medicao_itens_bloqueio
  before insert or update or delete on public.medicao_itens
  for each row execute function public.tg_bm_fechado();

-- registra a data de fechamento automaticamente
create or replace function public.tg_bm_fechamento()
returns trigger language plpgsql set search_path = '' as $$
begin
  if new.fechada and not old.fechada then new.fechada_em := now(); end if;
  if not new.fechada then new.fechada_em := null; end if;
  return new;
end $$;
create trigger medicoes_fechamento before update on public.medicoes
  for each row execute function public.tg_bm_fechamento();

-- ---------- FOTOS (arquivo no Storage, bucket "fotos") ----------
create table public.fotos (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null default auth.uid() references auth.users(id) on delete cascade,
  obra_id     uuid not null references public.obras(id) on delete cascade,
  medicao_id  uuid references public.medicoes(id) on delete set null,
  item_id     uuid references public.itens(id) on delete set null,
  caminho     text not null,                         -- <user_id>/<obra_id>/<arquivo>
  legenda     text,
  data        date,
  ordem       integer not null default 0,
  created_at  timestamptz not null default now()
);
create index fotos_obra_idx on public.fotos(obra_id);
create index fotos_medicao_idx on public.fotos(medicao_id);
create index fotos_item_idx on public.fotos(item_id);
create index fotos_user_idx on public.fotos(user_id);

-- ---------- NOTIFICAÇÕES à contratada ----------
create table public.notificacoes (
  id              uuid primary key default gen_random_uuid(),
  user_id         uuid not null default auth.uid() references auth.users(id) on delete cascade,
  obra_id         uuid not null references public.obras(id) on delete cascade,
  numero          text,
  data            date not null default current_date,
  assunto         text not null,
  descricao       text,
  prazo           date,
  respondida      boolean not null default false,
  data_resposta   date,
  processo_siged  text,
  created_at      timestamptz not null default now()
);
create index notificacoes_obra_idx on public.notificacoes(obra_id);
create index notificacoes_user_idx on public.notificacoes(user_id);
