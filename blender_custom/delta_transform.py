"""
マウスを動かした量で、選択中のオブジェクト／頂点を移動・拡大縮小・回転する。

パネル用の別ウィンドウから使う（Blender 標準の変形は、別のウィンドウの 3D ビューを操作できないため）。
動かしている間はその場で反映し、finish() で確定（Undo に 1 回分積む）、cancel() で元に戻す。
"""

import math

import bmesh
import bpy
from mathutils import Matrix, Vector

AXIS_VECTORS = {'X': Vector((1.0, 0.0, 0.0)), 'Y': Vector((0.0, 1.0, 0.0)), 'Z': Vector((0.0, 0.0, 1.0))}
SCALE_PER_PIXEL = 0.005
DEGREES_PER_PIXEL = 0.5
SNAP_DEGREES = 15.0
UNDO_NAMES = {"translate": "移動", "resize": "拡大縮小", "rotate": "回転"}


class DeltaTransform:
    def __init__(self, kind, axis, view):
        """kind: 'translate' / 'resize' / 'rotate'、axis: 'X' / 'Y' / 'Z' / None、view: (window, area, region)"""
        self.kind = kind
        self.axis = axis
        self.window, self.area, self.region = view
        rv3d = self.area.spaces.active.region_3d
        self.view_right = rv3d.view_rotation @ Vector((1.0, 0.0, 0.0))
        self.view_up = rv3d.view_rotation @ Vector((0.0, 1.0, 0.0))
        self.view_dir = rv3d.view_rotation @ Vector((0.0, 0.0, -1.0))
        self.units_per_pixel = rv3d.view_distance * 2.0 / max(self.region.height, 1)
        self.objects = []
        self.edit_meshes = []

        context = bpy.context
        points = []
        if context.mode == 'EDIT_MESH':
            for obj in context.objects_in_mode_unique_data:
                if obj.type != 'MESH':
                    continue
                bm = bmesh.from_edit_mesh(obj.data)
                verts = [v for v in bm.verts if v.select and not v.hide]
                if not verts:
                    continue
                originals = [v.co.copy() for v in verts]
                self.edit_meshes.append((obj, verts, originals))
                points.extend(obj.matrix_world @ co for co in originals)
        elif context.mode == 'OBJECT':
            for obj in context.selected_editable_objects:
                self.objects.append((obj, obj.matrix_world.copy()))
                points.append(obj.matrix_world.translation.copy())
        self.is_valid = len(points) > 0
        self.pivot = sum(points, Vector()) / len(points) if points else Vector()

    def screen_amount(self, axis_vector, dx, dy):
        """軸の画面上の向きにドラッグした量（軸が画面の奥を向いているときは左右の量）"""
        screen = Vector((self.view_right.dot(axis_vector), self.view_up.dot(axis_vector)))
        if screen.length < 0.2:
            return dx
        screen.normalize()
        return dx * screen.x + dy * screen.y

    def build_matrix(self, dx, dy, speed, snap=False):
        """snap=True のとき、回転は 15° 刻みにする"""
        if self.kind == "translate":
            if self.axis is None:
                offset = (self.view_right * dx + self.view_up * dy) * self.units_per_pixel * speed
            else:
                axis_vector = AXIS_VECTORS[self.axis]
                offset = axis_vector * self.screen_amount(axis_vector, dx, dy) * self.units_per_pixel * speed
            return Matrix.Translation(offset)
        if self.kind == "resize":
            factor = max(0.01, 1.0 + dx * SCALE_PER_PIXEL * speed)
            values = [factor, factor, factor]
            if self.axis is not None:
                values = [1.0, 1.0, 1.0]
                values["XYZ".index(self.axis)] = factor
            core = Matrix.Diagonal((*values, 1.0))
        else:
            degrees = dx * DEGREES_PER_PIXEL * speed
            if snap:
                degrees = round(degrees / SNAP_DEGREES) * SNAP_DEGREES
            angle = math.radians(degrees)
            axis_vector = self.view_dir if self.axis is None else AXIS_VECTORS[self.axis]
            core = Matrix.Rotation(angle, 4, axis_vector)
        return Matrix.Translation(self.pivot) @ core @ Matrix.Translation(-self.pivot)

    def apply_matrix(self, matrix):
        for obj, original in self.objects:
            obj.matrix_world = matrix @ original
        for obj, verts, originals in self.edit_meshes:
            world = obj.matrix_world
            local = world.inverted() @ matrix @ world
            for vert, co in zip(verts, originals):
                vert.co = local @ co
            bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)
        self.area.tag_redraw()

    def update(self, dx, dy, speed, snap=False):
        self.apply_matrix(self.build_matrix(dx, dy, speed, snap))

    def cancel(self):
        self.apply_matrix(Matrix.Identity(4))

    def finish(self):
        with bpy.context.temp_override(window=self.window, area=self.area, region=self.region):
            bpy.ops.ed.undo_push(message="Edit Panel: " + UNDO_NAMES.get(self.kind, self.kind))
