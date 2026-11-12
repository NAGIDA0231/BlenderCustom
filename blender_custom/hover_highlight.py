"""
編集モードで、マウスを乗せた頂点・辺・面を黄色くハイライトする。

対象は今の選択モードに合わせる。裏向きの面は無視して、その奥の表向きの面を対象にする。
"""

import bmesh
import bpy
import gpu
from bpy.app.handlers import persistent
from bpy_extras.view3d_utils import location_3d_to_region_2d, region_2d_to_origin_3d, region_2d_to_vector_3d
from gpu_extras.batch import batch_for_shader
from mathutils import Vector
from mathutils.bvhtree import BVHTree

from . import listener

HIGHLIGHT_COLOR = (1.0, 0.85, 0.1)
FACE_FILL_ALPHA = 0.25
VERT_PICK_RADIUS = 25.0
EDGE_PICK_RADIUS = 10.0
MAX_BACKFACE_SKIPS = 64
RAY_STEP = 1e-4


class HoverState:
    mouse_x = -1
    mouse_y = -1
    draw_handle = None
    cache = {}
    dirty = True


STATE = HoverState()


def build_cache(obj):
    bm = bmesh.from_edit_mesh(obj.data)
    bm.verts.index_update()
    bm.faces.index_update()
    bm.verts.ensure_lookup_table()
    bm.faces.ensure_lookup_table()
    coords = [v.co.copy() for v in bm.verts]
    polys = []
    face_map = []
    face_verts = {}
    face_edges = {}
    for f in bm.faces:
        if f.hide:
            continue
        indices = [v.index for v in f.verts]
        polys.append(indices)
        face_map.append(f.index)
        face_verts[f.index] = indices
        face_edges[f.index] = [(e.verts[0].index, e.verts[1].index) for e in f.edges]
    tris = {}
    for loops in bm.calc_loop_triangles():
        face = loops[0].face
        if face.hide:
            continue
        tris.setdefault(face.index, []).append([loop.vert.index for loop in loops])
    bvh = BVHTree.FromPolygons(coords, polys, all_triangles=False) if polys else None
    return {"coords": coords, "bvh": bvh, "face_map": face_map, "vert_hidden": [v.hide for v in bm.verts],
            "face_verts": face_verts, "face_edges": face_edges, "tris": tris}


def get_cache(obj):
    if STATE.dirty:
        STATE.cache.clear()
        STATE.dirty = False
    data = STATE.cache.get(obj.name)
    if data is None:
        data = build_cache(obj)
        STATE.cache[obj.name] = data
    return data


def distance_to_segment(p, a, b):
    ab = b - a
    length_sq = ab.length_squared
    if length_sq == 0.0:
        return (p - a).length
    t = max(0.0, min(1.0, (p - a).dot(ab) / length_sq))
    return (p - (a + ab * t)).length


def cast_front_face(bvh, origin, direction, is_mirrored):
    """裏向きの面は無視して、レイが最初に当たる表向きの面を返す"""
    ray_origin = origin.copy()
    for _ in range(MAX_BACKFACE_SKIPS):
        location, normal, index, _ = bvh.ray_cast(ray_origin, direction)
        if location is None:
            return None, None
        facing = normal.dot(direction)
        if is_mirrored:
            facing = -facing
        if facing < 0.0:
            return location, index
        ray_origin = location + direction * RAY_STEP
    return None, None


def is_xray(context):
    space = context.space_data
    if space is None or space.type != 'VIEW_3D':
        return False
    shading = space.shading
    if shading.type == 'WIREFRAME':
        return shading.show_xray_wireframe
    return shading.show_xray


def edit_mesh_caches(context):
    for obj in context.objects_in_mode_unique_data:
        if obj.type == 'MESH':
            yield obj, get_cache(obj)


