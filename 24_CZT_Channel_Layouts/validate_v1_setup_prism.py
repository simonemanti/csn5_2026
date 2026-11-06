"""Validate PRISM dimensions and motion in a fresh Blender process.

Writes v1_Setup_PRISM_validation.json beside the inspected blend, without
saving or otherwise changing that blend. Tests modeled geometry only.
"""
import json
import math
from itertools import combinations
from pathlib import Path

import bpy
from mathutils import Vector

scene=bpy.context.scene
ctrl=bpy.data.objects["PRISM_Controls"]
station=bpy.data.objects["Station_origin__illuminated_spot"]
spot=station.matrix_world.translation.copy()
beam=station.matrix_world.to_3x3() @ Vector((1,0,0))
normal=station.matrix_world.to_3x3() @ Vector((-1,1,0)).normalized()
report={"blender_version":bpy.app.version_string,"blend":bpy.data.filepath,"checks":[],"limitations":
        "Selected modeled envelopes only; no supplier CAD, cable/hose routing, tolerances, beam footprint or spectral response validated."}


def check(condition, description):
    if not condition:
        raise AssertionError(description)
    report["checks"].append(description)


def update(t=0,r=35,h=45):
    ctrl["animate"]=False
    ctrl["transition"]=float(t)
    ctrl["radius_mm"]=float(r)
    ctrl["lift_mm"]=float(h)
    ctrl.update_tag()
    bpy.context.view_layer.update()


def box(obj, center=None, half=None):
    mat=obj.matrix_world
    if center is None:
        low=Vector(tuple(min(v[i] for v in obj.bound_box) for i in range(3)))
        high=Vector(tuple(max(v[i] for v in obj.bound_box) for i in range(3)))
        center=(low+high)/2
        half=(high-low)/2
    columns=[mat.to_3x3().col[i] for i in range(3)]
    return mat @ Vector(center), [v.normalized() for v in columns], [half[i]*columns[i].length for i in range(3)]


def overlap(b1,b2):
    c1,axes1,h1=b1
    c2,axes2,h2=b2
    axes=axes1+axes2+[a.cross(b) for a in axes1 for b in axes2]
    for axis in axes:
        if axis.length<1e-7:
            continue
        axis.normalize()
        r1=sum(h*abs(a.dot(axis)) for h,a in zip(h1,axes1))
        r2=sum(h*abs(a.dot(axis)) for h,a in zip(h2,axes2))
        if abs((c2-c1).dot(axis)) >= r1+r2-0.02:
            return False
    return True


def segment_box(start,end,b):
    center,axes,half=b
    low,high=0.0001,0.9999
    for axis,h in zip(axes,half):
        origin=(start-center).dot(axis)
        direction=(end-start).dot(axis)
        if abs(direction)<1e-10:
            if abs(origin)>h:
                return False
        else:
            t1,t2=sorted(((-h-origin)/direction,(h-origin)/direction))
            low=max(low,t1)
            high=min(high,t2)
            if low>high:
                return False
    return True


update()
check(scene.unit_settings.system=="METRIC" and abs(scene.unit_settings.scale_length-.001)<1e-9,"Metric scale: 1 BU = 1 mm")
crystals=[bpy.data.objects[f"D{i}_CZT__10x10x5mm"] for i in range(1,5)]
mods=[bpy.data.objects[f"D{i}_module"] for i in range(1,5)]
for crystal in crystals:
    extents=[max(v.co[i] for v in crystal.data.vertices)-min(v.co[i] for v in crystal.data.vertices) for i in range(3)]
    check(all(abs(a-b)<1e-5 for a,b in zip(extents,(10,10,5))),crystal.name+": physical 10 x 10 x 5 mm")
check(abs(sum(o["nominal_area_mm2"] for o in crystals)-400)<1e-7,"Total nominal sensor entrance area: 400 mm2")
foil=bpy.data.objects["Ag_foil__25x25x0.020mm"]
check(abs(max(v.co.z for v in foil.data.vertices)-min(v.co.z for v in foil.data.vertices)-.020)<1e-7,"Ag foil true thickness: 20 um")
takeoff=[]
for mod in mods:
    centre=mod.matrix_world.translation
    direction=(centre-spot).normalized()
    front=mod.matrix_world.to_3x3() @ Vector((0,0,1))
    check(abs((centre-spot).length-35)<1e-3,mod.name+": face centre at 35 mm")
    check(front.dot(-direction)>.999999,mod.name+": entrance face points to illuminated spot")
    check(direction.dot(normal)>0,mod.name+": reflection side of sample")
    takeoff.append(math.degrees(math.acos(max(-1,min(1,direction.dot(normal))))))
