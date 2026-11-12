"""アドオンの設定（パネル位置・テーマ変更前の値の保存先）。"""

import bpy


class BlenderCustomPreferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    edit_panel_x: bpy.props.IntProperty(name="Edit Panel 左からの位置", default=60)
    edit_panel_y: bpy.props.IntProperty(name="Edit Panel 上からの位置", default=110)
    quick_panel_x: bpy.props.IntProperty(name="QuickPanel 左からの位置", default=60)
    quick_panel_y: bpy.props.IntProperty(name="QuickPanel 上からの位置", default=275)

    # テーマ・プリファレンスを変更する前の値（JSON）。アドオンを無効にしたときに戻すため
    saved_defaults: bpy.props.StringProperty(default="")

    def draw(self, context):
        layout = self.layout
        col = layout.column(heading="パネルの位置")
        row = col.row()
        row.prop(self, "edit_panel_x")
        row.prop(self, "edit_panel_y")
        row = col.row()
        row.prop(self, "quick_panel_x")
        row.prop(self, "quick_panel_y")


def get_prefs():
    return bpy.context.preferences.addons[__package__].preferences


def register():
    bpy.utils.register_class(BlenderCustomPreferences)


def unregister():
    bpy.utils.unregister_class(BlenderCustomPreferences)
