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

  // Lê TODAS as linhas de uma consulta, em lotes. O Supabase devolve no máximo
  // 1.000 linhas por pedido; sem isso, obras grandes apareceriam pela metade.
  // Uso: const linhas = await SE.todos(() => sb.from('itens').select('*').eq(...).order('ordem'));
  async function todos(consulta, lote = 1000) {
    const saida = [];
    for (let de = 0; ; de += lote) {
      const { data, error } = await consulta().range(de, de + lote - 1);
      if (error) throw error;
      saida.push(...data);
      if (data.length < lote) return saida;
    }
  }

  window.SE = { sb, exigirLogin, sair, raiz, todos };
})();
