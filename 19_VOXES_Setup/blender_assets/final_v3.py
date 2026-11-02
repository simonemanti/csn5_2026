import bpy
from pathlib import Path
P=Path('/home/smanti/BANDI/Proposta_di_Grant_Giovani_in_CSN5_Anno_2026/19_VOXES_Setup');s=bpy.context.scene
for ob in s.objects:
 if ob.type=='FONT':ob.data.extrude=.00005
for cam in sorted((o for o in s.objects if o.type=='CAMERA'),key=lambda o:o.name):
 bpy.ops.voxes.camera(camera_name=cam.name);s.render.filepath=str(P/'previews_v3'/(cam.name.replace(' ','_')+'.png'));bpy.ops.render.render(write_still=True)
bpy.ops.voxes.camera(camera_name='01 Overview');s.render.filepath='//v3_VOXES.png';bpy.ops.wm.save_as_mainfile(filepath=str(P/'v3_VOXES.blend'))
