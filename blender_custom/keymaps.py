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

# D の全選択で、標準の select_all の代わりに使う操作（オブジェクトモードはアクティブなコレクションが対象）
SELECT_ALL_D_OPERATORS = {
    "Object Mode": "object.select_collection",
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
    # D / Ctrl+A 全選択、Ctrl+D 全解除
    for name, select_all in SELECT_ALL_OPERATORS.items():
        add_item(name, select_all, 'A', ctrl=True, action='SELECT')
        special = SELECT_ALL_D_OPERATORS.get(name)
        if special is not None:
            add_item(name, special, 'D')
        else:
            add_item(name, select_all, 'D', action='SELECT')
        add_item(name, select_all, 'D', ctrl=True, action='DESELECT')
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


# --- 変形中（G / R / S やギズモのドラッグ中）のキー ------------------------------------
# モーダルキーマップはアドオン用のキーマップに登録できないため、ユーザーキーマップで
# 標準の項目を無効にして新しい項目を追加し、アドオンを無効にしたときに元へ戻す。

TRANSFORM_MODAL_MAP = "Transform Modal Map"

# 無効にする標準の項目: (propvalue, キー, Shift 付きか)
TRANSFORM_MODAL_DISABLED = (
    ('PRECISION', 'LEFT_SHIFT', None),
    ('PRECISION', 'RIGHT_SHIFT', None),
    ('AXIS_Y', 'Y', False),
    ('AXIS_Z', 'Z', False),
    ('PLANE_Y', 'Y', True),
    ('PLANE_Z', 'Z', True),
)

# 追加する項目: (propvalue, キー, 押し方, any, Shift)
TRANSFORM_MODAL_ADDED = (
    # Shift を押している間は刻み（回転は 15°。刻み幅は snapping.py）
    ('SNAP_INV_ON', 'LEFT_SHIFT', 'PRESS', True, False),
    ('SNAP_INV_OFF', 'LEFT_SHIFT', 'RELEASE', True, False),
    ('SNAP_INV_ON', 'RIGHT_SHIFT', 'PRESS', True, False),
    ('SNAP_INV_OFF', 'RIGHT_SHIFT', 'RELEASE', True, False),
    # Unity に合わせて Y キーで上下（Blender の Z）、Z キーで奥行き（Blender の Y）に制限する
    ('AXIS_Z', 'Y', 'PRESS', False, False),
    ('AXIS_Y', 'Z', 'PRESS', False, False),
    ('PLANE_Z', 'Y', 'PRESS', False, True),
    ('PLANE_Y', 'Z', 'PRESS', False, True),
)


# --- ナイフツールの操作中のキー -------------------------------------------------------
# 標準では右ボタンを押した瞬間が「次の切れ目を始める」で、右ドラッグの回転ができない。
# ナイフの操作中は Blender がドラッグも右クリックも判定しないため、
# 右ボタンを押した瞬間は視点操作として後ろに渡し（knife_orbit.py が受け取って回転する）、
# 離したときを「確定」にする（回転した場合は knife_orbit.py が離したことをナイフに渡さない）。
# 標準の右クリックの「次の切れ目」は使わない（Enter / Space の確定は標準のまま）。

KNIFE_MODAL_MAP = "Knife Tool Modal Map"

KNIFE_MODAL_DISABLED = (
    ('NEW_CUT', 'RIGHTMOUSE', False),
)

KNIFE_MODAL_ADDED = (
    ('PANNING', 'RIGHTMOUSE', 'PRESS', False, False),
    ('CONFIRM', 'RIGHTMOUSE', 'RELEASE', False, False),
)

# モーダルキーマップごとの変更: キーマップ名 → (無効にする標準の項目, 追加する項目)
MODAL_PATCHES = {
    TRANSFORM_MODAL_MAP: (TRANSFORM_MODAL_DISABLED, TRANSFORM_MODAL_ADDED),
    KNIFE_MODAL_MAP: (KNIFE_MODAL_DISABLED, KNIFE_MODAL_ADDED),
}


def matches_disabled(kmi, disabled):
    for propvalue, key, shift in disabled:
        if kmi.propvalue == propvalue and kmi.type == key and not kmi.is_user_defined:
            if shift is None or bool(kmi.shift) == shift:
                return True
    return False


def matches_added(kmi, spec):
    propvalue, key, value, any_modifier, shift = spec
    return (kmi.is_user_defined and kmi.propvalue == propvalue and kmi.type == key and kmi.value == value
            and bool(kmi.any) == any_modifier and (any_modifier or bool(kmi.shift) == shift))


def apply_modal_patches():
    kc = bpy.context.window_manager.keyconfigs.user
    if kc is None:
        return 0.5
    for name, (disabled, added) in MODAL_PATCHES.items():
        km = kc.keymaps.get(name)
        if km is None:
            return 0.5
        for kmi in km.keymap_items:
            if matches_disabled(kmi, disabled):
                kmi.active = False
        # 以前の版で追加した、今の内容と違う項目を消す（同じキーで追加した自分の項目が対象）
        added_keys = {spec[1] for spec in added}
        for kmi in list(km.keymap_items):
            if (kmi.is_user_defined and kmi.type in added_keys
                    and not any(matches_added(kmi, spec) for spec in added)):
                km.keymap_items.remove(kmi)
        for spec in added:
            if not any(matches_added(k, spec) for k in km.keymap_items):
                propvalue, key, value, any_modifier, shift = spec
                km.keymap_items.new_modal(propvalue, key, value, any=any_modifier, shift=shift)
    return None


def restore_modal_patches():
    kc = bpy.context.window_manager.keyconfigs.user
    if kc is None:
        return
    for name, (disabled, added) in MODAL_PATCHES.items():
        km = kc.keymaps.get(name)
        if km is None:
            continue
        for kmi in list(km.keymap_items):
            if any(matches_added(kmi, spec) for spec in added):
                km.keymap_items.remove(kmi)
        for kmi in km.keymap_items:
            if matches_disabled(kmi, disabled):
                kmi.active = True


def register():
    wm = bpy.context.window_manager
    if wm.keyconfigs.addon is None:
        return
    register_navigation()
    register_selection()
    register_mesh_editing()
    bpy.app.timers.register(disable_press_context_menus, first_interval=0.1)
    bpy.app.timers.register(apply_modal_patches, first_interval=0.1)


def unregister():
    for timer in (disable_press_context_menus, apply_modal_patches):
        if bpy.app.timers.is_registered(timer):
            bpy.app.timers.unregister(timer)
    restore_modal_patches()
    set_press_context_menus_active(True)
    for km, kmi in addon_keymap_items:
        km.keymap_items.remove(kmi)
    addon_keymap_items.clear()
