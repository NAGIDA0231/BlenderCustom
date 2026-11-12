"""
ナイフツールの操作中に、右ドラッグで視点を回転する。

ナイフの操作中は Blender がドラッグを判定しないため、標準の「右ドラッグで回転」が働かない。
右ボタンを押した瞬間（ナイフのキー設定で視点操作に渡している。keymaps.py）に、ここで回転を始める。
  - マウスを動かしてから離した: 回転だけ（離したことはナイフに渡さない）
  - 動かさずに離した（右クリック）: 離したことをナイフに渡し、ナイフの「次の切れ目」にする
"""

import bpy
from mathutils import Quaternion, Vector

from . import listener

DRAG_THRESHOLD = 3
KNIFE_IDNAME = "MESH_OT_knife_tool"


def is_knife_running(window):
    return any(op is not None and op.bl_idname == KNIFE_IDNAME for op in getattr(window, "modal_operators", ()))


def view_under_mouse(window, mouse_x, mouse_y):
    for area in window.screen.areas:
        if area.type != 'VIEW_3D':
            continue
        for region in area.regions:
            if region.type != 'WINDOW':
                continue
            if region.x <= mouse_x < region.x + region.width and region.y <= mouse_y < region.y + region.height:
                return area, region
    return None


class BLENDERCUSTOM_OT_knife_orbit(bpy.types.Operator):
    """ナイフの操作中に右ドラッグで視点を回転する（内部用）"""
    bl_idname = "blendercustom.knife_orbit"
    bl_label = "Knife Orbit"
    bl_options = {'INTERNAL'}

    def invoke(self, context, event):
        self.rv3d = context.region_data
        self.area = context.area
        if self.rv3d is None:
            return {'CANCELLED'}
        self.start = (event.mouse_x, event.mouse_y)
        self.last = self.start
        self.dragged = False
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def rotate(self, dx, dy):
        """Blender 標準のターンテーブル回転と同じ向き・感度で回す"""
        sensitivity = bpy.context.preferences.inputs.view_rotate_sensitivity_turntable
        rotation = self.rv3d.view_rotation
        rotation = Quaternion(Vector((0.0, 0.0, 1.0)), -dx * sensitivity) @ rotation
        right = rotation @ Vector((1.0, 0.0, 0.0))
        rotation = Quaternion(right, dy * sensitivity) @ rotation
        rotation.normalize()
        self.rv3d.view_rotation = rotation
        self.area.tag_redraw()

    def modal(self, context, event):
        if event.type in {'MOUSEMOVE', 'INBETWEEN_MOUSEMOVE'}:
            x, y = event.mouse_x, event.mouse_y
            if not self.dragged:
                if abs(x - self.start[0]) + abs(y - self.start[1]) < DRAG_THRESHOLD:
                    return {'RUNNING_MODAL'}
                self.dragged = True
            self.rotate(x - self.last[0], y - self.last[1])
            self.last = (x, y)
            return {'RUNNING_MODAL'}
        if event.type == 'RIGHTMOUSE' and event.value == 'RELEASE':
            if self.dragged:
                return {'FINISHED'}
            # 動かさずに離した（右クリック）ので、ナイフの「次の切れ目」に使わせる
            return {'FINISHED', 'PASS_THROUGH'}
        if event.type == 'ESC':
            return {'FINISHED', 'PASS_THROUGH'}
        return {'RUNNING_MODAL'}


def handle_event(context, event):
    """ナイフの操作中に右ボタンが押されたら、視点の回転を始める"""
    if event.type != 'RIGHTMOUSE' or event.value != 'PRESS':
        return None
    window = context.window
    if not is_knife_running(window):
        return None
    view = view_under_mouse(window, event.mouse_x, event.mouse_y)
    if view is None:
        return None
    area, region = view
    with context.temp_override(window=window, area=area, region=region):
        bpy.ops.blendercustom.knife_orbit('INVOKE_DEFAULT')
    return {'RUNNING_MODAL'}


def register():
    bpy.utils.register_class(BLENDERCUSTOM_OT_knife_orbit)
    listener.add_handler(handle_event)


def unregister():
    listener.remove_handler(handle_event)
    bpy.utils.unregister_class(BLENDERCUSTOM_OT_knife_orbit)
