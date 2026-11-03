"""PRISM animation v2: original concave crystal, reference XAS, moving arrows.

Run: blender --background --python Y_Animation/create_animation_v2.py
Parameters after Blender's -- separator; --help includes all defaults.
"""

from __future__ import annotations

import argparse
import bisect
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector, Quaternion

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from create_animation import curve, emission_material, linear_keys, progress, smooth

FPS, END = 24, 336


def arguments():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    p.add_argument('--source', type=Path, default=ROOT / 'v1_Animation.blend', help='Existing animation to revise.')
    p.add_argument('--crystal-source', type=Path, default=ROOT.parent / '11_SETUP_XAS/v1.2_Setup_PRISM.blend', help='Original Crystal object, imported intact.')
    p.add_argument('--xas-data', type=Path, default=ROOT / 'v2_xas_reference.json', help='Prepared Ag foil reference spectrum.')
    p.add_argument('--output', type=Path, default=ROOT / 'v2_Animation.blend', help='Destination Blender file.')
    p.add_argument('--arrow-cycle-frames', type=float, default=84, help='Frames for one forward arrow pass; shorter means faster.')
    p.add_argument('--fluorescence-cycle-frames', type=float, default=42, help='Frames for one fluorescence arrow pass.')
    p.add_argument('--arrow-travel-start', type=float, default=0.08, help='Start of the moving arrows as a fraction of each beam.')
    p.add_argument('--arrow-travel-end', type=float, default=0.92, help='End of the moving arrows as a fraction of each beam.')
    p.add_argument('--arrow-size', type=float, default=1.25, help='Arrowhead scale multiplier.')
    p.add_argument('--arrows-per-beam', type=int, default=2, help='Moving arrowheads on incident and diffracted arms.')
    p.add_argument('--crystal-sweep-deg', type=float, default=80, help='Total Z sweep, centred on the original orientation.')
    p.add_argument('--preview-frames', default='1,76,112,180', help='Comma-separated preview frames; empty skips previews.')
    p.add_argument('--preview-percent', type=int, default=75, help='Preview resolution percentage; blend stays Full HD.')
    a = p.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])
    if min(a.arrow_cycle_frames, a.fluorescence_cycle_frames) <= 0:
        p.error('Arrow cycle lengths must be positive.')
    if not 0 <= a.arrow_travel_start < a.arrow_travel_end <= 1:
        p.error('Require 0 <= arrow-travel-start < arrow-travel-end <= 1.')
    if a.arrows_per_beam < 1 or a.arrow_size <= 0:
        p.error('Arrow count and size must be positive.')
    return a


def interp(xs, ys, x):
    i = max(0, min(len(xs) - 2, bisect.bisect_right(xs, x) - 1))
    a = (x - xs[i]) / (xs[i + 1] - xs[i])
    return ys[i] * (1 - a) + ys[i + 1] * a


def add_driver(obj, path, index, expression, controls, variables):
    d = obj.driver_add(path, index).driver
    d.type = 'SCRIPTED'
    for name, prop in variables.items():
        v = d.variables.new()
        v.name, v.type = name, 'SINGLE_PROP'
        v.targets[0].id = controls
        v.targets[0].data_path = f'["{prop}"]'
    d.expression = expression


