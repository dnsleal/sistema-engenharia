// Liga o app de orçamento ao Sistema de Engenharia:
// login, orçamentos salvos no banco, base SINAPI-MT pronta, composição analítica
// e "virar planilha da obra". Roda depois do script do app e usa as funções dele
// (P, save, render, fillMeta, saveBase, loadBases, numbering, itemCalc, computeAll…).
(function () {
  const { sb } = SE;
  const BASES_PRONTAS = 'bases/index.json';
  const n2 = v => Number(v || 0).toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const trunc2 = x => Math.floor(Math.abs(x) * 100 + 1e-7) / 100 * Math.sign(x || 1);
  let usuario = null;

  // ---------------------------------------------------------------- login
  (async () => {
    usuario = await SE.exigirLogin();
    if (!usuario) return;
    status(P.nuvemId ? 'salvo no sistema' : 'ainda não salvo no sistema');
    // primeiro acesso neste navegador: carrega a base pronta sozinho
    await esperar(() => DB.db || BASES.length, 4000);
    if (!BASES.some(b => b.banco === 'SINAPI')) carregarPronto(true);
  })();

  function esperar(cond, ms) {
    return new Promise(ok => { const t0 = Date.now(); (function v() { if (cond() || Date.now() - t0 > ms) ok(); else setTimeout(v, 100); })(); });
  }
  function status(t) { const s = document.getElementById('nuvemStatus'); if (s) s.textContent = t; }

  // ---------------------------------------------------------------- salvar / abrir no banco
  let tNuvem = null, salvando = false;
  const _save = save;
  // toda gravação local também agenda a gravação no sistema (se o orçamento já foi salvo lá)
  save = function () {
    _save();
    if (P.nuvemId) { status('alterações não salvas…'); clearTimeout(tNuvem); tNuvem = setTimeout(() => salvarNuvem(true), 3500); }
  };

  async function salvarNuvem(automatico) {
    if (salvando) { clearTimeout(tNuvem); tNuvem = setTimeout(() => salvarNuvem(automatico), 1500); return; }
    salvando = true;
    try {
      const { nuvemId, nuvemObra, ...resto } = P;
      const total = computeAll().TG;
      const reg = {
        titulo: (P.meta.obra || '').trim() || 'Sem título', total,
        dados: { app: 'orcamento-offline', versao: 1, basesUsadas: usedBasesMeta(), meta: resto.meta, rows: resto.rows },
        obra_id: nuvemObra || null
      };
      let r;
      if (nuvemId) r = await sb.from('orcamentos').update(reg).eq('id', nuvemId).select('id').single();
      else r = await sb.from('orcamentos').insert(reg).select('id').single();
      if (r.error) throw r.error;
      P.nuvemId = r.data.id; _save();
      status('salvo no sistema às ' + new Date().toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' }));
      if (!automatico) toast('Orçamento salvo no sistema');
    } catch (e) {
      status('erro ao salvar'); toast('Erro ao salvar no sistema: ' + e.message, 6000);
    } finally { salvando = false; }
  }
  document.getElementById('bSalvarNuvem').onclick = () => salvarNuvem(false);

  document.getElementById('bAbrir').onclick = async () => {
    openModal('<h2>Orçamentos salvos no sistema</h2><div class="small muted">Carregando…</div>');
    const { data, error } = await sb.from('orcamentos').select('id, titulo, total, updated_at, obra_id, obras(nome)').order('updated_at', { ascending: false });
    if (error) { $('#modalBox').innerHTML = `<h2>Erro</h2><p>${esc(error.message)}</p><div class="acts"><button onclick="closeModal()">Fechar</button></div>`; return; }
    $('#modalBox').innerHTML = `<h2>Orçamentos salvos no sistema</h2>
      ${data.length ? `<table class="simple"><tr><th>Orçamento</th><th>Obra vinculada</th><th class="n">Total (R$)</th><th>Atualizado</th><th></th></tr>
        ${data.map(o => `<tr><td><b>${esc(o.titulo)}</b>${o.id === P.nuvemId ? ' <span class="badge c">aberto</span>' : ''}</td>
          <td class="small">${esc(o.obras ? o.obras.nome : '—')}</td><td class="n">${n2(o.total)}</td>
          <td class="small">${new Date(o.updated_at).toLocaleString('pt-BR')}</td>
          <td style="white-space:nowrap"><button class="pri" data-abrir="${o.id}">Abrir</button> <button class="danger" data-excluir="${o.id}">Excluir</button></td></tr>`).join('')}</table>`
        : '<p class="muted">Nenhum orçamento salvo ainda. Use o botão <b>Salvar</b> no topo.</p>'}
      <div class="acts"><button onclick="closeModal()">Fechar</button></div>`;
    $$('[data-abrir]').forEach(b => b.onclick = () => abrirNuvem(b.dataset.abrir));
    $$('[data-excluir]').forEach(b => b.onclick = async () => {
      if (!confirm('Excluir este orçamento do sistema? Não dá para desfazer.')) return;
      const { error: e } = await sb.from('orcamentos').delete().eq('id', b.dataset.excluir);
      if (e) { toast('Erro: ' + e.message); return; }
      if (b.dataset.excluir === P.nuvemId) { delete P.nuvemId; delete P.nuvemObra; _save(); status('ainda não salvo no sistema'); }
      document.getElementById('bAbrir').click();
    });
  };

  async function abrirNuvem(id) {
    if (P.rows.length && P.nuvemId !== id && !P.nuvemId && !confirm('O orçamento aberto agora não foi salvo no sistema. Abrir outro mesmo assim?')) return;
    const { data, error } = await sb.from('orcamentos').select('*').eq('id', id).single();
    if (error) { toast('Erro: ' + error.message); return; }
    const j = data.dados;
    P = { meta: { ...DEFAULT_META(), ...j.meta }, rows: j.rows || [], nuvemId: data.id, nuvemObra: data.obra_id };
    if (j.basesUsadas) for (const b of j.basesUsadas) if (!BASES.find(x => x.id === b.id)) BASES.push({ ...b, count: 0, fantasma: true, ativa: false });
    undoStack = []; selId = null;
    closeModal(); fillMeta(); _save(); render();
    status('salvo no sistema'); toast('Orçamento aberto');
  }

  // "Novo" do app: o orçamento novo começa fora do sistema
  const bNovo = document.getElementById('bNovo'), novoOriginal = bNovo.onclick;
  bNovo.onclick = () => { const antes = P; novoOriginal(); if (P !== antes) status('ainda não salvo no sistema'); };

  // ---------------------------------------------------------------- base SINAPI-MT pronta
  async function carregarPronto(automatico) {
    let lista;
    try { lista = await (await fetch(BASES_PRONTAS, { cache: 'no-cache' })).json(); }
    catch (e) { if (!automatico) toast('Não consegui buscar a lista de bases prontas: ' + e.message, 6000); return; }
    let esc_ = lista[0];
    if (!automatico && lista.length > 1) {
      const nomes = lista.map((b, i) => `${i + 1}) ${b.rotulo}`).join('\n');
      const k = parseInt(prompt('Qual base carregar?\n' + nomes, '1'), 10);
      if (!(k >= 1 && k <= lista.length)) return;
      esc_ = lista[k - 1];
    }
    toast(`${automatico ? 'Primeiro acesso neste navegador: ' : ''}carregando ${esc_.rotulo}…`, 20000);
    try {
      const j = await (await fetch('bases/' + esc_.arquivo)).json();
      for (const b of j.bases) {
        await saveBase({ banco: b.banco, uf: b.uf, mes: b.mes, regime: b.regime, tipoLabel: b.tipo },
          b.itens.map(([codigo, descricao, unidade, preco]) => ({ codigo, descricao, unidade, preco, tipo: b.tipoItem })), b.sheet);
      }
      const chave = `${j.banco}:${j.uf}:${j.mes}`;
      await KV.set('ana:' + chave, j.analitico);
      await KV.set('mo:' + chave, j.maoDeObra);
      await KV.set('as:' + chave, j.precosAS || null);
      cacheAna[chave] = { ana: j.analitico, mo: j.maoDeObra, as: j.precosAS || null };
      await loadBases();
      const n = j.bases.reduce((s, b) => s + b.itens.length, 0);
      toast(`${esc_.rotulo}: ${n.toLocaleString('pt-BR')} itens carregados (desonerado e não desonerado).`, 6000);
    } catch (e) { toast('Erro ao carregar a base: ' + e.message, 8000); }
  }
  document.getElementById('bSinapiPronto').onclick = () => carregarPronto(false);

  // ---------------------------------------------------------------- composição analítica
  const cacheAna = {};
  async function analitico(chave) {
    if (!cacheAna[chave]) {
      const ana = await KV.get('ana:' + chave, null), mo = await KV.get('mo:' + chave, null), as = await KV.get('as:' + chave, null);
      if (!ana) return null;
      cacheAna[chave] = { ana, mo, as };
    }
    return cacheAna[chave];
  }

  document.getElementById('bAna').onclick = async () => {
    const i = selIndex(); if (i < 0) { toast('Selecione um item da planilha'); return; }
    const r = P.rows[i];
    if (r.tipo !== 'item') { toast('Selecione um item (não uma etapa)'); return; }
    const b = BASEMAP()[r.baseId];
    if (!b || b.banco !== 'SINAPI') { toast('O analítico está disponível para itens do SINAPI'); return; }
    mostrarAnalitico(String(r.codigo).trim(), b, []);
  };

  async function mostrarAnalitico(codigo, b, pilha) {
    const chave = `${b.banco}:${b.uf}:${b.mes}`;
    const A = await analitico(chave);
    if (!A) { toast(`Analítico de ${b.mes} não está neste navegador. Clique em “Carregar SINAPI-MT pronto” em Bancos de dados.`, 7000); return; }
    const linhas = A.ana[codigo];
    if (!linhas) { toast(`O código ${codigo} não tem composição analítica (é insumo ou não existe em ${b.mes}).`, 5000); return; }
    // preços do mesmo banco/UF/mês/regime
    const ids = new Set(BASES.filter(x => x.banco === b.banco && x.uf === b.uf && x.mes === b.mes && x.regime === b.regime).map(x => x.id));
    const preco = {};
    for (const it of ITENS) if (ids.has(it.baseId)) preco[(it.tipo || '') + it.codigo] = it;
    const comp = preco['C' + codigo];
    const AS = A.as ? A.as[b.regime] || {} : {};
    let soma = 0, faltam = 0, usouAS = 0;
    const tr = linhas.map(([t, cod, coef]) => {
      let it = preco[t + cod], marcaAS = '';
      // insumo sem preço em MT: a CAIXA usa o preço de São Paulo (%AS)
      if (!it && t === 'I' && AS[cod]) { it = { descricao: AS[cod][0], unidade: AS[cod][1], preco: AS[cod][2] }; marcaAS = ' <span class="badge warn" title="Sem preço em MT: preço de São Paulo, como faz a CAIXA">%AS</span>'; usouAS++; }
      const p = it ? it.preco : null;
      const tot = p == null ? null : trunc2(coef * p);
      if (tot == null) faltam++; else soma += tot;
      const link = t === 'C' ? `<a href="#" data-sub="${esc(cod)}">${esc(cod)}</a>` : esc(cod);
      return `<tr><td><span class="badge ${t === 'C' ? 'c' : 'i'}">${t === 'C' ? 'Comp.' : 'Insumo'}</span></td><td style="font-family:Consolas,monospace">${link}</td>
        <td>${esc(it ? it.descricao : '(sem preço em ' + b.uf + ')')}${marcaAS}</td><td>${esc(it ? it.unidade : '')}</td>
        <td class="n">${coef.toLocaleString('pt-BR', { maximumFractionDigits: 7 })}</td><td class="n">${p == null ? '—' : n2(p)}</td><td class="n">${tot == null ? '—' : n2(tot)}</td></tr>`;
    }).join('');
    soma = Math.round(soma * 100) / 100;
    const mo = A.mo && A.mo[b.regime === 'Desonerado' ? 'CD' : 'SD'] ? A.mo[b.regime === 'Desonerado' ? 'CD' : 'SD'][codigo] : null;
    const confere = comp && Math.abs(soma - comp.preco) < 0.011;
    openModal(`<h2>Composição analítica ${esc(codigo)}</h2>
      <div class="small muted" style="margin-bottom:6px">${esc(b.banco)} ${esc(b.uf)} ${esc(b.mes)} · ${esc(b.regime)}${mo != null ? ` · mão de obra ${n2(mo * 100)}% do custo` : ''}</div>
      <div style="margin-bottom:8px"><b>${esc(comp ? comp.descricao : '')}</b> ${comp ? '(' + esc(comp.unidade) + ')' : ''}</div>
      <div style="overflow:auto;max-height:55vh"><table class="simple"><tr><th>Tipo</th><th>Código</th><th>Descrição</th><th>Und</th><th class="n">Coeficiente</th><th class="n">Preço unit.</th><th class="n">Total</th></tr>${tr}
        <tr><td colspan="6"><b>Soma dos itens (truncados em 2 casas)</b></td><td class="n"><b>${n2(soma)}</b></td></tr>
        ${comp ? `<tr><td colspan="6">Custo oficial da composição</td><td class="n">${n2(comp.preco)}</td></tr>` : ''}</table></div>
      <p class="small ${confere ? 'bdiok' : 'bdiwarn'}">${comp ? (confere ? '✓ A soma confere com o custo oficial.' + (usouAS ? ` ${usouAS} insumo(s) sem preço em ${b.uf} com preço de São Paulo (%AS), como faz a CAIXA.` : '') : `A soma difere do custo oficial em ${n2(Math.abs(soma - comp.preco))}${faltam ? ` (${faltam} item(ns) sem preço em ${b.uf})` : ''}.`) : 'Composição sem custo em ' + b.uf + ' neste mês.'}</p>
      <div class="acts">${pilha.length ? '<button id="anaVoltar">← Voltar</button>' : ''}<button class="pri" onclick="closeModal()">Fechar</button></div>`);
    $$('[data-sub]').forEach(a => a.onclick = e => { e.preventDefault(); mostrarAnalitico(a.dataset.sub, b, [...pilha, codigo]); });
    const v = document.getElementById('anaVoltar');
    if (v) v.onclick = () => mostrarAnalitico(pilha[pilha.length - 1], b, pilha.slice(0, -1));
  }

  // ---------------------------------------------------------------- virar planilha da obra
  document.getElementById('bParaObra').onclick = async () => {
    const itensP = P.rows.filter(r => r.tipo === 'item');
    if (!itensP.length) { toast('A planilha está vazia'); return; }
    const semEtapa = P.rows.findIndex(r => r.tipo === 'etapa') < 0;
    const ref = computeAll(P.meta, true);
    const d = Number(P.meta.desconto || 0);
    const { data: obras, error } = await sb.from('obras').select('id, nome, status').order('nome');
    if (error) { toast('Erro: ' + error.message); return; }
    openModal(`<h2>Virar planilha da obra</h2>
      <p class="small muted" style="margin-top:0">O orçamento é gravado na obra como <b>planilha original</b> ou como <b>aditivo</b>, com o preço unitário com BDI e sem desconto.
      O desconto do contrato (${n2(d)}%) é aplicado pelo sistema sobre o total, como no boletim de medição.</p>
      <div class="grid">
        <div class="w2"><label>Obra</label><select id="vObra">
          <option value="__nova">+ Criar obra nova: “${esc(P.meta.obra || 'Sem nome')}”</option>
          ${obras.map(o => `<option value="${o.id}" ${o.id === P.nuvemObra ? 'selected' : ''}>${esc(o.nome)}</option>`).join('')}</select></div>
        <div><label>Gravar como</label><select id="vTipo"><option value="original">Planilha original</option><option value="aditivo">Aditivo</option></select></div>
        <div><label>Nº do aditivo</label><input id="vNum" type="number" min="1" value="1" disabled></div>
      </div>
      <table class="simple" style="margin-top:10px;max-width:520px">
        <tr><td>Linhas</td><td class="n">${P.rows.length} (${itensP.length} itens)</td></tr>
        <tr><td>Total com BDI, sem desconto</td><td class="n"><b>${n2(ref.TG)}</b></td></tr>
        <tr><td>Com o desconto de ${n2(d)}% sobre o total</td><td class="n"><b>${n2(Math.round(ref.TG * (1 - d / 100) * 100) / 100)}</b></td></tr>
      </table>
      ${semEtapa ? '<p class="small bdiwarn">A planilha não tem etapas: o cronograma e o boletim por etapa ficam sem agrupamento.</p>' : ''}
      <div id="vMsg" class="small" style="margin-top:8px"></div>
      <div class="acts"><button onclick="closeModal()">Cancelar</button><button class="pri" id="vOk">Gravar na obra</button></div>`);
    const vTipo = document.getElementById('vTipo'), vNum = document.getElementById('vNum');
    vTipo.onchange = () => { vNum.disabled = vTipo.value !== 'aditivo'; };
    document.getElementById('vOk').onclick = () => gravarNaObra(document.getElementById('vObra').value, vTipo.value, parseInt(vNum.value, 10) || 1);
  };

  async function gravarNaObra(obraSel, tipo, numAd) {
    const msg = t => { document.getElementById('vMsg').innerHTML = t; };
    const ok = document.getElementById('vOk'); ok.disabled = true;
    try {
      let obraId = obraSel;
      if (obraSel === '__nova') {
        if (tipo !== 'original') throw new Error('Obra nova começa pela planilha original.');
        const { data, error } = await sb.from('obras').insert({
          nome: (P.meta.obra || '').trim() || 'Obra sem nome', contratante: P.meta.orgao || null, endereco: P.meta.local || null,
          bdi_pct: Number(P.meta.bdi || 0), desconto_pct: Number(P.meta.desconto || 0), fonte_precos: bancosTexto().replace(/\n/g, ' · ') || null
        }).select('id').single();
        if (error) throw error;
        obraId = data.id;
      }
      const numero = tipo === 'original' ? 0 : numAd;
      const { data: ja } = await sb.from('planilhas').select('id').eq('obra_id', obraId).eq('tipo', tipo).eq('numero', numero).maybeSingle();
      if (ja) {
        const { count } = await sb.from('itens').select('id', { count: 'exact', head: true }).eq('planilha_id', ja.id);
        if (count && !confirm(`A obra já tem ${tipo === 'original' ? 'planilha original' : 'o aditivo ' + numero} com ${count} linhas. Substituir?`)) { ok.disabled = false; return; }
      }
      // monta as linhas no formato da função importar_planilha
      const nums = numbering();
      let etapaAtual = null;
      const itens = P.rows.map((r, i) => {
        const ordem = i + 1;
        if (r.tipo === 'etapa') {
          if (r.nivel === 1) etapaAtual = ordem;
          return { ordem, nivel: r.nivel, item: nums[i], tipo: 'etapa', descricao: r.descricao || '(etapa sem nome)', etapa_ordem: r.nivel === 1 ? null : etapaAtual };
        }
        const c = itemCalc(r, P.meta, true);
        return {
          ordem, nivel: r.nivel, item: nums[i], tipo: 'servico', codigo: r.codigo || null, banco: r.banco || null,
          descricao: r.descricao || '(sem descrição)', unidade: r.und || null, quantidade: Number(r.quant) || 0,
          pu_sem_bdi: Number(r.vu) || 0, pu_com_bdi: c.vb, etapa_ordem: etapaAtual
        };
      });
      msg('Gravando…');
      const { data, error } = await sb.rpc('importar_planilha', {
        p_obra_id: obraId, p_tipo: tipo, p_numero: numero, p_itens: itens, p_cronograma: [],
        p_descricao: tipo === 'original' ? 'Planilha original (orçamento)' : `Aditivo ${numero} (orçamento)`, p_data: null
      });
      if (error) throw error;
      if (tipo === 'original' && obraSel !== '__nova') {
        // completa BDI/desconto/bases da obra, sem apagar o que já estiver preenchido
        const { data: o } = await sb.from('obras').select('bdi_pct, desconto_pct, fonte_precos').eq('id', obraId).single();
        const upd = {};
        if (o.bdi_pct == null) upd.bdi_pct = Number(P.meta.bdi || 0);
        if (o.desconto_pct == null || Number(o.desconto_pct) === 0) upd.desconto_pct = Number(P.meta.desconto || 0);
        if (!o.fonte_precos) upd.fonte_precos = bancosTexto().replace(/\n/g, ' · ') || null;
        if (Object.keys(upd).length) await sb.from('obras').update(upd).eq('id', obraId);
      }
      P.nuvemObra = obraId;
      await salvarNuvem(true);
      msg(`<span class="bdiok">✓ Gravado: ${data.itens} linhas na obra.</span> <a href="../obras/obra.html?id=${obraId}">Abrir a obra →</a>`);
      ok.textContent = 'Gravado';
    } catch (e) {
      msg(`<span class="bdibad">Erro: ${esc(e.message)}</span>`); ok.disabled = false;
    }
  }
})();
