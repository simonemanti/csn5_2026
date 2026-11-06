"""PRISM sidebar. Embedded as an auto-run Text in v1_Setup_PRISM.blend.

If Blender blocks embedded scripts, open this text in the Text Editor and
choose Run Script (Alt-P). No network access or preference changes are used.
The keyframes and simple-expression drivers work independently of this panel.
"""
import math
import bpy

bl_info = {
    "name": "PRISM four-channel setup",
    "author": "PRISM",
    "version": (1, 0, 0),
    "blender": (4, 2, 0),
    "location": "3D View > N > PRISM",
    "category": "3D View",
}


def controls():
    return bpy.data.objects.get("PRISM_Controls")


def refresh():
    ctrl = controls()
    if ctrl:
        ctrl.update_tag()
    bpy.context.view_layer.update()
    for screen in bpy.data.screens:
        for area in screen.areas:
            area.tag_redraw()


def stop_playback(context):
    if context.screen and context.screen.is_animation_playing:
        bpy.ops.screen.animation_cancel(restore_frame=False)


class PRISM_OT_mode(bpy.types.Operator):
    bl_idname = "prism.set_mode"
    bl_label = "Set measurement mode"
    bl_options = {"REGISTER", "UNDO"}
    mode: bpy.props.EnumProperty(items=[("FLUORESCENCE", "Fluorescence", ""),
                                        ("INCIDENT", "Incident beam", "")])

    def execute(self, context):
        stop_playback(context)
        ctrl = controls()
        ctrl["animate"] = False
        ctrl["transition"] = 0.0 if self.mode == "FLUORESCENCE" else 1.0
        refresh()
        return {"FINISHED"}


class PRISM_OT_play(bpy.types.Operator):
    bl_idname = "prism.play_switch"
    bl_label = "Play switching sequence"

    def execute(self, context):
        stop_playback(context)
        controls()["animate"] = True
        context.scene.frame_set(1)
        refresh()
        bpy.ops.screen.animation_play()
        return {"FINISHED"}


class PRISM_OT_pause(bpy.types.Operator):
    bl_idname = "prism.pause_switch"
    bl_label = "Freeze current position"

    def execute(self, context):
        ctrl = controls()
        value = float(ctrl["cycle"] if ctrl["animate"] else ctrl["transition"])
        stop_playback(context)
        ctrl["animate"] = False
        ctrl["transition"] = value
        refresh()
        return {"FINISHED"}


class PRISM_OT_view(bpy.types.Operator):
    bl_idname = "prism.view"
    bl_label = "Choose setup view"
    view: bpy.props.EnumProperty(items=[("DETAIL", "Detail", ""),
                                       ("OVERVIEW", "Full setup", ""),
                                       ("TOP", "Top", "")])

    def execute(self, context):
        camera = bpy.data.objects.get("Camera_" + self.view)
        if camera is None:
            return {"CANCELLED"}
        context.scene.camera = camera
        if context.area and context.area.type == "VIEW_3D":
            context.space_data.region_3d.view_perspective = "CAMERA"
        refresh()
        return {"FINISHED"}


class PRISM_PT_setup(bpy.types.Panel):
    bl_label = "PRISM | 4 CZT channels"
    bl_idname = "PRISM_PT_setup"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "PRISM"

    @classmethod
    def poll(cls, context):
        return controls() is not None

    def draw(self, context):
        layout = self.layout
        ctrl = controls()
        t = float(ctrl["cycle"] if ctrl["animate"] else ctrl["transition"])
        col = layout.column(align=True)
        col.label(text="Measurement mode")
        row = col.row(align=True)
        row.operator("prism.set_mode", text="Fluorescence").mode = "FLUORESCENCE"
        row.operator("prism.set_mode", text="Incident I0").mode = "INCIDENT"
        row = col.row()
        row.enabled = not ctrl["animate"]
        row.prop(ctrl, '["transition"]', text="Switch", slider=True)
        if t < 0.0001:
            col.label(text="If: sample in / all four channels", icon="CHECKMARK")
        elif t > 0.9999:
            col.label(text="I0: sample out / D1 on axis", icon="CHECKMARK")
        else:
            col.label(text="Motion: beam shutter closed", icon="INFO")

        box = layout.box()
        box.label(text="Physical dimensions | 1 BU = 1 mm")
        box.prop(ctrl, '["radius_mm"]', text="Face distance [mm]")
        box.prop(ctrl, '["lift_mm"]', text="Sample lift [mm]")
        box.label(text="4 crystals: 10 x 10 x 5 mm each")
        box.label(text="Quasi-hemispherical electrodes")
        box.label(text="1 central + 3 at 30 deg")
        radius = float(ctrl["radius_mm"])
        omega = 16.0 * math.atan(25.0 / (radius * math.sqrt(radius**2 + 50.0)))
        box.label(text=f"Nominal area: 400 mm2 / Omega: {omega:.3f} sr")
        box.label(text=f"Geometric acceptance: {100*omega/(4*math.pi):.2f}% of 4pi")

        box = layout.box()
        box.label(text="Animation | lift, then rotate")
        box.prop(ctrl, '["animate"]', text="Drive from timeline")
        row = box.row(align=True)
        row.operator("prism.play_switch", text="Play", icon="PLAY")
        row.operator("prism.pause_switch", text="Freeze", icon="PAUSE")
        box.label(text="252 frames / 24 fps / reversible cycle")
        angle = math.degrees(bpy.data.objects["CZT_orbital_rotation"].rotation_euler.z)
        height = bpy.data.objects["Sample_vertical_translation"].location.z
        box.label(text=f"Head: {angle:.1f} deg / Sample z: {height:.1f} mm")

        box = layout.box()
        box.label(text="Views and guides")
        row = box.row(align=True)
        row.operator("prism.view", text="Detail").view = "DETAIL"
        row.operator("prism.view", text="Full").view = "OVERVIEW"
        row.operator("prism.view", text="Top").view = "TOP"
        box.prop(ctrl, '["show_rays"]', text="Show ray guides")
        box.prop(ctrl, '["show_dimensions"]', text="Show dimensions")

        box = layout.box()
        box.label(text="Concept geometry, not supplier CAD", icon="INFO")
        box.label(text="Packages and mounts: assumed sizes")
        box.label(text="22 keV performance and price: to verify")
        box.label(text="I0 sequential; no simultaneous monitor")


CLASSES = (PRISM_OT_mode, PRISM_OT_play, PRISM_OT_pause, PRISM_OT_view, PRISM_PT_setup)


def unregister():
    for cls in reversed(CLASSES):
        old = getattr(bpy.types, cls.__name__, None)
        if old:
            bpy.utils.unregister_class(old)


def register():
    unregister()
    for cls in CLASSES:
        bpy.utils.register_class(cls)


if __name__ == "__main__" or __name__.startswith("PRISM"):
    register()
