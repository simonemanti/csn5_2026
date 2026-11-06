"""Simplify v1 to a bare sample and one shared four-channel CZT case.

Run with Blender: --background --python create_v2_setup_prism.py -- --render
All coordinates remain in millimetres. v1 and the original optics are preserved.
"""
import argparse
import importlib.util
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

HERE=Path(__file__).resolve().parent


def arguments():
    p=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    p.add_argument("--source",type=Path,default=HERE/"v1_Setup_PRISM.blend",help="Source v1 scene")
    p.add_argument("--output",type=Path,default=HERE/"v2_Setup_PRISM.blend",help="Simplified output")
    p.add_argument("--render",action="store_true",help="Render the two modes and full setup")
    p.add_argument("--width",type=int,default=1400,help="Preview width in pixels")
    p.add_argument("--samples",type=int,default=24,help="Cycles samples")
    return p.parse_args(sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else [])


def helpers():
    spec=importlib.util.spec_from_file_location("prism_mesh_helpers",HERE/"create_v1_setup_prism.py")
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def shared_case(h,coll,parent,material):
    """One 30 x 30 x 30 mm cube with a flat 2 x 2 sensor face."""
    case=h.cube("CZT_SHARED_CASE",(30,30,30),(50,0,0),material,coll,parent)
    case["role"]="One cubic enclosure; four coplanar CZT channels in a 2 x 2 grid"
    case["dimensional_status"]="Concept enclosure, not manufacturer CAD"
    case["outer_dimensions_mm"]=(30,30,30)
    for i in range(1,5):
        module=bpy.data.objects[f"D{i}_module"]
        cutter=h.cube(f"TEMP_window_{i}",(10.5,10.5,15),(0,0,1),material,coll,module)
        bpy.context.view_layer.update()
        modifier=case.modifiers.new(f"Channel {i} aperture","BOOLEAN")
        modifier.operation="DIFFERENCE"
        modifier.solver="EXACT"
        modifier.object=cutter
        bpy.context.view_layer.objects.active=case
        case.select_set(True)
        bpy.ops.object.modifier_apply(modifier=modifier.name)
        bpy.data.objects.remove(cutter,do_unlink=True)
    bevel=case.modifiers.new("Small edge rounds","BEVEL")
    bevel.width=.25
    bevel.segments=3
    bevel.limit_method="ANGLE"
    case.modifiers.new("Weighted normals","WEIGHTED_NORMAL")
    return case


def arrow(h,name,location,direction,material,coll,parent,condition,variables):
    bpy.ops.mesh.primitive_cone_add(vertices=32,radius1=1.25,radius2=0,depth=4.5)
    obj=h.move(bpy.context.object,coll,parent)
    obj.name=name
    obj.location=location
    obj.rotation_euler=Vector(direction).to_track_quat("Z","Y").to_euler()
    obj.data.materials.append(material)
    h.hidden_if(obj,condition,variables)
    obj["role"]="Schematic direction arrow, not a physical beam envelope"
    return obj


