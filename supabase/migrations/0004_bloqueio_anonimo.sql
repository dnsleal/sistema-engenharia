-- =====================================================================
-- Segunda camada: quem não fez login não consulta nenhuma tabela/view.
-- (O RLS já devolvia zero linhas; aqui a consulta passa a ser recusada.)
-- =====================================================================
revoke all on public.obras, public.planilhas, public.itens, public.cronograma,
              public.medicoes, public.medicao_itens, public.fotos, public.notificacoes,
              public.v_itens_saldo, public.v_medicoes_resumo, public.v_obras_resumo
  from anon;

-- tabelas criadas no futuro também nascem fechadas para anônimos
alter default privileges in schema public revoke all on tables from anon;
