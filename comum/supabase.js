// Conexão com o Supabase e controle de login, usados por todas as páginas.
// Requer, antes deste arquivo: supabase-js (CDN) e comum/config.js
(function () {
  const cfg = window.SE_CONFIG;
  const sb = window.supabase.createClient(cfg.SUPABASE_URL, cfg.SUPABASE_KEY, {
    auth: { persistSession: true, autoRefreshToken: true }
  });

  // Caminho até a raiz do site, a partir da página atual (funciona em subpastas).
  function raiz() {
    const s = document.querySelector('script[src$="comum/supabase.js"]');
    return s ? s.getAttribute('src').replace('comum/supabase.js', '') : './';
  }

  // Exige login: se não houver sessão, manda para a tela de login.
  async function exigirLogin() {
    const { data } = await sb.auth.getSession();
    if (!data.session) {
      location.replace(raiz() + 'login.html?voltar=' + encodeURIComponent(location.pathname + location.search));
      return null;
    }
    return data.session.user;
  }

  async function sair() {
    await sb.auth.signOut();
    location.replace(raiz() + 'login.html');
  }

  window.SE = { sb, exigirLogin, sair, raiz };
})();
