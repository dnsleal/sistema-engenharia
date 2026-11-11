// Relatório de Fiscalização (fiscal técnico) e Relatório Final do Gestor do Contrato,
// nos modelos da SMS Cuiabá. Tudo vem da obra, dos responsáveis e do BM; os textos
// podem ser ajustados e ficam em medicoes.dados.rel_fiscal / rel_gestor.
// Requer: formatos.js (F), extenso.js (Extenso), medicao.js (Medicao)
(function () {
  const MESES = ['janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho', 'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro'];
  const E = s => F.esc(s ?? '');
  // **negrito** e quebras de parágrafo no texto editável
  const rico = t => E(t).replace(/\*\*(.+?)\*\*/g, '<b>$1</b>');
  const paragrafos = t => String(t || '').split(/\n\s*\n/).map(p => p.trim()).filter(Boolean)
    .map(p => `<p>${rico(p).replace(/\n/g, '<br>')}</p>`).join('');
  const pct = (a, b) => b ? a / b * 100 : 0;
  const fp = v => F.num(v, 2) + '%';
  const mesAno = c => c ? `${MESES[+c.slice(5, 7) - 1]}/${c.slice(0, 4)}` : '';
  const data = d => d ? F.data(d) : '';

  function periodoTexto(bm) {
    const i = bm.periodo_inicio, f = bm.periodo_fim;
    if (!i && !f) return bm.competencia ? `${MESES[+bm.competencia.slice(5, 7) - 1]} de ${bm.competencia.slice(0, 4)}` : '________';
    if (i && f && i.slice(0, 7) === f.slice(0, 7)) return `${MESES[+f.slice(5, 7) - 1]} de ${f.slice(0, 4)}`;
    return `${data(i)} a ${data(f)}`;
  }

  // contexto comum aos dois relatórios
  function contexto(M, pessoas) {
    const o = M.obra, bm = M.bm, d = bm.dados || {};
    const p = id => (id && pessoas[id]) || null;
    return {
      M, obra: o, bm, dados: d,
      fiscal: p(o.fiscal_id), gestor: p(o.gestor_id), fiscalAdm: p(o.fiscal_adm_id),
      valorBM: M.totalBM, pctBM: pct(M.totais.vb.liquido, M.totais.vc.liquido),
      numero: String(bm.numero)
    };
  }

  // ---------------- Relatório do Fiscal ----------------
  function textoFiscalPadrao(c) {
    const o = c.obra;
    const objeto = (o.objeto || o.nome || '').replace(/\.\s*$/, '');
    const local = o.endereco && !objeto.toUpperCase().includes(o.endereco.toUpperCase().slice(0, 12)) ? `, localizada a ${o.endereco}` : '';
    return `Cumprimentando-o cordialmente, vimos por meio desta apresentar a medição da **${o.contratada || '________'}**, **CNPJ:** ${o.cnpj_contratada || '________'}, do contrato nº ${o.num_contrato || '________'}.

Conforme consta nas planilhas de execução de ${objeto}${local}, foram executados no período de ${periodoTexto(c.bm)}. Sendo o percentual executado de ${F.num(c.pctBM, 2)}% dos serviços contratado, equivalente **a R$ ${F.num(c.valorBM, 2)}** (${Extenso.maiuscula(Extenso.reais(c.valorBM))}).`;
  }

  function tabelaBoletim(c) {
    const M = c.M, T = M.totais, tot = T.vc.bruto;
    const linhas = M.etapas.map(e => `<tr><td class="c">${E(e.item)}</td><td>${E(e.descricao)}</td>
      <td class="n">${F.num(e.vc, 2)}</td><td class="n">${fp(pct(e.vc, tot))}</td>
      <td class="n">${F.num(e.vb, 2)}</td><td class="n">${fp(pct(e.vb, e.vc))}</td>
      <td class="n">${F.num(e.vacum, 2)}</td><td class="n">${fp(pct(e.vacum, e.vc))}</td>
      <td class="n">${F.num(e.vsaldo, 2)}</td><td class="n">${fp(pct(e.vsaldo, e.vc))}</td></tr>`).join('');
    const linhaTot = (rot, k, cls = '') => `<tr class="${cls}"><td colspan="2">${rot}</td>
      <td class="n">${F.num(T.vc[k], 2)}</td><td class="n">${k === 'bruto' ? '100,00%' : ''}</td>
      <td class="n">${F.num(T.vb[k], 2)}</td><td class="n">${fp(pct(T.vb[k], T.vc[k]))}</td>
      <td class="n">${F.num(T.vacum[k], 2)}</td><td class="n">${fp(pct(T.vacum[k], T.vc[k]))}</td>
      <td class="n">${F.num(T.vsaldo[k], 2)}</td><td class="n">${fp(pct(T.vsaldo[k], T.vc[k]))}</td></tr>`;
    return `<table class="bol">
      <tr class="tit"><td colspan="10">BOLETIM ${E(c.numero)}ª MEDIÇÃO DO CONTRATO</td></tr>
      <tr class="cab"><td>ITEM</td><td>DESCRIÇÃO / ETAPA</td><td>VALOR CONTRATO (R$)</td><td>%</td><td>MEDIÇÃO DO MÊS (R$)</td><td>%</td><td>ACUMULADO GERAL (R$)</td><td>%</td><td>SALDO DO CONTRATO (R$)</td><td>%</td></tr>
      ${linhas}
      ${linhaTot('TOTAL', 'bruto', 'tot')}
      ${M.desconto ? `<tr><td colspan="2">DESCONTO DO CONTRATO (${F.num(M.desconto, 2)}%)</td><td class="n">${F.num(T.vc.desconto, 2)}</td><td></td><td class="n">${F.num(T.vb.desconto, 2)}</td><td></td><td class="n">${F.num(T.vacum.desconto, 2)}</td><td></td><td class="n">${F.num(T.vsaldo.desconto, 2)}</td><td></td></tr>
      ${linhaTot('TOTAL COM DESCONTO', 'liquido', 'tot')}` : ''}
      ${M.reajuste ? `<tr><td colspan="4">REAJUSTE DESTA MEDIÇÃO (${F.num(M.bm.reajuste_pct, 2)}%)</td><td class="n">${F.num(M.reajuste, 2)}</td><td colspan="5"></td></tr>` : ''}
      <tr class="tot"><td colspan="4">VALOR DESTA MEDIÇÃO</td><td class="n">${F.num(c.valorBM, 2)}</td><td colspan="5">${E(Extenso.maiuscula(Extenso.reais(c.valorBM)))}</td></tr>
    </table>`;
  }

  function assinatura(p, funcao, extra) {
    if (!p) return `<div class="assin"><div class="linha"></div><div><i>Responsável não definido na obra</i></div></div>`;
    return `<div class="assin"><div class="linha"></div>
      <div><b>${E(p.nome)}</b></div><div>${E(funcao)}</div>${extra || ''}
      ${p.unidade ? `<div>Unidade: ${E(p.unidade)}</div>` : ''}${p.portaria ? `<div>${E(p.portaria)}</div>` : ''}
      <div class="ass-el">(Assinado eletronicamente)</div></div>`;
  }

  function htmlFiscal(c, timbre) {
    const r = c.dados.rel_fiscal || {};
    const texto = r.texto || textoFiscalPadrao(c);
    return `<div class="rm folha">
      ${timbre ? `<div class="timbre"><img src="${timbre}" alt="Prefeitura de Cuiabá — Secretaria de Saúde"></div>` : ''}
      <h1>RELATÓRIO DE FISCALIZAÇÃO</h1>
      <div class="texto">${paragrafos(texto)}</div>
      ${r.semTabela ? '' : tabelaBoletim(c)}
      ${c.bm.data_relatorio ? `<p class="data">Cuiabá-MT, ${new Date(c.bm.data_relatorio + 'T12:00').toLocaleDateString('pt-BR', { day: 'numeric', month: 'long', year: 'numeric' })}.</p>` : ''}
      ${assinatura(c.fiscal, `${(c.fiscal && c.fiscal.cargo) || 'Fiscal Técnico do Contrato'} Nº ${c.obra.num_contrato || ''}`)}
    </div>`;
  }

  // ---------------- Relatório do Gestor ----------------
  const CONCLUSAO_PADRAO = `Na função de Gestor deste contrato, o que o faço na forma do § 3º do art. 8º da Lei nº 14.133 e do Decreto Municipal 10.070/2024, **CONCLUO E APROVO A FISCALIZAÇÃO** e declaro que os relatórios da fiscalização técnica e administrativa foram por mim analisados e que, a eles foram anexados todos os documentos necessários para comprovação da execução do objeto da contratação e das obrigações fiscais e trabalhistas.

Segue para a {destino} contendo os seguintes documentos:

a) Relatório da fiscalização técnica de serviços e documentos que fazem parte deste;
b) Relatório da fiscalização administrativa de serviços e documentos que fazem parte deste;
c) Cópia da Nota Fiscal devidamente atestada;`;
  const ANEXADOS = [
    ['tecnica', 'Relatório da fiscalização técnica de serviços e todos os documentos citados neste relatório?', 'sim'],
    ['administrativa', 'Relatório da fiscalização administrativa de serviços e todos os documentos citados neste relatório?', 'nao'],
    ['nf', 'Nota Fiscal devidamente conferida?', 'sim']
  ];
  const naoAplica = v => (v == null || v === '') ? 'não se aplica' : v;

  function htmlGestor(c, timbre) {
    const o = c.obra, bm = c.bm, r = c.dados.rel_gestor || {};
    const an = { ...Object.fromEntries(ANEXADOS.map(a => [a[0], a[2]])), ...(r.anexados || {}) };
    const conclusao = (r.conclusao || CONCLUSAO_PADRAO).replace('{destino}', r.destino || 'Diretoria de Aquisições e Contratos/SAG');
    const rs = v => v == null ? '' : 'R$ ' + F.num(v, 2);
    const cel = (rot, val, extra = '') => `<td ${extra}>${rot} ${val}</td>`;
    return `<div class="rm folha gestor">
      ${timbre ? `<div class="timbre"><img src="${timbre}" alt="Prefeitura de Cuiabá — Secretaria de Saúde"></div>` : ''}
      <table class="g">
        <tr class="verde"><td colspan="4">RELATÓRIO FINAL DO GESTOR DO CONTRATO COM RECEBIMENTO DEFINITIVO</td></tr>
        <tr>${cel('Processo:', E(bm.processo_pagamento || o.processo_siged || ''), 'colspan="2"')}${cel('Nº do contrato:', E(o.num_contrato || ''), 'colspan="2"')}</tr>
        <tr><td colspan="4" class="just">Objeto do contrato: "${E(o.objeto || o.nome)}"</td></tr>
        <tr><td colspan="4" class="c">Razão Social da Contratada: ${E(o.contratada || '')}</td></tr>
        <tr><td class="c">Mês de Competência:<br><b>${E(mesAno(bm.competencia))}</b></td><td class="c">CNPJ: ${E(o.cnpj_contratada || '')}</td><td colspan="2" class="c">Vigência: ${data(o.termino_vigente)}</td></tr>
        <tr><td colspan="2" class="c">Nº do Empenho: ${E(o.empenho_numero || '')}</td><td colspan="2" class="c">Saldo do Empenho: <b>${rs(o.empenho_saldo)}</b></td></tr>
        <tr class="secao"><td colspan="4">DADOS DO FATURAMENTO e VALOR MENSAL CONTRATADO X VALOR DA FATURA</td></tr>
        <tr><td class="c">Valor Contratado: ${rs(o.valor_contrato)}</td><td class="c">Aferição do IMR em %: ${bm.imr_pct == null ? 'não se aplica' : F.num(bm.imr_pct, 2)}</td><td class="c">Glosas: ${rs(bm.glosa === 'nao' ? 0 : (bm.glosa_valor || 0))}</td><td class="c">Valor da Fatura: ${rs(bm.nf_valor)}</td></tr>
        <tr class="secao"><td colspan="4">DADOS DA NOTA FISCAL</td></tr>
        <tr><td class="c">Nº da NF:<br>${E(bm.nf_numero || '')}</td><td class="c">Data de emissão da NF:<br><b>${data(bm.nf_data)}</b></td><td class="c">Valor Mensal Contratado: ${E(r.valor_mensal || 'não se aplica')}</td><td class="c">Valor da NF: <b>${rs(bm.nf_valor)}</b></td></tr>
        <tr class="secao"><td colspan="4">RETENÇÕES</td></tr>
        <tr><td colspan="2">Valor de Retenção para conta vinculada: ${E(naoAplica(bm.retencao_vinculada))}</td><td colspan="2">Valor a ser retido para pagamento de direito ao terceirizado: ${E(naoAplica(bm.retencao_terceirizado))}</td></tr>
        <tr><td colspan="4">Outros valores a serem retidos: ${E(naoAplica(bm.outras_retencoes))}</td></tr>
      </table>
      <table class="g anex">
        <tr class="secao"><td>Foram anexados à fiscalização?</td><td class="x">Sim</td><td class="x">Não</td></tr>
        ${ANEXADOS.map(([k, t]) => `<tr><td>${E(t)}</td><td class="x">${an[k] === 'sim' ? 'X' : ''}</td><td class="x">${an[k] === 'nao' ? 'X' : ''}</td></tr>`).join('')}
        <tr class="secao"><td colspan="3">CONCLUSÃO</td></tr>
        <tr><td colspan="3" class="concl">${paragrafos(conclusao)}
          ${assinatura(c.gestor, `${(c.gestor && c.gestor.cargo) || 'Gestor do Contrato'} nº ${o.num_contrato || ''}`).replace('<div><b>', '<div>Nome do servidor: <b>')}</td></tr>
      </table>
    </div>`;
  }

  // estilo dos dois documentos (tela e impressão)
  const CSS = `
  .rm { font-family: Arial, Helvetica, sans-serif; color: #111; font-size: 11pt; line-height: 1.45; background: #fff; }
  .rm.folha { width: 210mm; min-height: 297mm; padding: 14mm 18mm; margin: 0 auto; box-sizing: border-box; }
  .rm .timbre { text-align: center; margin-bottom: 10px; } .rm .timbre img { height: 58px; }
  .rm h1 { text-align: center; font-size: 13pt; margin: 8px 0 16px; }
  .rm .texto p { text-indent: 2.5cm; text-align: justify; margin: 0 0 10px; }
  .rm table { border-collapse: collapse; width: 100%; }
  .rm table.bol { font-size: 6.6pt; line-height: 1.2; margin: 10px 0 16px; }
  .rm table.bol td { border: 1px solid #333; padding: 2px 3px; }
  .rm table.bol tr.tit td { text-align: center; font-weight: 700; background: #d9e2f3; }
  .rm table.bol tr.cab td { text-align: center; font-weight: 700; background: #f2f2f2; }
  .rm table.bol tr.tot td { font-weight: 700; background: #f2f2f2; }
  .rm td.n { text-align: right; white-space: nowrap; } .rm td.c { text-align: center; }
  .rm .data { text-align: right; margin: 6px 0 0; }
  .rm .assin { text-align: center; margin-top: 34px; line-height: 1.35; break-inside: avoid; }
  .rm .assin .linha { width: 60%; margin: 0 auto 4px; border-top: 1px solid #111; }
  .rm .assin .ass-el { font-style: italic; }
  .rm.gestor { font-size: 9.5pt; }
  .rm table.g td { border: 1px solid #333; padding: 5px 7px; vertical-align: middle; }
  .rm table.g tr.verde td { background: #0b9447; color: #fff; text-align: center; font-weight: 700; font-size: 11pt; padding: 10px; }
  .rm table.g tr.secao td { text-align: center; font-weight: 700; }
  .rm table.g td.just { text-align: justify; }
  .rm table.anex { margin-top: 6px; } .rm table.anex td.x { width: 13%; text-align: center; font-weight: 700; }
  .rm table.anex td.concl p { text-align: justify; margin: 0 0 8px; }
  .rm table.anex td.concl .assin { margin-top: 26px; text-align: left; } .rm table.anex td.concl .assin .linha { margin: 0 0 4px; width: 55%; }
  `;

  window.RelMedicao = { contexto, textoFiscalPadrao, htmlFiscal, htmlGestor, CSS, CONCLUSAO_PADRAO, ANEXADOS, periodoTexto };
})();
