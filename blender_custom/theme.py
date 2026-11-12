"""
テーマの色とプリファレンスの変更。アドオンを無効にすると変更前の値に戻す。

変更前の値はアドオン設定の saved_defaults（JSON）に保存する。項目を追加した場合も、
まだ保存されていない項目だけを追加で保存するので、既存の環境でも元に戻せる。
"""

import json

import bpy

from .preferences import get_prefs

PINK = (1.0, 0.4, 0.75)
CYAN = (0.3, 0.85, 1.0)
LIGHT_CYAN = (0.65, 0.95, 1.0)


def view_3d_theme():
    return bpy.context.preferences.themes[0].view_3d


def ui_theme():
    return bpy.context.preferences.themes[0].user_interface


# (保存用のキー, 対象を返す関数, 属性名, 新しい値を返す関数)
# 新しい値の関数は、変更前の値の辞書（saved）を受け取る。Y と Z の入れ替えのように元の値を使うため
SETTINGS = (
    ("view_3d.vertex", view_3d_theme, "vertex", lambda saved: PINK),
    ("view_3d.wire_edit", view_3d_theme, "wire_edit", lambda saved: PINK),
    ("view_3d.vertex_select", view_3d_theme, "vertex_select", lambda saved: CYAN),
    ("view_3d.edge_select", view_3d_theme, "edge_select", lambda saved: CYAN),
    ("view_3d.edge_mode_select", view_3d_theme, "edge_mode_select", lambda saved: CYAN),
    ("view_3d.face_select", view_3d_theme, "face_select", lambda saved: CYAN),
    ("view_3d.face_mode_select", view_3d_theme, "face_mode_select", lambda saved: CYAN),
    ("view_3d.object_selected", view_3d_theme, "object_selected", lambda saved: CYAN),
    ("view_3d.object_active", view_3d_theme, "object_active", lambda saved: LIGHT_CYAN),
    # Unity に合わせて、縦（Blender の Z）を緑、奥行き（Blender の Y）を青にする
    ("user_interface.axis_y", ui_theme, "axis_y", lambda saved: saved["user_interface.axis_z"]),
    ("user_interface.axis_z", ui_theme, "axis_z", lambda saved: saved["user_interface.axis_y"]),
    ("view.smooth_view", lambda: bpy.context.preferences.view, "smooth_view", lambda saved: 0),
    ("inputs.use_auto_perspective", lambda: bpy.context.preferences.inputs, "use_auto_perspective",
     lambda saved: False),
)

# 以前の版の保存形式（{"colors": {...}, "preferences": {...}}）からの読み替え
LEGACY_SECTIONS = {"colors": "view_3d.", "preferences": ""}


def to_json_value(value):
    if isinstance(value, (bool, int, float, str)):
        return value
    return list(value)


def load_saved():
    prefs = get_prefs()
    if prefs.saved_defaults == "":
        return {}
    data = json.loads(prefs.saved_defaults)
    saved = {}
    for key, value in data.items():
        if key in LEGACY_SECTIONS and isinstance(value, dict):
            for name, item in value.items():
                saved[LEGACY_SECTIONS[key] + name] = item
        else:
            saved[key] = value
    return saved


def apply_value(owner, name, value):
    current = getattr(owner, name)
    if isinstance(current, (bool, int, float, str)):
        setattr(owner, name, value)
        return
    value = list(value)
    if len(current) == 4 and len(value) == 3:
        value.append(current[3])  # アルファ付きの色は RGB だけ変え、アルファは保つ
    setattr(owner, name, value[:len(current)])


def apply():
    saved = load_saved()
    for key, owner_getter, name, _ in SETTINGS:
        if key not in saved:
            saved[key] = to_json_value(getattr(owner_getter(), name))
    get_prefs().saved_defaults = json.dumps(saved)
    for key, owner_getter, name, value_getter in SETTINGS:
        apply_value(owner_getter(), name, value_getter(saved))


def restore():
    saved = load_saved()
    for key, owner_getter, name, _ in SETTINGS:
        if key in saved:
            apply_value(owner_getter(), name, saved[key])
    get_prefs().saved_defaults = ""


def register():
    apply()


def unregister():
    restore()
