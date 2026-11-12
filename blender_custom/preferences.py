"""アドオンの設定（パネル位置・テーマ変更前の値の保存先）。"""

import bpy


class BlenderCustomPreferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    show_in_viewport: bpy.props.BoolProperty(
        name="3D ビュー内にもパネルを表示",
        description="Edit Panel と QuickPanel を 3D ビューの上にも浮かべて表示する",
        default=False,
    )
    drag_speed: bpy.props.FloatProperty(
        name="パネルウィンドウのドラッグ速度",
        description="パネル用ウィンドウの Edit Panel で、マウスを動かした量に対する変形量の倍率",
        default=1.0, min=0.05, max=10.0,
    )
    edit_panel_x: bpy.props.IntProperty(name="Edit Panel 左からの位置", default=60)
    edit_panel_y: bpy.props.IntProperty(name="Edit Panel 上からの位置", default=110)
    quick_panel_x: bpy.props.IntProperty(name="QuickPanel 左からの位置", default=60)
    quick_panel_y: bpy.props.IntProperty(name="QuickPanel 上からの位置", default=275)

    # テーマ・プリファレンスを変更する前の値（JSON）。アドオンを無効にしたときに戻すため
    saved_defaults: bpy.props.StringProperty(default="")

    def draw(self, context):
        layout = self.layout
        layout.operator("blendercustom.open_panel_window", icon='WINDOW')
        layout.prop(self, "drag_speed")
        layout.prop(self, "show_in_viewport")
        col = layout.column(heading="3D ビュー内のパネルの位置")
        col.active = self.show_in_viewport
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
