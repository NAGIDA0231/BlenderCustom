"""
編集モードで、選んだ面・辺・頂点をコピー／切り取りして貼り付ける。

コピーした内容はワールド座標で保存し、貼り付け先でも同じ見た目の位置に置く。
Blender を終了すると消える。
"""

import bmesh
import bpy

from .mesh_delete import delete_type_for_selection

TEMP_MESH_NAME = "__blendercustom_clipboard__"


class ClipboardState:
    bm = None


CLIPBOARD = ClipboardState()


def copy_selection(context):
    """編集中のメッシュで選択している要素を、ワールド座標でクリップボードに保存する"""
    result = bmesh.new()
    temp = bpy.data.meshes.new(TEMP_MESH_NAME)
    count = 0
    try:
        for obj in context.objects_in_mode_unique_data:
            if obj.type != 'MESH':
                continue
            part = bmesh.from_edit_mesh(obj.data).copy()
            bmesh.ops.delete(part, geom=[f for f in part.faces if not f.select], context='FACES_ONLY')
            bmesh.ops.delete(part, geom=[e for e in part.edges if not e.select], context='EDGES')
            bmesh.ops.delete(part, geom=[v for v in part.verts if not v.select], context='VERTS')
            if len(part.verts) == 0:
                part.free()
                continue
            part.transform(obj.matrix_world)
            count += len(part.verts)
            part.to_mesh(temp)
            part.free()
            result.from_mesh(temp)
    finally:
        bpy.data.meshes.remove(temp)
    if count == 0:
        result.free()
        return False
    if CLIPBOARD.bm is not None:
        CLIPBOARD.bm.free()
    CLIPBOARD.bm = result
    return True


class MESH_OT_clipboard_copy(bpy.types.Operator):
    """選んだ面・辺・頂点をコピーする"""
    bl_idname = "mesh.clipboard_copy"
    bl_label = "Copy Mesh Selection"

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH'

    def execute(self, context):
        if copy_selection(context) is False:
            self.report({'WARNING'}, "コピーするものが選ばれていません")
            return {'CANCELLED'}
        self.report({'INFO'}, "コピーしました")
        return {'FINISHED'}


class MESH_OT_clipboard_cut(bpy.types.Operator):
    """選んだ面・辺・頂点を切り取る"""
    bl_idname = "mesh.clipboard_cut"
    bl_label = "Cut Mesh Selection"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH'

    def execute(self, context):
        if copy_selection(context) is False:
            self.report({'WARNING'}, "切り取るものが選ばれていません")
            return {'CANCELLED'}
        bpy.ops.mesh.delete(type=delete_type_for_selection(context))
        return {'FINISHED'}


class MESH_OT_clipboard_paste(bpy.types.Operator):
    """コピー／切り取りした面・辺・頂点を、編集中のメッシュに元の位置で貼り付ける"""
    bl_idname = "mesh.clipboard_paste"
    bl_label = "Paste Mesh Selection"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH' and context.edit_object is not None

    def execute(self, context):
        if CLIPBOARD.bm is None:
            self.report({'WARNING'}, "クリップボードが空です")
            return {'CANCELLED'}
        obj = context.edit_object
        bm = bmesh.from_edit_mesh(obj.data)
        # 既存の要素に目印（tag）を付け、貼り付け後に目印のないものを新しい要素とみなす
        for elem in list(bm.faces) + list(bm.edges) + list(bm.verts):
            elem.select = False
            elem.tag = True

        part = CLIPBOARD.bm.copy()
        part.transform(obj.matrix_world.inverted())
        temp = bpy.data.meshes.new(TEMP_MESH_NAME)
        try:
            part.to_mesh(temp)
            bm.from_mesh(temp)
        finally:
            part.free()
            bpy.data.meshes.remove(temp)

        for elem in list(bm.verts) + list(bm.edges) + list(bm.faces):
            if elem.tag:
                elem.tag = False
            else:
                elem.select = True
        bm.select_flush_mode()
        bmesh.update_edit_mesh(obj.data)
        return {'FINISHED'}


CLASSES = (MESH_OT_clipboard_copy, MESH_OT_clipboard_cut, MESH_OT_clipboard_paste)


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    if CLIPBOARD.bm is not None:
        CLIPBOARD.bm.free()
        CLIPBOARD.bm = None
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
