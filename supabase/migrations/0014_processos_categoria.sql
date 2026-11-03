-- Categoria do processo, para filtrar a lista.
-- Valores fixos usados pela tela: Resposta a vereador, ACP/TAC, PSCIP,
-- Manutenção, Diversos. Em "Outros" a tela grava o texto digitado.
alter table public.processos add column if not exists categoria text;
create index if not exists processos_categoria_idx on public.processos(user_id, categoria);
