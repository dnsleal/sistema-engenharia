// Valor em reais por extenso: Extenso.reais(34971.16) → "trinta e quatro mil novecentos e setenta e um reais e dezesseis centavos"
(function () {
  const U = ['', 'um', 'dois', 'três', 'quatro', 'cinco', 'seis', 'sete', 'oito', 'nove', 'dez', 'onze', 'doze', 'treze', 'quatorze', 'quinze', 'dezesseis', 'dezessete', 'dezoito', 'dezenove'];
  const D = ['', '', 'vinte', 'trinta', 'quarenta', 'cinquenta', 'sessenta', 'setenta', 'oitenta', 'noventa'];
  const C = ['', 'cento', 'duzentos', 'trezentos', 'quatrocentos', 'quinhentos', 'seiscentos', 'setecentos', 'oitocentos', 'novecentos'];
  function ate999(n) {
    if (n === 0) return '';
    if (n === 100) return 'cem';
    const c = Math.floor(n / 100), r = n % 100, p = [];
    if (c) p.push(C[c]);
    if (r) p.push(r < 20 ? U[r] : D[Math.floor(r / 10)] + (r % 10 ? ' e ' + U[r % 10] : ''));
    return p.join(' e ');
  }
  // escalas: [singular, plural]
  const ESC = [['', ''], ['mil', 'mil'], ['milhão', 'milhões'], ['bilhão', 'bilhões']];
  function inteiro(n) {
    if (n === 0) return 'zero';
    const g = []; while (n > 0) { g.push(n % 1000); n = Math.floor(n / 1000); }
    const partes = [];
    for (let i = g.length - 1; i >= 0; i--) {
      const v = g[i]; if (!v) continue;
      let t = i === 1 && v === 1 ? 'mil' : ate999(v) + (i ? ' ' + (v === 1 ? ESC[i][0] : ESC[i][1]) : '');
      partes.push({ t, v, i });
    }
    // "e" entre os grupos: só antes do último grupo quando ele é < 100 ou centena exata
    return partes.map((p, k) => {
      if (k === 0) return p.t;
      const ultimo = k === partes.length - 1;
      return (ultimo && (p.v < 100 || p.v % 100 === 0) ? ' e ' : ' ') + p.t;
    }).join('');
  }
  function reais(valor) {
    const cent = Math.round(Math.abs(Number(valor) || 0) * 100);
    const r = Math.floor(cent / 100), c = cent % 100;
    const pr = r ? inteiro(r) + (r === 1 ? ' real' : (r % 1000000 === 0 ? ' de reais' : ' reais')) : '';
    const pc = c ? inteiro(c) + (c === 1 ? ' centavo' : ' centavos') : '';
    return pr && pc ? `${pr} e ${pc}` : (pr || pc || 'zero real');
  }
  const maiuscula = s => s.charAt(0).toUpperCase() + s.slice(1);
  window.Extenso = { reais, inteiro, maiuscula };
})();
