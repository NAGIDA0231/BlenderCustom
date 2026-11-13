"""
辺消しモード: 編集モードで、クリックした辺を溶解する（穴は開けず、両側の面を 1 枚にする）。

QuickPanel の「辺消しモード」ボタンで始め、もう一度押すと終わる。右クリックか Esc でも終わる。右ドラッグは視点の回転。
メッシュが変わっても安全なように、BMesh の要素は保持せず、イベントのたびに読み直す
（保持した要素を Undo などの後に使うと Blender が落ちることがあるため）。
"""

import bmesh
import bpy
import gpu
from bpy_extras.view3d_utils import location_3d_to_region_2d
from gpu_extras.batch import batch_for_shader
from mathutils import Vector

from . import hover_highlight
from .floating_panel import show_status
from .knife_orbit import BLENDERCUSTOM_OT_knife_orbit

PICK_RADIUS = 12.0
DRAG_THRESHOLD = 3
HIGHLIGHT_COLOR = (1.0, 0.3, 0.3, 1.0)
HEADER_TEXT = "辺消しモード: 辺をクリックで溶解 / 右ドラッグで回転 / 右クリック・Esc で終了"
PASS_THROUGH_EVENTS = {'MIDDLEMOUSE', 'WHEELUPMOUSE', 'WHEELDOWNMOUSE', 'TRACKPADPAN', 'TRACKPADZOOM',
                       'MOUSEROTATE', 'MOUSESMARTZOOM', 'NDOF_MOTION'}
# 視点の切り替え（F1〜F3 の正面・側面・頭上など）は通す
VIEW_KEYS = {'F1', 'F2', 'F3'}


def distance_to_segment(p, a, b):
    ab = b - a
    length_sq = ab.length_squared
    if length_sq == 0.0:
        return (p - a).length
    t = max(0.0, min(1.0, (p - a).dot(ab) / length_sq))
    return (p - (a + ab * t)).length


def find_edge(context, region, rv3d, mouse):
    """マウスに一番近い、見えている辺を (オブジェクト名, 辺の番号, ワールド座標の両端) で返す。
    辺の番号は bm.edges を順に数えた位置（BMesh の index は書き換えない）"""
    radius = PICK_RADIUS * context.preferences.system.ui_scale
    candidates = []
    for obj in context.objects_in_mode_unique_data:
        if obj.type != 'MESH':
            continue
        mw = obj.matrix_world
        bm = bmesh.from_edit_mesh(obj.data)
        for number, edge in enumerate(bm.edges):
            if edge.hide:
                continue
            a = mw @ edge.verts[0].co
            b = mw @ edge.verts[1].co
            pa = location_3d_to_region_2d(region, rv3d, a)
            pb = location_3d_to_region_2d(region, rv3d, b)
            if pa is None or pb is None:
                continue
            distance = distance_to_segment(mouse, pa, pb)
            if distance <= radius:
                candidates.append((distance, obj.name, number, a.copy(), b.copy()))
    candidates.sort(key=lambda c: c[0])
    xray = hover_highlight.is_xray(context)
    for _, name, number, a, b in candidates:
        middle = (a + b) / 2
        screen = location_3d_to_region_2d(region, rv3d, middle)
        if xray or screen is None or hover_highlight.is_point_visible(context, region, rv3d, middle, screen):
            return name, number, (a, b)
    return None


def dissolve_edge(context, object_name, number):
    obj = bpy.data.objects.get(object_name)
    if obj is None or obj.mode != 'EDIT':
        return False
    bm = bmesh.from_edit_mesh(obj.data)
    edges = list(bm.edges)
    if number >= len(edges):
        return False
    # use_verts: 溶解したあとに残る、辺が 2 本だけの頂点も消す（ナイフで作った途中の頂点など）
    bmesh.ops.dissolve_edges(bm, edges=[edges[number]], use_verts=True, use_face_split=False)
    bmesh.update_edit_mesh(obj.data, loop_triangles=True, destructive=True)
    return True


# 動いている辺消しモード（重ねて始めない・ボタンで終了するために使う）
ACTIVE = set()


def is_active():
    return len(ACTIVE) > 0


def stop_all():
    """動いている辺消しモードをすべて終える（表示はすぐ消し、モード自体は次のイベントで終わる）"""
    for op in list(ACTIVE):
        op.stop_requested = True
        op.finish()


def draw_hover_edge(op):
    if op.hover is None:
        return
    a, b = op.hover[2]
    region = bpy.context.region
    shader = gpu.shader.from_builtin('POLYLINE_UNIFORM_COLOR')
    shader.uniform_float("viewportSize", (region.width, region.height))
    shader.uniform_float("lineWidth", 5.0)
    shader.uniform_float("color", HIGHLIGHT_COLOR)
    batch = batch_for_shader(shader, 'LINES', {"pos": [a, b]})
    gpu.state.depth_test_set('NONE')
    gpu.state.blend_set('ALPHA')
    batch.draw(shader)
    gpu.state.blend_set('NONE')


