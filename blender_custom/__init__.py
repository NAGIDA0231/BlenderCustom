"""
BlenderCustom: Unity ユーザー向けの操作カスタマイズをまとめたアドオン。

機能ごとにモジュールを分けている。新しい機能を追加するときは、モジュールを作って
MODULES に足す（各モジュールは register() / unregister() を持つ）。
"""

bl_info = {
    "name": "BlenderCustom",
    "author": "kakizaki",
    "version": (1, 0, 0),
    "blender": (4, 2, 0),
    "location": "3D View",
    "description": "操作・表示のカスタマイズ一式（キー割り当て、範囲選択、パネル、テーマなど）",
    "category": "3D View",
}

import importlib

from . import (
    preferences,
    theme,
    listener,
    enclosed_select,
    hover_highlight,
    select_mode_icons,
    mesh_delete,
    mesh_clipboard,
    select_all_toggle,
    edit_panel,
    quick_panel,
    keymaps,
)

# 登録順。keymaps は各オペレーターの登録後に行う
MODULES = (
    preferences,
    theme,
    enclosed_select,
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

if "bpy" in locals():
    for module in MODULES:
        importlib.reload(module)

import bpy  # noqa: E402  (再読み込み判定のため最後に import する)


def register():
    for module in MODULES:
        module.register()


def unregister():
    for module in reversed(MODULES):
        module.unregister()
