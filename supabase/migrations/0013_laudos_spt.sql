-- Boletim de sondagem SPT (NBR 6484:2020) salvo como documento.
alter table public.laudos drop constraint laudos_tipo_check;
alter table public.laudos add constraint laudos_tipo_check
  check (tipo in ('locacao','terreno','proposta','relatorio','spt'));
comment on table public.laudos is 'Documentos salvos: laudos (locação, terreno), propostas, relatórios de vistoria e boletins de sondagem SPT';
