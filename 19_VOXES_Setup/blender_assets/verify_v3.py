import bpy,json
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
P=Path('/home/smanti/BANDI/Proposta_di_Grant_Giovani_in_CSN5_Anno_2026/19_VOXES_Setup');s=bpy.context.scene
assert s['voxes_version']==3
assert hasattr(bpy.types,'VOXES_PT_views')
assert not any(o.get('FreeCAD_object')=='Part__Feature1585' for o in s.objects)
plates=[o for o in s.objects if o.get('FreeCAD_object')=='Part__Feature1604'];assert len(plates)==1
plate=plates[0];assert plate.get('voxes_visibility')=='TRANSMISSION'
z=[(plate.matrix_world@v.co).z for v in plate.data.vertices];assert abs(min(z)-.0645)<1e-5
results=[]
for cam in sorted((o for o in s.objects if o.type=='CAMERA'),key=lambda o:o.name):
 bpy.ops.voxes.camera(camera_name=cam.name);bpy.context.view_layer.update()
 mesh=[o for o in s.objects if o.type=='MESH' and not o.hide_render]
 verts=[];tris=[];owners=[];probes=[]
 for o in mesh:
  offset=len(verts);vs=[o.matrix_world@v.co for v in o.data.vertices];verts.extend(vs)
  for f in o.data.polygons:
   tris.append(tuple(offset+i for i in f.vertices));owners.append(o.get('component'))
  if o.get('FreeCAD_object')=='Part__Feature1630':probes=vs[::max(1,len(vs)//200)]
 tree=BVHTree.FromPolygons(verts,tris,all_triangles=True)
 direction=cam.rotation_euler.to_quaternion()@Vector((0,0,-1));visible=0
 for target in probes:
  loc,normal,idx,dist=tree.ray_cast(target-direction*5,direction,6)
  if idx is not None and owners[idx]=='Sample holder':visible+=1
 assert visible>0,(cam.name,'sample holder occluded')
 beam=[o for o in s.objects if o.get('voxes_beam') and not o.hide_render]
 assert bool(beam)==(cam.get('voxes_config')=='SETUP')
 assert all(o.data.font.packed_file for o in s.objects if o.type=='FONT')
 results.append({'camera':cam.name,'sample_holder_visible_rays':visible,'tested_rays':len(probes),'beam_segments':len(beam)})
s.voxes_beam=False;bpy.ops.voxes.camera(camera_name='01 Overview');assert not any(not o.hide_render for o in s.objects if o.get('voxes_beam'));s.voxes_beam=True
json.dump({'checks':'pass','cameras':results,'upper_cover_z_mm':[min(z)*1000,max(z)*1000]},open(P/'blender_assets/verification_v3.json','w'),indent=2)
print('V3 VERIFIED',results)
