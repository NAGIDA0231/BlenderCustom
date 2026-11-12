"""
Edit Panel: 移動・拡大縮小・回転を軸ごとに開始するボタン。

ボタンの上で押した瞬間に変形が始まり、押したまま動かして、離すと確定する。
"""

import bpy

from . import listener
from .floating_panel import Cell, FloatingPanel

COLUMNS = (("translate", "移動"), ("resize", "拡大"), ("rotate", "回転"))
# ボタンに表示する軸（Unity の呼び方）。Y が上下、Z が奥行き
ROWS = (None, 'X', 'Y', 'Z')
# ボタンの軸 → Blender の軸（Blender は Z が上下、Y が奥行き）
BLENDER_AXIS = {'X': 'X', 'Y': 'Z', 'Z': 'Y'}
AXIS_CONSTRAINT = {'X': (True, False, False), 'Y': (False, True, False), 'Z': (False, False, True)}
AXIS_COLOR = {None: (0.95, 0.95, 0.95, 1.0), 'X': (1.0, 0.4, 0.4, 1.0), 'Y': (0.5, 1.0, 0.5, 1.0),
              'Z': (0.5, 0.7, 1.0, 1.0)}


def cell_target(index):
    """ボタンの (変形の種類, 表示名) と、Blender の軸（None は軸なし）を返す"""
    row, col = divmod(index, len(COLUMNS))
    label_axis = ROWS[row]
    return COLUMNS[col], (None if label_axis is None else BLENDER_AXIS[label_axis])


def cell_label_axis(index):
    return ROWS[index // len(COLUMNS)]


def start_transform(context, window, area, region, kind, axis):
    """axis は Blender の軸"""
    kwargs = {"release_confirm": True}
    if axis is not None:
        kwargs["constraint_axis"] = AXIS_CONSTRAINT[axis]
        if kind == "rotate":
            kwargs["orient_axis"] = axis
    operator = getattr(bpy.ops.transform, kind)
    with context.temp_override(window=window, area=area, region=region):
        operator('INVOKE_DEFAULT', **kwargs)


class EditPanel(FloatingPanel):
    title = "Edit Panel"
    pref_x = "edit_panel_x"
    pref_y = "edit_panel_y"
    columns = 3
    cell_width = 30
    cell_height = 30

    def cell_count(self):
        return len(COLUMNS) * len(ROWS)

    def cells(self, context):
        result = []
        for index in range(self.cell_count()):
            (_, name), _ = cell_target(index)
            axis = cell_label_axis(index)
            if axis is None:
                result.append(Cell(name, AXIS_COLOR[None], 10))
            else:
                result.append(Cell(axis, AXIS_COLOR[axis], 13))
        return result

    def on_press(self, context, window, area, region, index):
        (kind, _), axis = cell_target(index)
        start_transform(context, window, area, region, kind, axis)


PANEL = EditPanel()


def register():
    PANEL.register_draw()
    listener.add_handler(PANEL.handle_event)


def unregister():
    listener.remove_handler(PANEL.handle_event)
    PANEL.unregister_draw()
