import bpy
import os

def setup(cam_loc=None, lamp_loc=None, lamp_energy=5):
    #scene
    bpy.context.scene.render.film_transparent = True
    bpy.context.scene.view_settings.view_transform = 'Standard'
    # remove default cube
    if 'Cube' in bpy.data.objects:
        bpy.data.objects['Cube'].select_set(True)
        bpy.ops.object.delete()
    #camera
    if cam_loc is not None:
        camera = bpy.data.objects["Camera"]
        camera.location = cam_loc
        camera.rotation_euler = (0,0,0)
    #lamp
    if lamp_loc is not None:
        lamp = bpy.data.objects["Light"]
        lamp.location = lamp_loc
        lamp.rotation_euler = (0,0,0)
        lamp.data.type = 'SUN'
        lamp.data.energy = lamp_energy
        lamp.data.use_shadow = False

def setup_hdri():
    setup()
    # Remove light
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
    node_environment.image = bpy.data.images.load("/home/smanti/Codes/blender-3.0.1-linux-x64/3.0/datafiles/studiolights/world/forest.exr")
    node_environment.location = -300,0
    # Add Output node
    node_output = tree_nodes.new(type='ShaderNodeOutputWorld')   
    node_output.location = 200,0
    # Link all nodes
    links = node_tree.links
    link = links.new(node_environment.outputs["Color"], node_background.inputs["Color"])
    link = links.new(node_background.outputs["Background"], node_output.inputs["Surface"])
