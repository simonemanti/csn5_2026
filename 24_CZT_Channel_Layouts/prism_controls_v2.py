"""PRISM sidebar. Embedded as an auto-run Text in v2_Setup_PRISM.blend.

If Blender blocks embedded scripts, open this text in the Text Editor and
choose Run Script (Alt-P). No network access or preference changes are used.
The keyframes and simple-expression drivers work independently of this panel.
"""
import math
import bpy

bl_info = {
    "name": "PRISM four-channel setup",
    "author": "PRISM",
    "version": (2, 0, 0),
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
    bl_label = "PRISM v2 | simple setup"
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
        row = layout.row(align=True)
        row.operator("prism.set_mode", text="Fluorescence").mode = "FLUORESCENCE"
        row.operator("prism.set_mode", text="Incident I0").mode = "INCIDENT"
        row = layout.row()
        row.enabled = not ctrl["animate"]
        row.prop(ctrl, '["transition"]', text="Switch", slider=True)
        layout.prop(ctrl, '["lift_mm"]', text="Sample lift [mm]")
        layout.separator()
        row = layout.row(align=True)
        row.operator("prism.play_switch", text="Play", icon="PLAY")
        row.operator("prism.pause_switch", text="Freeze", icon="PAUSE")
        layout.prop(ctrl, '["animate"]', text="Drive from timeline")
        row = layout.row(align=True)
        row.operator("prism.view", text="Detail").view = "DETAIL"
        row.operator("prism.view", text="Full").view = "OVERVIEW"
        row.operator("prism.view", text="Top").view = "TOP"
        layout.prop(ctrl, '["show_rays"]', text="Ray guides")
        layout.separator()
        layout.label(text="Cubic case / 2 x 2 CZT channels")
        layout.label(text="Case: 30 x 30 x 30 mm")
        layout.label(text="I0: sample out, D1 on beam axis")
        layout.label(text="Concept drawing / units: mm")


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
