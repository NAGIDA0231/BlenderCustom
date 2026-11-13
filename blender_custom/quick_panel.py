"""
QuickPanel: よく使う切り替えをまとめた便利パネル。

ボタンを追加するときは、label / is_on / execute を持つクラス（またはオブジェクト）を作り QUICK_ITEMS に足す。
選択を変えるだけのボタンは SelectionCommand で作れる。
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
            return "モディファイア なし"
        if any(m.show_viewport for m in modifiers):
            return "モディファイア 表示"
        return "モディファイア 非表示"

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


def count_selected(context):
    """編集中のメッシュで選んでいる頂点の数"""
    total = 0
    for obj in context.objects_in_mode_unique_data:
        if obj.type != 'MESH':
            continue
        obj.update_from_editmode()
        total += obj.data.count_selected_items()[0]
    return total


class SelectionCommand:
    """選んでいるものを起点に、選択を広げる・変えるボタン（編集モード用）"""

    def __init__(self, name, run):
        self.name = name
        self.run = run

    def label(self, context):
        return self.name

    def is_on(self, context):
        return False

    def execute(self, context):
        if context.mode != 'EDIT_MESH':
            show_status(f"{self.name}: 編集モードで使ってください")
            return
        if count_selected(context) == 0:
            show_status(f"{self.name}: 起点にするものを先に選んでください")
            return
        self.run()
        bpy.ops.ed.undo_push(message=self.name)


SELECT_LOOP = SelectionCommand("ループ選択", lambda: bpy.ops.mesh.select_edge_loop_multi())
SELECT_RING = SelectionCommand("リング選択", lambda: bpy.ops.mesh.select_edge_ring_multi())
SELECT_LINKED = SelectionCommand("リンク選択", lambda: bpy.ops.mesh.select_linked())
SELECT_MORE = SelectionCommand("選択を広げる", lambda: bpy.ops.mesh.select_more())
SELECT_LESS = SelectionCommand("選択を狭める", lambda: bpy.ops.mesh.select_less())

class StartEdgeEraser:
    """辺消しモードを始める（クリックした辺を溶解する）"""

    @staticmethod
    def label(context):
        return "辺消しモード"

    @staticmethod
    def is_on(context):
        # パネル用ウィンドウから見ても分かるよう、全ウィンドウを調べる
        return any(op is not None and op.bl_idname == "BLENDERCUSTOM_OT_edge_eraser"
                   for window in context.window_manager.windows for op in window.modal_operators)

    @staticmethod
    def execute(context):
        from . import edge_eraser
        edge_eraser.start(context)


# 2 列で、左から右・上から下の順に並ぶ
QUICK_ITEMS = (
    ToggleSelectTool, ToggleModifierDisplay,
    AlignVerticesToZeroX, SELECT_LINKED,
    SELECT_LOOP, SELECT_RING,
    SELECT_MORE, SELECT_LESS,
    StartEdgeEraser,
)


class QuickPanel(FloatingPanel):
    title = "QuickPanel"
    pref_x = "quick_panel_x"
    pref_y = "quick_panel_y"
    columns = 2
    cell_width = 120
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
