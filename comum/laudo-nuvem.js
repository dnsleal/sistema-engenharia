// Salva e reabre no sistema qualquer formulário de laudo (HTML preenchível):
// guarda os campos, as caixas de marcar, o logo e as fotos (reduzidas) na tabela "laudos".
// A página define antes deste arquivo:
//   window.LAUDO_CFG = { tipo, titulo(), valor(), antes(dados), depois(dados), extra() }
(function () {
  const C = window.LAUDO_CFG || {};
  const { sb } = SE;
  const P = new URLSearchParams(location.search);
  let laudoId = P.get('id'), timer = null, salvando = false, carregando = false, silencio = 0;
  // mudanças feitas pelo próprio sistema (restaurar, reduzir foto) não contam como edição
  async function semAgendar(fn) {
    silencio++;
    try { return await fn(); }
    finally { setTimeout(() => { silencio--; }, 50); }
  }

  // ---------------------------------------------------------------- barra do sistema
  const css = document.createElement('style');
  css.textContent = `
    .se-barra{position:sticky;top:0;z-index:1000;display:flex;gap:8px;align-items:center;flex-wrap:wrap;
      background:#1f3864;color:#fff;padding:8px 14px;font:13px "Segoe UI",Arial,sans-serif;margin:0 0 12px}
    .se-barra a{color:#dbe4f5;text-decoration:none}
    .se-barra b{font-weight:600}
    .se-barra button{font:inherit;font-weight:600;padding:5px 12px;border-radius:5px;border:1px solid rgba(255,255,255,.5);background:transparent;color:#fff;cursor:pointer}
    .se-barra button.pri{background:#fff;color:#1f3864;border-color:#fff}
    .se-barra .st{opacity:.8;font-size:12px}
    .se-barra .sp{flex:1}
    body > .barra{top:44px!important}
    @media print{.se-barra{display:none!important}}`;
  document.head.appendChild(css);
  const barra = document.createElement('div');
  barra.className = 'se-barra no-print';
  barra.innerHTML = `<a href="../laudos/index.html">← Documentos</a><b>${C.nome || "Documento"}</b>
    <span class="st" id="seStatus">ainda não salvo no sistema</span><span class="sp"></span>
    <button id="seNovo">Novo</button><button id="seDuplicar">Duplicar</button><button class="pri" id="seSalvar">Salvar no sistema</button>`;
  document.body.prepend(barra);
  const status = t => document.getElementById('seStatus').textContent = t;

  // ---------------------------------------------------------------- campos
  const ignorar = el => el.closest('.se-barra') || ['file', 'button', 'submit', 'hidden', 'reset'].includes((el.type || '').toLowerCase());
  function campos() { return [...document.querySelectorAll('input, select, textarea')].filter(el => !ignorar(el)); }
  function chaves() {
    let i = 0;
    return campos().map(el => [el.id ? 'id:' + el.id : 'n:' + (i++), el]);
  }

  // reduz imagens grandes (fotos) para caber bem no banco
  function reduzir(src, lado = 1400, q = 0.8) {
    return new Promise(ok => {
      if (!src || !src.startsWith('data:') || src.length < 350000) return ok(src);
      const im = new Image();
      im.onload = () => {
        const k = Math.min(1, lado / Math.max(im.width, im.height));
        const cv = document.createElement('canvas');
        cv.width = Math.round(im.width * k); cv.height = Math.round(im.height * k);
        const cx = cv.getContext('2d'); cx.fillStyle = '#fff'; cx.fillRect(0, 0, cv.width, cv.height);
        cx.drawImage(im, 0, 0, cv.width, cv.height);
        ok(cv.toDataURL('image/jpeg', q));
      };
      im.onerror = () => ok(src);
      im.src = src;
    });
  }

  // ---- modo "html": guarda o miolo editável da página (textos contenteditable,
  //      linhas criadas na hora). O timbre fixo da página não é copiado para o banco.
  const imgsFixas = [];
  if (C.modo === 'html') document.querySelectorAll(C.container + ' img').forEach(im => {
    const s = im.getAttribute('src') || ''; if (s.startsWith('data:') && !imgsFixas.includes(s)) imgsFixas.push(s);
  });
  function serializarHtml() {
    const raiz = document.querySelector(C.container);
    // valores digitados viram atributos, para sobreviver ao innerHTML
    raiz.querySelectorAll('input').forEach(el => {
      if (el.type === 'checkbox' || el.type === 'radio') { if (el.checked) el.setAttribute('checked', ''); else el.removeAttribute('checked'); }
      else el.setAttribute('value', el.value);
    });
    raiz.querySelectorAll('textarea').forEach(el => { el.textContent = el.value; });
    raiz.querySelectorAll('select').forEach(el => [...el.options].forEach(o => { if (o.selected) o.setAttribute('selected', ''); else o.removeAttribute('selected'); }));
    let html = raiz.innerHTML;
    imgsFixas.forEach((s, i) => { html = html.split(s).join(`[[TIMBRE:${i}]]`); });
    return { versao: 1, modo: 'html', html, extra: C.extra ? C.extra() : null };
  }
  function restaurarHtml(d) {
    let html = d.html || '';
    imgsFixas.forEach((s, i) => { html = html.split(`[[TIMBRE:${i}]]`).join(s); });
    document.querySelector(C.container).innerHTML = html;
  }

  // ---- modo "local": a página guarda o próprio estado no navegador (localStorage).
  function lerLocal() { try { return JSON.parse(localStorage.getItem(C.chave) || 'null'); } catch (_) { return null; } }

  async function serializar() {
    if (C.modo === 'html') return serializarHtml();
    if (C.modo === 'local') return { versao: 1, modo: 'local', estado: lerLocal() };
    const valores = {};
    for (const [k, el] of chaves()) valores[k] = (el.type === 'checkbox' || el.type === 'radio') ? !!el.checked : el.value;
    const imagens = {};
    for (const im of document.querySelectorAll('img[id]')) {
      const s = im.getAttribute('src') || '';
      if (s.startsWith('data:')) { imagens[im.id] = await reduzir(s); if (imagens[im.id] !== s) im.src = imagens[im.id]; }
    }
    return { versao: 1, valores, imagens, extra: C.extra ? C.extra() : null };
  }

  function restaurar(d) {
    carregando = true;
    try {
      if (C.antes) C.antes(d);
      if (d.modo === 'html') { restaurarHtml(d); if (C.depois) C.depois(d); return; }
      for (const [k, el] of chaves()) {
        if (!(k in d.valores)) continue;
        if (el.type === 'checkbox' || el.type === 'radio') el.checked = !!d.valores[k];
        else el.value = d.valores[k];
      }
      for (const [id, src] of Object.entries(d.imagens || {})) {
        const im = document.getElementById(id); if (!im) continue;
        im.src = src; im.style.display = 'block';
        const ph = im.previousElementSibling; if (ph && /ph/i.test(ph.className || ph.id || '')) ph.style.display = 'none';
      }
      if (C.depois) C.depois(d);
    } finally { carregando = false; }
  }

  // ---------------------------------------------------------------- banco
  async function salvar(auto) {
    if (salvando) { clearTimeout(timer); timer = setTimeout(() => salvar(auto), 1500); return; }
    salvando = true; status('salvando…');
    try {
      const dados = await semAgendar(serializar);
      const reg = { tipo: C.tipo, titulo: (C.titulo && C.titulo().trim()) || 'Sem título', valor: C.valor ? C.valor() : null, dados };
      if (reg.valor != null && !isFinite(reg.valor)) reg.valor = null;
      let r;
      if (laudoId) r = await sb.from('laudos').update(reg).eq('id', laudoId).select('id').single();
      else r = await sb.from('laudos').insert(reg).select('id').single();
      if (r.error) throw r.error;
      if (!laudoId) { laudoId = r.data.id; history.replaceState(null, '', location.pathname + '?id=' + laudoId); }
      status('salvo no sistema às ' + new Date().toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' }));
    } catch (e) {
      status('erro ao salvar'); if (!auto) alert('Erro ao salvar: ' + e.message);
    } finally { salvando = false; }
  }

  function agendar() {
    if (carregando || silencio || !laudoId) return;
    status('alterações não salvas…');
    clearTimeout(timer); timer = setTimeout(() => salvar(true), 4000);
  }

  (async function iniciar() {
    // espera a página montar tabelas e campos dinâmicos (DOMContentLoaded) antes de restaurar
    if (document.readyState === 'loading') await new Promise(ok => document.addEventListener('DOMContentLoaded', ok, { once: true }));
    await new Promise(ok => setTimeout(ok, 0));
    const u = await SE.exigirLogin(); if (!u) return;

    // modo "local": "novo" limpa o estado guardado no navegador; abrir um documento grava o estado e recarrega uma vez
    if (C.modo === 'local') {
      if (P.get('novo')) { localStorage.removeItem(C.chave); location.replace(location.pathname); return; }
      if (laudoId) {
        const flag = 'se_rest_' + laudoId;
        if (sessionStorage.getItem(flag)) { sessionStorage.removeItem(flag); }
        else {
          status('abrindo…');
          const { data, error } = await sb.from('laudos').select('dados').eq('id', laudoId).single();
          if (error || !data) { status('documento não encontrado'); laudoId = null; return; }
          if (data.dados.estado) localStorage.setItem(C.chave, JSON.stringify(data.dados.estado)); else localStorage.removeItem(C.chave);
          sessionStorage.setItem(flag, '1');
          location.reload(); return;
        }
      }
    }

    document.getElementById('seSalvar').onclick = () => salvar(false);
    document.getElementById('seNovo').onclick = () => {
      if (C.modo === 'local') localStorage.removeItem(C.chave);
      location.href = location.pathname;
    };
    document.getElementById('seDuplicar').onclick = async () => {
      if (!laudoId) { alert('Salve este documento antes de duplicar.'); return; }
      const dados = await semAgendar(serializar);
      const { data, error } = await sb.from('laudos').insert({ tipo: C.tipo, titulo: 'Cópia de ' + ((C.titulo && C.titulo()) || 'laudo'), valor: C.valor ? C.valor() : null, dados }).select('id').single();
      if (error) { alert('Erro: ' + error.message); return; }
      location.href = location.pathname + '?id=' + data.id;
    };
    document.addEventListener('input', e => { if (!e.target.closest('.se-barra')) agendar(); }, true);
    document.addEventListener('change', e => { if (!e.target.closest('.se-barra')) setTimeout(agendar, 300); }, true);
    // fotos/logo trocados também contam como alteração
    new MutationObserver(ms => { if (ms.some(m => m.attributeName === 'src')) agendar(); })
      .observe(document.body, { subtree: true, attributes: true, attributeFilter: ['src'] });
    // linhas/fotos/cartões criados ou removidos (botões da própria página) também contam
    if (C.modo === 'html' || C.modo === 'local') {
      const alvo = C.modo === 'html' ? document.querySelector(C.container) : document.body;
      new MutationObserver(ms => {
        if (ms.some(m => m.type === 'childList' && !(m.target.closest && m.target.closest('.se-barra, #toast, #report-print-container')))) setTimeout(agendar, 700);
      }).observe(alvo, { subtree: true, childList: true });
    }
    window.addEventListener('beforeunload', e => { if (/não salvas/.test(document.getElementById('seStatus').textContent)) { e.preventDefault(); e.returnValue = ''; } });

    if (laudoId) {
      status('abrindo…');
      const { data, error } = await sb.from('laudos').select('*').eq('id', laudoId).single();
      if (error) { status('documento não encontrado'); laudoId = null; return; }
      if (C.modo !== 'local') await semAgendar(() => restaurar(data.dados));
      document.title = data.titulo + ' — ' + (C.nome || 'Laudo');
      status('salvo no sistema');
    }
  })();
})();