def is_point_visible(context, region, rv3d, world_point, screen_point):
    """頂点が手前の（表向きの）面に隠れていないか"""
    origin = region_2d_to_origin_3d(region, rv3d, screen_point)
    to_point = world_point - origin
    distance = to_point.length
    if distance == 0.0:
        return True
    direction = to_point / distance
    margin = distance * 1e-3 + 1e-4
    for obj, data in edit_mesh_caches(context):
        if data["bvh"] is None:
            continue
        mw = obj.matrix_world
        inv = mw.inverted()
        local_dir = (inv.to_3x3() @ direction).normalized()
        location, _ = cast_front_face(data["bvh"], inv @ origin, local_dir, mw.determinant() < 0.0)
        if location is not None and ((mw @ location) - origin).length < distance - margin:
            return False
    return True


def nearest_visible_vertex(context, region, rv3d, mouse, radius):
    """マウスから radius ピクセル以内で一番近い、見えている頂点（面に関係なく探す）"""
    candidates = []
    for obj, data in edit_mesh_caches(context):
        mw = obj.matrix_world
        hidden = data["vert_hidden"]
        for index, co in enumerate(data["coords"]):
            if hidden[index]:
                continue
            world = mw @ co
            screen = location_3d_to_region_2d(region, rv3d, world)
            if screen is None:
                continue
            distance = (screen - mouse).length
            if distance <= radius:
                candidates.append((distance, obj, data, index, world, screen))
    candidates.sort(key=lambda c: c[0])
    xray = is_xray(context)
    for _, obj, data, index, world, screen in candidates:
        if xray or is_point_visible(context, region, rv3d, world, screen):
            return obj, data, index
    return None


def find_hover(context, region, rv3d, mouse):
    use_vert, use_edge, use_face = context.tool_settings.mesh_select_mode
    if use_vert:
        radius = VERT_PICK_RADIUS * context.preferences.system.ui_scale
        vertex = nearest_visible_vertex(context, region, rv3d, mouse, radius)
        if vertex is not None:
            obj, data, index = vertex
            return ("VERT", obj, data, index)

    origin = region_2d_to_origin_3d(region, rv3d, mouse)
    direction = region_2d_to_vector_3d(region, rv3d, mouse)
    best = None
    for obj in context.objects_in_mode_unique_data:
        if obj.type != 'MESH':
            continue
        data = get_cache(obj)
        if data["bvh"] is None:
            continue
        mw = obj.matrix_world
        inv = mw.inverted()
        local_origin = inv @ origin
        local_dir = (inv.to_3x3() @ direction).normalized()
        location, index = cast_front_face(data["bvh"], local_origin, local_dir, mw.determinant() < 0.0)
        if location is None:
            continue
        world_dist = ((mw @ location) - origin).length
        if best is None or world_dist < best[0]:
            best = (world_dist, obj, data, data["face_map"][index])
    if best is None:
        return None
    _, obj, data, face_index = best
    mw = obj.matrix_world

    def screen(vi):
        return location_3d_to_region_2d(region, rv3d, mw @ data["coords"][vi])

    only_one = (use_vert + use_edge + use_face) == 1

    # 頂点モードだけのときは、近くに頂点がなくても、マウスの下の面で一番近い頂点を出す
    if use_vert and only_one:
        nearest = None
        for vi in data["face_verts"][face_index]:
            p = screen(vi)
            if p is None:
                continue
            d = (p - mouse).length
            if nearest is None or d < nearest[0]:
                nearest = (d, vi)
        if nearest is not None and (only_one or nearest[0] <= VERT_PICK_RADIUS):
            return ("VERT", obj, data, nearest[1])
    if use_edge:
        nearest = None
        for a, b in data["face_edges"][face_index]:
            pa, pb = screen(a), screen(b)
            if pa is None or pb is None:
                continue
            d = distance_to_segment(mouse, pa, pb)
            if nearest is None or d < nearest[0]:
                nearest = (d, (a, b))
        if nearest is not None and (only_one or not use_face or nearest[0] <= EDGE_PICK_RADIUS):
            return ("EDGE", obj, data, nearest[1])
    if use_face:
        return ("FACE", obj, data, face_index)
    return None


