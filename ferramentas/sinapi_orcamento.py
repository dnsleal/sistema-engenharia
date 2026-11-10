# Uso: python sinapi_orcamento.py SINAPI_Referencia_AAAA_MM.xlsx AAAA-MM orcamento/bases/sinapi-mt-AAAA-MM.obracerta.json.gz
# Gera a base no formato do app de orçamento (ObraCerta) a partir do SINAPI_Referência (só MT)
import openpyxl, json, sys, gzip, re, math
REF, MES, SAIDA = sys.argv[1], sys.argv[2], sys.argv[3]   # MES = 'AAAA-MM'
UF='MT'
def num(v):
    if v is None or v=='' or v=='-': return None
    if isinstance(v,(int,float)): return float(v)
    try: return float(str(v).replace('.','').replace(',','.'))
    except: return None
def cod(v):
    if v is None: return ''
    if isinstance(v,float) and v.is_integer(): v=int(v)
    return str(v).strip()
wb=openpyxl.load_workbook(REF, read_only=True, data_only=True)
wf=openpyxl.load_workbook(REF, read_only=True)
rows=lambda ws:[list(r) for r in ws.iter_rows(values_only=True)]
def achar(R,alvo,ate=15):
    for i in range(ate):
        r=[str(x).strip().upper() if x is not None else '' for x in (R[i] if i<len(R) else [])]
        if alvo in r: return i, r.index(alvo)
    raise Exception('UF')
info={}
def ler(sh, comp):
    R=rows(wb[sh])
    if comp:
        Fm=rows(wf[sh])
        for r,f in zip(R,Fm):
            if isinstance(f[1],str) and f[1].startswith('=HYPERLINK'):
                m=re.search(r',\s*"?(\d+)"?\s*\)\s*$', f[1])
                if m: r[1]=m.group(1)
    info.setdefault('mes', R[2][1]); info.setdefault('emissao', R[3][1])
    h=next(i for i,r in enumerate(R[:20]) if any(isinstance(x,str) and x.strip().upper().startswith('DESCRI') for x in r))
    _,c=achar(R,UF)
    enc=None
    for r in R[:9]:
        if 'Horista' in r: enc=enc or {}; enc['h']=round(num(r[c])*100,2) if num(r[c]) is not None else None
        if 'Mensalista' in r: enc=enc or {}; enc['m']=round(num(r[c])*100,2) if num(r[c]) is not None else None
    return R,h,c,enc
I={}; ordemI=[]; encargos={}
for sh,k in [('ISD','nd'),('ICD','d')]:
    R,h,c,enc=ler(sh,False); encargos[k]=enc
    for r in R[h+1:]:
        if len(r)<=c: continue
        k2=cod(r[1]); d=r[2]
        if not k2 or not d: continue
        p=num(r[c]); orig=str(r[4] or '').strip()
        if k2 not in I: I[k2]=[k2.zfill(6),'','',None,None,orig or '-']; ordemI.append(k2)
        I[k2][1]=' '.join(str(d).split()); I[k2][2]=str(r[3] or '').strip()
        I[k2][3 if k=='nd' else 4]=p if p else None
C={}; ordemC=[]; grupos=[]
for sh,k in [('CSD','nd'),('CCD','d')]:
    R,h,c,enc=ler(sh,True)
    for r in R[h+1:]:
        if len(r)<=c+1: continue
        k2=cod(r[1]); d=r[2]
        if not k2 or k2=='0' or not d: continue
        g=str(r[0] or '').strip()
        if g not in grupos: grupos.append(g)
        p=num(r[c]); a=num(r[c+1])
        if k2 not in C: C[k2]=[k2,' '.join(str(d).split()),str(r[3] or '').strip(),grupos.index(g),None,None,None,None]; ordemC.append(k2)
        i=4 if k=='nd' else 5
        C[k2][i]=p if p else None
        C[k2][i+2]=int(math.floor(a*100+0.5)) if a else None
R=rows(wb['Analítico'])
h=next(i for i,r in enumerate(R[:20]) if r and r[0]=='Grupo')
A={}
for r in R[h+1:]:
    comp=cod(r[1]); ti=r[2]
    if not comp or not ti: continue
    A.setdefault(comp,[]).append(['C' if str(ti).upper().startswith('COMP') else 'I', cod(r[3]), num(r[6]) or 0])
for v in I.values():
    if v[3] is None and v[4] is None: v[5]='-'
mes=str(info['mes']); em=info['emissao']
em=em.strftime('%d/%m/%Y') if hasattr(em,'strftime') else str(em)
out={'id':f'SINAPI-{UF}-{MES}','fonte':'SINAPI','uf':UF,'ref':MES,'desc':f'SINAPI Cuiabá-{UF} {mes} (emissão {em})',
     'encargos':encargos,'grupos':grupos,'I':[I[k] for k in sorted(ordemI,key=lambda x:int(x) if x.isdigit() else 10**9)],'C':[C[k] for k in ordemC],'A':{k:sorted(A.get(k,[]),key=lambda e:int(e[1]) if e[1].isdigit() else 10**9) for k in ordemC}}
s=json.dumps(out,ensure_ascii=False,separators=(',',':'))
open(SAIDA,'wb').write(gzip.compress(s.encode(),9))
print(out['desc'],'I',len(out['I']),'C',len(out['C']),'A',len(out['A']),'enc',encargos,'MB',round(len(s)/1e6,2))
