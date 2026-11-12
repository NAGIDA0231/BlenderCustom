"""
QuickPanel: よく使う切り替えをまとめた便利パネル。

ボタンを追加するときは、label / is_on / execute を持つクラスを作り QUICK_ITEMS に足す。
  label(context)   : ボタンに表示する文字
  is_on(context)   : オン表示（青）にするか
  execute(context) : 押したときの処理（3D ビューのコンテキストで呼ばれる）
"""

import bmesh
import bpy

from . import listener
from .floating_panel import Cell, FloatingPanel, show_status

LASSO_TOOL = "builtin.select_lasso"
BOX_TOOL = "builtin.select_box"
SELECT_TOOL_NAMES = {LASSO_TOOL: "投げ縄", BOX_TOOL: "ボックス"}


def current_tool(context):
    return context.workspace.tools.from_space_view3d_mode(context.mode, create=False)


def current_tool_id(context):
    tool = current_tool(context)
    return tool.idname if tool is not None else ""


def drag_select_tool_id(context):
    """選択ツール使用中はそのツール、それ以外はヘッダーの「ドラッグ」で使う選択ツールを返す"""
    tool = current_tool(context)
    if tool is None:
        return ""
    if tool.idname in SELECT_TOOL_NAMES:
        return tool.idname
    return tool.idname_fallback


class ToggleSelectTool:
    """投げ縄選択とボックス選択を切り替える"""

    @staticmethod
    def label(context):
        return "選択: " + SELECT_TOOL_NAMES.get(drag_select_tool_id(context), "その他")

    @staticmethod
    def is_on(context):
        return drag_select_tool_id(context) == LASSO_TOOL

    @staticmethod
    def execute(context):
        target = BOX_TOOL if drag_select_tool_id(context) == LASSO_TOOL else LASSO_TOOL
        # 選択ツール使用中はツール自体を、それ以外はドラッグ時の選択ツールを切り替える
        as_fallback = current_tool_id(context) not in SELECT_TOOL_NAMES
        bpy.ops.wm.tool_set_by_id(name=target, as_fallback=as_fallback)


def modifier_targets(context):
    if context.mode == 'OBJECT':
        objects = list(context.selected_objects)
    else:
        objects = list(context.objects_in_mode)
    if not objects and context.active_object is not None:
        objects = [context.active_object]
    return [m for o in objects for m in o.modifiers]


class ToggleModifierDisplay:
    """選んでいるオブジェクトのモディファイアをまとめて表示・非表示にする"""

    @staticmethod
    def label(context):
        modifiers = modifier_targets(context)
        if not modifiers:
            return "モディファイア: なし"
        if any(m.show_viewport for m in modifiers):
            return "モディファイア: 表示中"
        return "モディファイア: 非表示"

    @staticmethod
    def is_on(context):
        return any(m.show_viewport for m in modifier_targets(context))

    @staticmethod
    def execute(context):
        modifiers = modifier_targets(context)
        if not modifiers:
            return
        show = not any(m.show_viewport for m in modifiers)
        for m in modifiers:
            m.show_viewport = show


class AlignVerticesToZeroX:
    """編集モードで選んでいる頂点の X 座標を 0 にそろえる（オブジェクトのローカル座標。ミラーの中心線）"""

    @staticmethod
    def label(context):
        return "頂点を X=0 に"

    @staticmethod
    def is_on(context):
        return False

    @staticmethod
    def execute(context):
        if context.mode != 'EDIT_MESH':
            show_status("頂点を X=0 に: 編集モードで使ってください")
            return
        count = 0
        for obj in context.objects_in_mode_unique_data:
            if obj.type != 'MESH':
                continue
            bm = bmesh.from_edit_mesh(obj.data)
            changed = False
            for vert in bm.verts:
                if vert.select and not vert.hide:
                    vert.co.x = 0.0
                    count += 1
                    changed = True
            if changed:
                bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)
        if count == 0:
            show_status("頂点を X=0 に: 頂点が選ばれていません")
            return
        bpy.ops.ed.undo_push(message="頂点を X=0 に")
        show_status(f"頂点を X=0 に: {count} 個の頂点をそろえました")


QUICK_ITEMS = (ToggleSelectTool, ToggleModifierDisplay, AlignVerticesToZeroX)


class QuickPanel(FloatingPanel):
    title = "QuickPanel"
    pref_x = "quick_panel_x"
    pref_y = "quick_panel_y"
    columns = 1
    cell_width = 146
    cell_height = 24

    def cell_count(self):
        return len(QUICK_ITEMS)

    def cells(self, context):
        return [Cell(item.label(context), is_on=item.is_on(context)) for item in QUICK_ITEMS]

    def on_press(self, context, window, area, region, index):
        with context.temp_override(window=window, area=area, region=region):
            QUICK_ITEMS[index].execute(bpy.context)


PANEL = QuickPanel()


def register():
    PANEL.register_draw()
    listener.add_handler(PANEL.handle_event)


def unregister():
    listener.remove_handler(PANEL.handle_event)
    PANEL.unregister_draw()
