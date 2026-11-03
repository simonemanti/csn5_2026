import bpy

from math import pi


def setup_camera(location=(0,0,0), rotation_euler=(0,0,0), ortho_scale=500):

    camera = bpy.data.objects['Camera']
    camera.rotation_euler = rotation_euler
    camera.location = location
    camera.data.type = 'ORTHO'
    camera.data.ortho_scale = ortho_scale
    camera.data.clip_start = 1e-3
    camera.data.clip_end = 1e3


def setup_scene():

    bpy.context.scene.render.film_transparent = True
    bpy.context.scene.view_settings.view_transform = 'Standard'

    # Set the scale to mm
    bpy.context.scene.unit_settings.scale_length = 1e-3
    # Increase maximum distance
    for a in bpy.context.screen.areas:
        if a.type == 'VIEW_3D':
            for s in a.spaces:
                if s.type == 'VIEW_3D':
                    s.clip_start = 10
                    s.clip_end = 1e5

    bpy.data.objects['Cube'].select_set(True)
    bpy.ops.object.delete()

    bpy.data.objects['Light'].select_set(True)
    bpy.ops.object.delete()
    # Get the environment node tree of the current scene
    node_tree = bpy.context.scene.world.node_tree
    tree_nodes = node_tree.nodes
    # Clear all nodes
    tree_nodes.clear()
    # Add Background node
    node_background = tree_nodes.new(type='ShaderNodeBackground')
    # Add Environment Texture node
    node_environment = tree_nodes.new('ShaderNodeTexEnvironment')
    # Load and assign the image to the node property
    node_environment.image = bpy.data.images.load("/home/smanti/Codes/blender-3.0.1-linux-x64/3.0/datafiles/studiolights/world/city.exr")
    node_environment.location = -300,0
    # Add Output node
    node_output = tree_nodes.new(type='ShaderNodeOutputWorld')   
    node_output.location = 200,0
    texture_coordinate = tree_nodes.new('ShaderNodeTexCoord')
    texture_coordinate.location = -700,0
    mapping = tree_nodes.new('ShaderNodeMapping')
    mapping.location = -500,0
    # Link all nodes
    links = node_tree.links
    link = links.new(node_environment.outputs["Color"], node_background.inputs["Color"])
    link = links.new(node_background.outputs["Background"], node_output.inputs["Surface"])
    links.new(texture_coordinate.outputs['Generated'], mapping.inputs['Vector'])
    links.new(mapping.outputs['Vector'], node_environment.inputs['Vector'])
    # Set Z rotation to 90 degrees (value in radians)
    #mapping.rotation.z = pi
    mapping.inputs[2].default_value[2] = pi


    bpy.context.scene.render.resolution_x = 1000
    bpy.context.scene.render.resolution_y = 1000