class BLENDERCUSTOM_OT_edge_eraser(bpy.types.Operator):
    """辺消しモード: クリックした辺を溶解する（右クリックか Esc で終了）"""
    bl_idname = "blendercustom.edge_eraser"
    bl_label = "辺消しモード"

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH' and context.area is not None and context.area.type == 'VIEW_3D'

    def invoke(self, context, event):
        self.area = context.area
        self.region = context.region
        self.rv3d = context.region_data
        self.hover = None
        self.right_press = None
        self.orbiting = False
        self.stop_requested = False
        self.handle = bpy.types.SpaceView3D.draw_handler_add(draw_hover_edge, (self,), 'WINDOW', 'POST_VIEW')
        self.area.header_text_set(HEADER_TEXT)
        context.window_manager.modal_handler_add(self)
        ACTIVE.add(self)
        return {'RUNNING_MODAL'}

    def finish(self):
        ACTIVE.discard(self)
        self.hover = None
        if self.handle is not None:
            bpy.types.SpaceView3D.draw_handler_remove(self.handle, 'WINDOW')
            self.handle = None
        try:
            self.area.header_text_set(None)
            self.area.tag_redraw()
        except ReferenceError:
            pass

    def cancel(self, context):
        self.finish()

    def mouse_in_region(self, event):
        region = self.region
        return Vector((event.mouse_x - region.x, event.mouse_y - region.y))

    def update_hover(self, context, event):
        mouse = self.mouse_in_region(event)
        inside = 0 <= mouse.x < self.region.width and 0 <= mouse.y < self.region.height
        with context.temp_override(area=self.area, region=self.region):
            self.hover = find_edge(bpy.context, self.region, self.rv3d, mouse) if inside else None
        self.area.tag_redraw()

    def modal(self, context, event):
        if self.stop_requested:
            return {'CANCELLED'}
        if context.mode != 'EDIT_MESH':
            self.finish()
            return {'CANCELLED'}

        # 右ボタン: ドラッグで視点の回転、動かさずに離したら終了
        if self.right_press is not None:
            if event.type in {'MOUSEMOVE', 'INBETWEEN_MOUSEMOVE'}:
                x, y = event.mouse_x, event.mouse_y
                if not self.orbiting:
                    start_x, start_y = self.right_press
                    if abs(x - start_x) + abs(y - start_y) < DRAG_THRESHOLD:
                        return {'RUNNING_MODAL'}
                    self.orbiting = True
                    self.last = self.right_press
                BLENDERCUSTOM_OT_knife_orbit.rotate(self, x - self.last[0], y - self.last[1])
                self.last = (x, y)
                return {'RUNNING_MODAL'}
            if event.type == 'RIGHTMOUSE' and event.value == 'RELEASE':
                orbited = self.orbiting
                self.right_press = None
                self.orbiting = False
                if orbited:
                    return {'RUNNING_MODAL'}
                self.finish()
                return {'FINISHED'}
            return {'RUNNING_MODAL'}

        if event.type in {'MOUSEMOVE', 'INBETWEEN_MOUSEMOVE'}:
            self.update_hover(context, event)
            return {'PASS_THROUGH'}
        if event.type == 'RIGHTMOUSE' and event.value == 'PRESS':
            self.right_press = (event.mouse_x, event.mouse_y)
            return {'RUNNING_MODAL'}
        if event.type == 'ESC' and event.value == 'PRESS':
            self.finish()
            return {'FINISHED'}
        if event.type == 'LEFTMOUSE':
            if event.value == 'PRESS':
                self.update_hover(context, event)
                if self.hover is not None:
                    name, number, _ = self.hover
                    if dissolve_edge(context, name, number):
                        with context.temp_override(area=self.area, region=self.region):
                            bpy.ops.ed.undo_push(message="辺を溶解")
                    self.update_hover(context, event)
            return {'RUNNING_MODAL'}
        if event.type in PASS_THROUGH_EVENTS or event.type in VIEW_KEYS or event.type.startswith('NUMPAD_'):
            return {'PASS_THROUGH'}
        if event.type in {'Z'} and event.ctrl:
            # Undo / Redo は通す（辺は毎回読み直すので安全）
            return {'PASS_THROUGH'}
        return {'RUNNING_MODAL'}


def toggle(context):
    """QuickPanel から呼ぶ（3D ビューのコンテキストで）。動いていれば終え、止まっていれば始める"""
    if is_active():
        stop_all()
        show_status("辺消しモードを終了しました")
        return
    if context.mode != 'EDIT_MESH':
        show_status("辺消し: 編集モードで使ってください")
        return
    bpy.ops.blendercustom.edge_eraser('INVOKE_DEFAULT')


def register():
    bpy.utils.register_class(BLENDERCUSTOM_OT_edge_eraser)


def unregister():
    stop_all()
    bpy.utils.unregister_class(BLENDERCUSTOM_OT_edge_eraser)
