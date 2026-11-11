// Checklist do processo de pagamento da medição (modelo SMS Cuiabá).
// O modelo fica aqui; as respostas de cada BM ficam em medicoes.dados.checklist:
//   { "<cod>": { r: 'sim'|'nao'|'na', fls, obs, anexo: {caminho, nome, em}, validade, manual: true } }
// Itens marcados com "auto" são respondidos pelo sistema com os dados da obra/BM,
// até você mudar a resposta (aí ficam "manual").
(function () {
  const MODELO = [
    { sec: '1', titulo: 'CONTRATO', itens: [
      { cod: '1.1', txt: 'Abertura de processo administrativo devidamente autuado, protocolado, numerado e CI de encaminhamento.', doc: true },
      { cod: '1.2', txt: 'Todos os documentos estão inseridos no sistema SIGED' },
      { cod: '1.3', txt: 'Extrato do Termo de Contrato publicado no DOE/MT e Publicação do Fiscal', doc: true }
    ] },
    { sec: '2', titulo: 'FISCAL E GESTOR DO CONTRATO', itens: [
      { cod: '2.1', txt: 'Emissão da Ordem de Fornecimento', doc: true },
      { cod: '2.2', txt: 'Nota Fiscal/Fatura devidamente assinado e datado pelo Fiscal', doc: true, auto: 'nf' },
      { cod: '2.3', txt: 'Declaração de existência de saldo orçamentário para execução da despesa, emitido por gestor, fiscal ou setor responsável', doc: true },
      { cod: '2.4', txt: 'Relatório Final do Gestor do Contrato Com Recebimento Definitivo assinado e datado.', auto: 'gestor' },
      { cod: '2.5', txt: 'Relatório de Fiscalização Técnica de Serviços assinado e datado pelo Fiscal.', auto: 'fiscal' },
      { cod: '2.6', txt: 'Relatório Fiscalização Administrativa de Serviços Com Dedicação Exclusiva de Mão de Obra assinado e datado pelo Responsável.', padrao: 'na' },
      { cod: '2.7', txt: 'Comprovação de Anexação do Relatório de Fiscalização no Sistema E-Jade', padrao: 'na' },
      { cod: '2.8', txt: 'Houve Glosa.', auto: 'glosa', tipo: 'glosa' },
      { cod: '2.9', txt: 'Emissão de Autenticidade do Documento Fiscal', doc: true },
      { cod: '2.10', txt: 'Justificativa da ausência do Fiscal (Caso não tenha fiscal nomeado)', auto: 'semfiscal' }
    ] },
    { sec: '3', titulo: 'CERTIDÕES DE REGULARIDADE FISCAL', itens: [
      { cod: '3.1', txt: 'Certidão Negativa de Débitos relativos a Créditos Tributários Federais e à Dívida Ativa da União - PGFN, com autenticidade e vigente.', doc: true, certidao: 'PGFN' },
      { cod: '3.2', txt: 'Certidão Negativa de Débitos da Fazenda Estadual SEFAZ conjunta com a Procuradoria Geral do Estado - PGE, com autenticidade e vigente.', doc: true, certidao: 'SEFAZ/PGE' },
      { cod: '3.3', txt: 'Certificado de Regularidade relativo à Seguridade Social e ao Fundo de Garantia por Tempo de Serviço – FGTS, com autenticidade e vigente.', doc: true, certidao: 'FGTS' },
      { cod: '3.4', txt: 'Certidão Negativa de Débitos Trabalhistas (CNDT) - TRT, com autenticidade e vigente.', doc: true, certidao: 'CNDT' },
      { cod: '3.5', txt: 'Certidão Negativa de Tributo Municipal com autenticidade e vigente.', doc: true, certidao: 'Municipal' }
    ] },
    { sec: '4', titulo: 'EMPENHO', itens: [
      { cod: '4.1', txt: 'Nota de Empenho Nº: {empenho}\na. Empenho emitido em data anterior à efetivação da despesa.', doc: true, auto: 'empenho' }
    ] },
    { sec: '5', titulo: 'DADOS BANCÁRIOS', itens: [
      { cod: '5.1', txt: 'Indicação da conta bancária para pagamento:', doc: true }
    ] }
  ];
  const ITENS = MODELO.flatMap(s => s.itens.map(i => ({ ...i, sec: s.sec, secTitulo: s.titulo })));
  const DOCS = ITENS.filter(i => i.doc);
  const ROT = { sim: 'Sim', nao: 'Não', na: 'N/A' };
  const GLOSA = { nao: 'Não', sim_ajustada: 'Sim, a nota fiscal já está ajustada com a glosa', sim_nao_ajustada: 'Sim, a nota fiscal NÃO está ajustada com a glosa' };

  // certidões/documentos que valem para o BM seguinte (enquanto vigentes): vêm do BM anterior
  const HERDA = new Set(['1.3', '3.1', '3.2', '3.3', '3.4', '3.5', '4.1', '5.1']);
  function herdar(atual, anterior, dataRef) {
    const out = { ...(atual || {}) };
    if (!anterior) return out;
    for (const cod of HERDA) {
      const a = anterior[cod];
      if (!a || !a.anexo || (out[cod] && out[cod].anexo)) continue;
      if (a.validade && dataRef && a.validade < dataRef) continue;      // vencida: não traz
      out[cod] = { ...(out[cod] || {}), anexo: a.anexo, validade: a.validade || null, herdado: true, fls: out[cod] && out[cod].fls || '' };
    }
    return out;
  }

  // resposta final de cada item: manual > automática > padrão do modelo
  function montar(obra, bm, salvo) {
    const C = salvo || {};
    const hoje = new Date().toISOString().slice(0, 10);
    const dataRef = bm.nf_data || hoje;
    return ITENS.map(it => {
      const s = C[it.cod] || {};
      let r = null, obs = s.obs || '', auto = '', alerta = '';
      // automáticos
      if (it.auto === 'nf') { r = s.anexo ? 'sim' : null; if (!s.obs && bm.nf_numero) obs = `Nota Fiscal nº ${bm.nf_numero}`; auto = bm.nf_numero ? 'nº da NF vem do BM' : ''; }
      if (it.auto === 'gestor') { r = obra.gestor_id ? 'sim' : null; auto = 'relatório gerado pelo sistema'; }
      if (it.auto === 'fiscal') { r = obra.fiscal_id ? 'sim' : null; auto = 'relatório gerado pelo sistema'; }
      if (it.auto === 'semfiscal') { r = obra.fiscal_id ? 'na' : 'sim'; auto = obra.fiscal_id ? 'há fiscal nomeado' : 'sem fiscal na obra: anexe a justificativa'; }
      if (it.auto === 'empenho') { r = s.anexo || obra.empenho_numero ? 'sim' : null; auto = obra.empenho_numero ? 'nº do empenho vem da obra' : ''; }
      if (it.auto === 'glosa') { r = bm.glosa === 'nao' ? 'nao' : 'sim'; auto = 'resposta vem do BM'; }
      if (!it.auto && it.doc && s.anexo) r = 'sim';
      if (r == null && it.padrao) r = it.padrao;
      // certidão: vigente na data da NF?
      if (it.certidao && s.anexo) {
        if (!s.validade) alerta = 'informe a validade';
        else if (s.validade < dataRef) { alerta = `vencida em ${s.validade.split('-').reverse().join('/')}`; r = 'nao'; }
      }
      const manual = !!(s.manual && s.r);
      if (manual) r = s.r;
      const texto = it.txt.replace('{empenho}', obra.empenho_numero || '________');
      return { ...it, txt: texto, r, obs, fls: s.fls || '', anexo: s.anexo || null, validade: s.validade || '', herdado: !!s.herdado, manual, auto, alerta, glosa: bm.glosa };
    });
  }

  function pendencias(linhas) {
    const P = [];
    for (const l of linhas) {
      if (l.alerta) P.push(`Item ${l.cod} (${l.certidao || 'documento'}): ${l.alerta}.`);
      else if (!l.r) P.push(`Checklist ${l.cod} sem resposta${l.doc ? ' (documento não anexado)' : ''}.`);
      else if (l.r === 'nao' && l.tipo !== 'glosa') P.push(`Checklist ${l.cod} marcado como "Não".`);
    }
    return P;
  }

  // documentos extras, fora do modelo: chk.O1, chk.O2… { desc, anexo, obs }
  const outros = chk => Object.entries(chk || {}).filter(([k, v]) => /^O\d+$/.test(k) && v && !v.removido)
    .sort((a, b) => +a[0].slice(1) - +b[0].slice(1)).map(([cod, v], i) => ({ cod, num: i + 1, desc: v.desc || '', anexo: v.anexo || null, obs: v.obs || '' }));
  const novoOutro = chk => 'O' + (Math.max(0, ...Object.keys(chk || {}).filter(k => /^O\d+$/.test(k)).map(k => +k.slice(1))) + 1);

  window.Checklist = { MODELO, ITENS, DOCS, ROT, GLOSA, montar, herdar, pendencias, outros, novoOutro };
})();
