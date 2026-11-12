"""
回転の刻み幅を 15° にする（変形中に Shift で刻む。Shift の割り当ては keymaps.py）。

刻み幅はシーンごとの設定なので、アドオンの有効化時とファイルを開いたときに全シーンへ設定する。
"""

import math

import bpy
from bpy.app.handlers import persistent

ROTATION_STEP_DEGREES = 15.0
BLENDER_DEFAULT_STEP_DEGREES = 5.0


def set_rotation_step(degrees):
    for scene in bpy.data.scenes:
        scene.tool_settings.snap_angle_increment_3d = math.radians(degrees)


@persistent
def on_load_post(*args):
    set_rotation_step(ROTATION_STEP_DEGREES)


def apply_later():
    # 有効化の直後は bpy.data にアクセスできないことがあるため、タイマーで設定する
    set_rotation_step(ROTATION_STEP_DEGREES)
    return None


def register():
    bpy.app.handlers.load_post.append(on_load_post)
    bpy.app.timers.register(apply_later, first_interval=0.1)


def unregister():
    if bpy.app.timers.is_registered(apply_later):
        bpy.app.timers.unregister(apply_later)
    if on_load_post in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(on_load_post)
    set_rotation_step(BLENDER_DEFAULT_STEP_DEGREES)
