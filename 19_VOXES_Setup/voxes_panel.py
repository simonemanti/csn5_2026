"""VOXES sidebar. Also embedded in v1_VOXES.blend for portability."""
import bpy
from bpy.app.handlers import persistent

def select_view(context, camera):
    scene=context.scene
    if not scene.get('voxes_document'): return
    scene.camera=camera
    transmission=camera.get('voxes_config')=='TRANSMISSION'
    for obj in scene.objects:
        mode=obj.get('voxes_visibility','')
        hide=(mode=='SETUP' and transmission) or (mode=='TRANSMISSION' and not transmission)
        if camera.get('voxes_config')=='SOURCE' and obj.get('component') in ['Slit S1','Slit S2','Crystal','MYTHEN','Beam']:
            hide=True
        if obj.get('voxes_beam') and not scene.voxes_beam:
            hide=True
        if obj.get('voxes_annotation'):
            hide=obj.get('voxes_camera')!=camera.name or not scene.voxes_labels
        obj.hide_render=hide
        obj.hide_set(hide)
        if obj.type=='FONT' and not hide:
            obj.data.body=obj.data.body
            obj.data.update_tag()
            obj.update_tag(refresh={'DATA'})
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type=='VIEW_3D':
                area.spaces.active.region_3d.view_perspective='CAMERA'
    context.view_layer.update()
    scene['active_configuration']='Transmission: rear-mounted tube' if transmission else 'VOXES: top-mounted tube'

def update_font_size(self,context):
    for obj in context.scene.objects:
        if obj.type == "FONT" and obj.get("voxes_annotation"):
            if "voxes_base_font_size" not in obj:
                obj["voxes_base_font_size"] = obj.data.size
            obj.data.size = obj["voxes_base_font_size"] * self.voxes_font_scale
    context.view_layer.update()

def update_labels(self,context):
    if context.scene.camera: select_view(context,context.scene.camera)

class VOXES_OT_camera(bpy.types.Operator):
    bl_idname='voxes.camera'
    bl_label='Seleziona vista VOXES'
    bl_options={'REGISTER','UNDO'}
    camera_name:bpy.props.StringProperty()
    def execute(self,context):
        cam=bpy.data.objects.get(self.camera_name)
        if not cam or cam.type!='CAMERA':return {'CANCELLED'}
        select_view(context,cam)
        return {'FINISHED'}

class VOXES_PT_views(bpy.types.Panel):
    bl_label='VOXES | Viste e configurazioni'
    bl_idname='VOXES_PT_views'
    bl_space_type='VIEW_3D'
    bl_region_type='UI'
    bl_category='VOXES'
    @classmethod
    def poll(cls,context):return bool(context.scene.get('voxes_document'))
    def draw(self,context):
        layout=self.layout
        layout.label(text='Setup semplificato',icon='OUTLINER_OB_CAMERA')
        cams=sorted((o for o in context.scene.objects if o.type=='CAMERA' and o.get('voxes_view')),key=lambda o:o.name)
        for cam in cams:
            if cam.get('voxes_config')=='TRANSMISSION':continue
            op=layout.operator('voxes.camera',text=cam['voxes_view'],depress=context.scene.camera==cam)
            op.camera_name=cam.name
        layout.separator()
        layout.label(text='Trasmissione: solo sorgente')
        for cam in cams:
            if cam.get('voxes_config')!='TRANSMISSION':continue
            op=layout.operator('voxes.camera',text=cam['voxes_view'],depress=context.scene.camera==cam)
            op.camera_name=cam.name
        layout.separator()
        layout.prop(context.scene,'voxes_labels',text='Etichette Arial')
        layout.prop(context.scene,'voxes_font_scale',text='Dimensione etichette',slider=True)
        if context.scene.get('voxes_version',1)>=3:
            layout.prop(context.scene,'voxes_beam',text='Fascio schematico')
        layout.prop(context.scene.render,'film_transparent',text='Sfondo trasparente')
        layout.label(text='F12: render della vista attiva',icon='RENDER_STILL')

@persistent
def voxes_load(_):
    if bpy.context.scene and bpy.context.scene.get('voxes_document') and bpy.context.scene.camera:
        select_view(bpy.context,bpy.context.scene.camera)

def register():
    for cls in (VOXES_OT_camera,VOXES_PT_views):
        old=getattr(bpy.types,cls.__name__,None)
        if old:bpy.utils.unregister_class(old)
        bpy.utils.register_class(cls)
    bpy.types.Scene.voxes_font_scale=bpy.props.FloatProperty(name='Dimensione etichette',description='Scala delle etichette rispetto alla dimensione originale',default=1.0,min=0.25,max=3.0,soft_min=0.5,soft_max=2.0,update=update_font_size)
    bpy.types.Scene.voxes_beam=bpy.props.BoolProperty(name='Fascio schematico',default=True,update=update_labels)
    bpy.types.Scene.voxes_labels=bpy.props.BoolProperty(name='Etichette Arial',default=True,update=update_labels)
    for handler in list(bpy.app.handlers.load_post):
        if handler.__name__=='voxes_load':bpy.app.handlers.load_post.remove(handler)
    bpy.app.handlers.load_post.append(voxes_load)

def unregister():
    for cls in (VOXES_PT_views,VOXES_OT_camera):
        old=getattr(bpy.types,cls.__name__,None)
        if old:bpy.utils.unregister_class(old)
    if hasattr(bpy.types.Scene,'voxes_font_scale'):del bpy.types.Scene.voxes_font_scale
    if hasattr(bpy.types.Scene,'voxes_labels'):del bpy.types.Scene.voxes_labels
    if hasattr(bpy.types.Scene,'voxes_beam'):del bpy.types.Scene.voxes_beam
    for handler in list(bpy.app.handlers.load_post):
        if handler.__name__=='voxes_load':bpy.app.handlers.load_post.remove(handler)

if __name__=='__main__':register()
