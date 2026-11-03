import numpy as np
import bpy

mpl_colors = {'C0': [31,119,180],
              'C1': [255,127,14],
              'C2': [44,160,44],
              'C3': [214,39,40],
              }

def transparent_color(objname, color):
    mat = bpy.data.materials.new('mat-' + objname)
    mat.use_nodes = True
    mat.blend_method = 'BLEND'
    mat.diffuse_color = list((np.array(color)/255)**(2.2)) + [1]
    nodes = mat.node_tree.nodes
    nodes.clear()
    links = mat.node_tree.links
    material_output = nodes.new('ShaderNodeOutputMaterial')
    mix = nodes.new('ShaderNodeMixShader')
    links.new(mix.outputs['Shader'], material_output.inputs['Surface'])
    layerweight = nodes.new('ShaderNodeLayerWeight')
    layerweight.inputs['Blend'].default_value = 0.9
    power = nodes.new('ShaderNodeMath')
    power.operation = 'POWER'
    power.inputs[1].default_value = 1.0
    links.new(layerweight.outputs['Facing'], power.inputs[0])
    links.new(power.outputs['Value'], mix.inputs['Fac'])
    transparent = nodes.new('ShaderNodeBsdfTransparent')
    links.new(transparent.outputs['BSDF'], mix.inputs[1])
    emission = nodes.new('ShaderNodeEmission')
    emission.inputs[0].default_value = list((np.array(color)/255)**(2.2)) + [1]
    emission.inputs[1].default_value = 1.0
    links.new(emission.outputs['Emission'], mix.inputs[2])
    bpy.data.objects[objname].active_material = mat

def glossy_color(objname, color, ior):
    mat = bpy.data.materials.new('mat-' + objname)
    mat.use_nodes = True
    mat.blend_method = 'BLEND'
    mat.diffuse_color = list((np.array(color)/255)**(2.2)) + [1]
    nodes = mat.node_tree.nodes
    nodes.clear() # remove defaults
    links = mat.node_tree.links
    material_output = nodes.new('ShaderNodeOutputMaterial')
    mix = nodes.new('ShaderNodeMixShader')
    links.new(mix.outputs['Shader'], material_output.inputs['Surface'])
    glossy = nodes.new('ShaderNodeBsdfGlossy')
    glossy.inputs[1].default_value = 0.1
    links.new(glossy.outputs['BSDF'], mix.inputs[2])
    emission = nodes.new('ShaderNodeEmission')
    emission.inputs[0].default_value = list((np.array(color)/255)**(2.2)) + [1]
    emission.inputs[1].default_value = 1.0
    links.new(emission.outputs['Emission'], mix.inputs[1])
    fresnel = nodes.new('ShaderNodeFresnel')
    fresnel.inputs[0].default_value = ior
    links.new(fresnel.outputs['Fac'], mix.inputs['Fac'])
    bpy.data.objects[objname].active_material = mat

def rgbcolor(objname, color):
    mat = bpy.data.materials.new('mat-' + objname)
    mat.use_nodes = True
    mat.blend_method = 'BLEND'
    mat.diffuse_color = list((np.array(color)/255)**(2.2)) + [1]
    nodes = mat.node_tree.nodes
    nodes.clear()
    links = mat.node_tree.links
    material_output = nodes.new('ShaderNodeOutputMaterial')
    rgb = nodes.new('ShaderNodeRGB')
    rgb.outputs[0].default_value = list((np.array(color)/255)**(2.2)) + [1]
    links.new(rgb.outputs['Color'], material_output.inputs['Surface'])
    bpy.data.objects[objname].active_material = mat
