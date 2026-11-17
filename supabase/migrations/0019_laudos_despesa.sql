-- Cálculo de despesas de serviços (serviços + deslocamento/estadia/alimentação, com imposto) salvo como documento.
alter table public.laudos drop constraint laudos_tipo_check;
alter table public.laudos add constraint laudos_tipo_check
  check (tipo in ('locacao','terreno','proposta','relatorio','spt','despesa'));
