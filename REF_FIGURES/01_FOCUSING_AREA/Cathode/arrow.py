import bpy
import bmesh
import numpy as np
from mathutils import Vector
#
class arrow:
    def __init__(self, pos, v, cap, width, L, name="arrow",r = 0.05, theta=np.pi/3):
        l = cap
        w = l*np.cos(theta)-width/2
        self.v = v
        self.name = name
        #
        if L <= l*np.sin(theta):
            L = l*np.sin(theta)
            r = 0
        #
        verts = [(0, 0, 0),
                 (-l*np.cos(theta), -l*np.sin(theta), 0),
                 (-l*np.cos(theta)+w, -l*np.sin(theta)+r, 0),
                 (-l*np.cos(theta)+w, -L, 0),
                 (+l*np.cos(theta)-w, -L, 0),
                 (+l*np.cos(theta)-w, -l*np.sin(theta)+r, 0),
                 (+l*np.cos(theta), -l*np.sin(theta), 0),
                 (0, 0, 0)]
        #
        mesh = bpy.data.meshes.new("mesh")  # add a new mesh
        obj = bpy.data.objects.new(name, mesh)  # add a new object using the mesh
        #
        scene = bpy.context.scene
        bpy.context.collection.objects.link(obj)  # put the object into the scene (link)
        bpy.context.view_layer.objects.active = obj  # set as the active object in the scene
        obj.select_set(True)  # select object
        mesh = bpy.context.object.data
        bm = bmesh.new()
        for vert in verts:
            bm.verts.new(vert)  # add a new vert
        bm.faces.new(bm.verts)
        # make the bmesh the object's mesh
        bm.to_mesh(mesh)  
        bm.free()  # always do this when finished            
        #bpy.ops.object.origin_set(type='ORIGIN_CENTER_OF_MASS', center='MEDIAN')
        bpy.data.objects[name].location = (pos.x, pos.y, pos.z) 
        bpy.ops.transform.rotate(value=-np.arctan2(self.v.y,self.v.x)+np.pi/2, 
                                 orient_axis='Z')
        #bpy.context.view_layer.objects.active = None
        mat = bpy.data.materials.new('black')
        mat.diffuse_color = (0,0,0,1)
        mat.roughness = 1
        mat.specular_intensity = 0
        bpy.data.objects[name].active_material = mat
        obj.select_set(False)

    def update_direction(self,v):
        self.v = v
        obj = bpy.data.objects[self.name]  # add a new object using the mesh
        bpy.context.view_layer.objects.active = obj  # set as the active object in the scene
        obj.select_set(True) 
        bpy.ops.transform.rotate(value=-np.arctan2(self.v.y,self.v.x), 
                                 orient_axis='Z')
        bpy.ops.anim.keyframe_insert_menu(type='Rotation')
