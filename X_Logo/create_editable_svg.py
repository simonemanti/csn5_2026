"""Rebuild the PRISM concepts with a small number of editable Bezier nodes."""
from pathlib import Path
from xml.sax.saxutils import escape

OUT = Path(__file__).resolve().parent
letters = '''<g inkscape:groupmode="layer" inkscape:label="Lettere nere" id="letters" fill="#080909">
<path id="P" fill-rule="evenodd" d="M 291,568 V 312 H 408 C 475,312 509,345 509,395 C 509,447 473,479 408,479 H 337 V 568 Z M 337,352 V 439 H 405 C 444,439 462,423 462,395 C 462,368 444,352 405,352 Z"/>
<path id="R" fill-rule="evenodd" d="M 552,568 V 312 H 664 C 727,312 763,343 763,394 C 763,432 742,459 707,471 L 774,568 H 718 L 657,479 H 598 V 568 Z M 598,352 V 439 H 660 C 697,439 716,423 716,395 C 716,367 697,352 660,352 Z"/>
<path id="I" d="M 829,312 H 874 V 568 H 829 Z"/>
<path id="M" d="M 1198,568 V 312 H 1253 L 1341,453 L 1429,312 H 1483 V 568 H 1437 V 385 L 1341,533 L 1244,385 V 568 Z"/>
</g>'''
curves = {
'06_rosso_lieve': 'M 907,537 H 963 C 993,537 1003,525 1007,493 L 1022,325 C 1025,292 1040,268 1066,268 C 1093,268 1106,284 1140,284 C 1177,284 1205,275 1237,275 C 1273,275 1302,284 1340,284 C 1380,284 1404,279 1436,279 H 1483',
'07_rosso_medio': 'M 907,537 H 963 C 993,537 1003,524 1007,490 L 1022,310 C 1026,275 1044,250 1072,250 C 1105,250 1125,289 1157,289 C 1190,289 1211,259 1238,259 C 1268,259 1284,287 1311,287 C 1337,287 1355,270 1377,270 C 1400,270 1412,285 1437,285 H 1483',
'08_rosso_forte': 'M 907,537 H 963 C 993,537 1003,523 1007,486 L 1022,302 C 1026,258 1047,224 1071,224 C 1106,224 1121,291 1148,291 C 1177,291 1193,248 1218,248 C 1245,248 1264,289 1289,289 C 1311,289 1325,260 1345,260 C 1369,260 1384,284 1408,284 C 1432,284 1442,282 1459,282 H 1483',
}
for name, d in curves.items():
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape" width="1774" height="887" viewBox="0 0 1774 887">
<title>PRISM — {escape(name)}</title>
<desc>Editable vector reconstruction. Separate letter outlines and an open cubic Bezier absorption curve. Transparent background.</desc>
{letters}
<g inkscape:groupmode="layer" inkscape:label="Bordo XAS rosso" id="edge">
<path id="S-edge" d="{d}" fill="none" stroke="#E71932" stroke-width="34" stroke-linecap="butt" stroke-linejoin="round"/>
</g>
</svg>'''
    (OUT / f'PRISM_{name}.svg').write_text(svg)
    print(OUT / f'PRISM_{name}.svg')
