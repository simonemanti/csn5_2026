import bpy,math,json
from mathutils import Vector,Matrix
from bpy_extras.object_utils import world_to_camera_view
from pathlib import Path
P=Path('/home/smanti/BANDI/Proposta_di_Grant_Giovani_in_CSN5_Anno_2026/19_VOXES_Setup')
scene=bpy.context.scene;scene['voxes_version']=3
scene['Visual reference']='1_Ref_Old_VOXES.png'
scene['Beam']='Schematic connection of existing CAD optical centres; not a ray-tracing result.'
removed=[]
for ob in list(scene.objects):
 n=ob.get('FreeCAD_object');mode=ob.get('voxes_visibility')
 if n=='Part__Feature1585' or (n=='Part__Feature1604' and mode=='SETUP'):
  removed.append(ob.name);bpy.data.objects.remove(ob,do_unlink=True)
 elif n=='Part__Feature1604' and mode=='TRANSMISSION':
  ob.matrix_world=Matrix.Translation((0,0,-.0105))@Matrix.Rotation(-math.pi/2,4,'X')
  ob['Mount']='Upper face: lower surface at z=64.5 mm'
for ob in list(scene.objects):
 if ob.get('voxes_annotation'):bpy.data.objects.remove(ob,do_unlink=True)

def material(name,color,metal=.1,rough=.5,emission=False):
 m=bpy.data.materials.new(name);m.diffuse_color=(*color,1);m.use_nodes=True
 ns=m.node_tree.nodes;bs=ns.get('Principled BSDF');bs.inputs['Base Color'].default_value=(*color,1);bs.inputs['Metallic'].default_value=metal;bs.inputs['Roughness'].default_value=rough
 if emission:
  e=ns.new('ShaderNodeEmission');e.inputs['Color'].default_value=(*color,1);e.inputs['Strength'].default_value=1;m.node_tree.links.new(e.outputs[0],ns.get('Material Output').inputs[0])
 return m
mats={'aluminium':material('v3 | Light aluminium',(.43,.43,.39),.22),'black':material('v3 | Black anodized',(.012,.014,.013),.12),'brass':material('v3 | Brass / sample holder',(.46,.35,.13),.35),'silver':material('v3 | Grey detector',(.24,.25,.24),.3),'crystal':material('v3 | Cyan HAPG',(.07,.40,.44),.25),'label':material('v3 | Black Arial',(.005,.005,.005),emission=True),'line':material('v3 | Black leaders',(.04,.04,.04),emission=True),'beam':material('v3 | Red beam',(.8,.004,.003),emission=True)}
for ob in scene.objects:
 if ob.type!='MESH':continue
 g=ob.get('component');n=ob.get('FreeCAD_object')
 mat=mats['aluminium']
 if g in ['Slit S1','Slit S2']:mat=mats['black']
 if g=='X-ray tube':mat=mats['black'] if not n.startswith('Vite') else mats['silver']
 if n=='BaseFlangiataTubo':mat=mats['brass']
 if g=='Laser mount':mat=mats['silver']
 if g=='Sample holder' or n in ['Part__Feature1592','Part__Feature1604']:mat=mats['brass']
 if g=='Crystal':mat=mats['crystal'] if n in ['CristalloHAPG','Substrato'] else mats['black']
 if g=='MYTHEN':mat=mats['crystal'] if n=='FinestraMYTHEN' else mats['silver']
 ob.data.materials.clear();ob.data.materials.append(mat)
