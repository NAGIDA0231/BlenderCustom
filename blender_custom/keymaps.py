"""
キーの割り当て。

新しい割り当てはアドオン用のキーマップに登録する（既存の割り当てより優先され、
アドオンを無効にすると消える）。押し方が違うために優先されない既存の割り当て
（右クリックを押した瞬間に出るメニュー）だけは、ユーザーキーマップで無効にし、
アドオンを無効にしたときに有効へ戻す。
"""

import bpy

CONTEXT_MENU_KEYMAPS = ("Object Mode", "Mesh", "Curve", "Curves", "Pose", "Armature", "Metaball", "Lattice",
                        "Particle", "Font", "Grease Pencil Edit Mode")

SELECT_ALL_OPERATORS = {
    "Object Mode": "object.select_all",
    "Mesh": "mesh.select_all",
    "Curve": "curve.select_all",
    "Curves": "curves.select_all",
    "Pose": "pose.select_all",
    "Armature": "armature.select_all",
    "Metaball": "mball.select_all",
    "Lattice": "lattice.select_all",
    "Particle": "particle.select_all",
}

# Ctrl+D の切り替え。ここにない編集モードは Blender 標準の TOGGLE を使う
SELECT_TOGGLE_OPERATORS = {
    "Object Mode": "object.toggle_select_collection",
    "Mesh": "mesh.toggle_select_all_strict",
}

VIEW_AXIS_KEYS = (("F1", 'RIGHT', 'LEFT'), ("F2", 'TOP', 'BOTTOM'), ("F3", 'FRONT', 'BACK'))
SELECT_MODE_KEYS = (("ONE", 'VERT'), ("TWO", 'EDGE'), ("THREE", 'FACE'))
GESTURE_MODES = ((False, False, 'SET'), (True, False, 'ADD'), (False, True, 'SUB'), (True, True, 'AND'))
LASSO_TOOL_KEYMAPS = ("3D View Tool: Select Lasso", "3D View Tool: Select Lasso (fallback)")
BOX_TOOL_KEYMAPS = ("3D View Tool: Select Box", "3D View Tool: Select Box (fallback)")

addon_keymap_items = []


def get_addon_keymap(name):
    wm = bpy.context.window_manager
    default = wm.keyconfigs.default.keymaps[name]
    return wm.keyconfigs.addon.keymaps.new(name=name, space_type=default.space_type,
                                           region_type=default.region_type)


def add_item(keymap_name, idname, key, value='PRESS', shift=False, ctrl=False, alt=False, **properties):
    km = get_addon_keymap(keymap_name)
    kmi = km.keymap_items.new(idname, key, value, shift=shift, ctrl=ctrl, alt=alt)
    for name, prop_value in properties.items():
        setattr(kmi.properties, name, prop_value)
    addon_keymap_items.append((km, kmi))
    return kmi


def default_context_menu(keymap_name):
    """標準キーマップで右クリックを押したときに出すメニューの名前"""
    km = bpy.context.window_manager.keyconfigs.default.keymaps.get(keymap_name)
    if km is None:
        return None
    for kmi in km.keymap_items:
        if (kmi.idname == 'wm.call_menu' and kmi.type == 'RIGHTMOUSE' and kmi.value == 'PRESS'
                and not (kmi.shift or kmi.ctrl or kmi.alt)):
            return kmi.properties.name
    return None


def is_press_context_menu(kmi):
    return (kmi.idname == 'wm.call_menu' and kmi.type == 'RIGHTMOUSE' and kmi.value == 'PRESS'
            and not (kmi.shift or kmi.ctrl or kmi.alt))


def set_press_context_menus_active(active):
    kc = bpy.context.window_manager.keyconfigs.user
    if kc is None:
        return False
    for name in CONTEXT_MENU_KEYMAPS:
        km = kc.keymaps.get(name)
        if km is None:
            continue
        for kmi in km.keymap_items:
            if is_press_context_menu(kmi):
                kmi.active = active
    return True


def disable_press_context_menus():
    if set_press_context_menus_active(False) is False:
        return 0.5
    return None


def register_navigation():
    # 右ドラッグで回転、中ボタンで平行移動
    add_item("3D View", 'view3d.rotate', 'RIGHTMOUSE', 'CLICK_DRAG')
    add_item("3D View", 'view3d.move', 'MIDDLEMOUSE', 'PRESS')
    # 右クリック（ドラッグせずに離す）でメニュー
    for name in CONTEXT_MENU_KEYMAPS:
        menu = default_context_menu(name)
        if menu is not None:
            add_item(name, 'wm.call_menu', 'RIGHTMOUSE', 'CLICK', name=menu)
    # F1 側面 / F2 頭上 / F3 正面（Shift で反対側）
    for key, axis, opposite in VIEW_AXIS_KEYS:
        add_item("3D View", 'view3d.view_axis', key, type=axis)
        add_item("3D View", 'view3d.view_axis', key, shift=True, type=opposite)


def register_selection():
    # 1/2/3 で選択モードを個別にオン・オフ、Shift+1/2/3 でそのモードだけ
    for key, mode in SELECT_MODE_KEYS:
        add_item("Mesh", 'mesh.select_mode', key, type=mode, use_extend=True, action='TOGGLE')
        add_item("Mesh", 'mesh.select_mode', key, shift=True, type=mode, use_extend=False, action='TOGGLE')
    # Ctrl+A 全選択 / Ctrl+D 全選択と全解除の切り替え
    for name, select_all in SELECT_ALL_OPERATORS.items():
        add_item(name, select_all, 'A', ctrl=True, action='SELECT')
        toggle = SELECT_TOGGLE_OPERATORS.get(name)
        if toggle is not None:
            add_item(name, toggle, 'D', ctrl=True)
        else:
            add_item(name, select_all, 'D', ctrl=True, action='TOGGLE')
    # 投げ縄・ボックス選択は、完全に囲んだものだけを選ぶ版に置き換える
    for names, idname in ((LASSO_TOOL_KEYMAPS, 'view3d.enclosed_lasso_select'),
                          (BOX_TOOL_KEYMAPS, 'view3d.enclosed_box_select')):
        for name in names:
            for shift, ctrl, mode in GESTURE_MODES:
                add_item(name, idname, 'LEFTMOUSE', 'CLICK_DRAG', shift=shift, ctrl=ctrl, mode=mode)


def register_mesh_editing():
    add_item("Mesh", 'mesh.merge', 'J', ctrl=True, type='CENTER')
    add_item("Mesh", 'mesh.delete_by_select_mode', 'DEL')
    add_item("Mesh", 'mesh.clipboard_copy', 'C', ctrl=True)
    add_item("Mesh", 'mesh.clipboard_cut', 'X', ctrl=True)
    add_item("Mesh", 'mesh.clipboard_paste', 'V', ctrl=True)


def register():
    wm = bpy.context.window_manager
    if wm.keyconfigs.addon is None:
        return
    register_navigation()
    register_selection()
    register_mesh_editing()
    bpy.app.timers.register(disable_press_context_menus, first_interval=0.1)


def unregister():
    if bpy.app.timers.is_registered(disable_press_context_menus):
        bpy.app.timers.unregister(disable_press_context_menus)
    set_press_context_menus_active(True)
    for km, kmi in addon_keymap_items:
        km.keymap_items.remove(kmi)
    addon_keymap_items.clear()
