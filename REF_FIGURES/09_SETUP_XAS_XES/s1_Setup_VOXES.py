import bpy

from math import pi

from pathlib import Path

import os

import blender_utils as utils

deg2rad = pi / 180


def main():
    
    utils.setup_scene()
    utils.setup_camera(
        location=(-50,500,50),
        ortho_scale=1000,
        rotation_euler=(90*deg2rad,0,180*deg2rad),
    )

    bpy.ops.import_scene.gltf(
        filepath="/home/smanti/Bandi/fis3/FIGURES/07_SETUP_XAS_XES/Source.gltf", 
        files=[{"name":"Source.gltf", "name":"Source.gltf"}], 
        loglevel=50
     )

    bpy.context.scene.unit_settings.length_unit = 'MILLIMETERS'

def load_group(material_name):

    filepaths = Path(f"Crystal/{material_name}/").glob(f"*.STL")    

    material = bpy.data.materials[material_name]
    
    for filepath in filepaths:
        print(filepath)
        load_stl(str(filepath))
        obj = bpy.data.objects[str(filepath.parts[-1].replace(' ',' '))[:-4]]
        obj.active_material = material
 
def setup_material(material_name, rgb_value):       

    # Create a new material
    mat = bpy.data.materials.new(material_name)  
    mat.use_nodes = True

    # Set the Material node as active
    node_tree = mat.node_tree
    nodes = node_tree.nodes
    nodes.active = nodes.get("Principled BSDF")

    # Set the material properties
    nodes.active.inputs["Base Color"].default_value = rgb_value
    nodes.active.inputs["Metallic"].default_value = 0.3
    nodes.active.inputs["Specular"].default_value = 0.5
    nodes.active.inputs["Roughness"].default_value = 0.2
    
        
if __name__ == '__main__':
    main()
