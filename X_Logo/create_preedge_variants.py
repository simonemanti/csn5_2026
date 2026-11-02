from pathlib import Path
import xml.etree.ElementTree as ET
import subprocess

out = Path(__file__).resolve().parent
source = (out / 'PRISM_08_rosso_forte.svg').read_text()
ns = {'s': 'http://www.w3.org/2000/svg'}
old = ET.fromstring(source).find('.//s:path[@id="S-edge"]', ns).attrib['d']
post = old[old.index('C 1026,258'):]
variants = [
 ('09_preedge_corto', 'Pre-edge corto', 'M 815,610 H 932 C 986,610 998,571 1004,500 L 1022,302 '),
 ('10_preedge_medio', 'Pre-edge medio', 'M 705,610 H 912 C 975,610 995,570 1003,500 L 1022,302 '),
 ('11_preedge_simmetrico', 'Pre-edge simmetrico', 'M 565,610 H 880 C 958,610 987,570 1000,500 L 1022,302 '),
]
for name, label, pre in variants:
    svg = source.replace(old, pre + post).replace('PRISM — 08_rosso_forte', 'PRISM — ' + label)
    path = out / ('PRISM_' + name + '.svg')
    path.write_text(svg)
    subprocess.run(['inkscape', str(path), '--export-background=white', '--export-filename=' + str(path.with_suffix('.png'))], check=True, capture_output=True)
# A vector comparison sheet; each logo keeps its paths.
rows=[]
for i,(name,label,_) in enumerate(variants):
    root=ET.fromstring((out/('PRISM_'+name+'.svg')).read_text())
    groups=''.join(ET.tostring(g,encoding='unicode') for g in root.findall('s:g',ns))
    rows.append(f'<text x="45" y="{i*380+35}" font-family="sans-serif" font-size="20" fill="#555">{label}</text><g transform="translate(-105,{i*380-100}) scale(.72)">{groups}</g>')
board='<svg xmlns="http://www.w3.org/2000/svg" width="1100" height="1140" viewBox="0 0 1100 1140"><rect width="1100" height="1140" fill="white"/>'+''.join(rows)+'</svg>'
path=out/'PRISM_preedge_confronto.svg'
path.write_text(board)
subprocess.run(['inkscape',str(path),'--export-filename='+str(path.with_suffix('.png'))],check=True,capture_output=True)
print('Created three editable SVG variants, PNG previews and comparison sheet.')
