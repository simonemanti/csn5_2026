import bpy,json,math,sys,os
from mathutils import Vector,Matrix
from bpy_extras.object_utils import world_to_camera_view
from pathlib import Path
P=Path('/home/smanti/BANDI/Proposta_di_Grant_Giovani_in_CSN5_Anno_2026/19_VOXES_Setup')
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
for c in list(bpy.data.collections):
 if c.name!='Collection':bpy.data.collections.remove(c)
scene=bpy.context.scene
scene['voxes_document']=True
scene['CAD_source']='v004_VOXES.FCStd'
scene['Geometry']='CAD tessellation, millimetres converted to metres; original component placement preserved.'
scene['Transmission_mount']='Tube flange aligned with rear chamber face x=-70 mm; laser adapter removed. Visual configuration, not a certified mounting design.'
scene.unit_settings.system='METRIC';scene.unit_settings.length_unit='MILLIMETERS'
scene.render.engine='CYCLES';scene.cycles.samples=64
scene.cycles.use_denoising=True
scene.render.resolution_x=1800;scene.render.resolution_y=1000;scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG';scene.render.image_settings.color_mode='RGBA'
scene.render.film_transparent=False
scene.world.use_nodes=True
wn=scene.world.node_tree.nodes; wl=scene.world.node_tree.links;wn.clear()
out=wn.new('ShaderNodeOutputWorld'); ambient=wn.new('ShaderNodeBackground');ambient.inputs['Color'].default_value=(1,1,1,1);ambient.inputs['Strength'].default_value=.35
white=wn.new('ShaderNodeBackground');white.inputs['Color'].default_value=(1,1,1,1);white.inputs['Strength'].default_value=1
lp=wn.new('ShaderNodeLightPath');mix=wn.new('ShaderNodeMixShader');wl.new(lp.outputs['Is Camera Ray'],mix.inputs[0]);wl.new(ambient.outputs[0],mix.inputs[1]);wl.new(white.outputs[0],mix.inputs[2]);wl.new(mix.outputs[0],out.inputs[0])
scene.view_settings.view_transform='Standard'
scene.render.image_settings.color_depth='8'
scene.render.fps=24

def collection(name):
 c=bpy.data.collections.new(name);scene.collection.children.link(c);return c
cols={k:collection(k) for k in ['01 Source','02 Slits','03 Crystal','04 MYTHEN','05 Transmission source','06 Cameras','07 Labels Arial','08 Lighting']}
def material(name,color,metal=0,rough=.45,emission=False):
 m=bpy.data.materials.new(name);m.diffuse_color=(*color,1);m.use_nodes=True
 bs=m.node_tree.nodes.get('Principled BSDF');bs.inputs['Base Color'].default_value=(*color,1);bs.inputs['Metallic'].default_value=metal;bs.inputs['Roughness'].default_value=rough
 if emission:
  em=m.node_tree.nodes.new('ShaderNodeEmission');em.inputs['Color'].default_value=(*color,1);em.inputs['Strength'].default_value=1;m.node_tree.links.new(em.outputs[0],m.node_tree.nodes.get('Material Output').inputs['Surface'])
 return m
mats={'metal':material('Satin aluminium',(.22,.26,.30),.30),'dark':material('Graphite housing',(.065,.08,.10),.35),'crystal':material('HAPG surface',(.12,.42,.53),.55,.22),'glass':material('Crystal substrate',(.45,.61,.67),.35),'sample':material('Sample holder',(.69,.51,.25),.5),'label':material('Arial navy',(.008,.034,.065),0,1,True),'line':material('Leader slate',(.23,.34,.40),0,1,True)}
by_name={}
for row in json.load(open(P/'blender_assets/voxes_meshes.json')):
 name=row['name'];g=row['group']
 me=bpy.data.meshes.new(name);me.from_pydata(row['vertices'],[],row['faces']);me.update()
 ob=bpy.data.objects.new(row['label']+' ['+name+']',me)
 key='01 Source' if g in ['Source chamber','Sample holder','Laser mount','X-ray tube'] else ('02 Slits' if g.startswith('Slit') else '03 Crystal' if g=='Crystal' else '04 MYTHEN')
 cols[key].objects.link(ob);ob['FreeCAD_object']=name;ob['component']=g;ob['voxes_visibility']='SETUP'
 mat=mats['dark'] if g in ['X-ray tube','Laser mount','Slit S1','Slit S2','MYTHEN'] else mats['metal']
 if g=='Sample holder':mat=mats['sample']
 if name=='Substrato':mat=mats['glass']
 if name=='CristalloHAPG' or name=='FinestraMYTHEN':mat=mats['crystal']
 ob.data.materials.append(mat)
 # Smooth only neighboring faces below 35 degrees; preserve CAD hard edges.
 for face in me.polygons:face.use_smooth=True
 me.set_sharp_from_angle(angle=math.radians(35))
 by_name[name]=ob
