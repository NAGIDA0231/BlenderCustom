"""
3D ビューの表示の初期値（裏面の非表示・縦の軸の線）。
Blender の起動時とファイルを開いたとき（新規ファイルを含む）に設定する。

これらは .blend ファイルごとの設定なので、プリファレンスでは固定できない。
その後に手で切り替えた場合は、次にファイルを開くまでそのまま。
"""

import bpy
from bpy.app.handlers import persistent


def apply_to_space(space):
    # 面の裏側を表示しない（Unity と同じく表側から見たときだけ面を描く）
    space.shading.show_backface_culling = True
    # 縦の軸の線（Blender の Z 軸。Unity の呼び方では Y 軸で、テーマで緑にしている）を表示する
    space.overlay.show_axis_z = True


def apply_to_all_views():
    for screen in bpy.data.screens:
        for area in screen.areas:
            for space in area.spaces:
                if space.type == 'VIEW_3D':
                    apply_to_space(space)


@persistent
def on_load_post(*args):
    apply_to_all_views()


def apply_later():
    # 有効化の直後は bpy.data にアクセスできないことがあるため、タイマーで設定する
    apply_to_all_views()
    return None


def register():
    bpy.app.handlers.load_post.append(on_load_post)
    bpy.app.timers.register(apply_later, first_interval=0.1)


def unregister():
    if bpy.app.timers.is_registered(apply_later):
        bpy.app.timers.unregister(apply_later)
    if on_load_post in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(on_load_post)
