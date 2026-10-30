// Leitura da planilha orçamentária e do cronograma físico-financeiro.
// Recebe as linhas de uma aba já convertidas pelo SheetJS e devolve itens prontos
// para a função importar_planilha do banco. Funciona no navegador e no Node (testes).
(function (raiz) {

  const norm = s => String(s ?? '').normalize('NFD').replace(/[̀-ͯ]/g, '')
    .toUpperCase().replace(/\s+/g, ' ').trim();
  const txt = v => (v == null ? '' : String(v).trim());
  const num = v => {
    if (v == null || v === '') return null;
    if (typeof v === 'number') return Number.isFinite(v) ? v : null;
    let t = String(v).trim().replace(/\s|R\$/g, '');
    if (!t || t.startsWith('#')) return null;
    if (t.includes(',')) t = t.replace(/\./g, '').replace(',', '.');
    const n = Number(t);
    return Number.isFinite(n) ? n : null;
  };
  // Arredonda como o Excel: primeiro limpa o "ruído" de ponto flutuante
  // (38,5 × 210,67 = 8110,794999… vira 8110,795) e depois arredonda meio para cima.
  const r2 = n => {
    const limpo = Number(Number(n).toPrecision(15));
    return Math.sign(limpo) * Math.round(Math.abs(limpo) * 100 + 1e-9) / 100;
  };
  // aceita 0,245 ou 24,5 → devolve em %
  const comoPct = v => { const n = num(v); return n == null ? null : (Math.abs(n) <= 1 ? n * 100 : n); };

  // ---------------------------------------------------------------------------
  // Orçamento
  // rawRows: valores crus (números como números); txtRows: o texto como aparece no Excel
  // ---------------------------------------------------------------------------
  function lerOrcamento(rawRows, txtRows) {
    txtRows = txtRows || rawRows;
    const avisos = [];

    // 1. linha de cabeçalho: tem "Item" e "Unid" e "Quant"
    let h = -1;
    for (let r = 0; r < Math.min(rawRows.length, 60); r++) {
      const cel = (rawRows[r] || []).map(norm);
      if (cel.some(c => c === 'ITEM' || c === 'ITENS') && cel.some(c => c.startsWith('UNID') || c === 'UN' || c === 'UND')
          && cel.some(c => c.startsWith('QUANT') || c.startsWith('QTD') || c.startsWith('QTDE'))) { h = r; break; }
    }
    if (h < 0) throw new Error('Não encontrei a linha de cabeçalho (com "Item", "Unid." e "Quant.").');

    const cab = (rawRows[h] || []).map(norm);
    const acha = (fn, de = 0) => { for (let c = de; c < cab.length; c++) if (fn(cab[c])) return c; return -1; };
    const col = {};
    col.item = acha(c => c === 'ITEM' || c === 'ITENS');
    col.unidade = acha(c => c.startsWith('UNID') || c === 'UN' || c === 'UND');
    col.quant = acha(c => c.startsWith('QUANT') || c.startsWith('QTD'));
    col.puSem = acha(c => c.includes('SEM BDI'));
    col.bdi = acha(c => c.startsWith('BDI'));
    col.puCom = acha(c => c.includes('COM BDI') && (c.includes('UNIT') || c.startsWith('PR') || c.startsWith('P.U') || c.startsWith('PU')) && !c.includes('TOTAL'));
    col.total = acha(c => c.includes('TOTAL'));
    col.descricao = acha(c => c.includes('DESCRI') || c.includes('ORCAMENTO') || c.includes('SERVICO') || c.includes('DISCRIMINA'));
    if (col.descricao < 0 || col.descricao >= col.unidade) col.descricao = col.unidade - 1;
    // entre "Item" e "Descrição": 2 colunas = banco + código; 1 coluna = código
    const meio = col.descricao - col.item - 1;
    col.banco = meio >= 2 ? col.item + 1 : -1;
    col.codigo = meio >= 1 ? col.descricao - 1 : -1;
    if (col.puCom < 0) col.puCom = acha(c => c.includes('UNIT'), col.quant + 1);
    for (const k of ['item', 'unidade', 'quant', 'puCom']) {
      if (col[k] < 0) throw new Error('Coluna não encontrada no cabeçalho: ' + k);
    }

    // 2. dados do cabeçalho da obra (linhas acima)
    const meta = { contratante: [], fonte_precos: txt(rawRows[h][col.banco >= 0 ? col.banco : col.codigo]).replace(/\s*\n\s*/g, ' · ') || null };
    for (let r = 0; r < h; r++) {
      const t = txt((rawRows[r] || [])[0]);
      if (!t) continue;
      const n = norm(t);
      if (n.startsWith('OBRA')) meta.obra = t.replace(/^OBRA\s*:\s*/i, '');
      else if (n.startsWith('LOCAL') || n.startsWith('ENDERECO')) meta.endereco = t.replace(/^(LOCAL|ENDEREÇO|ENDERECO)\s*:\s*/i, '');
      else if (n.startsWith('DATA-BASE') || n.startsWith('DATA BASE')) meta.data_base = t.replace(/^DATA[- ]BASE\s*:\s*/i, '');
      else if (r < 4) meta.contratante.push(t);
    }

    // valor de uma linha de total: a coluna "Total" (R$); se vazia, o maior número da linha
    const valorTotal = row => {
      const v = col.total >= 0 ? num(row[col.total]) : null;
      if (v != null && Math.abs(v) > 1) return v;
      const ns = row.map(num).filter(n => n != null);
      return ns.length ? Math.max(...ns) : null;
    };

    // 3. itens até "TOTAL GERAL"
    const itens = [];
    let ordem = 0, etapaAtual = null, totalArquivo = null, totalComDesconto = null, desconto = null;
    for (let r = h + 1; r < rawRows.length; r++) {
      const raw = rawRows[r] || [], tx = txtRows[r] || [];
      const primeiro = norm(raw.find(v => v != null && String(v).trim() !== '') ?? '');
      if (primeiro.startsWith('TOTAL GERAL COM DESCONTO') || primeiro.startsWith('VALOR TOTAL COM DESCONTO')) {
        totalComDesconto = valorTotal(raw); continue;
      }
      if (primeiro.startsWith('DESCONTO')) {
        const ns = raw.map(num).filter(n => n != null);
        const p = ns.find(n => n > 0 && n < 1) ?? ns.find(n => n > 0 && n < 100 && n !== ns[ns.length - 1]);
        if (p != null) desconto = p < 1 ? r2(p * 100 * 100) / 100 : p;
        continue;
      }
      if (primeiro.startsWith('TOTAL GERAL') || primeiro === 'TOTAL' || primeiro.startsWith('VALOR TOTAL')) {
        if (totalArquivo == null) totalArquivo = valorTotal(raw);
        continue;
      }
      if (totalArquivo != null) continue;            // depois do total, nada mais é item

      const item = txt(tx[col.item]) || txt(raw[col.item]);
      const descricao = txt(raw[col.descricao]);
      const unidade = txt(raw[col.unidade]);
      if (!item && !descricao) continue;

      const puCom = num(raw[col.puCom]);
      const codigo = col.codigo >= 0 ? txt(raw[col.codigo]) : '';
      let tipo;
      if (unidade || (codigo && puCom != null)) tipo = 'servico';
      else if (item) tipo = 'etapa';
      else tipo = 'titulo';

      const nivel = item ? item.split('.').filter(Boolean).length : 0;
      ordem++;
      const reg = {
        ordem, nivel, item: item || null, tipo, descricao: descricao || '(sem descrição)',
        banco: col.banco >= 0 ? (txt(raw[col.banco]) || null) : null,
        codigo: codigo || null, unidade: unidade || null,
        quantidade: tipo === 'servico' ? (num(raw[col.quant]) ?? 0) : 0,
        pu_sem_bdi: tipo === 'servico' && col.puSem >= 0 ? num(raw[col.puSem]) : null,
        pu_com_bdi: tipo === 'servico' ? puCom : null,
        etapa_ordem: null
      };
      if (tipo === 'etapa' && nivel === 1) etapaAtual = reg.ordem;
      if (tipo === 'servico' || (tipo === 'etapa' && nivel > 1)) reg.etapa_ordem = etapaAtual;
      if (tipo === 'servico' && reg.pu_com_bdi == null) avisos.push(`Item ${item || '?'} (linha ${r + 1}) sem preço unitário com BDI — entra com valor zero.`);
      itens.push(reg);
    }

    // 4. conferência
    const servicos = itens.filter(i => i.tipo === 'servico');
    const totalCalculado = r2(servicos.reduce((s, i) => s + r2((i.quantidade || 0) * (i.pu_com_bdi || 0)), 0));
    const semQuant = servicos.filter(i => !i.quantidade).length;
    const vistos = {};
    for (const i of servicos) if (i.item) vistos[i.item] = (vistos[i.item] || 0) + 1;
    const repetidos = Object.keys(vistos).filter(k => vistos[k] > 1);
    if (repetidos.length) avisos.push(`Numeração repetida em ${repetidos.length} item(ns): ${repetidos.slice(0, 8).join(', ')}${repetidos.length > 8 ? ' e outros' : ''}. Não impede a importação; confira se é intencional.`);

    return {
      itens, colunas: col, linhaCabecalho: h + 1, meta, desconto,
      totalArquivo, totalComDesconto, totalCalculado,
      confere: totalArquivo == null ? null : Math.abs(totalArquivo - totalCalculado) < 0.05,
      resumo: {
        etapas: itens.filter(i => i.tipo === 'etapa' && i.nivel === 1).length,
        servicos: servicos.length, semQuantidade: semQuant
      },
      avisos
    };
  }

  // ---------------------------------------------------------------------------
  // Cronograma físico-financeiro (por etapa, % por período em dias)
  // etapas: [{ordem, item, descricao}] da planilha já lida
  // ---------------------------------------------------------------------------
  function lerCronograma(rawRows, etapas) {
    let h = -1, cServ = -1, cItem = -1;
    for (let r = 0; r < Math.min(rawRows.length, 40); r++) {
      const cel = (rawRows[r] || []).map(norm);
      const s = cel.findIndex(c => c.startsWith('SERVICO') || c.startsWith('DESCRI') || c.startsWith('ETAPA'));
      const i = cel.findIndex(c => c === 'ITEM');
      if (s >= 0 && i >= 0) { h = r; cServ = s; cItem = i; break; }
    }
    if (h < 0) throw new Error('Não encontrei o cabeçalho do cronograma (com "Item" e "Serviço").');

    // linha dos períodos: a primeira, logo abaixo, com números crescentes (30, 60, 90…) ou "MÊS 1"
    let pr = -1, periodos = [];
    for (let r = h; r <= h + 2 && r < rawRows.length; r++) {
      const row = rawRows[r] || [];
      const lista = [];
      for (let c = cServ + 1; c < row.length; c++) {
        const n = num(row[c]);
        const m = norm(row[c]).match(/^(MES|MÊS|PERIODO)\s*(\d+)/);
        if (n != null && n > 0 && n <= 3650 && Number.isInteger(n)) lista.push({ col: c, dias: n });
        else if (m) lista.push({ col: c, dias: Number(m[2]) * 30 });
      }
      if (lista.length >= 2) { pr = r; periodos = lista; break; }
    }
    if (!periodos.length) throw new Error('Não encontrei a linha dos períodos (30, 60, 90… dias).');

    const porNome = new Map(etapas.map(e => [norm(e.descricao), e]));
    const porNumero = new Map(etapas.map(e => [String(e.item), e]));
    const linhas = [], semPar = [];
    for (let r = pr + 1; r < rawRows.length; r++) {
      const row = rawRows[r] || [];
      const nome = txt(row[cServ]);
      if (!nome || norm(nome).startsWith('TOTAL')) continue;
      // valores em %: frações (0,3) ou porcentagens (30)
      const pcts = periodos.map((p, k) => ({ periodo: k + 1, dias: p.dias, pct: comoPct(row[p.col]) }))
                           .filter(x => x.pct != null && x.pct > 0);
      if (!pcts.length) continue;
      if (pcts.reduce((s, x) => s + x.pct, 0) > 100.5) continue;       // linha em R$, não em %
      const etapa = porNome.get(norm(nome)) || porNumero.get(txt(row[cItem]));
      if (!etapa) { semPar.push(nome); continue; }
      for (const x of pcts) linhas.push({ etapa_ordem: etapa.ordem, periodo: x.periodo, dias: x.dias, pct: Math.round(x.pct * 10000) / 10000 });
    }
    const ligadas = new Set(linhas.map(l => l.etapa_ordem)).size;
    return { cronograma: linhas, periodos: periodos.map(p => p.dias), etapasLigadas: ligadas, semPar };
  }

  const api = { lerOrcamento, lerCronograma, norm, num };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else raiz.Importar = api;
})(typeof window !== 'undefined' ? window : globalThis);