# Transmission: shared CAD meshes, independent rigid tube transformation.
rear=Matrix.Translation(Vector((-.0055,0,0))) @ Matrix.Rotation(math.radians(-90),4,'Y')
for row in json.load(open(P/'blender_assets/voxes_meshes.json')):
 if row['group'] not in ['Source chamber','Sample holder','X-ray tube']:continue
 orig=by_name[row['name']];ob=orig.copy();ob.data=orig.data;ob.name='Transmission | '+orig.name
 cols['05 Transmission source'].objects.link(ob);ob['voxes_visibility']='TRANSMISSION'
 if row['group']=='X-ray tube':ob.matrix_world=rear
 ob.hide_render=True;ob.hide_set(True)
# Cameras use orthographic projection to retain dimensional proportions.
def camera(name,label,loc,target,scale,config='SETUP'):
 data=bpy.data.cameras.new(name);data.type='ORTHO';data.ortho_scale=scale;data.lens=50;data.clip_start=.001;data.clip_end=100
 ob=bpy.data.objects.new(name,data);cols['06 Cameras'].objects.link(ob);ob.location=loc;ob.rotation_euler=(Vector(target)-ob.location).to_track_quat('-Z','Y').to_euler();ob['voxes_view']=label;ob['voxes_config']=config
 return ob
cams=[camera('01 Overview','Insieme · obliqua frontale',(.35,-2.1,1.4),(.61,-.14,.015),1.70),camera('02 Reverse','Insieme · obliqua opposta',(.4,2,1.25),(.61,-.14,.015),1.72),camera('03 Top','Pianta · percorso ottico',(.60,-.15,3),(.60,-.15,0),1.72),camera('04 Elevation','Prospetto · altezza fascio',(.60,-2.6,.42),(.60,-.14,.02),1.70),camera('05 Source','Dettaglio · sorgente VOXES',(-.36,-.65,.37),(-.015,-.025,.035),.65,'SOURCE'),camera('06 Transmission','Trasmissione · obliqua',(-.38,-.62,.35),(-.055,-.02,.005),.60,'TRANSMISSION'),camera('07 Transmission top','Trasmissione · dall’alto',(-.045,-.03,1),(-.045,-.03,0),.60,'TRANSMISSION')]
for name,loc,power,size in [('Key',(.2,-.8,1.8),35,2.0),('Fill',(1.1,.6,1.4),25,1.6),('Rim',(-.4,.5,.7),20,1.0)]:
 data=bpy.data.lights.new(name,'AREA');data.energy=power;data.shape='DISK';data.size=size;ob=bpy.data.objects.new(name,data);cols['08 Lighting'].objects.link(ob);ob.location=loc;ob.rotation_euler=(Vector((.5,-.1,0))-ob.location).to_track_quat('-Z','Y').to_euler()
font=bpy.data.fonts.load('/usr/local/share/fonts/a/ARIAL.ttf');font.pack()
font_bold=bpy.data.fonts.load('/usr/local/share/fonts/a/ARIALBD.ttf') if Path('/usr/local/share/fonts/a/ARIALBD.ttf').exists() else font
if font_bold!=font:font_bold.pack()

def annotation_tag(ob,cam):
 ob['voxes_annotation']=True;ob['voxes_camera']=cam.name;ob.visible_shadow=False;cols['07 Labels Arial'].objects.link(ob)

