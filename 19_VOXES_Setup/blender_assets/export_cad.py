import FreeCAD as A, MeshPart, json, os, hashlib
p='/home/smanti/BANDI/Proposta_di_Grant_Giovani_in_CSN5_Anno_2026/19_VOXES_Setup'
d=A.openDocument(p+'/v004_VOXES.FCStd')
groups={
'Source chamber':['Part__Feature'+str(i) for i in [1583,1584,1585,1586,1591,1592,1604,1605]],
'Sample holder':['Part__Feature'+str(i) for i in [1628,1629,1630,1635]],
'Laser mount':['Part__Feature1657'],
'X-ray tube':[o.Name for o in d.TuboRaggiX.Group if o.Name!='TuboCompleto'],
'Slit S1':['Part__Feature2723'],
'Slit S2':['Part__Feature2726'],
'Crystal':['Substrato','CristalloHAPG','Part__Feature116','Part__Feature117'],
'MYTHEN':['InvolucroMYTHEN','FinestraMYTHEN','ConnettoreMYTHEN']}
rows=[]
for group,names in groups.items():
 for n in names:
  o=d.getObject(n); s=o.Shape.copy(); s.Placement=o.getGlobalPlacement()
  m=MeshPart.meshFromShape(Shape=s,LinearDeflection=0.12,AngularDeflection=0.22,Relative=False)
  v,f=m.Topology
  rows.append({'name':n,'label':o.Label,'group':group,'vertices':[[x.x*.001,x.y*.001,x.z*.001] for x in v],'faces':f})
json.dump(rows,open(p+'/blender_assets/voxes_meshes.json','w'),separators=(',',':'))
json.dump({'source':'v004_VOXES.FCStd','sha256':hashlib.sha256(open(p+'/v004_VOXES.FCStd','rb').read()).hexdigest(),'objects':len(rows),'triangles':sum(len(x['faces']) for x in rows),'units':'metres','rear_mount':'Tube rotated -90 deg about Y; flange aligned to x=-70 mm; laser adapter removed in transmission.'},open(p+'/blender_assets/export_manifest.json','w'),indent=2)
print('EXPORT_DONE',len(rows))
