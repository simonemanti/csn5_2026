import bpy

# 1) Clean up the default scene
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)

#
# 2) Create the Parallelepiped (Crystal)
#
bpy.ops.mesh.primitive_cube_add(
    size=1.0,            # the 'base' size of the cube
    location=(0, 0.1, 0)   # place at the origin
)
crystal = bpy.context.active_object
crystal.name = "Crystal"

# Scale the cube to create a rectangular prism (parallelepiped)
# e.g. wider in X, taller in Z, thinner in Y
crystal.scale = (3.0, 0.5, 3.0)  
# Adjust these (X, Y, Z) to get the shape you want.

#
# 3) Create the Cylinder for Cutting
#

rho = 3.5  # Radius of the cylinder

bpy.ops.mesh.primitive_cylinder_add(
    vertices=128,
    radius=rho,              # Cylinder radius
    depth=4.0,               # Cylinder height
    location=(0, rho, 0)       # Position to ensure proper overlap
)
cylinder = bpy.context.active_object
cylinder.name = "CutCylinder"

# Rotate the cylinder to lay it horizontally along the X-axis
cylinder.rotation_euler[1] = 1.5708  # 90 degrees in radians

#
# 4) Boolean Difference: Subtract the cylinder from the crystal
#
# Make the crystal the active object, add a Boolean modifier
bpy.context.view_layer.objects.active = crystal
bool_mod = crystal.modifiers.new("BooleanCut", 'BOOLEAN')
bool_mod.object = cylinder
bool_mod.operation = 'DIFFERENCE'

# Apply the modifier
bpy.ops.object.modifier_apply(modifier="BooleanCut")

# Optionally, remove the cylinder object from the scene
bpy.data.objects.remove(cylinder, do_unlink=True)

#
# 5) Optional Cleanup & Smoothing
#
# Select the resulting object, smooth shade it.
#bpy.context.view_layer.objects.active = crystal
#bpy.ops.object.shade_smooth()
