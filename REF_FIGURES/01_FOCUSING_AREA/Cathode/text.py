import numpy as np
import bpy

class Text:
    def __init__(self,
                 text,
                 loc=(0,0,0),
                 size=1.,
                 font='Helvetica',
                 color=(255,0,0),
                 name="text"):
                     
        bpy.ops.object.text_add(radius=size)
        txt = bpy.data.objects['Text']
        txt.name = name
        txt.data.body = text
        if font == 'Helvetica':
            fontfile = 'C:\\Users\\45276\\Downloads\\Helvetica_Font_Family_(Fontmirror)\\Helvetica 400.ttf'
        if font == 'Helvetica-bold':
            fontfile = 'C:\\Users\\45276\\Downloads\\Helvetica-Bold-Font\\helvetica-bold.ttf'
        if font == 'Monospace':
            fontfile = 'C:\\Users\\45276\\Downloads\\monospaced-ubuntu\\UbuntuMono-R.ttf'
        fnt = bpy.data.fonts.load(fontfile)
        txt.data.font = fnt
        bpy.ops.object.origin_set(type='ORIGIN_CENTER_OF_MASS', center='MEDIAN')
        txt.location = loc
        mat = bpy.data.materials.new("Text")
        mat.diffuse_color = list((np.array(color)/255)**(2.2)) + [1]
        mat.specular_intensity = 0
        txt.active_material = mat
