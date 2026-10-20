import bpy
import numpy as np

class Line:
    def __init__(self, line):
        self.line = line

    def get_grease_pencil(self,gpencil_obj_name='GPencil') -> bpy.types.GreasePencil:
        """
        Return the grease-pencil object with the given name. Initialize one if not already present.
        :param gpencil_obj_name: name/key of the grease pencil object in the scene
        """

        # If not present already, create grease pencil object
        if gpencil_obj_name not in bpy.context.scene.objects:
            bpy.ops.object.gpencil_add(align='WORLD', location=(0, 0, 0), type='EMPTY')
            # rename grease pencil
            bpy.context.scene.objects[-1].name = gpencil_obj_name
    
        # Get grease pencil object
        gpencil = bpy.context.scene.objects[gpencil_obj_name]

        return gpencil

    def get_grease_pencil_layer(self,gpencil: bpy.types.GreasePencil, gpencil_layer_name='GP_Layer',
                                clear_layer=False) -> bpy.types.GPencilLayer:
        """
        Return the grease-pencil layer with the given name. Create one if not already present.
        :param gpencil: grease-pencil object for the layer data
        :param gpencil_layer_name: name/key of the grease pencil layer
        :param clear_layer: whether to clear all previous layer data
        """
    
        # Get grease pencil layer or create one if none exists
        if gpencil.data.layers and gpencil_layer_name in gpencil.data.layers:
            gpencil_layer = gpencil.data.layers[gpencil_layer_name]
        else:
            gpencil_layer = gpencil.data.layers.new(gpencil_layer_name, set_active=True)

        if clear_layer:
            gpencil_layer.clear()  # clear all previous layer data
    
        # bpy.ops.gpencil.paintmode_toggle()  # need to trigger otherwise there is no frame
    
        return gpencil_layer

    # Util for default behavior merging previous two methods
    def init_grease_pencil(self,gpencil_obj_name='GPencil', gpencil_layer_name='GP_Layer',
                           clear_layer=True) -> bpy.types.GPencilLayer:
        gpencil = self.get_grease_pencil(gpencil_obj_name)
        gpencil_layer = self.get_grease_pencil_layer(gpencil, gpencil_layer_name, clear_layer=clear_layer)
        return gpencil_layer

    def draw(self, w, color=(0,0,0), name="line"):
        gp_layer = self.init_grease_pencil()
        gp_frame = gp_layer.frames.new(0)
        gp_stroke = gp_frame.strokes.new()
        gp_stroke.display_mode = '3DSPACE'
        #gp_stroke.draw_cyclic = True
        gp_stroke.points.add(count=len(self.line))
        gp_stroke.line_width = w
        #
        for n in range(len(self.line)):
            gp_stroke.points[n].co = self.line[n]
        objgp = bpy.data.objects["GPencil"]
        objgp.name = name

        matgp = bpy.data.materials.new(name="mat-"+name)
        bpy.data.materials.create_gpencil_data(matgp)
        matgp.grease_pencil.color = list((np.array(color)/255)) + [1]
        objgp.data.materials.append(matgp)
