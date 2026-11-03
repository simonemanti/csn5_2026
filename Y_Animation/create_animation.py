"""Build the label-free PRISM teaser from the existing setup, using Blender.

blender --background --python Y_Animation/create_animation.py
blender --background --python Y_Animation/create_animation.py -- --help

The XAS curve, enlarged crystal and 80-degree sweep are illustrative. This is
not a ray tracing result or a measured spectrum. Every animation is baked to
ordinary keyframes: no Python handlers, external libraries or auto-run needed.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parent
EDGE = 0.32
FPS = 24
END = 336


def arguments():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    p.add_argument('--source', type=Path, default=ROOT.parent / '11_SETUP_XAS/v2_Setup_PRISM.blend', help='Existing setup to animate.')
    p.add_argument('--output', type=Path, default=ROOT / 'v1_Animation.blend', help='Destination Blender file.')
    p.add_argument('--preview-frames', default='1,85,112,180', help='Comma-separated PNG preview frames; empty disables rendering.')
    p.add_argument('--preview-percent', type=int, default=75, help='Preview resolution percentage; saved file remains full HD.')
    return p.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])


def smooth(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


def progress(frame):
    if frame <= 24:
        return 0.0
    if frame <= 180:
        return smooth((frame - 24) / 156.0)
    if frame <= 216:
        return 1.0
    if frame <= 312:
        return 1.0 - smooth((frame - 216) / 96.0)
    return 0.0


def absorption(t):
    """Schematic absorption edge and damped post-edge fine structure."""
    rise = smooth((t - EDGE) / 0.065)
    d = max(0.0, t - 0.395)
    fine = 0.10 * math.exp(-3.3 * d) * math.sin(42.0 * d) * smooth(d / 0.03)
    white_line = 0.14 * math.exp(-((t - 0.405) / 0.032) ** 2)
    return 0.12 + 0.025 * t + rise * (0.57 + white_line + fine)


def emission_material(name, color, strength=1.0):
    m = bpy.data.materials.new(name)
    m.diffuse_color = (*color, 1)
    m.use_nodes = True
    n = m.node_tree.nodes
    n.clear()
    out = n.new('ShaderNodeOutputMaterial')
    emit = n.new('ShaderNodeEmission')
    emit.inputs['Color'].default_value = (*color, 1)
    emit.inputs['Strength'].default_value = strength
    m.node_tree.links.new(emit.outputs[0], out.inputs['Surface'])
    return m, emit


def solid_material(name, color, metallic=0.0, roughness=0.35):
    m = bpy.data.materials.new(name)
    m.diffuse_color = (*color, 1)
    m.use_nodes = True
    p = m.node_tree.nodes.get('Principled BSDF')
    p.inputs['Base Color'].default_value = (*color, 1)
    p.inputs['Metallic'].default_value = metallic
    p.inputs['Roughness'].default_value = roughness
    return m, p


def curve(name, pts, radius, mat, collection, cyclic=False):
    data = bpy.data.curves.new(name, 'CURVE')
    data.dimensions = '3D'
    data.resolution_u = 1
    data.bevel_depth = radius
    data.bevel_resolution = 3
    sp = data.splines.new('POLY')
    sp.points.add(len(pts) - 1)
    for dest, pt in zip(sp.points, pts):
        dest.co = (*pt, 1.0)
    sp.use_cyclic_u = cyclic
    obj = bpy.data.objects.new(name, data)
    collection.objects.link(obj)
    data.materials.append(mat)
    return obj


def sphere(name, radius, mat, collection):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=12, radius=radius)
    obj = bpy.context.object
    obj.name = name
    for c in list(obj.users_collection):
        c.objects.unlink(obj)
    collection.objects.link(obj)
    obj.data.materials.append(mat)
    for p in obj.data.polygons:
        p.use_smooth = True
    return obj


def linear_keys(block):
    if not block.animation_data or not block.animation_data.action:
        return
    action = block.animation_data.action
    for layer in action.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                for fcurve in bag.fcurves:
                    for k in fcurve.keyframe_points:
                        k.interpolation = 'CONSTANT' if fcurve.data_path in ('hide_render', 'hide_viewport') else 'LINEAR'


def main():
    args = arguments()
    bpy.ops.wm.open_mainfile(filepath=str(args.source.resolve()))
    scene = bpy.context.scene
    scene.frame_start, scene.frame_end = 1, END
    scene.render.fps = FPS
    scene.render.resolution_x, scene.render.resolution_y = 1920, 1080
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = False
    scene.render.engine = 'BLENDER_EEVEE'
    scene.eevee.taa_render_samples = 32
    scene.view_settings.view_transform = 'Standard'
    scene.view_settings.look = 'None'
    scene.view_settings.exposure = 0
    scene.world.node_tree.nodes['Neutral camera background'].inputs['Color'].default_value = (0.006, 0.011, 0.022, 1)
    scene.world.node_tree.nodes['Neutral camera background'].inputs['Strength'].default_value = 1
    scene.world.node_tree.nodes['Studio background'].inputs['Strength'].default_value = 1.0
    for obj in list(scene.objects):
        obj.animation_data_clear()
        if obj.type == 'FONT' or obj.name == 'Weighted_sagittal_focus':
            bpy.data.objects.remove(obj, do_unlink=True)
    for m in bpy.data.materials:
        if m.node_tree:
            m.node_tree.animation_data_clear()

    collection = bpy.data.collections.new('Animation | XAS and light')
    scene.collection.children.link(collection)
    hardware = bpy.data.collections.new('Animation | crystal rotation')
    scene.collection.children.link(hardware)
    controller = bpy.data.objects.new('Scan_progress', None)
    collection.objects.link(controller)
    controller['progress'] = 0.0
    controller['edge_progress'] = EDGE
    controller['description'] = 'Shared baked scan coordinate: illustrative energy, crystal angle and emission.'

    camera = scene.camera
    bpy.context.view_layer.update()
    basis = camera.matrix_world.to_3x3()
    right, up, forward = (basis @ Vector(v) for v in ((1, 0, 0), (0, 1, 0), (0, 0, -1)))
    width = camera.data.ortho_scale
    height = width * scene.render.resolution_y / scene.render.resolution_x

    def screen(u, v, depth=1000):
        return camera.location + forward * depth + right * ((u - 0.5) * width) + up * ((v - 0.5) * height)

    # Quiet, unlabelled XAS trace floating immediately above the detector.
    graph_origin = (0.705, 0.56)
    graph_size = (0.255, 0.24)

    def graph(t):
        return screen(graph_origin[0] + graph_size[0] * t,
                      graph_origin[1] + graph_size[1] * absorption(t))

    trace_mat, _ = emission_material('XAS | ivory cyan', (0.58, 0.83, 0.91), 1.0)
    axes_mat, _ = emission_material('XAS | quiet axes', (0.10, 0.18, 0.25), 0.85)
    red_mat, _ = emission_material('XAS | red energy marker', (1.0, 0.012, 0.025), 1.2)
    curve('XAS_static_curve', [graph(i / 700) for i in range(701)], 1.05, trace_mat, collection)
    curve('XAS_static_axes', [screen(0.695, 0.79), screen(0.695, 0.56), screen(0.968, 0.56)], 0.48, axes_mat, collection)
    dot = sphere('XAS_red_energy_marker', 4.3, red_mat, collection)
    # Marker centre projects exactly onto the curve; closer to the camera to avoid occlusion.
    marker_offset = -forward * 4.0

    # A large sweep, enlarged crystal and rotating lower arm expose the Z rotation.
    crystal = bpy.data.objects['Ge_880_crystal']
    angle0 = crystal.rotation_euler.z
    crystal.scale = (2.35, 2.35, 2.35)
    crystal['animation_display_scale'] = 2.35
    crystal['animation_sweep_degrees'] = 80.0
    crystal['dimensional_status'] = 'Enlarged 2.35x for this illustrative teaser; original mesh retained.'
    surface, _ = solid_material('Animation | polished germanium', (0.22, 0.36, 0.43), 0.58, 0.24)
    edge_mat, _ = emission_material('Animation | crystal edge', (0.18, 0.61, 0.73), 0.7)
    crystal.data.materials[0] = surface
    crystal.data.materials[1] = edge_mat
    pts = []
    for x, zs in ((-10, range(-20, 21)), (10, range(20, -21, -1))):
        for z in zs:
            pts.append((x, 250 - math.sqrt(250 ** 2 - z ** 2) - 0.12, z))
    rim = curve('Crystal_rotating_rim', pts, 0.16, edge_mat, hardware, True)
    rim.parent = crystal
    base_mat, _ = solid_material('Animation | rotation stage', (0.07, 0.11, 0.15), 0.60, 0.35)
    ring_mat, _ = emission_material('Animation | rotation guide', (0.10, 0.23, 0.30), 0.7)
    center = crystal.location.copy()
    curve('Z_rotation_base_ring', [center + Vector((35 * math.cos(i * math.tau / 128), 35 * math.sin(i * math.tau / 128), -56)) for i in range(128)], 1.1, ring_mat, hardware, True)
    arm = curve('Z_rotation_pointer', [(0, 0, -24), (17, 0, -24)], 0.42, edge_mat, hardware)
    arm.parent = crystal
    curve('Z_rotation_spindle', [center + Vector((0, 0, -56)), center + Vector((0, 0, -47))], 2.5, base_mat, hardware)

    # Soften the very dark slits without changing their geometry.
    if 'Black' in bpy.data.materials:
        mat = bpy.data.materials['Black']
        p = next((n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
        if p:
            p.inputs['Base Color'].default_value = (0.065, 0.085, 0.105, 1)
            mat.diffuse_color = (0.065, 0.085, 0.105, 1)

    gold_mat, _ = emission_material('Animation | incident gold', (1.0, 0.49, 0.065), 1.35)
    for name in ('Incident_beam', 'Diffracted_beam', 'Incident_beam_direction', 'Diffracted_beam_direction'):
        obj = bpy.data.objects[name]
        obj.data.materials.clear()
        obj.data.materials.append(gold_mat)
        if name.endswith('direction'):
            obj.scale = (1.15,) * 3
    sample = bpy.data.objects['Ag_sample']
    sample_mat, sample_shader = solid_material('Animation | Ag emission', (0.14, 0.20, 0.23), 0.3, 0.3)
    sample_shader.inputs['Emission Color'].default_value = (0.025, 0.62, 1.0, 1)
    sample.data.materials.clear()
    sample.data.materials.append(sample_mat)
    cyan_mat, cyan_node = emission_material('Animation | fluorescence', (0.015, 0.63, 1.0), 1.5)
    fluorescent_objects = []
    for name in ('Fluorescence_to_CZT', 'Fluorescence_direction'):
        obj = bpy.data.objects[name]
        obj.data.materials.clear()
        obj.data.materials.append(cyan_mat)
        fluorescent_objects.append(obj)
        if name.endswith('direction'):
            obj.scale = (1.2,) * 3
    path = bpy.data.objects['Fluorescence_to_CZT'].data.splines[0]
    start, stop = (Vector(path.points[i].co[:3]) for i in (0, -1))
    photons = [sphere(f'Fluorescence_photon_{i+1:02d}', 2.5, cyan_mat, collection) for i in range(5)]
    fluorescent_objects.extend(photons)
    spot = sphere('Ag_excited_spot', 4.2, cyan_mat, collection)
    spot.location = sample.location - forward * 2
    fluorescent_objects.append(spot)

    # Bake every frame; this also makes timing portable and editable in the file.
    log = []
    for frame in range(1, END + 1):
        t = progress(frame)
        activation = smooth((t - EDGE) / 0.055)
        intensity = activation * (0.8 + 0.28 * absorption(t))
        controller['progress'] = t
        controller.keyframe_insert(data_path='["progress"]', frame=frame)
        crystal.rotation_euler.z = angle0 + math.radians(-40 + 80 * t)
        crystal.keyframe_insert(data_path='rotation_euler', index=2, frame=frame)
        dot.location = graph(t) + marker_offset
        dot.keyframe_insert(data_path='location', frame=frame)
        sample_shader.inputs['Emission Strength'].default_value = 2.8 * intensity
        sample_shader.inputs['Emission Strength'].keyframe_insert(data_path='default_value', frame=frame)
        cyan_node.inputs['Strength'].default_value = 0.35 + 2.4 * intensity
        cyan_node.inputs['Strength'].keyframe_insert(data_path='default_value', frame=frame)
        for obj in fluorescent_objects:
            obj.hide_render = obj.hide_viewport = t <= EDGE
            obj.keyframe_insert(data_path='hide_render', frame=frame)
            obj.keyframe_insert(data_path='hide_viewport', frame=frame)
        for i, photon in enumerate(photons):
            phase = ((frame - 1) / 27.0 + i / len(photons)) % 1.0
            photon.location = start.lerp(stop, phase)
            photon.scale = (max(0.01, activation * math.sin(math.pi * phase) ** 0.5),) * 3
            photon.keyframe_insert(data_path='location', frame=frame)
            photon.keyframe_insert(data_path='scale', frame=frame)
        log.append(dict(frame=frame, progress=t, angle_deg=math.degrees(crystal.rotation_euler.z), absorption=absorption(t), fluorescence=intensity))
    for block in list(bpy.data.objects) + [sample_mat.node_tree, cyan_mat.node_tree]:
        linear_keys(block)

    # A gentle bloom makes the edge-triggered emission legible on projection.
    tree = bpy.data.node_groups.new('PRISM | subtle optical glow', 'CompositorNodeTree')
    tree.interface.new_socket(name='Image', in_out='OUTPUT', socket_type='NodeSocketColor')
    layers = tree.nodes.new('CompositorNodeRLayers')
    glow = tree.nodes.new('CompositorNodeGlare')
    glow.inputs['Type'].default_value = 'Fog Glow'
    glow.inputs['Quality'].default_value = 'High'
    glow.inputs['Threshold'].default_value = 1.1
    glow.inputs['Strength'].default_value = 0.32
    glow.inputs['Size'].default_value = 0.2
    output = tree.nodes.new('NodeGroupOutput')
    tree.links.new(layers.outputs['Image'], glow.inputs['Image'])
    tree.links.new(glow.outputs['Image'], output.inputs['Image'])
    scene.compositing_node_group = tree

    scene.timeline_markers.clear()
    for name, frame in [('START', 1), ('SCAN UP', 25), ('EDGE UP', next(x['frame'] for x in log if x['progress'] > EDGE)), ('HIGH ENERGY', 180), ('SCAN DOWN', 217), ('EDGE DOWN', next(x['frame'] for x in log if x['frame'] > 216 and x['progress'] <= EDGE)), ('LOOP', 336)]:
        scene.timeline_markers.new(name, frame=frame)
    scene['animation_notes'] = '14 s, 24 fps, continuous loop. Schematic XAS, 80 degree Z sweep and enlarged crystal; fixed illustrative beam paths. Not a simulated or measured scan.'
    scene['background'] = 'solid midnight blue'
    scene['annotations'] = 'No labels or text in the visible scene.'
    scene['animation_source'] = '//../11_SETUP_XAS/v2_Setup_PRISM.blend'
    readme = bpy.data.texts.new('READ ME - PRISM animation')
    readme.write('PRISM — animation v1\n\nSpace: play. Numpad 0: camera.\nFrames 1–336 / 24 fps / 14 seconds.\n\nThe curve stays fixed; the red point scans in both directions.\nThe sample and fluorescence illuminate only above the illustrated edge.\nThe crystal rotates 80 degrees around world Z and is enlarged 2.35x.\n\nAll animation is baked into editable keyframes. No Python execution required.\nThe spectrum and motion are illustrative, not measured or ray-traced data.\nThe original optical layout is preserved; the exaggerated rotation does not\nrecompute the diffracted beam. No visible labels. All textures packed.\n')
    scene.frame_set(1)
    bpy.ops.object.select_all(action='DESELECT')
    crystal.select_set(True)
    bpy.context.view_layer.objects.active = crystal
    for screen_data in bpy.data.screens:
        for area in screen_data.areas:
            if area.type == 'VIEW_3D':
                space = area.spaces.active
                space.region_3d.view_perspective = 'CAMERA'
                space.overlay.show_overlays = False
                space.shading.type = 'MATERIAL'
                space.shading.use_scene_world = True
                space.shading.use_scene_lights = True
                space.region_3d.view_camera_zoom = 10
    args.output.parent.mkdir(parents=True, exist_ok=True)
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGB'
    scene.render.filepath = '//frames/prism_'
    bpy.ops.file.pack_all()
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(args.output.resolve()))
    (ROOT / 'animation_timing.json').write_text(json.dumps(log, indent=2) + '\n')
    print('ANIMATION_SAVED', str(args.output), 'libraries', len(bpy.data.libraries), 'text_objects', sum(o.type == 'FONT' for o in scene.objects))
    if args.preview_frames:
        (ROOT / 'previews').mkdir(exist_ok=True)
        scene.render.resolution_percentage = args.preview_percent
        for frame in map(int, args.preview_frames.split(',')):
            scene.frame_set(frame)
            scene.render.filepath = str(ROOT / 'previews' / f'frame_{frame:03d}.png')
            bpy.ops.render.render(write_still=True)


if __name__ == '__main__':
    main()
