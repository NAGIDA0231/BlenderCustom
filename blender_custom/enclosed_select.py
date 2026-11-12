"""
編集モードの投げ縄選択・ボックス選択で、完全に囲んだ頂点・辺・面だけを選ぶ。

範囲内の頂点は Blender 標準の選択（頂点モード・一時的に透過表示）で判定するので、
裏側に隠れている頂点も対象になる。編集モード以外では標準の選択と同じ動きをする。
"""

import bmesh
import bpy
import gpu
from gpu_extras.batch import batch_for_shader

MODE_ITEMS = (
    ('SET', "Set", "新しく選択する"),
    ('ADD', "Extend", "選択に追加する"),
    ('SUB', "Subtract", "選択から外す"),
    ('XOR', "Difference", "選択を反転する"),
    ('AND', "Intersect", "選択との共通部分にする"),
)


def combine(original, target, mode):
    if mode == 'SET':
        return target
    if mode == 'ADD':
        return original or target
    if mode == 'SUB':
        return original and not target
    if mode == 'XOR':
        return original != target
    if mode == 'AND':
        return original and target
    return target


class SelectThrough:
    """範囲内の頂点を調べる間だけ透過表示にして、隠れている頂点も対象にする（表示は元に戻す）"""

    def __init__(self, context):
        space = context.space_data
        self.shading = space.shading if space is not None and space.type == 'VIEW_3D' else None
        self.saved = None

    def __enter__(self):
        shading = self.shading
        if shading is None:
            return self
        if shading.type == 'WIREFRAME':
            self.saved = ("show_xray_wireframe", shading.show_xray_wireframe,
                          "xray_alpha_wireframe", shading.xray_alpha_wireframe)
            shading.show_xray_wireframe = True
            if shading.xray_alpha_wireframe >= 1.0:
                shading.xray_alpha_wireframe = 0.5
        else:
            self.saved = ("show_xray", shading.show_xray, "xray_alpha", shading.xray_alpha)
            shading.show_xray = True
            if shading.xray_alpha >= 1.0:
                shading.xray_alpha = 0.5
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self.saved is not None:
            flag_name, flag_value, alpha_name, alpha_value = self.saved
            setattr(self.shading, flag_name, flag_value)
            setattr(self.shading, alpha_name, alpha_value)
        return False


def enclosed_select(context, mode, select_inside_verts):
    """select_inside_verts() は頂点モードで、範囲内の頂点を SET で選択する関数"""
    ts = context.tool_settings
    orig_mode = tuple(ts.mesh_select_mode)
    objects = [o for o in context.objects_in_mode_unique_data if o.type == 'MESH']

    saved = {}
    for obj in objects:
        bm = bmesh.from_edit_mesh(obj.data)
        bm.verts.index_update()
        bm.edges.index_update()
        bm.faces.index_update()
        history = [(type(elem).__name__, elem.index) for elem in bm.select_history]
        saved[obj.name] = (
            [v.select for v in bm.verts],
            [e.select for e in bm.edges],
            [f.select for f in bm.faces],
            history,
        )

    ts.mesh_select_mode = (True, False, False)
    with SelectThrough(context):
        select_inside_verts()
    inside = {}
    for obj in objects:
        bm = bmesh.from_edit_mesh(obj.data)
        inside[obj.name] = [v.select for v in bm.verts]
    ts.mesh_select_mode = orig_mode

    use_vert, use_edge, use_face = orig_mode
    for obj in objects:
        bm = bmesh.from_edit_mesh(obj.data)
        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()
        bm.faces.ensure_lookup_table()
        vert_sel, edge_sel, face_sel, history = saved[obj.name]
        vin = inside[obj.name]

        final_verts = []
        final_edges = []
        final_faces = []
        if use_vert:
            for v in bm.verts:
                target = vin[v.index] and not v.hide
                if combine(vert_sel[v.index], target, mode):
                    final_verts.append(v)
        if use_edge:
            for e in bm.edges:
                target = (not e.hide) and all(vin[v.index] for v in e.verts)
                if combine(edge_sel[e.index], target, mode):
                    final_edges.append(e)
        if use_face:
            for f in bm.faces:
                target = (not f.hide) and all(vin[v.index] for v in f.verts)
                if combine(face_sel[f.index], target, mode):
                    final_faces.append(f)

        for f in bm.faces:
            f.select = False
        for e in bm.edges:
            e.select = False
        for v in bm.verts:
            v.select = False

        for v in final_verts:
            v.select_set(True)
        for e in final_edges:
            e.select_set(True)
        for f in final_faces:
            f.select_set(True)

        select_mode = set()
        if use_vert:
            select_mode.add('VERT')
        if use_edge:
            select_mode.add('EDGE')
        if use_face:
            select_mode.add('FACE')
        bm.select_mode = select_mode
        bm.select_flush_mode()

        bm.select_history.clear()
        sequences = {"BMVert": bm.verts, "BMEdge": bm.edges, "BMFace": bm.faces}
        for kind, index in history:
            seq = sequences.get(kind)
            if seq is None or index >= len(seq):
                continue
            elem = seq[index]
            if elem.select:
                bm.select_history.add(elem)

        bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)
    return {'FINISHED'}


