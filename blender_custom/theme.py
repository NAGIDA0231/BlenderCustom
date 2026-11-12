"""テーマの色とプリファレンスの変更。アドオンを無効にすると変更前の値に戻す。"""

import json

import bpy

from .preferences import get_prefs

PINK = (1.0, 0.4, 0.75)
CYAN = (0.3, 0.85, 1.0)
LIGHT_CYAN = (0.65, 0.95, 1.0)

# (テーマ view_3d の属性名, 値)。アルファ付きの色は RGB だけ変えてアルファは保つ
VIEW_3D_COLORS = (
    ("vertex", PINK),
    ("wire_edit", PINK),
    ("vertex_select", CYAN),
    ("edge_select", CYAN),
    ("edge_mode_select", CYAN),
    ("face_select", CYAN),
    ("face_mode_select", CYAN),
    ("object_selected", CYAN),
    ("object_active", LIGHT_CYAN),
)

# (プリファレンスの区分, 属性名, 値)
PREFERENCE_VALUES = (
    ("view", "smooth_view", 0),
    ("inputs", "use_auto_perspective", False),
)


def view_3d_theme():
    return bpy.context.preferences.themes[0].view_3d


def capture_current():
    theme = view_3d_theme()
    preferences = bpy.context.preferences
    return {
        "colors": {name: list(getattr(theme, name)) for name, _ in VIEW_3D_COLORS},
        "preferences": {f"{section}.{name}": getattr(getattr(preferences, section), name)
                        for section, name, _ in PREFERENCE_VALUES},
    }


def apply():
    prefs = get_prefs()
    if prefs.saved_defaults == "":
        prefs.saved_defaults = json.dumps(capture_current())
    theme = view_3d_theme()
    for name, rgb in VIEW_3D_COLORS:
        current = getattr(theme, name)
        if len(current) == 4:
            setattr(theme, name, (*rgb, current[3]))
        else:
            setattr(theme, name, rgb)
    preferences = bpy.context.preferences
    for section, name, value in PREFERENCE_VALUES:
        setattr(getattr(preferences, section), name, value)


def restore():
    prefs = get_prefs()
    if prefs.saved_defaults == "":
        return
    saved = json.loads(prefs.saved_defaults)
    theme = view_3d_theme()
    for name, value in saved["colors"].items():
        setattr(theme, name, value)
    preferences = bpy.context.preferences
    for key, value in saved["preferences"].items():
        section, name = key.split(".")
        setattr(getattr(preferences, section), name, value)
    prefs.saved_defaults = ""


def register():
    apply()


def unregister():
    restore()