def build(args):
    h=helpers()
    bpy.ops.wm.open_mainfile(filepath=str(args.source.resolve()),load_ui=False,use_scripts=False)
    scene=bpy.context.scene
    scene.name="PRISM_4CZT_v2_SIMPLE"
    ctrl=bpy.data.objects["PRISM_Controls"]
    ctrl["animate"]=False
    ctrl["transition"]=0.0
    ctrl["radius_mm"]=35.0
    ctrl.id_properties_ui("radius_mm").update(min=35,max=35,soft_min=35,soft_max=35,description="Fixed perpendicular distance to the 2 x 2 entrance plane: 35 mm")
    ctrl["show_dimensions"]=False
    ctrl.update_tag()
    scene.frame_set(1)
    bpy.context.view_layer.update()
    station=bpy.data.objects["Station_origin__illuminated_spot"]
    bank=bpy.data.objects["CZT_orbital_rotation"]
    for name in ("03_Mechanics__design_assumptions","06_Dimensions"):
        coll=bpy.data.collections.get(name)
        if coll:
            for obj in list(coll.objects):
                bpy.data.objects.remove(obj,do_unlink=True)
            bpy.data.collections.remove(coll)
    # Only the actual foil remains in the sample collection.
    for obj in list(bpy.data.collections["04_Sample__25x25x0.020_mm"].objects):
        if obj.name!="Ag_foil__25x25x0.020mm":
            bpy.data.objects.remove(obj,do_unlink=True)
    for obj in list(scene.objects):
        if obj.name.endswith("_mount_position"):
            bpy.data.objects.remove(obj,do_unlink=True)
    # All four windows lie in one plane. A small rigid offset during the
    # orbital motion makes D1, rather than the cross-shaped gap, meet I0.
    head=h.empty("CZT_grid_alignment",bpy.data.collections["01_Controls_and_kinematics"],bank)
    phase=h.smooth("min(max((t-0.32)/0.68,0),1)")
    h.drive(head,"location",f"6*{phase}",{"t":(ctrl,"state")},1)
    h.drive(head,"location",f"-6*{phase}",{"t":(ctrl,"state")},2)
    positions=[(35,-6,6),(35,6,6),(35,-6,-6),(35,6,-6)]
    # Module local +Z faces the sample; all four entrance faces are parallel.
    orientation=Matrix(((0,-1,0),(0,0,1),(-1,0,0))).transposed().to_euler()
    for i,position in enumerate(positions,1):
        module=bpy.data.objects[f"D{i}_module"]
        module.animation_data_clear()
        module.parent=head
        module.location=position
        module.rotation_euler=orientation
        module["package_status"]="Bare crystal inside one cubic CZT_SHARED_CASE"
        module["layout"]="2 x 2 coplanar, 12 mm pitch, 2 mm inter-crystal gap"
        module["axis_direction_bank"]=(1,0,0)
    coll=h.collection("03_One_shared_CZT_case")
    case_material=h.material("CZT common case | light blue",(.22,.43,.58),.3,.32)
    shared_case(h,coll,head,case_material)
    # Use high contrast guides and simple directional arrows only.
    ray_coll=bpy.data.collections["05_Ray_guides__not_beam_envelopes"]
    variables={"t":(ctrl,"state"),"show":(ctrl,"show_rays")}
    green=bpy.data.materials["Incident beam guide"]
    orange=bpy.data.materials["Fluorescence guide"]
    for name in ("Source_to_Ge_guide","Ge_to_sample_guide"):
        bpy.data.objects[name].data.bevel_depth=.33
    for i in range(1,5):
        ray=bpy.data.objects[f"If_D{i}"]
        ray.animation_data_clear()
        ray.data.animation_data_clear()
        ray.parent=head
        ray.scale=(1,1,1)
        ray.data.splines[0].points[0].co=(0,0,0,1)
        ray.data.splines[0].points[1].co=(*positions[i-1],1)
        ray.data.bevel_depth=.18
        h.hidden_if(ray,"(t>0.0001) or (not show)",variables)
    bpy.data.objects["I0_to_D1"].data.bevel_depth=.30
    bpy.data.objects["Transmitted_beam_guide"].data.bevel_depth=.14
    arrow(h,"Beam_direction",(-38,0,0),(1,0,0),green,ray_coll,station,
          "((t>0.0001) and (t<0.9999)) or (not show)",variables)
    arrow(h,"If_direction",(17.5,-3,3),(35,-6,6),orange,ray_coll,head,"(t>0.0001) or (not show)",variables)
    arrow(h,"I0_direction",(18,0,0),(1,0,0),green,ray_coll,station,"(t<0.9999) or (not show)",variables)

    # The detail view now contains only the free sample and detector head.
    def world(co):
        return station.matrix_world @ Vector(co)
    detail=bpy.data.objects["Camera_DETAIL"]
    detail.location=world((-160,-260,185))
    target=world((10,15,15))
    detail.rotation_euler=(target-detail.location).to_track_quat("-Z","Y").to_euler()
    detail.data.ortho_scale=135
    top=bpy.data.objects["Camera_TOP"]
    top.location=world((10,15,300))
    top.rotation_euler=(world((10,15,0))-top.location).to_track_quat("-Z","Y").to_euler()
    top.data.ortho_scale=150
    scene.camera=detail
    scene.render.resolution_x=args.width
    scene.render.resolution_y=round(args.width*.75)
    scene.cycles.samples=args.samples
    scene["version"]="v2: minimal explanatory model"
    scene["source_blend"]=str(args.source.resolve())
    scene["dimensional_status"]="Millimetres. Bare foil and 4 crystals unchanged; single conceptual enclosure. No supports, bases, towers or independent detector packages."
    scene["design_rationale"]="One 30 mm cubic case; four parallel 10x10 mm entrance faces in a 2x2 grid, 12 mm pitch. Orbital rotation plus 6 mm horizontal/vertical head offset align D1 with I0."
    scene["performance_status"]="Explanatory geometry only; not a validated detector or mechanical design."
    panel_src=(HERE/"prism_controls.py").read_text()
    start=panel_src.index("class PRISM_PT_setup")
    end=panel_src.index("CLASSES =",start)
    # Keep self-contained, proven operators; replace the crowded v1 panel.
    panel_src=panel_src[:start]+'''class PRISM_PT_setup(bpy.types.Panel):
    bl_label = "PRISM v2 | simple setup"
    bl_idname = "PRISM_PT_setup"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "PRISM"

    @classmethod
    def poll(cls, context):
        return controls() is not None

    def draw(self, context):
        layout = self.layout
        ctrl = controls()
        row = layout.row(align=True)
        row.operator("prism.set_mode", text="Fluorescence").mode = "FLUORESCENCE"
        row.operator("prism.set_mode", text="Incident I0").mode = "INCIDENT"
        row = layout.row()
        row.enabled = not ctrl["animate"]
        row.prop(ctrl, '["transition"]', text="Switch", slider=True)
        layout.prop(ctrl, '["lift_mm"]', text="Sample lift [mm]")
        layout.separator()
        row = layout.row(align=True)
        row.operator("prism.play_switch", text="Play", icon="PLAY")
        row.operator("prism.pause_switch", text="Freeze", icon="PAUSE")
        layout.prop(ctrl, '["animate"]', text="Drive from timeline")
        row = layout.row(align=True)
        row.operator("prism.view", text="Detail").view = "DETAIL"
        row.operator("prism.view", text="Full").view = "OVERVIEW"
        row.operator("prism.view", text="Top").view = "TOP"
        layout.prop(ctrl, '["show_rays"]', text="Ray guides")
        layout.separator()
        layout.label(text="Cubic case / 2 x 2 CZT channels")
        layout.label(text="Case: 30 x 30 x 30 mm")
        layout.label(text="I0: sample out, D1 on beam axis")
        layout.label(text="Concept drawing / units: mm")


'''+panel_src[end:]
    panel_src=panel_src.replace("v1_Setup_PRISM.blend","v2_Setup_PRISM.blend").replace('"version": (1, 0, 0)','"version": (2, 0, 0)')
    panel=bpy.data.texts["PRISM_Controls.py"]
    panel.clear()
    panel.write(panel_src)
    panel.use_module=True
    exec(compile(panel_src,panel.name,"exec"),{"__name__":"__main__"})
    (HERE/"prism_controls_v2.py").write_text(panel_src)
    readme=bpy.data.texts["START_HERE.txt"]
    readme.clear()
    readme.write((HERE/"README_v2_Setup_PRISM.md").read_text())
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type=="VIEW_3D":
                space=area.spaces.active
                space.show_region_ui=True
                space.overlay.show_extras=False
                space.region_3d.view_rotation=detail.rotation_euler.to_quaternion()
                space.region_3d.view_location=target
                space.region_3d.view_distance=170
                space.region_3d.view_perspective="ORTHO"
            elif area.type=="TEXT_EDITOR":
                area.spaces.active.text=panel
    bpy.ops.object.select_all(action="DESELECT")
    bpy.context.view_layer.objects.active=ctrl
    bpy.context.preferences.filepaths.save_version=0
    bpy.context.view_layer.update()
    bpy.ops.wm.save_as_mainfile(filepath=str(args.output.resolve()))
    if args.render:
        for label,cam in (("fluorescence",detail),("incident",detail),("overview",bpy.data.objects["Camera_OVERVIEW"])):
            ctrl["transition"]=1.0 if label=="incident" else 0.0
            ctrl.update_tag()
            bpy.context.view_layer.update()
            scene.camera=cam
            scene.render.filepath=str(args.output.parent/f"v2_Setup_PRISM_{label}.png")
            bpy.ops.render.render(write_still=True)
        ctrl["transition"]=0.0
        ctrl.update_tag()
        scene.camera=detail
        bpy.context.view_layer.update()
        bpy.ops.wm.save_as_mainfile(filepath=str(args.output.resolve()))
    print("PRISM_V2_COMPLETE",args.output)


if __name__=="__main__":
    build(arguments())
