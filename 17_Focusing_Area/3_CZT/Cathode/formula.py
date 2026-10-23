import bpy
import subprocess
import sys
import os

class Formula:
    def __init__(self, loc=(0,0,0), scale=1, mat=[0,0,0,1], center=False,  join=True):
        self.loc = loc
        self.s = scale*100
        self.mat = mat
        self.center = center
        self.join = join
    def draw(self, filename, name):
        svg_file = '%s.svg' % filename
        start_objs = bpy.data.objects[:]
        bpy.ops.import_curve.svg(filepath=svg_file)
        new_curves = [o for o in bpy.data.objects if o not in start_objs]
        for obj in new_curves:
            obj.scale = (self.s,self.s,self.s)
            obj.select_set(True)
            bpy.context.view_layer.objects.active = obj
        if self.join:

            bpy.ops.object.join()
            if self.center:
                bpy.ops.object.origin_set(type='ORIGIN_CENTER_OF_MASS', center='MEDIAN')
            bpy.context.view_layer.objects.active.name = name
            bpy.context.view_layer.objects.active.location = self.loc
            mat = bpy.data.materials.new(name)
            mat.diffuse_color = self.mat 
            mat.specular_intensity = 0 
            bpy.data.objects[name].active_material = mat 
            obj.select_set(False)
        
    def generate(self, equation, name="formula", save=False):
        self.name = name
        with open("%s.tex" % name, "w") as tex_file:
            tex_file.write(r"""
            \documentclass{standalone}
            \usepackage{lmodern} %or whatever you like 
            \usepackage[intlimits]{amsmath}
            \usepackage{amsthm, amssymb, amsfonts} %Useful stuff
            \begin{document}
            $""" + ''.join(equation) + """$
            \end{document}
            """)

        subprocess.call(["pdflatex", "%s.tex" % name])
        subprocess.call(["pdftocairo", "-svg", "%s.pdf" % name, "%s.svg" % name])    
        
        self.draw(name, name=name)

        for ext in ['.pdf','.tex','.log','.aux']:
             os.remove("%s" % name + ext)

        if not save:
            os.remove("%s.svg" % name)

    def show(self, start, end=None):
        obj =  bpy.data.objects[self.name]
        obj.hide_render = True
        obj.keyframe_insert('hide_render', frame=1)
        obj.hide_viewport = True
        obj.keyframe_insert('hide_viewport', frame=1)
        obj.hide_render = False
        obj.keyframe_insert('hide_render', frame=start)
        obj.hide_viewport = False
        obj.keyframe_insert('hide_viewport', frame=start)
        if end is not None:
            obj.hide_render = True
            obj.keyframe_insert('hide_render', frame=end)
            obj.hide_viewport = True
            obj.keyframe_insert('hide_viewport', frame=end)
        