def polyline_shader(region, width):
    shader = gpu.shader.from_builtin('POLYLINE_UNIFORM_COLOR')
    shader.uniform_float("viewportSize", (region.width, region.height))
    shader.uniform_float("lineWidth", width)
    return shader


def draw_highlight():
    context = bpy.context
    if context.mode != 'EDIT_MESH':
        return
    region = context.region
    rv3d = context.region_data
    if region is None or rv3d is None:
        return
    mouse = Vector((STATE.mouse_x - region.x, STATE.mouse_y - region.y))
    if not (0 <= mouse.x < region.width and 0 <= mouse.y < region.height):
        return
    try:
        hover = find_hover(context, region, rv3d, mouse)
    except (ReferenceError, KeyError, IndexError):
        STATE.dirty = True
        return
    if hover is None:
        return
    kind, obj, data, target = hover
    mw = obj.matrix_world
    coords = data["coords"]
    color = HIGHLIGHT_COLOR

    gpu.state.blend_set('ALPHA')
    gpu.state.depth_test_set('NONE')
    if kind == 'VERT':
        shader = gpu.shader.from_builtin('POINT_UNIFORM_COLOR')
        gpu.state.point_size_set(12.0)
        batch = batch_for_shader(shader, 'POINTS', {"pos": [mw @ coords[target]]})
        shader.uniform_float("color", (*color, 1.0))
        batch.draw(shader)
        gpu.state.point_size_set(1.0)
    elif kind == 'EDGE':
        a, b = target
        shader = polyline_shader(region, 4.0)
        batch = batch_for_shader(shader, 'LINES', {"pos": [mw @ coords[a], mw @ coords[b]]})
        shader.uniform_float("color", (*color, 1.0))
        batch.draw(shader)
    else:
        fill = gpu.shader.from_builtin('UNIFORM_COLOR')
        tri_coords = [mw @ coords[vi] for tri in data["tris"].get(target, []) for vi in tri]
        if tri_coords:
            batch = batch_for_shader(fill, 'TRIS', {"pos": tri_coords})
            fill.uniform_float("color", (*color, FACE_FILL_ALPHA))
            batch.draw(fill)
        loop = [mw @ coords[vi] for vi in data["face_verts"][target]]
        line_coords = []
        for i in range(len(loop)):
            line_coords.append(loop[i])
            line_coords.append(loop[(i + 1) % len(loop)])
        shader = polyline_shader(region, 2.5)
        batch = batch_for_shader(shader, 'LINES', {"pos": line_coords})
        shader.uniform_float("color", (*color, 1.0))
        batch.draw(shader)
    gpu.state.blend_set('NONE')


def handle_event(context, event):
    """マウス位置を記録して、編集モードなら 3D ビューを再描画する（イベントは消費しない）"""
    if event.type in {'MOUSEMOVE', 'INBETWEEN_MOUSEMOVE'}:
        STATE.mouse_x = event.mouse_x
        STATE.mouse_y = event.mouse_y
        if context.mode == 'EDIT_MESH':
            for area in context.window.screen.areas:
                if area.type == 'VIEW_3D':
                    area.tag_redraw()
    return None


@persistent
def on_depsgraph_update(scene, depsgraph):
    STATE.dirty = True


@persistent
def on_load_post(*args):
    STATE.dirty = True


def register():
    STATE.draw_handle = bpy.types.SpaceView3D.draw_handler_add(draw_highlight, (), 'WINDOW', 'POST_VIEW')
    bpy.app.handlers.depsgraph_update_post.append(on_depsgraph_update)
    bpy.app.handlers.load_post.append(on_load_post)
    listener.add_handler(handle_event)


def unregister():
    listener.remove_handler(handle_event)
    if on_load_post in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(on_load_post)
    if on_depsgraph_update in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(on_depsgraph_update)
    if STATE.draw_handle is not None:
        bpy.types.SpaceView3D.draw_handler_remove(STATE.draw_handle, 'WINDOW')
        STATE.draw_handle = None
