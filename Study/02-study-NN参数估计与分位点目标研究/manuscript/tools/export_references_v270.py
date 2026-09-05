"""Export the 19 manuscript references to RIS without adding new citations."""
from pathlib import Path
import re

M=Path(__file__).resolve().parents[1]
AUTHORS=[['Weibull, W.'],['Rinne, H.'],['Murthy, D.N.P.','Xie, M.','Jiang, R.'],
 ['Meeker, W.Q.','Escobar, L.A.'],['Xie, L.','Wu, N.','Yang, X.'],
 ['谢里阳','朱文慧','吴宁祥','杨小玉'],['Yang, X.','Xie, L.','Chen, J.','Zhao, B.','Wang, K.'],
 ['Koenker, R.','Bassett, G.'],['Elmachtoub, A.N.','Grigas, P.'],['Wilder, B.','Dilkina, B.','Tambe, M.'],
 ['Donti, P.L.','Amos, B.','Kolter, J.Z.'],['Abbasi, B.','Rabelo, L.','Hosseinkouchack, M.'],
 ['Cousineau, D.'],['Nagatsuka, H.','Kamakura, T.','Balakrishnan, N.'],['Gneiting, T.'],
 ['Jokiel-Rokita, A.','Piątek, S.'],['Nocedal, J.','Wright, S.J.'],
 ['Cranmer, K.','Brehmer, J.','Louppe, G.'],['Radev, S.T.','Mertens, U.K.','Voss, A.','Ardizzone, L.','Köthe, U.']]

def main():
 source=(M/'Study02论文初稿-v2.7.0.md').read_text(encoding='utf-8').split('## 参考文献')[1]
 refs=re.findall(r'^\[(\d+)\] (.+)$',source,re.M);assert len(refs)==len(AUTHORS)==19
 records=[]
 for (index,ref),authors in zip(refs,AUTHORS):
  year=re.search(r'\((\d{4})\)',ref).group(1);after=ref.split(f'({year}). ',1)[1]
  book=int(index) in {2,3,4,17}
  title=re.search(r'\*([^*]+)\*',after).group(1) if book else after.split('. *',1)[0]
  kind='BOOK' if book else ('CONF' if int(index) in {10,11} else 'JOUR')
  lines=[f'TY  - {kind}',f'ID  - Study02-{index}']
  lines += [f'AU  - {a}' for a in authors];lines += [f'PY  - {year}',f'TI  - {title}']
  if book:lines.append('PB  - '+{2:'Chapman & Hall/CRC Press',3:'Wiley-Interscience',4:'Wiley',17:'Springer'}[int(index)])
  if int(index)==17:lines.append('ET  - 2')
  if not book:
   journal=re.search(r'\*([^*]+)\*',after);assert journal,index
   lines.append('T2  - '+journal.group(1))
   tail=after[journal.end():]
   v=re.match(r',\s*(\d+)(?:\(([^)]+)\))?,\s*([^\.]+)\.',tail)
   if v:
    lines.append('VL  - '+v.group(1))
    if v.group(2):lines.append('IS  - '+v.group(2))
    pages=v.group(3).split('–');lines.append('SP  - '+pages[0])
    if len(pages)==2:lines.append('EP  - '+pages[1])
  doi=re.search(r'https://doi.org/(\S+)',ref)
  if doi:lines += ['DO  - '+doi.group(1),'UR  - '+doi.group(0)]
  lines += ['N1  - Exact manuscript reference: '+ref,'ER  - ']
  records.append('\n'.join(lines))
 dest=M/'submission/Study02-references-v2.7.0.ris';dest.write_text('\n\n'.join(records)+'\n',encoding='utf-8')
 assert dest.read_text(encoding='utf-8').count('TY  - ')==19
 print('PASS 19 RIS records exported from manuscript bibliography')

if __name__=='__main__':main()
