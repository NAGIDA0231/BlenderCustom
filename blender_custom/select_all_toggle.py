"""
D キーの全選択のうち、オブジェクトモード用の処理。

オブジェクトモードの D は、アウトライナーで選んでいるコレクション（入れ子を含む）のオブジェクトを全部選ぶ。
編集モードなどの D（全選択）と Ctrl+D（全解除）は Blender 標準の select_all を使う（keymaps.py）。
"""

import bpy


def collection_objects(context):
    collection = context.view_layer.active_layer_collection.collection
    return [o for o in collection.all_objects
            if o.visible_get(view_layer=context.view_layer) and not o.hide_select]


class OBJECT_OT_select_collection(bpy.types.Operator):
    """アウトライナーで選んでいるコレクションのオブジェクトを全部選ぶ（ほかのオブジェクトの選択は外す）"""
    bl_idname = "object.select_collection"
    bl_label = "Select Collection Objects"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'

    def execute(self, context):
        targets = collection_objects(context)
        if not targets:
            return {'CANCELLED'}
        for obj in context.view_layer.objects:
            obj.select_set(False)
        for obj in targets:
            obj.select_set(True)
        if context.view_layer.objects.active not in targets:
            context.view_layer.objects.active = targets[0]
        return {'FINISHED'}


CLASSES = (OBJECT_OT_select_collection,)


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