def enclosed_lasso(context, points, mode):
    path = [{"name": "", "loc": p, "time": 0.0} for p in points]
    if context.mode != 'EDIT_MESH':
        return bpy.ops.view3d.select_lasso(path=path, mode=mode)
    return enclosed_select(context, mode, lambda: bpy.ops.view3d.select_lasso(path=path, mode='SET'))


def enclosed_box(context, xmin, xmax, ymin, ymax, mode):
    rect = dict(xmin=int(xmin), xmax=int(xmax), ymin=int(ymin), ymax=int(ymax), wait_for_input=False)
    if context.mode != 'EDIT_MESH':
        return bpy.ops.view3d.select_box(mode=mode, **rect)
    return enclosed_select(context, mode, lambda: bpy.ops.view3d.select_box(mode='SET', **rect))


def draw_outline(coords):
    shader = gpu.shader.from_builtin('UNIFORM_COLOR')
    batch = batch_for_shader(shader, 'LINE_STRIP', {"pos": coords})
    gpu.state.blend_set('ALPHA')
    gpu.state.line_width_set(3.0)
    shader.uniform_float("color", (0.0, 0.0, 0.0, 0.6))
    batch.draw(shader)
    gpu.state.line_width_set(1.0)
    shader.uniform_float("color", (1.0, 1.0, 1.0, 0.9))
    batch.draw(shader)
    gpu.state.blend_set('NONE')


def draw_lasso(op):
    if len(op.points) < 2:
        return
    draw_outline(list(op.points) + [op.points[0]])


def draw_box(op):
    (x0, y0), (x1, y1) = op.start, op.end
    draw_outline([(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)])


def press_position(context, event):
    region = context.region
    x = getattr(event, "mouse_prev_press_x", event.mouse_x) - region.x
    y = getattr(event, "mouse_prev_press_y", event.mouse_y) - region.y
    return (x, y)


class GestureOperatorBase:
    """ドラッグ中に枠を描き、ボタンを離したら finish_gesture() を呼ぶ共通処理"""

    draw_function = None

    @classmethod
    def poll(cls, context):
        return context.area is not None and context.area.type == 'VIEW_3D'

    def start_gesture(self, context):
        self.handle = bpy.types.SpaceView3D.draw_handler_add(type(self).draw_function, (self,), 'WINDOW',
                                                             'POST_PIXEL')
        context.window_manager.modal_handler_add(self)
        context.area.tag_redraw()
        return {'RUNNING_MODAL'}

    def end_gesture(self, context):
        if self.handle is not None:
            bpy.types.SpaceView3D.draw_handler_remove(self.handle, 'WINDOW')
            self.handle = None
        context.area.tag_redraw()

    def modal(self, context, event):
        if event.type in {'MOUSEMOVE', 'INBETWEEN_MOUSEMOVE'}:
            self.update_gesture(context, (event.mouse_region_x, event.mouse_region_y))
            context.area.tag_redraw()
            return {'RUNNING_MODAL'}
        if event.type == 'LEFTMOUSE' and event.value == 'RELEASE':
            self.end_gesture(context)
            return self.finish_gesture(context)
        if event.type in {'ESC', 'RIGHTMOUSE'}:
            self.end_gesture(context)
            return {'CANCELLED'}
        return {'RUNNING_MODAL'}


class VIEW3D_OT_enclosed_lasso_select(GestureOperatorBase, bpy.types.Operator):
    """投げ縄で完全に囲んだ頂点・辺・面だけを選択する"""
    bl_idname = "view3d.enclosed_lasso_select"
    bl_label = "Enclosed Lasso Select"
    bl_options = {'REGISTER', 'UNDO'}

    mode: bpy.props.EnumProperty(name="Mode", items=MODE_ITEMS, default='SET')
    draw_function = draw_lasso

    def invoke(self, context, event):
        self.points = [press_position(context, event), (event.mouse_region_x, event.mouse_region_y)]
        return self.start_gesture(context)

    def update_gesture(self, context, point):
        last = self.points[-1]
        if abs(point[0] - last[0]) + abs(point[1] - last[1]) >= 2:
            self.points.append(point)

    def finish_gesture(self, context):
        if len(self.points) < 3:
            return {'CANCELLED'}
        enclosed_lasso(context, self.points, self.mode)
        return {'FINISHED'}


class VIEW3D_OT_enclosed_box_select(GestureOperatorBase, bpy.types.Operator):
    """ボックスで完全に囲んだ頂点・辺・面だけを選択する"""
    bl_idname = "view3d.enclosed_box_select"
    bl_label = "Enclosed Box Select"
    bl_options = {'REGISTER', 'UNDO'}

    mode: bpy.props.EnumProperty(name="Mode", items=MODE_ITEMS, default='SET')
    draw_function = draw_box

    def invoke(self, context, event):
        self.start = press_position(context, event)
        self.end = (event.mouse_region_x, event.mouse_region_y)
        return self.start_gesture(context)

    def update_gesture(self, context, point):
        self.end = point

    def finish_gesture(self, context):
        (x0, y0), (x1, y1) = self.start, self.end
        if abs(x1 - x0) < 2 or abs(y1 - y0) < 2:
            return {'CANCELLED'}
        enclosed_box(context, min(x0, x1), max(x0, x1), min(y0, y1), max(y0, y1), self.mode)
        return {'FINISHED'}


CLASSES = (VIEW3D_OT_enclosed_lasso_select, VIEW3D_OT_enclosed_box_select)


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
