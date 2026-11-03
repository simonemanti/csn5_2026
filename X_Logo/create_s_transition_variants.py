from pathlib import Path
import xml.etree.ElementTree as ET
import subprocess
out=Path(__file__).resolve().parent
source=(out/'PRISM_08_rosso_forte.svg').read_text()
ns={'s':'http://www.w3.org/2000/svg'}
old=ET.fromstring(source).find('.//s:path[@id="S-edge"]',ns).attrib['d']
variants=[
('12_S_classica','S più leggibile','M 932,503 C 952,541 992,550 1035,550 C 1092,550 1134,527 1134,486 C 1134,449 1099,434 1041,416 C 985,399 945,380 945,340 C 945,287 985,240 1036,240 C 1081,240 1109,288 1145,288 C 1174,288 1192,250 1218,250 C 1245,250 1263,284 1289,284 C 1312,284 1326,264 1347,264 C 1371,264 1386,282 1411,282 H 1483'),
('13_S_transizione','S con salita più netta','M 929,513 C 955,543 993,550 1037,550 C 1096,550 1134,526 1134,486 C 1134,444 1090,430 1040,415 C 988,400 966,380 969,343 C 971,294 990,234 1034,234 C 1082,234 1109,289 1145,289 C 1174,289 1192,250 1218,250 C 1245,250 1263,284 1289,284 C 1312,284 1326,264 1347,264 C 1371,264 1386,282 1411,282 H 1483'),
('14_S_edge','S più stilizzata, bordo più ripido','M 924,531 C 958,544 994,550 1034,550 C 1093,550 1132,526 1132,486 C 1132,451 1098,433 1058,419 C 1021,406 1004,387 1007,353 L 1014,290 C 1018,255 1036,225 1061,225 C 1095,225 1117,289 1148,289 C 1177,289 1193,248 1218,248 C 1245,248 1264,289 1289,289 C 1311,289 1325,260 1345,260 C 1369,260 1384,284 1408,284 C 1432,284 1442,282 1459,282 H 1483')]
rows=[]
for i,(name,label,d) in enumerate(variants):
 svg=source.replace(old,d).replace('PRISM — 08_rosso_forte','PRISM — '+label)
 p=out/('PRISM_'+name+'.svg');p.write_text(svg)
 subprocess.run(['inkscape',str(p),'--export-background=white','--export-filename='+str(p.with_suffix('.png'))],check=True,capture_output=True)
 root=ET.fromstring(svg)
 groups=''.join(ET.tostring(g,encoding='unicode') for g in root.findall('s:g',ns))
 rows.append(f'<text x="45" y="{i*340+30}" font-family="sans-serif" font-size="20" fill="#555">{label}</text><g transform="translate(-105,{i*340-110}) scale(.72)">{groups}</g>')
board='<svg xmlns="http://www.w3.org/2000/svg" width="1100" height="1020" viewBox="0 0 1100 1020"><rect width="1100" height="1020" fill="white"/>'+''.join(rows)+'</svg>'
p=out/'PRISM_S_transizione_confronto.svg';p.write_text(board)
subprocess.run(['inkscape',str(p),'--export-filename='+str(p.with_suffix('.png'))],check=True,capture_output=True)
print('Created three SVGs and PNG previews.')
