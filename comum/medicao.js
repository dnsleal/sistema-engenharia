// Dados de um Boletim de Medição: carrega a obra, os itens e todos os lançamentos,
// e calcula, item a item e etapa a etapa: anterior, este BM, acumulado e saldo.
// Usado pela tela de lançamento (medicao.html) e pelo boletim impresso (boletim.html).
(function () {
  const r2 = n => {
    const limpo = Number(Number(n).toPrecision(15));
    return Math.sign(limpo) * Math.round(Math.abs(limpo) * 100 + 1e-9) / 100;
  };

  async function carregar(sb, obraId, bmId) {
    // itens e lançamentos podem passar de 1.000 linhas: lidos em lotes (SE.todos)
    const comoResposta = p => p.then(data => ({ data, error: null }), error => ({ data: null, error }));
    const [o, pl, it, ms, li] = await Promise.all([
      sb.from('obras').select('*').eq('id', obraId).single(),
      sb.from('planilhas').select('*').eq('obra_id', obraId).order('tipo', { ascending: false }).order('numero'),
      comoResposta(SE.todos(() => sb.from('v_itens_saldo').select('*').eq('obra_id', obraId).order('planilha_numero').order('ordem').order('item_id'))),
      sb.from('medicoes').select('*').eq('obra_id', obraId).order('numero'),
      comoResposta(SE.todos(() => sb.from('medicao_itens').select('id, item_id, quantidade, medicao_id, medicoes!inner(obra_id, numero)')
        .eq('medicoes.obra_id', obraId).order('id')))
    ]);
    for (const r of [o, pl, it, ms, li]) if (r.error) throw r.error;
    const bm = ms.data.find(m => m.id === bmId);
    if (!bm) throw new Error('Boletim não encontrado.');
    return montar(o.data, pl.data, it.data, ms.data, li.data, bm);
  }

  function montar(obra, planilhas, itens, medicoes, lancamentos, bm) {
    const desconto = Number(obra.desconto_pct || 0);
    const anterior = {}, atual = {};
    for (const l of lancamentos) {
      const n = l.medicoes.numero, q = Number(l.quantidade);
      if (n < bm.numero) anterior[l.item_id] = (anterior[l.item_id] || 0) + q;
      else if (n === bm.numero) atual[l.item_id] = q;
    }
    const nomePl = p => p.tipo === 'original' ? 'Planilha original' : 'Aditivo ' + p.numero;

    // itens de serviço com os quatro estados
    const linhas = itens.map(i => {
      if (i.tipo !== 'servico') return { ...i };
      const qc = Number(i.qtd_contratada || 0), pu = Number(i.pu_com_bdi || 0);
      const qa = anterior[i.item_id] || 0, qb = atual[i.item_id] || 0;
      return {
        ...i, qc, pu, qa, qb, qacum: qa + qb, qsaldo: qc - qa - qb,
        vc: r2(qc * pu), va: r2(qa * pu), vb: r2(qb * pu), vacum: r2((qa + qb) * pu), vsaldo: r2((qc - qa - qb) * pu),
        excede: qa + qb - qc > 1e-9
      };
    });

    // resumo por etapa (nível 1), separado por planilha
    const etapas = [];
    const porId = new Map();
    for (const p of planilhas) {
      for (const e of linhas.filter(x => x.planilha_id === p.id && x.tipo === 'etapa' && x.nivel === 1)) {
        const reg = { planilha: nomePl(p), planilha_tipo: p.tipo, item: e.item, descricao: e.descricao, vc: 0, va: 0, vb: 0, vacum: 0, vsaldo: 0 };
        etapas.push(reg); porId.set(e.item_id, reg);
      }
    }
    const semEtapa = { planilha: '', item: '', descricao: 'Itens sem etapa', vc: 0, va: 0, vb: 0, vacum: 0, vsaldo: 0 };
    for (const s of linhas.filter(x => x.tipo === 'servico')) {
      const e = porId.get(s.etapa_id) || semEtapa;
      for (const k of ['vc', 'va', 'vb', 'vacum', 'vsaldo']) e[k] = r2(e[k] + s[k]);
    }
    if (semEtapa.vc || semEtapa.vb) etapas.push(semEtapa);

    // totais (bruto → desconto sobre o total → líquido; reajuste só sobre este BM)
    const soma = k => r2(etapas.reduce((s, e) => s + e[k], 0));
    const tot = {};
    for (const k of ['vc', 'va', 'vb', 'vacum', 'vsaldo']) {
      const bruto = soma(k), desc = r2(bruto * desconto / 100);
      tot[k] = { bruto, desconto: desc, liquido: r2(bruto - desc) };
    }
    const reajuste = r2(tot.vb.liquido * Number(bm.reajuste_pct || 0) / 100);

    return {
      obra, planilhas, medicoes, bm, linhas, etapas, totais: tot, desconto,
      reajuste, totalBM: r2(tot.vb.liquido + reajuste),
      pct: (v, base) => base ? v / base * 100 : 0,
      nomePl
    };
  }

  window.Medicao = { carregar, montar, r2 };
})();
