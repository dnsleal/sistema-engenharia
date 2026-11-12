// Endereço e chave PÚBLICA do projeto Supabase.
// A chave publishable pode ficar no código: quem protege os dados é o RLS do banco.
// NUNCA coloque aqui a chave secreta (service_role / sb_secret_...).
// Para instalar uma cópia nova, troque os dois valores pelos do seu projeto.
window.SE_CONFIG = {
  SUPABASE_URL: 'https://qwmvejmjtennukqqhlil.supabase.co',
  SUPABASE_KEY: 'sb_publishable_nc5OeDbk2tcNZZ_yvivhrA_1ESmWcY4',
  NOME_SISTEMA: 'Sistema Integrado de Engenharia',
  // Nome usado pelo D.I.E.G.O. na saudação da tela de entrada ("BEM-VINDO, DIEGO.")
  NOME_OPERADOR: 'Diego',
  // ID do cliente OAuth do Google (público). Vazio = botões do Drive avisam que falta configurar.
  GOOGLE_CLIENT_ID: '567086241384-20jd956hfu18jdds2h0aq41q8iheh65v.apps.googleusercontent.com',
  // Padrões dos orçamentos novos (app de orçamento). Tudo pode ser trocado depois em "Dados e BDI".
  ORCAMENTO: {
    orgao: 'SECRETARIA MUNICIPAL DE SAÚDE',
    municipio: 'Cuiabá - MT',
    local: 'Cuiabá – MT',
    responsavel: 'Diego Leal',
    crea: 'Engenheiro Civil - CREA-MT 37420',
    matricula: '',
    adm: 6            // taxa de administração da obra (% sobre o custo direto); 0 = não incluir
  }
};
