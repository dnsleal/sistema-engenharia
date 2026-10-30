// Cálculo de prazos administrativos.
// Regra: não se conta o dia do começo; inclui-se o do vencimento; se o vencimento cair
// em dia sem expediente (fim de semana ou feriado), prorroga-se para o próximo dia útil.
//   corridos: conta todos os dias
//   úteis:    conta só os dias com expediente
// Dias sem expediente: sábados, domingos, feriados nacionais, aniversário de Cuiabá (8/4)
// e os pontos facultativos usuais (Carnaval segunda e terça, Sexta-feira Santa, Corpus Christi).
// Datas sempre como texto 'AAAA-MM-DD' (sem fuso horário, para não "voltar um dia").
(function (raiz) {
  const FIXOS = {
    '01-01': 'Confraternização Universal', '04-08': 'Aniversário de Cuiabá', '04-21': 'Tiradentes',
    '05-01': 'Dia do Trabalho', '09-07': 'Independência', '10-12': 'Nossa Senhora Aparecida',
    '11-02': 'Finados', '11-15': 'Proclamação da República', '11-20': 'Consciência Negra', '12-25': 'Natal'
  };
  const cacheMoveis = {};

  const dt = s => { const [a, m, d] = s.split('-').map(Number); return new Date(Date.UTC(a, m - 1, d)); };
  const iso = d => d.toISOString().slice(0, 10);
  const soma = (s, n) => { const d = dt(s); d.setUTCDate(d.getUTCDate() + n); return iso(d); };

  // Domingo de Páscoa (algoritmo de Meeus/Jones/Butcher)
  function pascoa(a) {
    const A = a % 19, B = Math.floor(a / 100), C = a % 100, D = Math.floor(B / 4), E = B % 4,
      F = Math.floor((B + 8) / 25), G = Math.floor((B - F + 1) / 3), H = (19 * A + B - D - G + 15) % 30,
      I = Math.floor(C / 4), K = C % 4, L = (32 + 2 * E + 2 * I - H - K) % 7, M = Math.floor((A + 11 * H + 22 * L) / 451),
      mes = Math.floor((H + L - 7 * M + 114) / 31), dia = ((H + L - 7 * M + 114) % 31) + 1;
    return iso(new Date(Date.UTC(a, mes - 1, dia)));
  }
  function moveis(a) {
    if (!cacheMoveis[a]) {
      const p = pascoa(a);
      cacheMoveis[a] = {
        [soma(p, -48)]: 'Carnaval (ponto facultativo)', [soma(p, -47)]: 'Carnaval (ponto facultativo)',
        [soma(p, -2)]: 'Sexta-feira Santa', [soma(p, 60)]: 'Corpus Christi (ponto facultativo)'
      };
    }
    return cacheMoveis[a];
  }

  function feriado(s) { return FIXOS[s.slice(5)] || moveis(Number(s.slice(0, 4)))[s] || null; }
  function util(s) { const w = dt(s).getUTCDay(); return w !== 0 && w !== 6 && !feriado(s); }
  function proximoUtil(s) { while (!util(s)) s = soma(s, 1); return s; }

  // data-limite a partir da data de entrada/ciência
  function limite(inicio, dias, contagem) {
    if (!inicio || dias == null || dias === '' || isNaN(dias)) return null;
    dias = Number(dias);
    if (contagem === 'uteis') {
      let s = inicio, n = 0;
      while (n < dias) { s = soma(s, 1); if (util(s)) n++; }
      return dias === 0 ? proximoUtil(inicio) : s;
    }
    return proximoUtil(soma(inicio, dias));
  }

  function hoje() {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  }
  // dias corridos entre hoje e o limite (negativo = vencido)
  function diasAte(lim, ref = hoje()) { return lim ? Math.round((dt(lim) - dt(ref)) / 864e5) : null; }

  const api = { limite, util, feriado, proximoUtil, diasAte, hoje, soma, pascoa };
  if (typeof module !== 'undefined' && module.exports) module.exports = api; else raiz.Prazos = api;
})(typeof window !== 'undefined' ? window : globalThis);
