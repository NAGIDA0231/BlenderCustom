"""
BlenderCustom: Unity ユーザー向けの操作カスタマイズをまとめたアドオン。

機能ごとにモジュールを分けている。新しい機能を追加するときは、モジュールを作って
MODULES に足す（各モジュールは register() / unregister() を持つ）。
"""

bl_info = {
    "name": "BlenderCustom",
    "author": "kakizaki",
    "version": (1, 1, 0),
    "blender": (4, 2, 0),
    "location": "3D View / ウィンドウ > BlenderCustom パネルを開く",
    "description": "操作・表示のカスタマイズ一式（キー割り当て、範囲選択、パネル、テーマなど）",
    "category": "3D View",
}

if "bpy" in locals():
    # アドオンの再読み込み時は、依存される側から順に読み込み直す
    import importlib

    for _name in (
        "preferences", "listener", "floating_panel", "delta_transform", "theme", "enclosed_select",
        "hover_highlight", "select_mode_icons", "mesh_delete", "mesh_clipboard", "select_all_toggle",
        "edit_panel", "quick_panel", "panel_window", "keymaps",
    ):
        if _name in locals():
            importlib.reload(locals()[_name])

import bpy  # noqa: E402

from . import (  # noqa: E402
    preferences,
    listener,
    floating_panel,
    delta_transform,
    theme,
    enclosed_select,
    hover_highlight,
    select_mode_icons,
    mesh_delete,
    mesh_clipboard,
    select_all_toggle,
    edit_panel,
    quick_panel,
    panel_window,
    keymaps,
)

# 登録順。keymaps は各オペレーターの登録後に行う。
# panel_window はパネル用ウィンドウのマウス操作を先に受け取るため、hover_highlight より前に置く
MODULES = (
    preferences,
    theme,
    enclosed_select,
    panel_window,
    hover_highlight,
    select_mode_icons,
    mesh_delete,
    mesh_clipboard,
    select_all_toggle,
    edit_panel,
    quick_panel,
    listener,
    keymaps,
)


def register():
    for module in MODULES:
        module.register()


def unregister():
    for module in reversed(MODULES):
        module.unregister()