def main():
    args = arguments()
    data = json.loads(args.xas_data.read_text())
    xs, ys = data['relative_energy_eV'], data['normalized_absorption']
    xmin, xmax = xs[0], xs[-1]
    edge = data['edge_progress']
    bpy.ops.wm.open_mainfile(filepath=str(args.source.resolve()))
    scene = bpy.context.scene
    old_center = bpy.data.objects['Ge_880_crystal'].location.copy()
    for name in ('Ge_880_crystal', 'Crystal_rotating_rim', 'Z_rotation_pointer', 'Z_rotation_base_ring', 'Z_rotation_spindle', 'XAS_static_curve', 'XAS_static_axes'):
        obj = bpy.data.objects.get(name)
        if obj:
            bpy.data.objects.remove(obj, do_unlink=True)
    # Keep the exact source mesh, original object scale and material nodes.
    with bpy.data.libraries.load(str(args.crystal_source.resolve()), link=False) as (source, target):
        assert 'Crystal' in source.objects
        target.objects = ['Crystal']
    crystal = target.objects[0]
    scene.collection.children['PRISM_Assets'].objects.link(crystal)
    crystal.location = old_center
    angle0 = crystal.rotation_euler.z
    crystal['source_blend'] = '//../11_SETUP_XAS/v1.2_Setup_PRISM.blend'
    crystal['source_object'] = 'Crystal'
    crystal['preserved'] = 'Mesh, material, scale, shading and base orientation; translated to optical centre, animated only around Z.'
    crystal['base_angle_z_radians'] = angle0

    # Pure white camera background; original HDRI still supplies object lighting.
    bg = scene.world.node_tree.nodes['Neutral camera background']
    bg.inputs['Color'].default_value = (1, 1, 1, 1)
    bg.inputs['Strength'].default_value = 1
    scene.render.film_transparent = False
    scene.compositing_node_group = None
    scene['background'] = 'white RGB 255 255 255'
    scene['annotations'] = 'Only graph axes and ticks are labelled.'
    scene.render.resolution_percentage = 100
    scene.render.resolution_x, scene.render.resolution_y = 1920, 1080

    controls = bpy.data.objects['Scan_progress']
    controls.name = 'Animation_Controls'
    controls['edge_progress'] = edge
    controls['edge_energy_eV'] = data['e0_derivative_eV']
    props = {
        'arrow_cycle_frames': (args.arrow_cycle_frames, 'Frames per beam pass; smaller = faster.', 1, 1000),
        'fluorescence_cycle_frames': (args.fluorescence_cycle_frames, 'Frames per fluorescence pass.', 1, 1000),
        'arrow_travel_start': (args.arrow_travel_start, 'First visible fraction of each beam.', 0, 1),
        'arrow_travel_end': (args.arrow_travel_end, 'Last visible fraction of each beam.', 0, 1),
        'arrow_size': (args.arrow_size, 'Arrow scale; changes all moving arrows.', 0.05, 5),
    }
    for key, (value, description, low, high) in props.items():
        controls[key] = float(value)
        controls.id_properties_ui(key).update(description=description, min=low, max=high)
    controls['arrows_per_beam'] = args.arrows_per_beam
    controls['crystal_sweep_deg'] = args.crystal_sweep_deg

    collection = bpy.data.collections.new('V2 | reference XAS and axes')
    scene.collection.children.link(collection)
    camera = scene.camera
    bpy.context.view_layer.update()
    basis = camera.matrix_world.to_3x3()
    right, up, forward = (basis @ Vector(v) for v in ((1, 0, 0), (0, 1, 0), (0, 0, -1)))
    width = camera.data.ortho_scale
    height = width * 1080 / 1920

    def screen(u, v, depth=1000):
        return camera.location + forward * depth + right * ((u - .5) * width) + up * ((v - .5) * height)

    # Plot coordinates leave room for readable tick values and both axis labels.
    left, bottom, gw, gh = .715, .58, .247, .275
    ymin, ymax = -.05, 1.15

    def xy(x, y):
        return screen(left + gw * (x - xmin) / (xmax - xmin), bottom + gh * (y - ymin) / (ymax - ymin))

    plot_mat, _ = emission_material('V2 | XAS deep teal', (.008, .15, .22), 1)
    ink, _ = emission_material('V2 | axis ink', (.025, .035, .045), 1)
    grid, _ = emission_material('V2 | faint grid', (.78, .81, .83), 1)
    trace = curve('XAS_static_curve', [xy(x, y) for x, y in zip(xs, ys)], 1.05, plot_mat, collection)
    trace['reference'] = 'Ag foil, NIMS/JASRI, DOI 10.48505/nims.1453'
    trace['data_text'] = 'V2_XAS_reference.json'
    trace['x_axis'] = 'Energy relative to slope-defined E0 of reference dataset.'
    curve('XAS_static_axes', [xy(xmin, ymax), xy(xmin, ymin), xy(xmax, ymin)], .55, ink, collection)
    font_path = Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')
    font = bpy.data.fonts.load(str(font_path)) if font_path.exists() else bpy.data.fonts.get('Bfont')

    def label(name, text, uv, pixels, rotation=0, align='CENTER'):
        cu = bpy.data.curves.new(name, 'FONT')
        cu.body, cu.align_x, cu.align_y = text, align, 'CENTER'
        cu.font = font
        cu.size = width * pixels / 1920
        cu.resolution_u = 12
        ob = bpy.data.objects.new(name, cu)
        collection.objects.link(ob)
        ob.location = screen(*uv, depth=995)
        ob.rotation_mode = 'QUATERNION'
        ob.rotation_quaternion = camera.matrix_world.to_quaternion() @ Quaternion((0, 0, 1), rotation)
        cu.materials.append(ink)
        return ob

    for x in (-40, 0, 40, 80, 120):
        u = left + gw * (x - xmin) / (xmax - xmin)
        curve(f'XAS_tick_x_{x}', [screen(u, bottom), screen(u, bottom - .007)], .48, ink, collection)
        label(f'XAS_tick_x_label_{x}', str(x).replace('-', '−'), (u, bottom - .024), 22)
    for y in (0, .5, 1):
        v = bottom + gh * (y - ymin) / (ymax - ymin)
        curve(f'XAS_grid_y_{y}', [screen(left, v, 1002), screen(left + gw, v, 1002)], .24, grid, collection)
        curve(f'XAS_tick_y_{y}', [screen(left - .004, v), screen(left, v)], .48, ink, collection)
        label(f'XAS_tick_y_label_{y}', f'{y:.1f}', (left - .010, v), 22, align='RIGHT')
    label('XAS_label_energy', 'E − E₀ (eV)', (left + gw / 2, bottom - .061), 27)
    label('XAS_label_absorption', 'Normalized absorption', (left - .053, bottom + gh / 2), 25, rotation=math.pi / 2)

    dot = bpy.data.objects['XAS_red_energy_marker']
    dot.animation_data_clear()
    red = next(n for n in dot.data.materials[0].node_tree.nodes if n.type == 'EMISSION')
    red.inputs['Color'].default_value = (.78, .004, .012, 1)
    red.inputs['Strength'].default_value = 1

    # High contrast beams on white. Preserve original beam curves and arrow shapes.
    gold = bpy.data.materials['Animation | incident gold']
    gold_node = next(n for n in gold.node_tree.nodes if n.type == 'EMISSION')
    gold_node.inputs['Color'].default_value = (.75, .21, .006, 1)
    gold_node.inputs['Strength'].default_value = 1
    gold.diffuse_color = (.75, .21, .006, 1)
    cyan = bpy.data.materials['Animation | fluorescence']
    cyan.node_tree.animation_data_clear()
    cyan_node = next(n for n in cyan.node_tree.nodes if n.type == 'EMISSION')
    cyan_node.inputs['Color'].default_value = (0, .15, .38, 1)
    sample_mat = bpy.data.materials['Animation | Ag emission']
    sample_mat.node_tree.animation_data_clear()
    sample_node = sample_mat.node_tree.nodes.get('Principled BSDF')
    sample_node.inputs['Emission Color'].default_value = (0, .18, .45, 1)
    # The original white housing disappears on white; retain geometry and add contrast.
    for m, color in zip(bpy.data.objects['CZT_detector'].data.materials, ((.20, .26, .30, 1), (.43, .49, .54, 1))):
        for node in m.node_tree.nodes:
            if node.type == 'BSDF_PRINCIPLED':
                node.inputs['Base Color'].default_value = color
        m.diffuse_color = color

    # Simple expression drivers expose live speed, travel and size controls in Blender.
    def move_arrow(obj, start, end, phase, fluorescent=False):
        obj.animation_data_clear()
        obj['motion'] = 'Forward flow along beam; adjust Animation_Controls custom properties.'
        obj['phase_offset'] = phase
        variables = dict(p='fluorescence_cycle_frames' if fluorescent else 'arrow_cycle_frames', a='arrow_travel_start', b='arrow_travel_end', size='arrow_size')
        ph = f'(((frame-1)/max(p,1)+{phase})%1)'
        fraction = f'(a+(b-a)*{ph})'
        for index in range(3):
            add_driver(obj, 'location', index, f'{start[index]}+({end[index]-start[index]})*{fraction}', controls, variables)
            add_driver(obj, 'scale', index, f'size*max(0.001,min(1,{ph}/0.08,(1-{ph})/0.08))', controls, variables)

    fluor_objects = []
    for path_name, arrow_name in [('Incident_beam', 'Incident_beam_direction'), ('Diffracted_beam', 'Diffracted_beam_direction'), ('Fluorescence_to_CZT', 'Fluorescence_direction')]:
        path = bpy.data.objects[path_name]
        points = path.data.splines[0].points
        start, stop = (path.matrix_world @ Vector(points[i].co[:3]) for i in (0, -1))
        original = bpy.data.objects[arrow_name]
        fluorescent = path_name == 'Fluorescence_to_CZT'
        count = 1 if fluorescent else args.arrows_per_beam
        for i in range(count):
            obj = original if i == 0 else original.copy()
            if i:
                obj.name = f'{arrow_name}_{i + 1:02d}'
                collection.objects.link(obj)
            phase = i / count + (.25 if path_name == 'Diffracted_beam' else 0)
            move_arrow(obj, start, stop, phase, fluorescent)
            if fluorescent:
                fluor_objects.append(obj)
    # One moving fluorescence arrow is sufficient; remove the previous photon train.
    for ob in list(scene.objects):
        if ob.name.startswith('Fluorescence_photon_'):
            bpy.data.objects.remove(ob, do_unlink=True)
    fluor_objects.extend([bpy.data.objects['Fluorescence_to_CZT'], bpy.data.objects['Ag_excited_spot']])
    for ob in fluor_objects:
        # Preserve motion drivers on the arrow while replacing only visibility curves.
        if ob.name != 'Fluorescence_direction':
            ob.animation_data_clear()

    # The original measured trace is fixed; only the red point scans across it.
    # Emission turns on at the reference curve's derivative-defined edge.
    timing = []
    for frame in range(1, END + 1):
        t = progress(frame)
        x = xmin + (xmax - xmin) * t
        y = interp(xs, ys, x)
        activation = smooth(x / 6.0)
        intensity = activation * max(0, min(1.15, y))
        controls['progress'] = t
        controls['relative_energy_eV'] = x
        controls.keyframe_insert(data_path='["progress"]', frame=frame)
        controls.keyframe_insert(data_path='["relative_energy_eV"]', frame=frame)
        crystal.rotation_euler.z = angle0 + math.radians(args.crystal_sweep_deg * (t - .5))
        crystal.keyframe_insert(data_path='rotation_euler', index=2, frame=frame)
        dot.location = xy(x, y) - forward * 4
        dot.keyframe_insert(data_path='location', frame=frame)
        sample_node.inputs['Emission Strength'].default_value = 1.8 * intensity
        sample_node.inputs['Emission Strength'].keyframe_insert(data_path='default_value', frame=frame)
        cyan_node.inputs['Strength'].default_value = .5 + 1.6 * intensity
        cyan_node.inputs['Strength'].keyframe_insert(data_path='default_value', frame=frame)
        for obj in fluor_objects:
            obj.hide_render = obj.hide_viewport = x <= 0
            obj.keyframe_insert(data_path='hide_render', frame=frame)
            obj.keyframe_insert(data_path='hide_viewport', frame=frame)
        timing.append(dict(frame=frame, progress=t, relative_energy_eV=x, normalized_absorption=y, fluorescence=intensity))
    for block in list(bpy.data.objects) + [sample_mat.node_tree, cyan.node_tree]:
        linear_keys(block)

    scene.timeline_markers.clear()
    markers = [('START', 1), ('SCAN UP', 25), ('EDGE UP', next(row['frame'] for row in timing if row['relative_energy_eV'] > 0)), ('HIGH ENERGY', 180), ('SCAN DOWN', 217), ('EDGE DOWN', next(row['frame'] for row in timing if row['frame'] > 216 and row['relative_energy_eV'] <= 0)), ('LOOP', 336)]
    for name, frame in markers:
        scene.timeline_markers.new(name, frame=frame)
    scene['animation_notes'] = 'v2: white background; exact Crystal from v1.2; 80-degree illustrative sweep; measured Ag foil reference curve; forward beam arrows controlled with simple expression drivers.'
    scene['reference_xas_doi'] = '10.48505/nims.1453'
    scene['reference_xas_is_prism_measurement'] = False
    scene['animation_source'] = '//v1_Animation.blend'
    scene['arrow_loop_note'] = 'At default periods 84/42 frames arrows repeat exactly every 336 frames; frame 337 equals frame 1.'
    for textblock in list(bpy.data.texts):
        if textblock.name.startswith('READ ME'):
            bpy.data.texts.remove(textblock)
    info = bpy.data.texts.new('READ ME - PRISM animation v2')
    info.write('PRISM animation v2 — 14 seconds, 24 fps, 1920×1080\n\nSpace: play. Numpad 0: camera.\n\nCrystal: appended intact from v1.2_Setup_PRISM.blend, object Crystal.\nOriginal mesh, scale, material and flat shading preserved.\n80-degree illustrative Z sweep; beam paths remain fixed.\n\nXAS: measured Ag foil reference from NIMS/JASRI, DOI 10.48505/nims.1453.\nPCHIP interpolation, no spectral smoothing or energy realignment.\nE0 is the maximum-slope energy of this reference dataset.\nThis reference is not a PRISM measurement or performance prediction.\nData and source metadata are embedded in V2_XAS_reference.json.\n\nSelect Animation_Controls > Object Properties > Custom Properties:\narrow_cycle_frames: 84 (3.5 s); smaller = faster.\nfluorescence_cycle_frames: 42 (1.75 s).\narrow_travel_start/end: 0.08/0.92; fractions of beam length.\narrow_size: 1.25. These parameters update live through simple drivers.\nFor an exactly periodic 14 s loop, use periods dividing 336 frames.\nArrow count and crystal sweep can be changed in create_animation_v2.py CLI.\n\nAll textures and font are packed. No Python handlers or auto-run required.\n')
    embedded = bpy.data.texts.new('V2_XAS_reference.json')
    embedded.write(args.xas_data.read_text())
    scene.frame_set(1)
    bpy.ops.object.select_all(action='DESELECT')
    controls.select_set(True)
    bpy.context.view_layer.objects.active = controls
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGB'
    scene.render.filepath = '//frames_v2/prism_'
    args.output.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.file.pack_all()
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(args.output.resolve()))
    (ROOT / 'v2_animation_timing.json').write_text(json.dumps(timing, indent=2) + '\n')
    print('SAVED', args.output, 'Crystal vertices', len(crystal.data.vertices), 'scale', list(crystal.scale))
    if args.preview_frames:
        preview = ROOT / 'previews_v2'
        preview.mkdir(exist_ok=True)
        scene.render.resolution_percentage = args.preview_percent
        for frame in map(int, args.preview_frames.split(',')):
            scene.frame_set(frame)
            scene.render.filepath = str(preview / f'frame_{frame:03d}.png')
            bpy.ops.render.render(write_still=True)


if __name__ == '__main__':
    main()
