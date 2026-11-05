"""Generate XANES-only dash variants from the current TikZ source and reference data."""
from pathlib import Path
import copy
import os
import re
import runpy
import subprocess
import tempfile
import xml.etree.ElementTree as ET
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
REFERENCE = ROOT.parent / '21_XANES_Ag'
OPTIONS = [
    ('A', 'Attuale', 'on 2pt off 1.2pt', '2 / 1.2 pt'),
    ('B', 'Corto, spaziato', 'on 1pt off 1.8pt', '1 / 1.8 pt'),
    ('C', 'Medio, spaziato', 'on 2pt off 2.5pt', '2 / 2.5 pt'),
    ('D', 'Lungo', 'on 3.5pt off 2.5pt', '3.5 / 2.5 pt'),
    ('E', 'Molto lungo', 'on 4.5pt off 3.5pt', '4.5 / 3.5 pt'),
    ('F', 'Puntinato', 'on 0pt off 2pt', '0 / 2 pt'),
]
NS = 'http://www.w3.org/2000/svg'
ET.register_namespace('', NS)
ET.register_namespace('xlink', 'http://www.w3.org/1999/xlink')

def run(*args, **kwargs):
    result = subprocess.run(args, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, **kwargs)
    if result.returncode:
        raise RuntimeError(result.stdout)

preamble = (ROOT / 'Focusing_Area.tex').read_text().split(r'\begin{document}')[0]
body = r'''
\begin{document}
\begin{tikzpicture}[focusing]
\path[use as bounding box] (-1.10,-1.10) rectangle (1.10,1.10);
\begin{pgfinterruptboundingbox}
\coordinate (XANES) at (0,0);
\DrawXANES{XANES}
\end{pgfinterruptboundingbox}
\end{tikzpicture}
\end{document}
'''
module = runpy.run_path(str(REFERENCE / 's1_ref_comparison.py'))
with tempfile.TemporaryDirectory(prefix='xanes-dashes-') as temp:
    tmp = Path(temp)
    for folder, filename, *_ in module['SAMPLES']:
        energy, mu = np.loadtxt(REFERENCE / 'data' / folder / filename).T
        normalized, _ = module['normalize'](energy, mu, 25514., (-280., -150.), (150., 700.))
        name = 'oxide' if folder == 'Ag2O' else 'metal'
        np.savetxt(tmp / f'xanes_{name}.dat', np.column_stack((energy, normalized)), fmt='%.12g')
    for key, title, pattern, label in OPTIONS:
        name = f'XANES_{key}'
        source = re.sub(r'dash pattern=on [0-9.]+pt off [0-9.]+pt', f'dash pattern={pattern}', preamble, count=1) + body
        (tmp / f'{name}.tex').write_text(source)
        run('xelatex', '-no-pdf', '-interaction=nonstopmode', '-halt-on-error', f'{name}.tex', cwd=tmp)
        run('dvisvgm', '--no-fonts', '--bbox=papersize', f'--output={HERE / (name + ".svg")}', str(tmp / (name + '.xdv')), cwd=tmp)
        run('inkscape', str(HERE / (name + '.svg')), '--export-width=660', '--export-background-opacity=0', f'--export-filename={HERE / (name + ".png")}')
        print(f'{key}: {title} ({label})', flush=True)

# Contact sheet embeds original vector objects, never rasterizes the curves.
root = ET.Element(f'{{{NS}}}svg', {'width': '180mm', 'height': '139mm', 'viewBox': '0 0 900 695'})
ET.SubElement(root, f'{{{NS}}}rect', {'width':'900', 'height':'695', 'fill':'white'})
def text(x, y, value, size=17, weight='normal'):
    e = ET.SubElement(root, f'{{{NS}}}text', {'x':str(x),'y':str(y),'text-anchor':'middle','font-family':'Arial','font-size':str(size),'font-weight':weight,'fill':'#002a48'})
    e.text = value
text(450, 29, 'XANES — confronto tratteggi', 23, 'bold')
text(450, 55, 'Ag₂O continua · Ag metallico tratteggiato · stessa scala e spessore', 16)
for index, (key, title, pattern, label) in enumerate(OPTIONS):
    x = 150 + (index % 3) * 300
    y = 85 + (index // 3) * 300
    icon = ET.parse(HERE / f'XANES_{key}.svg').getroot()
    ids = {e.get('id'):key + '-' + e.get('id') for e in icon.iter() if e.get('id')}
    for e in icon.iter():
        for attr, value in list(e.attrib.items()):
            if attr == 'id': e.set(attr, ids[value]); continue
            for old, new in ids.items():
                value = value.replace('url(#' + old + ')', 'url(#' + new + ')')
                if value == '#' + old: value = '#' + new
            e.set(attr, value)
    icon.attrib.update(x=str(x-110), y=str(y), width='220', height='220')
    root.append(icon)
    text(x, y+246, key + ' · ' + title, 18, 'bold')
    text(x, y+270, 'tratto / spazio: ' + label, 15)
ET.ElementTree(root).write(HERE / 'Confronto.svg', encoding='UTF-8', xml_declaration=True)
run('inkscape', str(HERE / 'Confronto.svg'), '--export-width=1800', f'--export-filename={HERE / "Confronto.png"}')
print('Saved Confronto.svg and Confronto.png')
