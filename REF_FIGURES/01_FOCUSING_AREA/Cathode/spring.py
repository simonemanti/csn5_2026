import bpy
from math import sin, cos, pi, atan2
from mathutils import Vector, Euler
import numpy as np

class Spring:
    def __init__(self, atom1, atom2, name, lenght, r = 0.08, R = 0.2, nturns = 7):
        self.r = r
        self.R = R
        self.atom1 = atom1
        self.atom2 = atom2
        self.delta = atom2.position - atom1.position
        self.name = name
        self.lenght = lenght
        self.nverts = 32
        self.n_turns = nturns
        self.th = self.lenght / self.n_turns
        self.ipt = 50
    def draw(self):
        diameter = self.R * 2 
        section_angle = 2.0 * pi / self.nverts
        rad_slice = 2.0 * pi / self.ipt
        total_segments = (self.ipt * self.n_turns) + 1
        z_jump = self.lenght / total_segments
        x_rotation = atan2(self.th / 2, diameter)

        n = self.nverts        
        Verts = []
        for segment in range(total_segments):
            rad_angle = rad_slice * segment    

            for i in range(n):
                
                # create the vector
                 this_angle = section_angle * i
                 x_float = self.r * sin(this_angle) + self.R
                 z_float = self.r * cos(this_angle)
                 v1 = Vector((x_float, 0.0, z_float))
              
                 # rotate it
                 xz_euler = Euler((-x_rotation, 0.0, -rad_angle), 'XYZ')
                 v1.rotate(xz_euler)
        
                 # add extra z height per segment
                 v1 += Vector((0, 0, (segment * z_jump)))
          
                 # append it
                 Verts.append(v1)
 
        Faces = []
        # skin it, normals facing outwards
        for t in range(total_segments-1):
            for i in range(n-1):
                p0 = i + (n*t) 
                p1 = i + (n*t) + 1
                p2 = i + (n*t + n) + 1 
                p3 = i + (n*t + n)
                Faces.append([p3,p2,p1,p0])
            p0 = n*t
            p1 = n*t + n
            p2 = n*t + (2 * n) - 1
            p3 = n*t + n-1
            Faces.append([p3,p2,p1,p0])

        #create mesh and object
        mesh = bpy.data.meshes.new(self.name)
        object = bpy.data.objects.new(self.name,mesh)
  
        #set mesh location
        object.location = self.atom1.position + 0.0 * self.delta
        bpy.context.collection.objects.link(object)
        
        #create mesh from python data
        mesh.from_pydata(Verts,[],Faces)
        mesh.update(calc_edges=True)
        
        obj = bpy.data.objects[self.name]
        obj.select_set(True)
        
        obj.rotation_euler[1] = np.arccos(self.delta[2]/self.lenght)
        obj.rotation_euler[2] = np.arctan2(self.delta[1], self.delta[0])
        bpy.ops.object.shade_smooth()
