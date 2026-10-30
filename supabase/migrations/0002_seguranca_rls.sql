-- =====================================================================
-- Segurança: cada usuário só lê e grava as próprias linhas (RLS).
-- Ao gravar, também se exige que o "pai" (obra, planilha, medição…)
-- pertença ao mesmo usuário — ninguém pendura dados na obra de outro.
-- =====================================================================

alter table public.obras          enable row level security;
alter table public.planilhas      enable row level security;
alter table public.itens          enable row level security;
alter table public.cronograma     enable row level security;
alter table public.medicoes       enable row level security;
alter table public.medicao_itens  enable row level security;
alter table public.fotos          enable row level security;
alter table public.notificacoes   enable row level security;

-- ---------- OBRAS ----------
create policy obras_select on public.obras for select to authenticated
  using (user_id = (select auth.uid()));
create policy obras_insert on public.obras for insert to authenticated
  with check (user_id = (select auth.uid()));
create policy obras_update on public.obras for update to authenticated
  using (user_id = (select auth.uid())) with check (user_id = (select auth.uid()));
create policy obras_delete on public.obras for delete to authenticated
  using (user_id = (select auth.uid()));

-- ---------- PLANILHAS ----------
create policy planilhas_select on public.planilhas for select to authenticated
  using (user_id = (select auth.uid()));
create policy planilhas_insert on public.planilhas for insert to authenticated
  with check (user_id = (select auth.uid())
    and exists (select 1 from public.obras o where o.id = obra_id and o.user_id = (select auth.uid())));
create policy planilhas_update on public.planilhas for update to authenticated
  using (user_id = (select auth.uid()))
  with check (user_id = (select auth.uid())
    and exists (select 1 from public.obras o where o.id = obra_id and o.user_id = (select auth.uid())));
create policy planilhas_delete on public.planilhas for delete to authenticated
  using (user_id = (select auth.uid()));

-- ---------- ITENS ----------
create policy itens_select on public.itens for select to authenticated
  using (user_id = (select auth.uid()));
create policy itens_insert on public.itens for insert to authenticated
  with check (user_id = (select auth.uid())
    and exists (select 1 from public.planilhas p where p.id = planilha_id and p.user_id = (select auth.uid())));
create policy itens_update on public.itens for update to authenticated
  using (user_id = (select auth.uid()))
  with check (user_id = (select auth.uid())
    and exists (select 1 from public.planilhas p where p.id = planilha_id and p.user_id = (select auth.uid())));
create policy itens_delete on public.itens for delete to authenticated
  using (user_id = (select auth.uid()));

-- ---------- CRONOGRAMA ----------
create policy cronograma_select on public.cronograma for select to authenticated
  using (user_id = (select auth.uid()));
create policy cronograma_insert on public.cronograma for insert to authenticated
  with check (user_id = (select auth.uid())
    and exists (select 1 from public.obras o where o.id = obra_id and o.user_id = (select auth.uid()))
    and (item_id is null or exists (select 1 from public.itens i where i.id = item_id and i.user_id = (select auth.uid()))));
create policy cronograma_update on public.cronograma for update to authenticated
  using (user_id = (select auth.uid()))
  with check (user_id = (select auth.uid())
    and exists (select 1 from public.obras o where o.id = obra_id and o.user_id = (select auth.uid()))
    and (item_id is null or exists (select 1 from public.itens i where i.id = item_id and i.user_id = (select auth.uid()))));
create policy cronograma_delete on public.cronograma for delete to authenticated
  using (user_id = (select auth.uid()));

-- ---------- MEDIÇÕES ----------
create policy medicoes_select on public.medicoes for select to authenticated
  using (user_id = (select auth.uid()));
create policy medicoes_insert on public.medicoes for insert to authenticated
  with check (user_id = (select auth.uid())
    and exists (select 1 from public.obras o where o.id = obra_id and o.user_id = (select auth.uid())));
create policy medicoes_update on public.medicoes for update to authenticated
  using (user_id = (select auth.uid()))
  with check (user_id = (select auth.uid())
    and exists (select 1 from public.obras o where o.id = obra_id and o.user_id = (select auth.uid())));
create policy medicoes_delete on public.medicoes for delete to authenticated
  using (user_id = (select auth.uid()));

-- ---------- ITENS MEDIDOS ----------
create policy medicao_itens_select on public.medicao_itens for select to authenticated
  using (user_id = (select auth.uid()));
create policy medicao_itens_insert on public.medicao_itens for insert to authenticated
  with check (user_id = (select auth.uid())
    and exists (select 1 from public.medicoes m where m.id = medicao_id and m.user_id = (select auth.uid()))
    and exists (select 1 from public.itens i where i.id = item_id and i.user_id = (select auth.uid())));
create policy medicao_itens_update on public.medicao_itens for update to authenticated
  using (user_id = (select auth.uid()))
  with check (user_id = (select auth.uid())
    and exists (select 1 from public.medicoes m where m.id = medicao_id and m.user_id = (select auth.uid()))
    and exists (select 1 from public.itens i where i.id = item_id and i.user_id = (select auth.uid())));
create policy medicao_itens_delete on public.medicao_itens for delete to authenticated
  using (user_id = (select auth.uid()));

-- ---------- FOTOS ----------
create policy fotos_select on public.fotos for select to authenticated
  using (user_id = (select auth.uid()));
create policy fotos_insert on public.fotos for insert to authenticated
  with check (user_id = (select auth.uid())
    and exists (select 1 from public.obras o where o.id = obra_id and o.user_id = (select auth.uid())));
create policy fotos_update on public.fotos for update to authenticated
  using (user_id = (select auth.uid()))
  with check (user_id = (select auth.uid())
    and exists (select 1 from public.obras o where o.id = obra_id and o.user_id = (select auth.uid())));
create policy fotos_delete on public.fotos for delete to authenticated
  using (user_id = (select auth.uid()));

-- ---------- NOTIFICAÇÕES ----------
create policy notificacoes_select on public.notificacoes for select to authenticated
  using (user_id = (select auth.uid()));
create policy notificacoes_insert on public.notificacoes for insert to authenticated
  with check (user_id = (select auth.uid())
    and exists (select 1 from public.obras o where o.id = obra_id and o.user_id = (select auth.uid())));
create policy notificacoes_update on public.notificacoes for update to authenticated
  using (user_id = (select auth.uid()))
  with check (user_id = (select auth.uid())
    and exists (select 1 from public.obras o where o.id = obra_id and o.user_id = (select auth.uid())));
create policy notificacoes_delete on public.notificacoes for delete to authenticated
  using (user_id = (select auth.uid()));

-- ---------- STORAGE: bucket privado de fotos ----------
-- Caminho obrigatório: <user_id>/<obra_id>/<arquivo>
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('fotos', 'fotos', false, 5242880, array['image/jpeg','image/png','image/webp'])
on conflict (id) do nothing;

create policy fotos_storage_select on storage.objects for select to authenticated
  using (bucket_id = 'fotos' and (storage.foldername(name))[1] = (select auth.uid())::text);
create policy fotos_storage_insert on storage.objects for insert to authenticated
  with check (bucket_id = 'fotos' and (storage.foldername(name))[1] = (select auth.uid())::text);
create policy fotos_storage_update on storage.objects for update to authenticated
  using (bucket_id = 'fotos' and (storage.foldername(name))[1] = (select auth.uid())::text);
create policy fotos_storage_delete on storage.objects for delete to authenticated
  using (bucket_id = 'fotos' and (storage.foldername(name))[1] = (select auth.uid())::text);
