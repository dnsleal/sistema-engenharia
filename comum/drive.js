// Google Drive: botões "Salvar no Drive" (formato Google, editável) e
// "Exportar no Drive" (PDF, Word .docx ou Excel .xlsx).
// O sistema só enxerga os arquivos e pastas que ele mesmo criou (permissão drive.file).
//
// Uso numa página:
//   Drive.botoes({
//     barra: '.ferramentas',              // onde pôr os botões (seletor ou função)
//     alvo: '.folha',                     // o que vira documento (seletor; vários = várias páginas)
//     nome: () => document.title,         // nome do arquivo
//     pasta: () => ['Obras', 'CMEI X', 'Notificações'],   // dentro de "Sistema de Engenharia"
//     salvar: 'doc' | 'planilha',         // formato do "Salvar no Drive" (padrão: doc)
//     formatos: ['pdf', 'docx', 'xlsx'],  // opções do "Exportar"
//     xlsx: () => workbook,               // opcional: planilha pronta (SheetJS)
//     remover: '.algo, .outro'            // opcional: o que não entra no documento
//   });
(function () {
  const CFG = window.SE_CONFIG || {};
  const CID = CFG.GOOGLE_CLIENT_ID || '';
  const RAIZ = 'Sistema de Engenharia';
  const API = 'https://www.googleapis.com/drive/v3';
  const UP = 'https://www.googleapis.com/upload/drive/v3';
  const MIME = {
    pasta: 'application/vnd.google-apps.folder',
    gdoc: 'application/vnd.google-apps.document',
    gsheet: 'application/vnd.google-apps.spreadsheet',
    pdf: 'application/pdf',
    docx: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    xlsx: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    json: 'application/json'
  };
  const LIBS = {
    gsi: 'https://accounts.google.com/gsi/client',
    xlsx: 'https://cdn.jsdelivr.net/npm/xlsx@0.18.5/dist/xlsx.full.min.js',
    pdf: 'https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.1/html2pdf.bundle.min.js'
  };
  const REMOVER = 'script, style, button, input[type=file], .no-print, .se-barra, .ferramentas, .barra, .aviso, .drv-caixa, #drvAviso, #toast, [data-drive="fora"]';

  // ------------------------------------------------------------------ utilidades
  const carregadas = {};
  function carregar(url) {
    if (url === LIBS.xlsx && window.XLSX) return Promise.resolve();
    if (url === LIBS.pdf && window.html2pdf) return Promise.resolve();
    if (url === LIBS.gsi && window.google && google.accounts) return Promise.resolve();
    return carregadas[url] = carregadas[url] || new Promise((ok, erro) => {
      const s = document.createElement('script');
      s.src = url; s.async = true; s.onload = ok;
      s.onerror = () => { delete carregadas[url]; erro(new Error('não consegui carregar ' + url.split('/')[2])); };
      document.head.appendChild(s);
    });
  }
  const limparNome = s => String(s || 'Documento').replace(/[\\/:*?"<>|]+/g, '-').replace(/\s+/g, ' ').trim().slice(0, 150);
  const sess = {
    get: k => { try { return sessionStorage.getItem(k); } catch (_) { return null; } },
    set: (k, v) => { try { sessionStorage.setItem(k, v); } catch (_) {} },
    del: k => { try { sessionStorage.removeItem(k); } catch (_) {} }
  };

  // ------------------------------------------------------------------ login Google
  let token = null, expira = 0;
  if (CID) carregar(LIBS.gsi).catch(() => {});     // já deixa pronto: o pedido de login precisa ser imediato ao clique
  async function obterToken() {
    if (!CID) throw new Error('O Google Drive ainda não foi configurado no sistema (falta o ID do cliente Google em comum/config.js).');
    if (token && Date.now() < expira - 60000) return token;
    await carregar(LIBS.gsi);
    return new Promise((ok, erro) => {
      const cli = google.accounts.oauth2.initTokenClient({
        client_id: CID,
        scope: 'https://www.googleapis.com/auth/drive.file',
        callback: r => {
          if (r.error) return erro(new Error('O Google recusou o acesso: ' + r.error));
          token = r.access_token; expira = Date.now() + (r.expires_in || 3600) * 1000; ok(token);
        },
        error_callback: e => erro(new Error(e && e.type === 'popup_closed' ? 'A janela do Google foi fechada antes de autorizar.'
          : e && e.type === 'popup_failed_to_open' ? 'O navegador bloqueou a janela do Google: permita pop-ups para este site e tente de novo.'
          : 'Falha no login do Google.'))
      });
      cli.requestAccessToken({ prompt: '' });
    });
  }

  async function api(url, opt = {}) {
    const t = await obterToken();
    const r = await fetch(url, { ...opt, headers: { ...(opt.headers || {}), Authorization: 'Bearer ' + t } });
    if (r.status === 401) { token = null; throw new Error('A autorização do Google expirou. Clique de novo.'); }
    if (!r.ok) {
      let m = r.status + ''; try { const j = await r.json(); m = (j.error && j.error.message) || m; } catch (_) {}
      throw new Error('Google Drive: ' + m);
    }
    return opt.blob ? r.blob() : r.status === 204 ? null : r.json();
  }
  const q = s => s.replace(/\\/g, '\\\\').replace(/'/g, "\\'");

  // ------------------------------------------------------------------ pastas e arquivos
  async function pasta(caminho) {
    const nomes = [RAIZ, ...(caminho || []).filter(Boolean).map(limparNome)];
    const chave = 'drv_pasta:' + nomes.join('/');
    const salvo = sess.get(chave);
    if (salvo) {
      try { const f = await api(`${API}/files/${salvo}?fields=id,trashed`); if (!f.trashed) return salvo; } catch (_) {}
      sess.del(chave);
    }
    let pai = 'root';
    for (const nome of nomes) {
      const busca = await api(`${API}/files?q=${encodeURIComponent(`name='${q(nome)}' and mimeType='${MIME.pasta}' and '${pai}' in parents and trashed=false`)}&fields=files(id)&pageSize=1`);
      if (busca.files.length) pai = busca.files[0].id;
      else pai = (await api(`${API}/files?fields=id`, { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: nome, mimeType: MIME.pasta, parents: [pai] }) })).id;
    }
    sess.set(chave, pai);
    return pai;
  }

  // grava um arquivo; se já existe um com o mesmo nome na pasta, substitui (o Drive guarda as versões dos arquivos comuns)
  async function enviar(blob, nome, caminho, converterPara) {
    const pid = await pasta(caminho);
    const existe = (await api(`${API}/files?q=${encodeURIComponent(`name='${q(nome)}' and '${pid}' in parents and trashed=false`)}&fields=files(id,mimeType)`)).files;
    const alvoMime = converterPara || blob.type;
    const mesmo = existe.find(f => f.mimeType === alvoMime);
    if (mesmo && !converterPara) {
      return api(`${UP}/files/${mesmo.id}?uploadType=media&fields=id,name,webViewLink`, { method: 'PATCH', headers: { 'Content-Type': blob.type }, body: blob });
    }
    // documento Google: a versão anterior vai para a lixeira (fica lá 30 dias)
    if (mesmo) await api(`${API}/files/${mesmo.id}`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ trashed: true }) });
    const meta = { name: nome, parents: [pid] };
    if (converterPara) meta.mimeType = converterPara;
    const form = new FormData();
    form.append('metadata', new Blob([JSON.stringify(meta)], { type: 'application/json' }));
    form.append('file', blob);
    return api(`${UP}/files?uploadType=multipart&fields=id,name,webViewLink`, { method: 'POST', body: form });
  }
  const exportarArquivo = (id, mime) => api(`${API}/files/${id}/export?mimeType=${encodeURIComponent(mime)}`, { blob: true });
  const excluir = id => api(`${API}/files/${id}`, { method: 'DELETE' });

  // ------------------------------------------------------------------ montagem do documento
  const ESTILOS = ['font-size', 'font-weight', 'font-style', 'color', 'background-color', 'text-align', 'vertical-align', 'text-decoration-line',
    'border-top', 'border-right', 'border-bottom', 'border-left', 'padding-top', 'padding-right', 'padding-bottom', 'padding-left'];
  function elementos(alvo) {
    const l = typeof alvo === 'function' ? alvo() : [...document.querySelectorAll(alvo)];
    return (Array.isArray(l) ? l : [l]).filter(Boolean);
  }
  function svgParaImg(svg) {
    return new Promise(ok => {
      const r = svg.getBoundingClientRect();
      const w = Math.max(1, Math.round(r.width)), h = Math.max(1, Math.round(r.height));
      const c = svg.cloneNode(true);
      c.setAttribute('xmlns', 'http://www.w3.org/2000/svg'); c.setAttribute('width', w); c.setAttribute('height', h);
      const url = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(new XMLSerializer().serializeToString(c));
      const im = new Image();
      im.onload = () => {
        const cv = document.createElement('canvas'); cv.width = w * 2; cv.height = h * 2;
        const cx = cv.getContext('2d'); cx.fillStyle = '#fff'; cx.fillRect(0, 0, cv.width, cv.height); cx.drawImage(im, 0, 0, cv.width, cv.height);
        ok({ src: cv.toDataURL('image/png'), w, h });
      };
      im.onerror = () => ok(null);
      im.src = url;
    });
  }
  // copia uma página para documento: valores dos campos viram texto, gráficos viram imagem
  async function clonar(el, cfg, comEstilo) {
    const orig = [el, ...el.querySelectorAll('*')];
    const copia = el.cloneNode(true);
    const cop = [copia, ...copia.querySelectorAll('*')];
    const remover = REMOVER + (cfg.remover ? ', ' + cfg.remover : '');
    const tarefas = [];
    orig.forEach((o, i) => {
      const c = cop[i]; if (!c) return;
      const cs = getComputedStyle(o);
      if (i && (o.matches(remover) || (cs.display === 'none' && !o.closest('svg')))) { c.dataset.drvFora = '1'; return; }
      if (comEstilo && !(o instanceof SVGElement)) {
        let st = '';
        for (const p of ESTILOS) {
          const v = cs.getPropertyValue(p);
          if (!v || v === 'normal' || v === 'none' || v === 'rgba(0, 0, 0, 0)' || v === '0px' || /^0px none/.test(v) || v === 'start' || v === 'baseline') continue;
          st += `${p}:${v};`;
        }
        if (st) c.setAttribute('style', st + (c.getAttribute('style') || ''));
      }
      const tag = o.tagName;
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || tag === 'OUTPUT') {
        let v = tag === 'SELECT' ? (o.selectedOptions[0] ? o.selectedOptions[0].text : '') : o.value;
        if (o.type === 'checkbox' || o.type === 'radio') v = o.checked ? '☒' : '☐';
        const s = document.createElement('span');
        s.textContent = v || '';
        s.setAttribute('style', `font-size:${cs.fontSize};font-weight:${cs.fontWeight};white-space:pre-wrap;`);
        c.replaceWith(s);
      } else if (tag === 'svg' && !o.parentElement.closest('svg')) {
        tarefas.push(svgParaImg(o).then(r => { if (!r) return; const im = document.createElement('img'); im.src = r.src; im.width = r.w; im.height = r.h; im.style.maxWidth = '100%'; c.replaceWith(im); }));
      } else if (tag === 'CANVAS') {
        try { const im = document.createElement('img'); im.src = o.toDataURL('image/png'); im.style.maxWidth = '100%'; c.replaceWith(im); } catch (_) {}
      } else if (tag === 'IMG' && o.currentSrc && !o.getAttribute('src').startsWith('data:')) {
        c.setAttribute('src', o.currentSrc);                    // endereço completo (o Google busca a imagem)
      }
      if (c.removeAttribute) { c.removeAttribute('contenteditable'); c.removeAttribute('spellcheck'); }
    });
    await Promise.all(tarefas);
    copia.querySelectorAll('[data-drv-fora]').forEach(n => n.remove());
    if (copia.dataset && copia.dataset.drvFora) return null;
    return copia;
  }

  async function htmlDoc(cfg, titulo) {
    const partes = [];
    for (const el of elementos(cfg.alvo)) { const c = await clonar(el, cfg, true); if (c) partes.push(c.outerHTML); }
    if (!partes.length) throw new Error('Não há conteúdo para enviar.');
    return `<!doctype html><html><head><meta charset="utf-8"><title>${titulo.replace(/</g, '&lt;')}</title>
      <style>body{font-family:Arial,Helvetica,sans-serif;font-size:11pt} table{border-collapse:collapse} img{max-width:100%}</style></head>
      <body>${partes.join('<p style="page-break-before:always"></p>')}</body></html>`;
  }

  async function gerarPdf(cfg) {
    await carregar(LIBS.pdf);
    // o conteúdo não pode ter posição fora da tela (o html2canvas o desenharia em branco): quem fica fora é o invólucro
    // largura útil da página em px (96 dpi): o conteúdo é ajustado a ela para não ser cortado
    const mg = cfg.margemPdf ?? 8, m4 = Array.isArray(mg) ? mg : [mg, mg, mg, mg];
    const larg = Math.floor(((cfg.paisagem ? 297 : 210) - m4[1] - m4[3]) * 96 / 25.4);
    const fora = document.createElement('div');
    fora.style.cssText = `position:fixed;left:-10000px;top:0;width:${larg}px;height:0;overflow:visible;`;
    const caixa = document.createElement('div');
    caixa.className = 'drv-pdf';
    caixa.style.cssText = `width:${larg}px;background:#fff;`;
    fora.appendChild(caixa);
    const css = document.createElement('style');
    css.textContent = '.drv-pdf *{box-shadow:none!important} .drv-pdf > *{margin:0!important} .drv-pdf .folha{min-height:0!important} .drv-pdf .drv-quebra{page-break-before:always}' + (cfg.cssPdf || '');
    caixa.appendChild(css);
    const els = elementos(cfg.alvo);
    for (let i = 0; i < els.length; i++) {
      const c = await clonar(els[i], cfg, false); if (!c) continue;
      if (i) { const qb = document.createElement('div'); qb.className = 'html2pdf__page-break'; caixa.appendChild(qb); }
      c.style.width = '100%'; c.style.maxWidth = '100%'; c.style.boxSizing = 'border-box';
      caixa.appendChild(c);
    }
    document.body.appendChild(fora);
    try {
      return await html2pdf().set({
        margin: m4, image: { type: 'jpeg', quality: 0.93 },
        html2canvas: { scale: 2, useCORS: true, backgroundColor: '#ffffff', logging: false },
        jsPDF: { unit: 'mm', format: 'a4', orientation: cfg.paisagem ? 'landscape' : 'portrait' },
        pagebreak: { mode: ['css', 'legacy'], avoid: ['tr', 'img', '.foto', '.assin'] }
      }).from(caixa).outputPdf('blob');
    } finally { fora.remove(); }
  }

  async function gerarXlsx(cfg) {
    await carregar(LIBS.xlsx);
    if (cfg.xlsx) return cfg.xlsx();
    const wb = XLSX.utils.book_new();
    let n = 0;
    for (const el of elementos(cfg.alvo)) {
      const tabs = el.tagName === 'TABLE' ? [el] : [...el.querySelectorAll('table')];
      for (const t of tabs) {
        if (t.closest('svg') || !t.rows.length) continue;
        const ws = XLSX.utils.table_to_sheet(t, { raw: false });
        XLSX.utils.book_append_sheet(wb, ws, 'Tabela ' + (++n));
      }
    }
    if (!n) throw new Error('Este documento não tem tabelas para virar planilha.');
    return wb;
  }
  const wbBlob = wb => new Blob([XLSX.write(wb, { bookType: 'xlsx', type: 'array' })], { type: MIME.xlsx });
  const temTabela = cfg => !!cfg.xlsx || elementos(cfg.alvo).some(el => el.tagName === 'TABLE' || el.querySelector('table'));

  // ------------------------------------------------------------------ ações
  async function acao(cfg, tipo) {
    const nome = limparNome(cfg.nome ? cfg.nome() : document.title);
    const caminho = cfg.pasta ? cfg.pasta() : [];
    // pede o login antes de montar o arquivo (o navegador só abre a janela do Google logo após o clique)
    await obterToken();
    if (tipo === 'gdoc' && cfg.salvar === 'planilha') tipo = 'gsheet';
    if (tipo === 'gdoc') {
      avisar('Preparando o documento…', true);
      const html = await htmlDoc(cfg, nome);
      avisar('Enviando para o Drive…', true);
      return enviar(new Blob([html], { type: 'text/html' }), nome, caminho, MIME.gdoc);
    }
    if (tipo === 'gsheet') {
      avisar('Preparando a planilha…', true);
      return enviar(wbBlob(await gerarXlsx(cfg)), nome, caminho, MIME.gsheet);
    }
    if (tipo === 'pdf') {
      avisar('Gerando o PDF…', true);
      const b = await gerarPdf(cfg);
      avisar('Enviando para o Drive…', true);
      return enviar(new Blob([b], { type: MIME.pdf }), nome + '.pdf', caminho);
    }
    if (tipo === 'xlsx') {
      avisar('Gerando o Excel…', true);
      return enviar(wbBlob(await gerarXlsx(cfg)), nome + '.xlsx', caminho);
    }
    if (tipo === 'docx') {
      // o Google converte a página num documento e o exporta como Word; o temporário é apagado
      avisar('Gerando o Word…', true);
      const html = await htmlDoc(cfg, nome);
      const tmp = await enviar(new Blob([html], { type: 'text/html' }), nome + ' (temporário)', caminho, MIME.gdoc);
      try {
        const docx = await exportarArquivo(tmp.id, MIME.docx);
        avisar('Enviando para o Drive…', true);
        return await enviar(new Blob([docx], { type: MIME.docx }), nome + '.docx', caminho);
      } finally { excluir(tmp.id).catch(() => {}); }
    }
  }

  async function executar(cfg, tipo, botao) {
    if (botao) botao.disabled = true;
    try {
      const r = await acao(cfg, tipo);
      const onde = [RAIZ, ...(cfg.pasta ? cfg.pasta() : [])].filter(Boolean).join(' / ');
      avisar(`✓ Salvo no Drive em <b>${esc(onde)}</b>${r && r.webViewLink ? ` — <a href="${r.webViewLink}" target="_blank" rel="noopener">abrir</a>` : ''}`, false, 9000);
      return r;
    } catch (e) {
      avisar('⚠ ' + esc(e.message), false, 10000, true);
    } finally { if (botao) botao.disabled = false; }
  }

  // ------------------------------------------------------------------ interface
  const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const css = document.createElement('style');
  css.textContent = `
    .drv-caixa{position:relative;display:inline-flex;gap:6px;align-items:center}
    .drv-menu{position:absolute;top:calc(100% + 4px);right:0;z-index:2000;background:#fff;color:#1f2937;border:1px solid #cbd5e1;border-radius:8px;
      box-shadow:0 8px 24px rgba(0,0,0,.18);padding:4px;min-width:190px;font:13px "Segoe UI",Arial,sans-serif;display:none}
    .drv-menu.aberto{display:block}
    .drv-menu button{display:block;width:100%;text-align:left;background:none!important;border:none!important;color:#1f2937!important;padding:8px 10px!important;border-radius:6px;cursor:pointer;font:inherit!important}
    .drv-menu button:hover{background:#eef2f8!important}
    .drv-menu small{color:#64748b;display:block;font-size:11px}
    #drvAviso{position:fixed;left:50%;bottom:22px;transform:translateX(-50%);z-index:3000;background:#1f3864;color:#fff;padding:10px 16px;border-radius:8px;
      font:13px "Segoe UI",Arial,sans-serif;box-shadow:0 6px 20px rgba(0,0,0,.25);max-width:min(560px,92vw);display:none}
    #drvAviso.erro{background:#b42318} #drvAviso a{color:#cfe0ff;font-weight:600}
    @media print{.drv-caixa,#drvAviso{display:none!important}}`;
  document.head.appendChild(css);
  let timerAviso = null;
  function avisar(html, fixo, ms = 6000, erro) {
    let a = document.getElementById('drvAviso');
    if (!a) { a = document.createElement('div'); a.id = 'drvAviso'; a.setAttribute('role', 'status'); document.body.appendChild(a); }
    a.innerHTML = html; a.className = erro ? 'erro' : ''; a.style.display = 'block';
    clearTimeout(timerAviso);
    if (!fixo) timerAviso = setTimeout(() => { a.style.display = 'none'; }, ms);
  }

  function botoes(cfg) {
    const montar = () => {
      const barra = typeof cfg.barra === 'function' ? cfg.barra() : document.querySelector(cfg.barra);
      if (!barra) return false;
      if (barra.querySelector('.drv-caixa')) return true;
      const fmts = (cfg.formatos || ['pdf', 'docx', 'xlsx']);
      const caixa = document.createElement('span');
      caixa.className = 'drv-caixa';
      caixa.innerHTML = `<button type="button" class="${cfg.classe || 'sec'}" data-drv="salvar" title="Grava como ${cfg.salvar === 'planilha' ? 'Planilha Google' : 'Documento Google'}, editável no Drive">Salvar no Drive</button>
        <button type="button" class="${cfg.classe || 'sec'}" data-drv="menu" aria-haspopup="true">Exportar no Drive ▾</button>
        <div class="drv-menu" role="menu">
          ${fmts.includes('pdf') ? '<button type="button" data-fmt="pdf">PDF<small>como fica impresso</small></button>' : ''}
          ${fmts.includes('docx') ? '<button type="button" data-fmt="docx">Word (.docx)<small>para editar no Word</small></button>' : ''}
          ${fmts.includes('xlsx') ? '<button type="button" data-fmt="xlsx">Excel (.xlsx)<small>tabelas do documento</small></button>' : ''}
        </div>`;
      if (cfg.antesDe) barra.insertBefore(caixa, barra.querySelector(cfg.antesDe)); else barra.appendChild(caixa);
      const menu = caixa.querySelector('.drv-menu');
      caixa.querySelector('[data-drv="salvar"]').onclick = e => executar(cfg, 'gdoc', e.currentTarget);
      caixa.querySelector('[data-drv="menu"]').onclick = e => {
        e.stopPropagation();
        const x = menu.querySelector('[data-fmt="xlsx"]');
        if (x) x.style.display = temTabela(cfg) ? '' : 'none';
        menu.classList.toggle('aberto');
      };
      menu.querySelectorAll('[data-fmt]').forEach(b => b.onclick = e => { menu.classList.remove('aberto'); executar(cfg, b.dataset.fmt, caixa.querySelector('[data-drv="menu"]')); });
      document.addEventListener('click', e => { if (!caixa.contains(e.target)) menu.classList.remove('aberto'); });
      return true;
    };
    if (!montar()) {                                    // barra criada depois (ex.: barra dos documentos salvos)
      const ob = new MutationObserver(() => { if (montar()) ob.disconnect(); });
      ob.observe(document.body, { childList: true, subtree: true });
    }
  }

  // envio direto de um arquivo pronto (ex.: backup)
  async function enviarArquivo(blob, nome, caminho, converterPara) {
    await obterToken();
    return enviar(blob, limparNome(nome), caminho, converterPara);
  }

  window.Drive = { botoes, executar, enviarArquivo, avisar, configurado: () => !!CID, MIME, obterToken, carregar, LIBS };
})();
