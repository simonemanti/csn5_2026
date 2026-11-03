import bpy,json,hashlib
from pathlib import Path
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view
P=Path('/home/smanti/BANDI/Proposta_di_Grant_Giovani_in_CSN5_Anno_2026/19_VOXES_Setup')
assert hasattr(bpy.types,'VOXES_PT_views'),'Sidebar not registered after reopen'
s=bpy.context.scene
assert s.get('voxes_document')
assert all(o.data.font.packed_file and o.data.font.name.startswith('Arial') for o in s.objects if o.type=='FONT')
manifest=json.load(open(P/'blender_assets/export_manifest.json'))
assert hashlib.sha256((P/'v004_VOXES.FCStd').read_bytes()).hexdigest()==manifest['sha256'],'CAD source modified'
report={'source_unchanged':True,'sidebar_registered_after_reopen':True,'packed_Arial':True,'cameras':[]}
for cam in sorted((o for o in s.objects if o.type=='CAMERA'),key=lambda x:x.name):
 assert bpy.ops.voxes.camera(camera_name=cam.name)=={'FINISHED'}
 tr=cam.get('voxes_config')=='TRANSMISSION'
 source=cam.get('voxes_config')=='SOURCE'
 visible=[o for o in s.objects if o.type=='MESH' and not o.hide_render]
 groups=sorted(set(o.get('component') for o in visible))
 if tr:
  assert set(groups)=={'Source chamber','Sample holder','X-ray tube'}
  assert all(o.get('voxes_visibility')=='TRANSMISSION' for o in visible)
 elif source:assert set(groups)=={'Source chamber','Sample holder','X-ray tube','Laser mount'}
 else:assert set(groups)=={'Source chamber','Sample holder','X-ray tube','Laser mount','Slit S1','Slit S2','Crystal','MYTHEN'}
 bpy.context.view_layer.update()
 projected=[world_to_camera_view(s,cam,o.matrix_world@Vector(v)) for o in visible for v in o.bound_box]
 bounds=[min(p.x for p in projected),min(p.y for p in projected),max(p.x for p in projected),max(p.y for p in projected)]
 assert all(v>=0 for v in bounds[:2]) and all(v<=1 for v in bounds[2:]),(cam.name,bounds)
 labels=[o for o in s.objects if o.type=='FONT' and not o.hide_render]
 assert labels and all(o.get('voxes_camera')==cam.name for o in labels)
 s.voxes_labels=False
 assert not any(not o.hide_render for o in s.objects if o.get('voxes_annotation'))
 s.voxes_labels=True
 report['cameras'].append({'name':cam.name,'configuration':cam.get('voxes_config'),'visible_meshes':len(visible),'groups':groups,'frame_bounds':bounds,'labels':[o.data.body for o in labels]})
bpy.ops.voxes.camera(camera_name='01 Overview')
json.dump(report,open(P/'blender_assets/verification.json','w'),indent=2)
print('VERIFIED',len(report['cameras']),'cameras; CAD unchanged; sidebar loaded; labels toggled; all objects inside frames.')
