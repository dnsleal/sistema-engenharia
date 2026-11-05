// Leitura do arquivo oficial "SINAPI_Referência_AAAA_MM.xlsx" (CAIXA) direto no navegador.
// Usa só as abas ISD, ICD (insumos) e CSD, CCD (composições) e só a coluna da UF pedida.
// Resultado no mesmo formato de orcamento/bases/*.json (sem o analítico).
// As referências carregadas ficam guardadas no Storage do usuário: <uid>/sinapi/sinapi-mt-AAAA-MM.json
(function () {
  const ABAS = [['ISD', 'I', 'Não desonerado'], ['ICD', 'I', 'Desonerado'], ['CSD', 'C', 'Não desonerado'], ['CCD', 'C', 'Desonerado']];
  const num = v => { if (v == null || v === '') return null; if (typeof v === 'number') return v; const n = Number(String(v).replace(/\./g, '').replace(',', '.')); return Number.isFinite(n) ? n : null; };
  const cod = v => { if (v == null) return ''; if (typeof v === 'number' && Number.isInteger(v)) return String(v); return String(v).trim(); };
  const limpa = s => String(s ?? '').replace(/\s+/g, ' ').trim();
  const r2 = n => Math.round((n + Number.EPSILON) * 100) / 100;
  const espera = () => new Promise(ok => setTimeout(ok, 30));

  async function lerReferencia(buf, uf = 'MT', progresso = () => {}) {
    progresso('Abrindo o arquivo (pode levar uns segundos)…'); await espera();
    const wb = XLSX.read(buf, { type: 'array', cellFormula: true, sheets: ABAS.map(a => a[0]) });
    const falta = ABAS.map(a => a[0]).filter(n => !wb.Sheets[n]);
    if (falta.length) throw new Error(`Este arquivo não parece ser o "SINAPI_Referência": faltam as abas ${falta.join(', ')}.`);
    let mes = null;
    const bases = [];
    for (const [aba, tipo, regime] of ABAS) {
      progresso(`Lendo ${aba} (${tipo === 'C' ? 'composições' : 'insumos'}, ${regime.toLowerCase()})…`); await espera();
      const ws = wb.Sheets[aba];
      const ini = XLSX.utils.decode_range(ws['!ref'] || 'A1').s;   // a leitura começa na 1ª célula usada
      const R = XLSX.utils.sheet_to_json(ws, { header: 1, raw: true, defval: null, blankrows: true });
      // mês de referência (linha "Mês de Referência:")
      for (let i = 0; i < 6 && !mes; i++) { const r = R[i] || []; const k = r.findIndex(x => /M[ÊE]S DE REFER/i.test(String(x || ''))); if (k >= 0) mes = limpa(r[k + 1]); }
      // coluna da UF e linha de cabeçalho
      let col = -1, colSP = -1;
      for (let i = 0; i < 15 && col < 0; i++) { const r = (R[i] || []).map(x => limpa(x).toUpperCase()); col = r.indexOf(uf); if (col >= 0) colSP = r.indexOf('SP'); }
      if (col < 0) throw new Error(`Não achei a coluna ${uf} na aba ${aba}.`);
      const h = R.findIndex((r, i) => i < 20 && (r || []).some(x => /^DESCRI/i.test(limpa(x))));
      if (h < 0) throw new Error(`Não achei o cabeçalho da aba ${aba}.`);
      const cab = R[h].map(x => limpa(x).toUpperCase());
      const cd = cab.findIndex(x => x.startsWith('DESCRI')), cu = cab.findIndex(x => x.startsWith('UNID'));
      const itens = [];
      for (let i = h + 1; i < R.length; i++) {
        const r = R[i]; if (!r) continue;
        let k = cod(r[1]);
        if (tipo === 'C') {   // o código da composição fica numa fórmula HYPERLINK(...;"104658") com valor 0
          const c = ws[XLSX.utils.encode_cell({ r: i + ini.r, c: 1 + ini.c })];
          if (c && c.f && /HYPERLINK/i.test(c.f)) { const m = c.f.match(/[,;]\s*"?(\d+)"?\s*\)\s*$/); if (m) k = m[1]; }
        }
        const d = limpa(r[cd]);
        if (!k || k === '0' || !d) continue;
        const p = num(r[col]);
        if (!p) continue;
        itens.push([k, d, limpa(r[cu]), r2(p)]);
      }
      if (!itens.length) throw new Error(`A aba ${aba} não trouxe preços para ${uf}.`);
      bases.push({ banco: 'SINAPI', uf, mes, regime, tipo: tipo === 'C' ? 'Composições' : 'Insumos', sheet: aba, tipoItem: tipo, itens });
    }
    if (!mes || !/^\d{2}\/\d{4}$/.test(mes)) throw new Error('Não consegui ler o mês de referência do arquivo.');
    bases.forEach(b => b.mes = mes);
    return { versao: 1, banco: 'SINAPI', uf, mes, parcial: true, gerado: new Date().toISOString().slice(0, 10),
      fonte: `CAIXA/IBGE — SINAPI_Referência ${mes} (somente ${uf}), lido no navegador`, bases };
  }

  // ---- guardar / listar / abrir no Storage do usuário ----
  const pasta = uid => `${uid}/sinapi`;
  const arquivo = (uf, mes) => `sinapi-${uf.toLowerCase()}-${mes.slice(3)}-${mes.slice(0, 2)}.json`;
  async function guardar(sb, uid, d) {
    const nome = arquivo(d.uf, d.mes);
    const { error } = await sb.storage.from('fotos').upload(`${pasta(uid)}/${nome}`, new Blob([JSON.stringify(d)], { type: 'application/json' }), { upsert: true, contentType: 'application/json' });
    if (error) throw error;
    return nome;
  }
  async function listar(sb, uid) {
    const { data, error } = await sb.storage.from('fotos').list(pasta(uid), { limit: 200 });
    if (error) return [];
    return (data || []).filter(f => /^sinapi-[a-z]{2}-\d{4}-\d{2}\.json$/.test(f.name)).map(f => {
      const [, uf, a, m] = f.name.match(/^sinapi-([a-z]{2})-(\d{4})-(\d{2})\.json$/);
      return { caminho: `${pasta(uid)}/${f.name}`, uf: uf.toUpperCase(), mes: `${m}/${a}`, rotulo: `SINAPI-${uf.toUpperCase()} ${m}/${a}` };
    });
  }
  async function abrir(sb, caminho) {
    const { data, error } = await sb.storage.from('fotos').download(caminho);
    if (error) throw error;
    return JSON.parse(await data.text());
  }
  async function excluir(sb, caminho) {
    const { error } = await sb.storage.from('fotos').remove([caminho]);
    if (error) throw error;
  }

  window.Sinapi = { lerReferencia, guardar, listar, abrir, excluir };
})();
