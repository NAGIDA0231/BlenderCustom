"""
3D ビューのヘッダーにある頂点・辺・面の選択モードのアイコンを差し替える。

クリックでそのモードだけをオン・オフ、Shift+クリックでそのモードだけにする（数字キーと同じ動き）。
Blender 本体のヘッダー描画の 1 行を置き換えているため、置き換えられない版では元の表示のままになる。
"""

import inspect
import textwrap

import bl_ui.space_view3d as space_view3d
import bpy

TEMPLATE_CALL = "layout.template_header_3D_mode()"
REPLACEMENT = "__import__(%r, fromlist=['_']).draw_select_mode(layout, context)" % __name__


class PatchState:
    original_draw = None


STATE = PatchState()


class MESH_OT_independent_select_mode(bpy.types.Operator):
    """クリックでこの選択モードをオン・オフ（Shift+クリックでこのモードだけにする）"""
    bl_idname = "mesh.independent_select_mode"
    bl_label = "Toggle Select Mode"
    bl_options = {'REGISTER', 'UNDO'}

    type: bpy.props.EnumProperty(items=(('VERT', "Vertex", ""), ('EDGE', "Edge", ""), ('FACE', "Face", "")))

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH'

    def invoke(self, context, event):
        if event.shift:
            return bpy.ops.mesh.select_mode(type=self.type, use_extend=False, use_expand=event.ctrl)
        return bpy.ops.mesh.select_mode(type=self.type, use_extend=True, use_expand=event.ctrl, action='TOGGLE')

    def execute(self, context):
        return bpy.ops.mesh.select_mode(type=self.type, use_extend=True, action='TOGGLE')


def draw_select_mode(layout, context):
    if context.mode != 'EDIT_MESH':
        layout.template_header_3D_mode()
        return
    vert, edge, face = context.tool_settings.mesh_select_mode
    row = layout.row(align=True)
    for mode_type, icon, is_on in (('VERT', 'VERTEXSEL', vert), ('EDGE', 'EDGESEL', edge), ('FACE', 'FACESEL', face)):
        op = row.operator(MESH_OT_independent_select_mode.bl_idname, text="", icon=icon, depress=is_on)
        op.type = mode_type


def build_patched_draw(original):
    source = textwrap.dedent(inspect.getsource(original))
    if TEMPLATE_CALL not in source:
        return None
    source = source.replace(TEMPLATE_CALL, REPLACEMENT, 1)
    namespace = {}
    exec(compile(source, space_view3d.__file__, "exec"), space_view3d.__dict__, namespace)
    return namespace.get("draw")


def register():
    bpy.utils.register_class(MESH_OT_independent_select_mode)
    STATE.original_draw = bpy.types.VIEW3D_HT_header.draw
    patched = build_patched_draw(STATE.original_draw)
    if patched is not None:
        bpy.types.VIEW3D_HT_header.draw = patched


def unregister():
    if STATE.original_draw is not None:
        bpy.types.VIEW3D_HT_header.draw = STATE.original_draw
        STATE.original_draw = None
    bpy.utils.unregister_class(MESH_OT_independent_select_mode)
