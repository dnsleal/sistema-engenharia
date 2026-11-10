# Uso: python sinapi_auditoria.py SINAPI_Referencia_AAAA_MM.xlsx SINAPI_mao_de_obra_AAAA_MM.xlsx MM/AAAA orcamento/bases/sinapi-mt-AAAA-MM.json
import openpyxl, json, sys, gzip, os
REF, MO, mes, SAIDA = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
UF='MT'
def num(v):
    if v is None or v=='': return None
    try: return float(str(v).replace(',','.')) if not isinstance(v,(int,float)) else float(v)
    except: return None
def cod(v):
    if v is None: return ''
    if isinstance(v,float) and v.is_integer(): v=int(v)
    return str(v).strip()
wb=openpyxl.load_workbook(REF, read_only=True, data_only=True)
wf=openpyxl.load_workbook(REF, read_only=True)
import re
def rows(ws): return [list(r) for r in ws.iter_rows(values_only=True)]
def achar(R, alvo, ate=15):
    for i in range(ate):
        r=[str(x).strip().upper() if x is not None else '' for x in (R[i] if i<len(R) else [])]
        if alvo in r: return i, r.index(alvo)
    raise Exception('UF não achada')
bases=[]; precos={}; precosAS={'Não desonerado':{}, 'Desonerado':{}}
for sh,tipo,reg in [('ISD','I','Não desonerado'),('ICD','I','Desonerado'),('CSD','C','Não desonerado'),('CCD','C','Desonerado')]:
    R=rows(wb[sh])
    if sh.startswith('C'):
        # código está dentro da fórmula HYPERLINK(...,104658): o valor salvo é 0
        F=rows(wf[sh])
        for i,(r,f) in enumerate(zip(R,F)):
            if isinstance(f[1],str) and f[1].startswith('=HYPERLINK'):
                m=re.search(r',\s*"?(\d+)"?\s*\)\s*$', f[1])
                if m: r[1]=m.group(1)
    # cabeçalho: linha com "Descrição"
    h=next(i for i,r in enumerate(R[:20]) if any(isinstance(x,str) and x.strip().upper().startswith('DESCRI') for x in r))
    _,c=achar(R,UF)
    try: _,csp=achar(R,'SP')
    except Exception: csp=None
    cab=[str(x or '').upper() for x in R[h]]
    cc=1; cd=next(i for i,x in enumerate(cab) if x.startswith('DESCRI')); cu=next(i for i,x in enumerate(cab) if x.startswith('UNID'))
    itens=[]; sem=0
    for r in R[h+1:]:
        if len(r)<=c: continue
        k=cod(r[cc]); d=(r[cd] or '').strip() if isinstance(r[cd],str) else r[cd]
        if not k or not d: continue
        p=num(r[c])
        if (p is None or p == 0) and tipo=='I':
            # insumo sem preço em MT: a CAIXA usa o preço de SP (%AS) nas composições
            psp=num(r[csp]) if csp is not None and len(r)>csp else None
            if psp: precosAS[reg][k]=[' '.join(str(d).split()),str(r[cu] or '').strip(),round(psp,2)]
        if p is None or p == 0: sem+=1; continue
        itens.append([k,' '.join(str(d).split()),str(r[cu] or '').strip(),round(p,2)])
        precos[(reg,tipo,k)]=round(p,2)
    bases.append({'banco':'SINAPI','uf':UF,'mes':mes,'regime':reg,'tipo':'Composições' if tipo=='C' else 'Insumos','sheet':sh,'tipoItem':tipo,'itens':itens})
    print(sh, UF,'col',c, 'itens',len(itens),'sem preço/custo em MT',sem)
# analítico (coeficientes valem para todas as UFs)
R=rows(wb['Analítico'])
h=next(i for i,r in enumerate(R[:20]) if r and r[0]=='Grupo')
ana={}
for r in R[h+1:]:
    comp=cod(r[1]); ti=r[2]
    if not comp or not ti: continue
    ana.setdefault(comp,[]).append(['C' if str(ti).upper().startswith('COMP') else 'I', cod(r[3]), num(r[6]) or 0])
print('analítico: composições',len(ana),'linhas',sum(len(v) for v in ana.values()))
# % mão de obra MT
wm=openpyxl.load_workbook(MO, read_only=True, data_only=True); mo={}
for sh,k in [('SEM Desoneração','SD'),('COM Desoneração','CD')]:
    R=rows(wm[sh]); hi,c=achar(R,UF)
    mo[k]={cod(r[1]):round(num(r[c]),4) for r in R[hi+1:] if r and cod(r[1]) and num(r[c]) is not None}
    print('mão de obra',k,len(mo[k]))
out={'versao':1,'banco':'SINAPI','uf':UF,'mes':mes,'gerado':__import__('datetime').date.today().isoformat(),'fonte':f'CAIXA/IBGE — SINAPI_Referência, SINAPI_mão_de_obra {mes} (somente MT)',
     'bases':bases,'analitico':ana,'maoDeObra':mo,'precosAS':precosAS}
s=json.dumps(out,ensure_ascii=False,separators=(',',':'))
open(SAIDA,"w").write(s)
print('arquivo', round(len(s)/1e6,2),'MB; gzip', round(len(gzip.compress(s.encode()))/1e6,2),'MB')

