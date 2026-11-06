"""Keep Arial labels editable; group TeX math outlines for exact rendering."""
import argparse
import copy
import re
import xml.etree.ElementTree as ET

parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument('text_svg', help='dvisvgm SVG with text')
parser.add_argument('outline_svg', help='matching dvisvgm SVG with outlined glyphs')
parser.add_argument('output', help='editable output SVG')
args = parser.parse_args()
ns = '{http://www.w3.org/2000/svg}'
ink = '{http://www.inkscape.org/namespaces/inkscape}'
ET.register_namespace('', ns[1:-1])
ET.register_namespace('xlink', 'http://www.w3.org/1999/xlink')
ET.register_namespace('inkscape', ink[1:-1])
root = ET.parse(args.text_svg).getroot()
outlined = ET.parse(args.outline_svg).getroot()
style = root.find(ns + 'style')
classes = dict(re.findall(r'text\.(\w+) \{font-family:([^;]+);', style.text))
# Plain Arial labels contain only native XeTeX fonts. Math nodes also
# contain Computer Modern symbols, so no generated font ID is hard-coded.
plain_classes = {cls for cls, family in classes.items() if family.startswith('nf')}
groups = [g for g in root.iter(ns + 'g') if g.get('stroke') == 'none']
path_groups = [g for g in outlined.iter(ns + 'g') if g.get('stroke') == 'none']
assert len(groups) == len(path_groups), 'SVG exports have different structures'
counts = {'text': 0, 'math': 0}
for group, paths in zip(groups, path_groups):
    texts = group.findall(ns + 'text')
    if not texts:
        continue
    label = ''.join(''.join(t.itertext()) for t in texts)
    if all(t.get('class') in plain_classes for t in texts):
        counts['text'] += 1
        group.set('id', f'label-{counts["text"]}')
        readable = {
            'AgK-edge': 'Ag K-edge', '10cm': '10 cm',
            'Support:52×27mm': 'Support: 52 × 27 mm',
            'X-RayTube': 'X-Ray Tube', 'EntranceSlit': 'Entrance Slit',
            'CollimatingSlit': 'Collimating Slit', 'AgSample': 'Ag Sample',
            'MultichannelCZT': 'Multichannel CZT',
        }
        lines = []
        for original in texts:
            # dvisvgm can put multiple TeX lines into one text element.
            # Split on explicit y changes before normalizing word spaces.
            segments = []
            current_y = original.get('y')
            current_x = original.get('x')
            value = original.text or ''
            for span in original:
                next_y = span.get('y', current_y)
                if next_y != current_y and value:
                    segments.append((current_x, current_y, value))
                    value = ''
                    current_x = span.get('x', original.get('x'))
                current_y = next_y
                value += ''.join(span.itertext())
            segments.append((current_x, current_y, value))
            fill = next((t.get('fill') for t in original.iter() if t.get('fill')), '#243746')
            size = re.search(r'text\.' + original.get('class') + r' \{[^}]*font-size:([^;}]+)', style.text).group(1)
            for x, y, value in segments:
                node = copy.deepcopy(original)
                node.set('x', x)
                node.set('y', y)
                lines.append((node, readable.get(value, value), fill, size))
        for original in texts:
            group.remove(original)
        group.append(lines[0][0])
        group.set(ink + 'label', ' / '.join(value for _, value, _, _ in lines))
        first = lines[0][0]
        for node, value, fill, size in lines:
            node[:] = []
            node.text = value
            node.set('fill', fill)
            node.set('style', f'font-family:Arial;font-size:{size};font-weight:normal')
            node.attrib.pop('class', None)
        # Keep explicitly positioned lines as editable text objects in one
        # label group. Inkscape otherwise reflows multiline tspans on import.
        for node, _, _, _ in lines[1:]:
            group.append(node)
    else:
        counts['math'] += 1
        group[:] = [copy.deepcopy(child) for child in paths]
        group.set('id', f'formula-{counts["math"]}')
        group.set(ink + 'label', 'Formula: ' + label)
for defs in outlined.findall(ns + 'defs'):
    root.insert(0, copy.deepcopy(defs))
root.remove(style)
ET.ElementTree(root).write(args.output, encoding='UTF-8', xml_declaration=True)
print(f'Editable SVG: {counts["text"]} text groups, {counts["math"]} vector formula groups')