def add_label(cam,text,anchor,xy):
 # Labels and leaders lie on a plane facing the selected camera.
 w=cam.data.ortho_scale;h=w/1.8;dep=.25
 q=cam.rotation_euler.to_quaternion()
 def at(x,y):return cam.location+q@Vector(((x-.5)*w,(y-.5)*h,-dep))
 data=bpy.data.curves.new(cam.name+' '+text,'FONT');data.body=text;data.font=font;data.align_x='CENTER';data.size=w*.017;data.space_line=1.05
 ob=bpy.data.objects.new(data.name,data);ob.location=at(*xy);ob.rotation_euler=cam.rotation_euler;data.materials.append(mats['label']);annotation_tag(ob,cam)
 bpy.context.view_layer.update()
 p=world_to_camera_view(scene,cam,Vector(anchor))
 start=(xy[0],xy[1]-.013 if p.y<xy[1] else xy[1]+.032)
 curve=bpy.data.curves.new('Leader '+text,'CURVE');curve.dimensions='3D';curve.bevel_depth=w*.00045;curve.bevel_resolution=2
 s=curve.splines.new('POLY');s.points.add(2)
 pts=[at(*start),at(start[0],start[1]+(-.03 if p.y<xy[1] else .03)),at(p.x,p.y)]
 for a,b in zip(s.points,pts):a.co=(*b,1)
 leader=bpy.data.objects.new(curve.name,curve);curve.materials.append(mats['line']);annotation_tag(leader,cam)
for cam in cams:
 bpy.context.view_layer.update()
 if cam.name[:2] in ['01','02','03','04']:
  anchors=[('X-ray tube',(0,-.02,.104)),('Sample chamber',(0,-.078,0)),('Slit S1',(.098,0,0)),('Slit S2',(.626,0,0)),('HAPG crystal',(.706,0,0)),('MYTHEN detector',(1.29,-.395,0))]
  projected=[(t,a,world_to_camera_view(scene,cam,Vector(a)).x) for t,a in anchors]
  # Fixed separate lanes keep adjacent slit/crystal labels readable.
  positions={'X-ray tube':(.12,.85),'Sample chamber':(.12,.14),'Slit S1':(.30,.72),'Slit S2':(.49,.83),'HAPG crystal':(.66,.72),'MYTHEN detector':(.86,.18)}
  if cam.name.startswith('02'):
   positions={k:(1-v[0],v[1]) for k,v in positions.items()}
  for t,a,_ in projected:add_label(cam,t,a,positions[t])
 else:
  tr=cam.get('voxes_config')=='TRANSMISSION'
  anchors=[('X-ray tube',(-.109,-.02,0) if tr else (0,-.02,.104),(.18,.85)),('Sample chamber',(0,-.078,0),(.84,.76))]
  if not tr:anchors.append(('Laser mount',(-.095,0,0),(.20,.16)))
  for t,a,pos in anchors:add_label(cam,t,a,pos)
# Embed the panel script; startup module supplies automatic local availability.
sys.path.insert(0,str(P));import voxes_panel;voxes_panel.register()
script=bpy.data.texts.load(str(P/'voxes_panel.py'));script.use_module=False
readme=bpy.data.texts.new('README · VOXES');readme.write('N > VOXES: choose camera/configuration. F12: render. Labels use packed Arial. CAD source: v004_VOXES.FCStd. All geometry is mesh-converted with original world placement; no ED-XRF, motors, rails or table. Transmission rigidly relocates tube to rear laser port. On another computer run voxes_panel.py in the Text Editor once, or install it as a startup script.\n')
voxes_panel.select_view(bpy.context,cams[0])
for screen in bpy.data.screens:
 for area in screen.areas:
  if area.type=='VIEW_3D':
   sp=area.spaces.active;sp.show_region_ui=True;sp.overlay.show_overlays=False;sp.shading.type='MATERIAL';sp.region_3d.view_perspective='CAMERA';sp.region_3d.view_camera_zoom=5
bpy.ops.wm.save_as_mainfile(filepath=str(P/'v1_VOXES.blend'))
(P/'previews').mkdir(exist_ok=True)
for cam in cams:
 voxes_panel.select_view(bpy.context,cam);scene.render.filepath=str(P/'previews'/('v1_'+cam.name.replace(' ','_')+'.png'));bpy.ops.render.render(write_still=True)
voxes_panel.select_view(bpy.context,cams[0]);scene.render.filepath='//v1_VOXES.png';bpy.ops.wm.save_as_mainfile(filepath=str(P/'v1_VOXES.blend'))
print('BUILD_AND_RENDER_DONE')
