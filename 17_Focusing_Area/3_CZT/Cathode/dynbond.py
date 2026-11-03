import bpy
import bmesh

class Dynbond:
    def __init__(self, atom_i, atom_j, name, radius):
        self.name_i = atom_i.symbol + '-' + str(atom_i.index)
        self.name_j = atom_j.symbol + '-' + str(atom_j.index)
        self.name = name
        # Reference two atoms objects
        c1 = bpy.data.objects[self.name_i]
        c2 = bpy.data.objects[self.name_j]
        # Create new connector mesh and mesh object and link to scene
        m = bpy.data.meshes.new('connector')
        bm = bmesh.new()
        v1 = bm.verts.new(c1.location)
        v2 = bm.verts.new(c2.location)
        e  = bm.edges.new([v1,v2])

        bm.to_mesh(m)

        o = bpy.data.objects.new(self.name, m )
        bpy.context.scene.collection.objects.link(o)

        # Hook connector vertices to respective atoms
        for i, cyl in enumerate([ c1, c2 ]):
            bpy.ops.object.select_all( action = 'DESELECT' )
            cyl.select_set(True)
            o.select_set(True)
            bpy.context.view_layer.objects.active = o # Set connector as active

            # Select vertex
            bpy.ops.object.mode_set(mode='OBJECT')
            o.data.vertices[i].select = True    
            bpy.ops.object.mode_set(mode='EDIT')

            bpy.ops.object.hook_add_selob() # Hook to cylinder 
            bpy.ops.object.mode_set(mode='OBJECT')
            o.data.vertices[i].select = False 

        m = o.modifiers.new('Skin', 'SKIN')

        ## New bit starts here
        m.use_smooth_shade = True

        m = o.modifiers.new('Subsurf', 'SUBSURF' )
        m.levels = 2
        m.render_levels = 2
        obj = bpy.data.objects[self.name]
        for v in obj.data.skin_vertices[0].data:
            v.radius = radius, radius

        ## End of new bit
        bpy.ops.object.select_all( action = 'DESELECT' )
