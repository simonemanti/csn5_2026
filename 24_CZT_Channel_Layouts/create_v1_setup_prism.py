"""Build the real-scale four-CZT PRISM layout from 11_SETUP_XAS/v2.

Run: blender -b --python 24_CZT_Channel_Layouts/create_v1_setup_prism.py
Arguments follow Blender's -- separator. One Blender unit is one millimetre.
Only files in this script's output directory are written.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def arguments():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--source", type=Path, default=ROOT / "11_SETUP_XAS/v2_Setup_PRISM.blend", help="Original setup")
    parser.add_argument("--output", type=Path, default=HERE / "v1_Setup_PRISM.blend", help="Output Blender scene")
    parser.add_argument("--render", action="store_true", help="Render fluorescence, incident and overview PNGs")
    parser.add_argument("--samples", type=int, default=32, help="Cycles samples for previews")
    parser.add_argument("--width", type=int, default=1400, help="Preview width in pixels")
    return parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])


def material(name, rgb, metal=0.0, rough=0.35, emission=0.0):
    m = bpy.data.materials.new(name)
    m.diffuse_color = (*rgb, 1)
    m.use_nodes = True
    p = m.node_tree.nodes.get("Principled BSDF")
    p.inputs["Base Color"].default_value = (*rgb, 1)
    p.inputs["Metallic"].default_value = metal
    p.inputs["Roughness"].default_value = rough
    p.inputs["Emission Color"].default_value = (*rgb, 1)
    p.inputs["Emission Strength"].default_value = emission
    return m


def collection(name):
    c = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(c)
    return c


def move(obj, coll, parent=None):
    for c in list(obj.users_collection):
        c.objects.unlink(obj)
    coll.objects.link(obj)
    if parent:
        obj.parent = parent
    return obj


def empty(name, coll, parent=None, loc=(0, 0, 0)):
    obj = bpy.data.objects.new(name, None)
    coll.objects.link(obj)
    obj.parent = parent
    obj.location = loc
    obj.empty_display_type = "PLAIN_AXES"
    obj.empty_display_size = 4
    return obj


def cube(name, dims, loc, mat, coll, parent=None, bevel=0):
    bpy.ops.mesh.primitive_cube_add(size=1)
    obj = move(bpy.context.object, coll, parent)
    obj.name = name
    # Put physical dimensions into mesh coordinates. Object scales remain 1.
    for v in obj.data.vertices:
        v.co.x *= dims[0]
        v.co.y *= dims[1]
        v.co.z *= dims[2]
    obj.location = loc
    obj.data.materials.append(mat)
    obj["dimensions_mm"] = dims
    if bevel:
        modifier = obj.modifiers.new("Edge radii", "BEVEL")
        modifier.width = bevel
        modifier.segments = 3
        obj.modifiers.new("Weighted normals", "WEIGHTED_NORMAL")
    return obj


def line(name, coords, radius, mat, coll, parent=None):
    data = bpy.data.curves.new(name, "CURVE")
    data.dimensions = "3D"
    data.bevel_depth = radius
    data.bevel_resolution = 3
    spline = data.splines.new("POLY")
    spline.points.add(len(coords)-1)
    for point, co in zip(spline.points, coords):
        point.co = (*co, 1)
    obj = bpy.data.objects.new(name, data)
    coll.objects.link(obj)
    obj.parent = parent
    data.materials.append(mat)
    return obj


def cylinder(name, radius, depth, loc, mat, coll, parent=None):
    bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=radius, depth=depth)
    obj = move(bpy.context.object, coll, parent)
    obj.name = name
    obj.location = loc
    obj.data.materials.append(mat)
    return obj


def text_object(name, body, size, loc, mat, coll, parent=None, rotation=None):
    data = bpy.data.curves.new(name, "FONT")
    data.body = body
    data.size = size
    data.align_x = "CENTER"
    data.align_y = "CENTER"
    data.extrude = 0.002
    obj = bpy.data.objects.new(name, data)
    coll.objects.link(obj)
    obj.parent = parent
    obj.location = loc
    if rotation:
        obj.rotation_euler = rotation
    data.materials.append(mat)
    return obj


def prop(ctrl, name, val, lo=None, hi=None, description=""):
    ctrl[name] = val
    kw = {"description": description}
    if lo is not None:
        kw.update(min=lo, soft_min=lo, max=hi, soft_max=hi)
    ctrl.id_properties_ui(name).update(**kw)


def drive(obj, path, expression, variables, index=None):
    fcurve = obj.driver_add(path) if index is None else obj.driver_add(path, index)
    driver = fcurve.driver
    driver.type = "SCRIPTED"
    for name, (target, propname) in variables.items():
        v = driver.variables.new()
        v.name = name
        v.type = "SINGLE_PROP"
        v.targets[0].id = target
        v.targets[0].data_path = f'["{propname}"]'
    driver.expression = expression
    return driver


def hidden_if(obj, expression, variables):
    drive(obj, "hide_render", expression, variables)
    drive(obj, "hide_viewport", expression, variables)


def smooth(expression):
    return f"(({expression})**2*(3-2*({expression})))"


def camera(name, loc, target, scale, coll):
    data = bpy.data.cameras.new(name)
    data.type = "ORTHO"
    data.ortho_scale = scale
    data.clip_start = 0.01
    data.clip_end = 5000
    obj = bpy.data.objects.new(name, data)
    coll.objects.link(obj)
    obj.location = loc
    obj.rotation_euler = (Vector(target)-Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    return obj


def build(args):
    bpy.ops.wm.open_mainfile(filepath=str(args.source), load_ui=False, use_scripts=False)
    scene = bpy.context.scene
    scene.name = "PRISM_4CZT_v1"
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 0.001
    scene.unit_settings.length_unit = "MILLIMETERS"
    sample_world = bpy.data.objects["Ag_sample"].location.copy()
    crystal = bpy.data.objects["Ge_880_crystal"]
    beam_dir = (sample_world-crystal.location).normalized()
    heading = math.atan2(beam_dir.y, beam_dir.x)
    for obj in list(scene.objects):
        if obj.name not in {"X-ray tube", "Slit_1_XAS", "Slit_2_XAS", "Ge_880_crystal"}:
            bpy.data.objects.remove(obj, do_unlink=True)
    for old in list(bpy.data.texts):
        bpy.data.texts.remove(old)
    # Remove outdated scene claims inherited from the illustration.
    for key in list(scene.keys()):
        if key not in {"energy_keV", "crystal", "source_to_crystal_mm", "crystal_to_sample_mm",
                       "bragg_angle_deg", "central_deflection_angle_deg", "weighted_focus_distance_mm"}:
            del scene[key]
    for obj in (bpy.data.objects["X-ray tube"], bpy.data.objects["Slit_1_XAS"], bpy.data.objects["Slit_2_XAS"]):
        obj["dimensional_status"] = "Inherited approximate mechanical envelope, not manufacturer CAD. Optical locations preserved."

    rig = collection("01_Controls_and_kinematics")
    sensors = collection("02_CZT_sensors__physical_dimensions")
    mechanics = collection("03_Mechanics__design_assumptions")
    samples = collection("04_Sample__25x25x0.020_mm")
    rays = collection("05_Ray_guides__not_beam_envelopes")
    dimensions = collection("06_Dimensions")
    views = collection("07_Cameras_and_lights")

    mats = {
        "blue": material("CZT housing | sapphire", (0.025, 0.12, 0.25), 0.55),
        "gold": material("CZT entrance cathode | nominal 100 mm2", (0.7, 0.40, 0.09), 0.72, 0.27),
        "czt": material("CZT crystal", (0.13, 0.15, 0.17), 0.4),
        "silver": material("Anodized aluminium", (0.35, 0.43, 0.49), 0.7),
        "dark": material("Mechanics | graphite", (0.055, 0.075, 0.10), 0.5),
        "teal": material("Rotary stage | teal", (0.015, 0.32, 0.34), 0.5),
        "foil": material("Ag foil", (0.70, 0.74, 0.76), 0.7, 0.30),
        "green": material("Incident beam guide", (0.10, 0.52, 0.25), 0, 0.35, 0.5),
        "orange": material("Fluorescence guide", (0.98, 0.27, 0.035), 0, 0.35, 0.5),
        "ink": material("Dimension ink", (0.025, 0.09, 0.15), 0, 0.8),
        "white": material("Lettering", (0.85, 0.94, 0.98), 0, 0.6),
        "pcb": material("Readout board | envelope only", (0.02, 0.19, 0.15), 0.2),
    }

    station = empty("Station_origin__illuminated_spot", rig, loc=sample_world)
    station.rotation_euler.z = heading
    station["local_axes"] = "X = incident beam at sample; Y = fluorescence side; Z = vertical"
    ctrl = empty("PRISM_Controls", rig, station)
    prop(ctrl, "transition", 0.0, 0.0, 1.0, "0 = fluorescence, 1 = incident beam; lift precedes rotation")
    prop(ctrl, "cycle", 0.0, 0.0, 1.0, "Keyframed switching master")
    prop(ctrl, "animate", False, description="Use the timeline instead of the manual transition")
    prop(ctrl, "radius_mm", 35.0, 35.0, 80.0, "Distance from illuminated spot to the centre of each active face")
    prop(ctrl, "lift_mm", 45.0, 40.0, 65.0, "Vertical sample extraction stroke")
    prop(ctrl, "show_rays", True, description="Guide curves only; no photon transport simulation")
    prop(ctrl, "show_dimensions", True)
    prop(ctrl, "state", 0.0, 0.0, 1.0, "Evaluated transition; driven")
    drive(ctrl, '["state"]', "a*c+(1-a)*t", {"a":(ctrl,"animate"),"c":(ctrl,"cycle"),"t":(ctrl,"transition")})
    variables = {"t":(ctrl,"state")}
    radius_var = {"r":(ctrl,"radius_mm")}
    all_ray_vars = {**variables,"show":(ctrl,"show_rays")}

    bank = empty("CZT_orbital_rotation", rig, station)
    orbit = smooth("min(max((t-0.32)/0.68,0),1)")
    drive(bank, "rotation_euler", f"1.5707963267948966*(1-{orbit})", variables, 2)
    sample_lift = empty("Sample_vertical_translation", rig, station)
    lift = smooth("min(max(t/0.32,0),1)")
    drive(sample_lift, "location", f"h*{lift}", {**variables,"h":(ctrl,"lift_mm")}, 2)

    # Sample: real foil, supported from above. The support never crosses the beam.
    sample_frame = empty("Sample_45deg_orientation", rig, sample_lift)
    xaxis = Vector((1,1,0)).normalized()
    yaxis = Vector((0,0,1))
    zaxis = xaxis.cross(yaxis)
    sample_frame.rotation_euler = Matrix((xaxis,yaxis,zaxis)).transposed().to_euler()
    foil = cube("Ag_foil__25x25x0.020mm", (25,25,0.020), (0,0,0), mats["foil"], samples, sample_frame)
    foil["thickness_um"] = 20.0
    foil["provenance"] = "20 um Ag photon-budget baseline; 25 x 25 mm lateral size is a design assumption"
    for axis in (0,1):
        for sign in (-1,1):
            dims = (2,29,2) if axis == 0 else (25,2,2)
            loc = (sign*13.5,0,0) if axis == 0 else (0,sign*13.5,0)
            cube(f"Sample_frame_{axis}_{sign}", dims, loc, mats["silver"], samples, sample_frame, 0.35)
    cube("Sample_top_stem", (4,4,18), (0,0,23.5), mats["silver"], mechanics, sample_lift, 0.5)
    line("Sample_suspension_arm", [(-65,45,33),(0,0,33)], 2.2, mats["silver"], mechanics, sample_lift)
    carriage = cube("Sample_Z_carriage", (14,14,16), (-65,45,33), mats["teal"], mechanics, sample_lift, 1)
    cube("Sample_Z_tower", (10,10,150), (-65,45,24), mats["dark"], mechanics, station, 0.7)
    cylinder("Sample_Z_screw", 1.8, 150, (-59,45,24), mats["silver"], mechanics, station)

    # Four independent single-channel crystals; quasi-hemispherical is the
    # electrode/field geometry, not a spherical external detector enclosure.
    directions = [Vector((1,0,0))]
    for az in (90,210,330):
        polar = math.radians(30)
        az = math.radians(az)
        directions.append(Vector((math.cos(polar),math.sin(polar)*math.cos(az),math.sin(polar)*math.sin(az))))
    for channel, direction in enumerate(directions, 1):
        mod = empty(f"D{channel}_module", rig, bank)
        zaxis = -direction
        xaxis = Vector((0,0,1)).cross(zaxis).normalized()
        yaxis = zaxis.cross(xaxis)
        mod.rotation_euler = Matrix((xaxis,yaxis,zaxis)).transposed().to_euler()
        for axis in range(3):
            drive(mod, "location", f"r*{direction[axis]:.15f}", radius_var, axis)
        mod["detector_geometry"] = "Quasi-hemispherical electrode geometry, rectangular 10 x 10 x 5 mm crystal"
        mod["nominal_entrance_area_mm2"] = 100.0
        mod["package_status"] = "14 x 14 x 19 mm envelope assumed; NOT a supplier drawing"
        mod["axis_direction_bank"] = list(direction)
        crystal_obj = cube(f"D{channel}_CZT__10x10x5mm", (10,10,5), (0,0,-2.5), mats["czt"], sensors, mod)
        crystal_obj.data.materials.append(mats["gold"])
        for face in crystal_obj.data.polygons:
            if face.normal.z > 0.9:
                face.material_index = 1
        crystal_obj["nominal_area_mm2"] = 100.0
        crystal_obj["source"] = "Due2lab WP70, page 2: 10x10x5 mm3 hemispherical sensor example"
        # Open front: the housing does not obscure the nominal 10 x 10 face.
        for side in (-1,1):
            cube(f"D{channel}_side_x_{side}", (2,14,7), (side*6,0,-2.5), mats["blue"], mechanics, mod, .25)
            cube(f"D{channel}_side_y_{side}", (10,2,7), (0,side*6,-2.5), mats["blue"], mechanics, mod, .25)
        cube(f"D{channel}_rear_readout_envelope", (14,14,12), (0,0,-12), mats["blue"], mechanics, mod, .6)
        cube(f"D{channel}_PCB", (12,12,.7), (0,0,-5.5), mats["pcb"], mechanics, mod)
        text_object(f"D{channel}_label", f"D{channel}", 2.6, (0,5.9,1.05), mats["white"], dimensions, mod)
        # Ray guide and supporting riser share the same scalable radial rig.
        ray = line(f"If_D{channel}", [(0,0,0),direction], .11, mats["orange"], rays, bank)
        for axis in range(3):
            drive(ray, "scale", "r", radius_var, axis)
        # Curve scaling would also scale its stroke; compensate for that.
        drive(ray.data, "bevel_depth", "0.11/r", radius_var)
        hidden_if(ray, "(t>0.0001) or (not show)", all_ray_vars)
        # Mount post behind the crystal (local bank coordinates).
        mounting = empty(f"D{channel}_mount_position", rig, bank)
        for axis in (0,1):
            drive(mounting, "location", f"(r+14)*{direction[axis]:.15f}", radius_var, axis)
        top_z = 49*direction.z
        post = cylinder(f"D{channel}_mount_post", 1.6, top_z+31, (0,0,(top_z-31)/2), mats["silver"], mechanics, mounting)
        # Variable length/centre keeps upper end attached when radius changes.
        drive(post, "location", f"((r+14)*{direction.z:.15f}-31)/2", radius_var, 2)
        drive(post, "scale", f"((r+14)*{direction.z:.15f}+31)/{top_z+31:.15f}", radius_var, 2)
        foot = cube(f"D{channel}_mount_foot", (8,8,3), (0,0,-32.5), mats["dark"], mechanics, mounting, .5)

    # Low-profile rotary bearing and carrier stay below the optical plane.
    # Annulus built explicitly to preserve the central opening for the sample.
    vertices, faces = [], []
    for z in (-41,-35):
        for rad in (23,50):
            for i in range(96):
                a=2*math.pi*i/96
                vertices.append((rad*math.cos(a),rad*math.sin(a),z))
    for i in range(96):
        j=(i+1)%96
        faces.extend([(i,j,96+j,96+i),(192+i,288+i,288+j,192+j),
                      (i,192+i,192+j,j),(96+i,96+j,288+j,288+i)])
    mesh=bpy.data.meshes.new("Rotary_bearing_mesh")
    mesh.from_pydata(vertices,[],faces)
    bearing=bpy.data.objects.new("Rotary_bearing__100OD_46ID",mesh)
    mechanics.objects.link(bearing)
    bearing.parent=station
    mesh.materials.append(mats["teal"])
    carrier=cube("Rotating_carrier_plate", (53,60,3), (52.5,0,-34), mats["silver"], mechanics, bank, 1)
    drive(carrier,"location","r+17.5",radius_var,0)
    # The bearing link extends radially when the head distance is adjusted.
    link=cube("Carrier_radial_slide",(65,12,3),(32.5,0,-33),mats["dark"],mechanics,bank,.5)
    drive(link,"scale","(r+30)/65",radius_var,0)
    drive(link,"location","(r+30)/2",radius_var,0)
    cube("Station_base__200x180x8", (200,180,8), (15,0,-48), mats["silver"], mechanics, station, 2)
    for x in (-65,-40,85,110):
        for y in (-65,65):
            cylinder(f"Base_fastener_{x}_{y}", 2.8, .6, (x,y,-43.8), mats["dark"], mechanics, station)

    # Source and monochromator retain their original physical optical arms.
    for name, p0, p1 in [("Source_to_Ge_guide",Vector((0,0,0)),crystal.location.copy()),
                          ("Ge_to_sample_guide",crystal.location.copy(),sample_world)]:
        guide=line(name,[p0,p1],.20,mats["green"],rays)
        hidden_if(guide,"((t>0.0001) and (t<0.9999)) or (not show)",all_ray_vars)
    direct=line("I0_to_D1",[(0,0,0),(1,0,0)],.12,mats["green"],rays,station)
    drive(direct,"scale","r",radius_var,0)
    hidden_if(direct,"(t<0.9999) or (not show)",all_ray_vars)
    # Downstream transmission guide in fluorescence mode.
    transmitted=line("Transmitted_beam_guide",[(0,0,0),(85,0,0)],.08,mats["green"],rays,station)
    hidden_if(transmitted,"(t>0.0001) or (not show)",all_ray_vars)

    # True mm ruler, kept at the front edge of the base.
    line("Scale_bar_50mm",[(-10,-72,-43.7),(40,-72,-43.7)],.18,mats["ink"],dimensions,station)
    for x in range(-10,41,10):
        line(f"Ruler_tick_{x}",[(x,-74,-43.7),(x,-70,-43.7)],.16,mats["ink"],dimensions,station)
    text_object("Scale_label","50 mm",4,(15,-79,-43.6),mats["ink"],dimensions,station)
    text_object("Base_label","PRISM  /  4 CZT",5,(15,69,-43.6),mats["ink"],dimensions,station)
    for obj in dimensions.objects:
        hidden_if(obj,"not show",{"show":(ctrl,"show_dimensions")})

    # Reversible timeline; transforms use arithmetic-only drivers (no handlers).
    scene.frame_start=1
    scene.frame_end=252
    scene.render.fps=24
    for frame,value in [(1,0),(24,0),(108,1),(144,1),(228,0),(252,0)]:
        ctrl["cycle"]=float(value)
        ctrl.keyframe_insert(data_path='["cycle"]',frame=frame,group="PRISM switching")
    action=ctrl.animation_data.action
    for layer in action.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                for fc in bag.fcurves:
                    for kp in fc.keyframe_points:
                        kp.interpolation="LINEAR"
    for frame,label in [(1,"FLUORESCENCE | If"),(24,"Lift sample / shutter closed"),
                        (51,"Rotate CZT head"),(108,"INCIDENT BEAM | I0 on D1"),
                        (144,"Rotate head back"),(201,"Lower sample"),(228,"FLUORESCENCE | If")]:
        marker=scene.timeline_markers.new(label)
        marker.frame=frame

    bpy.context.view_layer.update()
    def world(co):
        return station.matrix_world @ Vector(co)
    detail=camera("Camera_DETAIL",world((-210,-290,190)),world((5,5,16)),285,views)
    camera("Camera_TOP",world((10,0,400)),world((10,0,0)),220,views)
    overview=camera("Camera_OVERVIEW",(390,-1500,1000),(410,-200,0),1150,views)
    scene.camera=detail
    scene.render.engine="CYCLES"
    scene.cycles.device="CPU"
    scene.cycles.samples=args.samples
    scene.cycles.use_denoising=True
    scene.render.resolution_x=args.width
    scene.render.resolution_y=round(args.width*0.75)
    scene.render.resolution_percentage=100
    scene.render.image_settings.file_format="PNG"
    scene.render.image_settings.color_mode="RGBA"
    scene.render.film_transparent=False
    # Frame the entire station using projected geometry, rather than guessing
    # the orthographic scale. The fixed tower also bounds the lifted sample.
    bpy.context.view_layer.update()
    inv=detail.matrix_world.inverted()
    points=[inv @ obj.matrix_world @ Vector(corner)
            for coll in (sensors,mechanics,samples,dimensions)
            for obj in coll.objects for corner in obj.bound_box]
    x0,x1=min(p.x for p in points),max(p.x for p in points)
    y0,y1=min(p.y for p in points),max(p.y for p in points)
    shift=detail.rotation_euler.to_quaternion() @ Vector(((x0+x1)/2,(y0+y1)/2,0))
    detail.location+=shift
    detail.data.ortho_scale=1.07*max(x1-x0,(y1-y0)*scene.render.resolution_x/scene.render.resolution_y)
    viewport_centre=world((5,5,16))+shift
    scene.view_settings.view_transform="AgX"
    scene.view_settings.look="AgX - Medium High Contrast"
    # Self-contained world and lights; no broken external HDRI references.
    w=bpy.data.worlds.new("PRISM studio")
    scene.world=w
    w.use_nodes=True
    w.node_tree.nodes["Background"].inputs["Color"].default_value=(.75,.80,.87,1)
    w.node_tree.nodes["Background"].inputs["Strength"].default_value=.65
    for name,offset,power,size in [("Key",(-180,-80,240),1800000,180),
                                   ("Fill",(100,-60,120),900000,150),
                                   ("Rim",(60,170,160),1500000,150)]:
        data=bpy.data.lights.new(name,"AREA")
        data.energy=power
        data.shape="DISK"
        data.size=size
        obj=bpy.data.objects.new(name,data)
        views.objects.link(obj)
        obj.location=world(offset)
        obj.rotation_euler=(sample_world-obj.location).to_track_quat("-Z","Y").to_euler()
    # A broad fill also lights source, slits and Ge in the full setup view.
    data=bpy.data.lights.new("Optics_fill","AREA")
    data.energy=15000000
    data.size=1000
    obj=bpy.data.objects.new("Optics_fill",data)
    views.objects.link(obj)
    obj.location=(400,-180,700)

    scene["source_blend"]=str(args.source.resolve())
    scene["geometry_source"]=str(ROOT/"03_Simulations/results/wp1/wp1_summary.json")
    scene["sensor_source"]="Due2lab WP70, p.2; 10x10x5 mm3 quasi-hemispherical example"
    scene["dimensional_status"]="1 BU = 1 mm. Optical arms and sensors physical; housings/mounts design assumptions. Tube/slit envelopes inherited approximations."
    scene["measurement"]="Sequential If / I0; D1 intercepts direct beam only after sample extraction."
    scene["performance_status"]="Geometrical concept only; no validated 22 keV response, count-rate limit, absolute flux or price."
    scene["design_rationale"]="1+3 spherical cap on reflection side; central D1 reaches direct beam by a single 90 degree horizontal orbital rotation."

    panel=bpy.data.texts.new("PRISM_Controls.py")
    panel.write((HERE/"prism_controls.py").read_text())
    panel.use_module=True
    exec(compile(panel.as_string(),panel.name,"exec"),{"__name__":"__main__"})
    readme=bpy.data.texts.new("START_HERE.txt")
    readme.write((HERE/"README_v1_Setup_PRISM.md").read_text())
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type=="VIEW_3D":
                space=area.spaces.active
                space.show_region_ui=True
                space.clip_start=.01
                space.clip_end=5000
                space.overlay.show_floor=False
                space.overlay.show_axis_x=False
                space.overlay.show_axis_y=False
                space.shading.type="SOLID"
                space.shading.color_type="MATERIAL"
                space.shading.show_cavity=True
                space.shading.cavity_type="BOTH"
                space.region_3d.view_rotation=detail.rotation_euler.to_quaternion()
                space.region_3d.view_location=viewport_centre
                space.region_3d.view_distance=260
                space.region_3d.view_perspective="ORTHO"
            elif area.type=="TEXT_EDITOR":
                area.spaces.active.text=panel
    bpy.ops.object.select_all(action="DESELECT")
    ctrl.select_set(True)
    bpy.context.view_layer.objects.active=ctrl
    scene.frame_set(1)
    ctrl["animate"]=False
    ctrl["transition"]=0.0
    ctrl.update_tag()
    bpy.context.view_layer.update()
    bpy.context.preferences.filepaths.save_version=0
    bpy.ops.wm.save_as_mainfile(filepath=str(args.output.resolve()))
    if args.render:
        for mode,cam in [("fluorescence",detail),("incident",detail),("overview",overview)]:
            ctrl["transition"]=1.0 if mode=="incident" else 0.0
            ctrl.update_tag()
            bpy.context.view_layer.update()
            scene.camera=cam
            scene.render.filepath=str(args.output.parent/f"v1_Setup_PRISM_{mode}.png")
            bpy.ops.render.render(write_still=True)
        ctrl["transition"]=0.0
        scene.camera=detail
        ctrl.update_tag()
        bpy.context.view_layer.update()
        bpy.ops.wm.save_as_mainfile(filepath=str(args.output.resolve()))
    print("PRISM_BUILD_COMPLETE",args.output)


if __name__=="__main__":
    build(arguments())