report["fluorescence_takeoff_to_normal_deg"]=takeoff
report["solid_angle_sr"]=16*math.atan(25/(35*math.sqrt(35**2+50)))
report["acceptance_fraction_4pi"]=report["solid_angle_sr"]/(4*math.pi)

sample_parts=[o for o in scene.objects if o.name.startswith("Sample_frame_") or o.name in {foil.name,"Sample_top_stem","Sample_Z_carriage","Sample_Z_tower"}]
plate=bpy.data.objects["Rotating_carrier_plate"]
positions=0
for r in (35,50,65,80):
    for h in (40,45,65):
        for step in range(101):
            t=step/100
            update(t,r,h)
            boxes=[box(m,(0,0,-8.5),(7,7,9.5)) for m in mods]
            for (i,b1),(j,b2) in combinations(enumerate(boxes),2):
                if overlap(b1,b2):
                    raise AssertionError(f"Detector envelopes overlap: D{i+1}/D{j+1}, t={t}, r={r}")
            for i,b1 in enumerate(boxes):
                for part in sample_parts+[plate]:
                    if overlap(b1,box(part)):
                        raise AssertionError(f"D{i+1} overlaps {part.name}: t={t}, r={r}, h={h}")
            if t>=.32:
                sample_z=(bpy.data.objects["Sample_vertical_translation"].matrix_world.translation-spot).z
                if abs(sample_z-h)>.001:
                    raise AssertionError("Head rotation starts before sample fully extracted")
            positions+=1
check(True,f"No selected envelope collisions at {positions} positions over 35-80 mm radius and 40-65 mm lift")
update(1)
d1=mods[0]
check((d1.matrix_world.translation-(spot+35*beam)).length<.001,"I0 beam intersects the centre of D1 at 35 mm downstream")
check((d1.matrix_world.to_3x3()@Vector((0,0,1))).dot(-beam)>.999999,"D1 entrance plane normal opposes incident beam in I0")
for part in sample_parts:
    check(not segment_box(spot-100*beam,spot+35*beam,box(part)),"I0 central ray clears "+part.name)

# Check that nominal face corners are not shadowed by the foil frame, a
# neighbouring detector envelope or the lifting structure.
update(0)
obstructions=[o for o in sample_parts if o!=foil]
for i,mod in enumerate(mods):
    blockers=[box(o) for o in obstructions]+[box(m,(0,0,-8.5),(7,7,9.5)) for j,m in enumerate(mods) if i!=j]
    for x,y in [(0,0),(-5,-5),(-5,5),(5,-5),(5,5)]:
        end=mod.matrix_world@Vector((x,y,0))
        check(not any(segment_box(spot,end,b) for b in blockers),f"D{i+1} face point ({x},{y}) unobstructed by selected geometry")

# Timeline playback has to work without panel-dependent update handlers.
ctrl["animate"]=True
ctrl.update_tag()
poses={}
for frame in (1,51,108,144,201,228,252):
    scene.frame_set(frame)
    bpy.context.view_layer.update()
    poses[frame] = {"state":float(ctrl["state"]),"sample_lift_mm":float(bpy.data.objects["Sample_vertical_translation"].location.z),
                   "head_angle_deg":math.degrees(bpy.data.objects["CZT_orbital_rotation"].rotation_euler.z)}
check(abs(poses[1]["head_angle_deg"]-90)<.001 and abs(poses[108]["head_angle_deg"])<.001,"Timeline reaches both detector orientations")
check(abs(poses[108]["sample_lift_mm"]-45)<.001 and abs(poses[252]["sample_lift_mm"])<.001,"Timeline extracts sample and returns it exactly")
report["timeline"]=poses

invalid=[]
for ids in (bpy.data.objects,bpy.data.curves):
    for obj in ids:
        if obj.animation_data:
            for fc in obj.animation_data.drivers:
                if not fc.driver.is_valid:
                    invalid.append(obj.name+":"+fc.data_path)
check(not invalid,"All saved drivers evaluate without invalid expressions")
panel_present=getattr(bpy.types,"PRISM_PT_setup",None) is not None
check(panel_present,"Embedded sidebar auto-registers in a fresh Blender session with script execution enabled")
bpy.ops.prism.set_mode(mode="INCIDENT")
check(ctrl["transition"]==1.0 and not ctrl["animate"],"Sidebar Incident I0 operator works")
bpy.ops.prism.set_mode(mode="FLUORESCENCE")
check(ctrl["transition"]==0.0 and not ctrl["animate"],"Sidebar Fluorescence operator works")
report["result"]="PASS"
out=Path(bpy.data.filepath).with_name("v1_Setup_PRISM_validation.json")
out.write_text(json.dumps(report,indent=2))
print("PRISM_VALIDATION_PASS",len(report["checks"]),"checks",out)
