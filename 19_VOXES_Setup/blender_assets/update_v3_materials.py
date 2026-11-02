import bpy
from pathlib import Path
P=Path(bpy.data.filepath).parent
s=bpy.context.scene
ref=next(o for o in s.objects if o.get('FreeCAD_object')=='Part__Feature1605').active_material
metal=bpy.data.materials.new('v3 | Polished light steel');metal.use_nodes=True
metal.diffuse_color=(.65,.68,.7,1)
bs=metal.node_tree.nodes.get('Principled BSDF');bs.inputs['Base Color'].default_value=metal.diffuse_color;bs.inputs['Metallic'].default_value=.95;bs.inputs['Roughness'].default_value=.23
for o in s.objects:
 n=o.get('FreeCAD_object','')
 mat=None
 if n in ['Part__Feature1592','BaseFlangiataTubo','Part__Feature1604']:mat=ref
 elif n in ['CorpoTuboX','CoperchioAnteriore','CoperchioPosteriore','GhieraHV'] or n.startswith('ViteCoperchio'):mat=metal
 if mat:o.data.materials.clear();o.data.materials.append(mat)
 if o.type=='FONT' and o.get('voxes_annotation'):o['voxes_base_font_size']=o.data.size
s.voxes_font_scale=1.0
for screen in bpy.data.screens:
 for area in screen.areas:
  if area.type=='VIEW_3D':
   sh=area.spaces.active.shading;sh.type='MATERIAL';sh.studio_light='forest.exr';sh.use_scene_world=False;sh.use_scene_lights=False
# Use the same bundled Forest environment for rendering; preserve a white backdrop.
w=s.world;w.use_nodes=True;nt=w.node_tree;nt.nodes.clear()
out=nt.nodes.new('ShaderNodeOutputWorld');mix=nt.nodes.new('ShaderNodeMixShader');ray=nt.nodes.new('ShaderNodeLightPath')
env=nt.nodes.new('ShaderNodeTexEnvironment');env.image=bpy.data.images.load('/home/smanti/.local/opt/blender-5.2.0-linux-x64/5.2/datafiles/studiolights/world/forest.exr',check_existing=True);env.image.pack()
bg=nt.nodes.new('ShaderNodeBackground');bg.inputs['Strength'].default_value=1
white=nt.nodes.new('ShaderNodeBackground');white.inputs['Color'].default_value=(1,1,1,1)
nt.links.new(env.outputs['Color'],bg.inputs['Color']);nt.links.new(ray.outputs['Is Camera Ray'],mix.inputs[0]);nt.links.new(bg.outputs[0],mix.inputs[1]);nt.links.new(white.outputs[0],mix.inputs[2]);nt.links.new(mix.outputs[0],out.inputs[0])
s['voxes_world']='Forest studio HDRI (packed)'
t=bpy.data.texts.get('voxes_panel.py');t.clear();t.write((P/'voxes_panel.py').read_text())
# Verify the global size control and exact shared plate material.
labels=[o for o in s.objects if o.type=='FONT' and o.get('voxes_annotation')]
s.voxes_font_scale=1.4
assert all(abs(o.data.size/o['voxes_base_font_size']-1.4)<1e-5 for o in labels)
s.voxes_font_scale=1
assert all(o.active_material==ref for o in s.objects if o.get('FreeCAD_object') in ['Part__Feature1592','BaseFlangiataTubo','Part__Feature1604'])
bpy.ops.voxes.camera(camera_name='01 Overview');bpy.ops.wm.save_as_mainfile(filepath=str(P/'v3_VOXES.blend'))
for name in ['05 Source','06 Transmission','01 Overview','02 Reverse','03 Top','04 Elevation','07 Transmission top']:
 bpy.ops.voxes.camera(camera_name=name);s.render.filepath=str(P/'previews_v3'/(name.replace(' ','_')+'.png'));bpy.ops.render.render(write_still=True)
bpy.ops.voxes.camera(camera_name='01 Overview');s.render.filepath='//v3_VOXES.png';bpy.ops.wm.save_as_mainfile(filepath=str(P/'v3_VOXES.blend'))
print('VERIFIED: shared plate materials, Forest packed, label size control')
