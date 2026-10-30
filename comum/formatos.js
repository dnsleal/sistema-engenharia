// Formatação no padrão brasileiro: R$, %, números e datas.
(function () {
  const brl = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' });
  const num2 = new Intl.NumberFormat('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

  const F = {
    rs:  v => (v == null || v === '') ? '—' : brl.format(Number(v)),
    pct: v => (v == null || v === '') ? '—' : num2.format(Number(v)) + '%',
    num: (v, casas = 2) => (v == null || v === '') ? '—'
      : Number(v).toLocaleString('pt-BR', { minimumFractionDigits: casas, maximumFractionDigits: casas }),
    // "2026-10-30" → "30/10/2026" (sem conversão de fuso, para não voltar um dia)
    data: s => s ? s.slice(0, 10).split('-').reverse().join('/') : '—',
    // Lê "1.234,56", "1234,56" ou "1234.56" como número
    lerNum: txt => {
      if (txt == null) return null;
      let t = String(txt).trim().replace(/\s|R\$/g, '');
      if (!t) return null;
      if (t.includes(',')) t = t.replace(/\./g, '').replace(',', '.');
      const n = Number(t);
      return Number.isFinite(n) ? n : null;
    },
    esc: s => String(s ?? '').replace(/[&<>"']/g, c =>
      ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]))
  };

  window.F = F;
})();
