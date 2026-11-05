import bpy
from shader import glossy_color
import numpy as np

class Atom:
   def __init__(self, r=(0,0,0), name='Atom', size=1, color=[255,0,0]):
      self.pos = np.array(r)
      self.name = name
      self.size = size
      self.color = np.array(color)


   def draw(self):
      bpy.ops.mesh.primitive_uv_sphere_add(location=self.pos,radius=self.size)
      bpy.context.object.name = self.name
      mat = bpy.data.materials.new(self.name)
      mat.diffuse_color = list((np.array(self.color)/255)**(2.2)) + [1]
      mat.roughness = 0.1
      mat.specular_intensity = 0.3
      bpy.data.objects[self.name].active_material = mat
      bpy.ops.object.shade_smooth()
      self.color = mat.diffuse_color


   def draw_glossy(self):
      bpy.ops.mesh.primitive_uv_sphere_add(location=self.pos,radius=self.size)
      bpy.context.object.name = self.name
      mat = bpy.data.materials.new(self.name)
      color = list((np.array(self.color)))
      glossy_color(self.name, color=color, ior=1.45)
      bpy.ops.object.shade_smooth()


   def update(self):
      ob = bpy.data.objects[self.name]
      ob.location = self.pos
      ob.keyframe_insert(data_path="location", index =-1)


