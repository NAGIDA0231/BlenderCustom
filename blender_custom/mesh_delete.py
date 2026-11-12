"""編集モードの Delete キーで、メニューを出さずに選択モードに応じて削除する。"""

import bpy


def delete_type_for_selection(context):
    """面 → 辺 → 頂点の順に、選ばれているものがあるモードの削除方法を返す"""
    use_vert, use_edge, use_face = context.tool_settings.mesh_select_mode
    selected_edges = 0
    selected_faces = 0
    for obj in context.objects_in_mode_unique_data:
        if obj.type != 'MESH':
            continue
        obj.update_from_editmode()
        _, edges, faces = obj.data.count_selected_items()
        selected_edges += edges
        selected_faces += faces
    if use_face and selected_faces > 0:
        return 'FACE'
    if use_edge and selected_edges > 0:
        return 'EDGE'
    return 'VERT'


class MESH_OT_delete_by_select_mode(bpy.types.Operator):
    """選択モードに応じて、メニューを出さずに削除する"""
    bl_idname = "mesh.delete_by_select_mode"
    bl_label = "Delete (By Select Mode)"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH'

    def execute(self, context):
        return bpy.ops.mesh.delete(type=delete_type_for_selection(context))


def register():
    bpy.utils.register_class(MESH_OT_delete_by_select_mode)


def unregister():
    bpy.utils.unregister_class(MESH_OT_delete_by_select_mode)
