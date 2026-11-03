import bpy
from color import colors
import numpy as np

class Bond:
    def __init__(self, atom1, atom2, name, dist, r=0.1):
        self.atom1 = atom1
        self.atom2 = atom2
        self.delta = atom2.position - atom1.position
        self.dist = dist
        self.name = name
        self.r = r
    def draw(self):
        bpy.ops.mesh.primitive_cylinder_add(
            radius = self.r,
            depth = self.dist,
            location = self.atom1.position + 0.5 * self.delta
           )
        obj = bpy.context.object
        obj.name = self.name
        bpy.ops.object.select_all(action='DESELECT')

        # select just right object
        obj.select_set(True)
        bpy.ops.object.editmode_toggle()
        cut_z = obj.location.z + 0*(self.dist + self.delta[2])/2
        bpy.ops.mesh.bisect(plane_co=(0, 0, cut_z), plane_no=(0, 0, 1), use_fill=True, clear_inner=False)
        bpy.ops.object.editmode_toggle()
        # deselect all objects
        bpy.ops.object.select_all(action='DESELECT')
        m_1 = bpy.data.materials.new('O')
        m_1.diffuse_color = list((np.array(colors[self.atom1.symbol])/255)**(2.2)) + [1]
        m_1.roughness = 0.1
        m_1.specular_intensity = 0.3
        m_2 = bpy.data.materials.new('M')
        m_2.diffuse_color = list((np.array(colors[self.atom2.symbol])/255)**(2.2)) + [1]
        m_2.roughness = 0.1
        m_2.specular_intensity = 0.3
        obj.data.materials.append(m_1)
        obj.data.materials.append(m_2)
        for f in obj.data.polygons:
            if f.center.z > 0:
                f.material_index = 1
            if f.center.z <= 0:
                f.material_index = 0
        bpy.context.object.rotation_euler[1] = np.arccos(self.delta[2]/self.dist)
        bpy.context.object.rotation_euler[2] = np.arctan2(self.delta[1], self.delta[0])
        bpy.data.objects[self.name].select_set(True)
        bpy.ops.object.shade_smooth()
