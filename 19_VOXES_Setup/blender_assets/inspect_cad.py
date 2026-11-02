import FreeCAD as A, json, os
p='/home/smanti/BANDI/Proposta_di_Grant_Giovani_in_CSN5_Anno_2026/19_VOXES_Setup'
d=A.openDocument(p+'/v004_VOXES.FCStd')
rows=[]
for o in d.Objects:
 r={'name':o.Name,'label':o.Label,'type':o.TypeId,'parents':[i.Name for i in o.InList],'children':[i.Name for i in getattr(o,'Group',[])]}
 if hasattr(o,'Shape') and not o.Shape.isNull():
  s=o.Shape.copy(); s.Placement=o.getGlobalPlacement(); b=s.BoundBox
  r.update(bbox=[b.XMin,b.YMin,b.ZMin,b.XMax,b.YMax,b.ZMax],center=list(b.Center),placement=list(o.getGlobalPlacement().Matrix.A),volume=s.Volume)
 rows.append(r)
json.dump(rows,open(p+'/blender_assets/cad_inventory.json','w'),indent=2)
print('INVENTORY_DONE',len(rows))
