"""
全選択されていなければ全選択、全選択されていれば全解除する（Ctrl+D）。

オブジェクトモードでは、アウトライナーで選んでいるコレクション（入れ子を含む）が対象。
"""

import bmesh
import bpy


def collection_objects(context):
    collection = context.view_layer.active_layer_collection.collection
    return [o for o in collection.all_objects
            if o.visible_get(view_layer=context.view_layer) and not o.hide_select]


class OBJECT_OT_toggle_select_collection(bpy.types.Operator):
    """アクティブなコレクションのオブジェクトを全選択／全解除で切り替える"""
    bl_idname = "object.toggle_select_collection"
    bl_label = "Toggle Select Collection"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'

    def execute(self, context):
        targets = collection_objects(context)
        if not targets:
            return {'CANCELLED'}
        all_selected = all(o.select_get() for o in targets)
        for obj in context.view_layer.objects:
            obj.select_set(False)
        if all_selected:
            return {'FINISHED'}
        for obj in targets:
            obj.select_set(True)
        if context.view_layer.objects.active not in targets:
            context.view_layer.objects.active = targets[0]
        return {'FINISHED'}


class MESH_OT_toggle_select_all_strict(bpy.types.Operator):
    """見えている頂点がすべて選ばれていれば全解除、そうでなければ全選択する"""
    bl_idname = "mesh.toggle_select_all_strict"
    bl_label = "Toggle Select All"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH'

    def execute(self, context):
        all_selected = True
        for obj in context.objects_in_mode_unique_data:
            if obj.type != 'MESH':
                continue
            bm = bmesh.from_edit_mesh(obj.data)
            if any(not v.select for v in bm.verts if not v.hide):
                all_selected = False
                break
        return bpy.ops.mesh.select_all(action='DESELECT' if all_selected else 'SELECT')


CLASSES = (OBJECT_OT_toggle_select_collection, MESH_OT_toggle_select_all_strict)


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