configs=[
('01 Overview','Insieme · camera aperta',(.12,-2.3,.56),(.61,-.14,.015),1.72),
('02 Reverse','Insieme · obliqua destra',(.95,-2.35,.57),(.61,-.14,.015),1.72),
('03 Top','Insieme · vista rialzata',(.28,-2.4,.84),(.61,-.14,.015),1.72),
('04 Elevation','Prospetto · portacampione',(.18,-2.6,.16),(.61,-.14,.015),1.72),
('05 Source','Sorgente · portacampione',(-.12,-.65,.16),(-.008,-.01,.035),.55),
('06 Transmission','Trasmissione · camera aperta',(-.22,-.70,.18),(-.05,-.01,.01),.55),
('07 Transmission top','Trasmissione · coperchio superiore',(-.15,-.75,.32),(-.045,-.01,.01),.58)]
for n,label,loc,target,scale in configs:
 cam=bpy.data.objects[n];cam.location=loc;cam.rotation_euler=(Vector(target)-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=scale;cam['voxes_view']=label
# Red incident/exiting schematic beam; no ED-XRF branch.
beamcol=bpy.data.collections.new('09 Schematic beam');scene.collection.children.link(beamcol)
for name,pts in [('Tube to sample',[(0,0,.081),(0,0,0)]),('Sample - slits - crystal',[(0,0,0),(.705730,0,0)]),('Crystal - MYTHEN',[(.705730,0,0),(1.290380,-.395271,0)])]:
 c=bpy.data.curves.new(name,'CURVE');c.dimensions='3D';c.bevel_depth=.0017;c.bevel_resolution=3
 sp=c.splines.new('POLY');sp.points.add(len(pts)-1)
 for a,b in zip(sp.points,pts):a.co=(*b,1)
 ob=bpy.data.objects.new(name,c);beamcol.objects.link(ob);c.materials.append(mats['beam']);ob['component']='Beam';ob['voxes_beam']=True;ob['voxes_visibility']='SETUP';ob.visible_shadow=False
font=next(f for f in bpy.data.fonts if f.name.startswith('Arial'))
labels=bpy.data.collections['07 Labels Arial']
def tag(ob,cam):
 labels.objects.link(ob);ob['voxes_annotation']=True;ob['voxes_camera']=cam.name;ob.visible_shadow=False

def add_label(cam,text,anchor,xy):
 w=cam.data.ortho_scale;h=w/1.8;q=cam.rotation_euler.to_quaternion()
 def at(x,y):return cam.location+q@Vector(((x-.5)*w,(y-.5)*h,-.25))
 data=bpy.data.curves.new(cam.name+' '+text,'FONT');data.body=text;data.font=font;data.align_x='CENTER';data.size=w*.018;data.extrude=.00005
 ob=bpy.data.objects.new(data.name,data);ob.location=at(*xy);ob.rotation_euler=cam.rotation_euler;data.materials.append(mats['label']);tag(ob,cam)
 bpy.context.view_layer.update();p=world_to_camera_view(scene,cam,Vector(anchor))
 start=(xy[0],xy[1]-.013 if p.y<xy[1] else xy[1]+.033)
 cu=bpy.data.curves.new('Leader '+text,'CURVE');cu.dimensions='3D';cu.bevel_depth=w*.00045;cu.bevel_resolution=2
 sp=cu.splines.new('POLY');sp.points.add(2)
 for point,v in zip(sp.points,[at(*start),at(start[0],start[1]+(-.025 if p.y<xy[1] else .025)),at(p.x,p.y)]):point.co=(*v,1)
 ob=bpy.data.objects.new(cu.name,cu);cu.materials.append(mats['line']);tag(ob,cam)
for cam in sorted((o for o in scene.objects if o.type=='CAMERA'),key=lambda o:o.name):
 if cam.name[:2] in ['01','02','03','04']:
  for text,anchor,xy in [('X-ray tube',(0,-.02,.104),(.13,.82)),('Sample holder',(-.003,0,-.006),(.13,.19)),('Slit S1',(.098,0,0),(.29,.69)),('Slit S2',(.626,0,0),(.48,.81)),('HAPG crystal',(.706,0,0),(.66,.73)),('MYTHEN detector',(1.29,-.395,0),(.85,.20))]:add_label(cam,text,anchor,xy)
 else:
  tr=cam.get('voxes_config')=='TRANSMISSION'
  for text,anchor,xy in [('X-ray tube',(-.109,-.02,0) if tr else (0,-.02,.104),(.16,.82)),('Sample holder',(-.003,0,-.006),(.82,.20))]:add_label(cam,text,anchor,xy)
  if tr:add_label(cam,'Upper cover',(0,0,.0685),(.82,.81))
  else:add_label(cam,'Laser mount',(-.095,0,0),(.16,.20))
scene.cycles.samples=64;scene.cycles.use_denoising=True
bpy.data.texts['voxes_panel.py'].clear();bpy.data.texts['voxes_panel.py'].write((P/'voxes_panel.py').read_text());bpy.data.texts['voxes_panel.py'].use_module=False
scene['v3_removed']=json.dumps(removed)
scene['v3_cover']='Transmission 204A008A moved from y=-79 mm to upper face, z=68.5 mm centre.'
bpy.ops.voxes.camera(camera_name='01 Overview');scene.render.filepath='//v3_VOXES.png'
bpy.ops.wm.save_as_mainfile(filepath=str(P/'v3_VOXES.blend'))
(P/'previews_v3').mkdir(exist_ok=True)
for name in ['01 Overview','05 Source','06 Transmission','07 Transmission top']:
 bpy.ops.voxes.camera(camera_name=name);scene.render.filepath=str(P/'previews_v3'/(name.replace(' ','_')+'.png'));bpy.ops.render.render(write_still=True)
bpy.ops.voxes.camera(camera_name='01 Overview');scene.render.filepath='//v3_VOXES.png';bpy.ops.wm.save_as_mainfile(filepath=str(P/'v3_VOXES.blend'))
