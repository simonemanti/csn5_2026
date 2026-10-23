import bpy
import numpy as np
from ase.geometry.analysis import Analysis
from ase.io.cube import read_cube_data
#from skimage import measure
from bond import Bond
from dynbond import Dynbond
from spring import Spring
from atom import Atom
from color import colors
from vdw import radii
from line import Line

class System:
    """
    Class to draw an atoms object. Static bond and dynamic bond
    are available, for picture of phonons or relax animations

    Parameters:

    atoms: ASE atoms object
    scale: float define the scaling of the atoms
    """
    def __init__(self, atoms, scale=0.36):
        self.atoms = atoms
        self.traj = atoms
        self.N = len(atoms)
        self.scale = scale
        self.formula = self.atoms.get_chemical_formula(empirical=True)

    def draw(self, draw_bond = True, bonds = None, r=0.2, type="static", txt=None):
        self.btot = 0
        for n in range(self.N):
            atom = Atom()
            atom.pos = self.atoms[n].position
            atom.size = radii[self.atoms[n].symbol] * self.scale
            atom.color = colors[self.atoms[n].symbol]
            atom.name = self.atoms[n].symbol + '-%s' % n
            atom.draw()
            #atom.draw_glossy()
        if draw_bond:
            nbond = 1; 
            for bond in bonds:
                print(bond)
                self.atoms.pbc = (False,False,False)
                ana = Analysis(self.atoms)
                blist = ana.get_bonds(bond[0], bond[1], unique=True)
                btot = len(blist[0])
                for b in blist[0]:
                    print('Bond ', nbond, ' of ',btot, b)
                    atom_i = self.atoms[b[0]]
                    atom_j = self.atoms[b[1]]
                    dist = ana.get_bond_value(0,b)
                    name = 'bond-%s' % (nbond)
                    if txt is not None:
                        name = txt + 'bond-%s' % (nbond)
                    if name not in bpy.data.objects:
                        if type == "static":
                            b = Bond(atom_i, atom_j, name=name, dist=dist, r=r)
                            b.draw()
                        elif type == "dynamic":
                            b = Dynbond(atom_i, atom_j, name=name, radius=r)
                        elif type == "spring":
                            b = Spring(atom_i, atom_j, name=name, lenght=dist, r=self.r, R=self.R, nturns=self.nturns)
                            b.draw()
                        nbond += 1
            self.btot = nbond

    def draw_cell(self, width):

        cell = self.atoms.cell
        scell = [[0,0,0],cell[0],cell[0]+cell[1],cell[1],
                 [0,0,0],cell[2],cell[0]+cell[2],cell[0],
                 cell[0]+cell[2],cell[0]+cell[1]+cell[2],
                 cell[0]+cell[1],cell[0]+cell[1]+cell[2],
                 cell[1]+cell[2],cell[1],+cell[1]+cell[2],
                 cell[2]]

        f = Line(scell)
        f.draw(width)

    def set_springs(self, r=0.08, R=0.2, nturns=7):
        self.r = r
        self.R = R
        self.nturns = nturns
    
    def add_isosurface(self, wf, isolevel, color=None, name="isosurface"):
        cell = self.atoms.get_cell()

        spacing = tuple(1.0 / np.array(wf.shape))
        scaled_verts, faces, normals, values = measure.marching_cubes(wf,
                                                              level=isolevel,
                                                              spacing=spacing)
        verts = list(scaled_verts.dot(cell))
        faces = list(faces)

        mesh = bpy.data.meshes.new(name)
        object = bpy.data.objects.new(name,mesh)
        bpy.context.collection.objects.link(object)

        mesh.from_pydata(verts, [], faces)
        mesh.update(calc_edges=True)
 
        bpy.data.objects[name].select_set(True)
        bpy.ops.object.shade_smooth()
        bpy.data.objects[name].select_set(False)

        if color is not None:
            mat = bpy.data.materials.new('mat-' + name)
            mat.diffuse_color = list((np.array(color)/255)**(2.2)) + [1]
            mat.roughness = 0.1
            mat.specular_intensity = 0.3
            bpy.data.objects[name].active_material = mat


    def update(self, atoms):
        for n in range(self.N):
            name = atoms[n].symbol + '-%s' % n
            ob = bpy.data.objects[name]
            ob.location = atoms[n].position
            ob.keyframe_insert(data_path="location", index =-1)


    def center(self, center_pos = (0,0,0)):
        for n in range(len(self.atoms)):
            name = self.atoms[n].symbol + '-%s' % n
            bpy.data.objects[name].select_set(True)
        for nb in range(1,self.btot):
            name = 'bond-%s' % nb
            try: 
                bpy.data.objects[name].select_set(True)
            except:
                break
        bpy.ops.object.join()
        bpy.context.object.name = self.formula
        bpy.ops.object.origin_set(type='ORIGIN_CENTER_OF_VOLUME', center='MEDIAN')
        bpy.data.objects[self.formula].location = center_pos
