"""
ウィンドウ全体のマウス操作を受け取る共通のモーダルオペレーター。

各機能は add_handler() で関数を登録する。関数は (context, event) を受け取り、
イベントを消費するなら {'RUNNING_MODAL'}、しないなら None を返す。
"""

import bpy
from bpy.app.handlers import persistent

HANDLERS = []


class ListenerState:
    enabled = False
    running_windows = set()


STATE = ListenerState()


def add_handler(handler):
    if handler not in HANDLERS:
        HANDLERS.append(handler)


def remove_handler(handler):
    if handler in HANDLERS:
        HANDLERS.remove(handler)


class BLENDERCUSTOM_OT_listener(bpy.types.Operator):
    """BlenderCustom のマウス操作を受け付ける（内部用）"""
    bl_idname = "blendercustom.listener"
    bl_label = "BlenderCustom Listener"
    bl_options = {'INTERNAL'}

    def invoke(self, context, event):
        self.window_key = context.window.as_pointer()
        STATE.running_windows.add(self.window_key)
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        if STATE.enabled is False:
            STATE.running_windows.discard(self.window_key)
            return {'CANCELLED'}
        for handler in HANDLERS:
            try:
                result = handler(context, event)
            except Exception as error:
                print("BlenderCustom listener error:", repr(error))
                result = None
            if result is not None:
                return result
        return {'PASS_THROUGH'}


def start_listeners():
    if STATE.enabled is False:
        return None
    wm = bpy.context.window_manager
    if wm is None:
        return 0.5
    for window in wm.windows:
        if window.as_pointer() in STATE.running_windows:
            continue
        try:
            with bpy.context.temp_override(window=window):
                bpy.ops.blendercustom.listener('INVOKE_DEFAULT')
        except RuntimeError:
            return 0.5
    return 1.0


@persistent
def on_load_post(*args):
    STATE.running_windows.clear()


def register():
    STATE.enabled = True
    STATE.running_windows.clear()
    bpy.utils.register_class(BLENDERCUSTOM_OT_listener)
    bpy.app.handlers.load_post.append(on_load_post)
    bpy.app.timers.register(start_listeners, first_interval=0.1, persistent=True)


def unregister():
    STATE.enabled = False
    if bpy.app.timers.is_registered(start_listeners):
        bpy.app.timers.unregister(start_listeners)
    if on_load_post in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(on_load_post)
    bpy.utils.unregister_class(BLENDERCUSTOM_OT_listener)
