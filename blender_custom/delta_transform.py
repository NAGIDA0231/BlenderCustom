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
SNAP_DISTANCE = 0.01  # Shift を押しているときの移動の刻み（m）
SNAP_SCALE = 0.01  # Shift を押しているときの拡大縮小の刻み（倍率）
PIXELS_PER_STEP = 5  # Shift を押しているとき、マウスを何ピクセル動かすと 1 刻み進むか


def steps(pixels, speed):
    """Shift を押しているときの刻み数（速度の設定も反映する）"""
    return round(pixels * speed / PIXELS_PER_STEP)
UNDO_NAMES = {"translate": "移動", "resize": "拡大縮小", "rotate": "回転"}
# Blender の軸 → 表示する軸（Edit Panel のボタンと同じ Unity の呼び方。Y が上下、Z が奥行き）
DISPLAY_AXIS = {'X': 'X', 'Y': 'Z', 'Z': 'Y'}


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
        self.base = Matrix.Identity(4)
        self.current = Matrix.Identity(4)

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
                # bm への参照を持ち続ける。手放すと Python 側の BMesh が解放され、頂点が無効になる
                self.edit_meshes.append((obj, bm, verts, originals))
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
        """snap=True（Shift）のとき、移動は 0.01 m、拡大縮小は 0.01 倍、回転は 15° 刻みにする。
        移動と拡大縮小は、マウスを PIXELS_PER_STEP ピクセル動かすごとに 1 刻み進む（細かく合わせやすくするため）"""
        if self.kind == "translate":
            if self.axis is None:
                if snap:
                    offset = (self.view_right * steps(dx, speed) + self.view_up * steps(dy, speed)) * SNAP_DISTANCE
                else:
                    offset = (self.view_right * dx + self.view_up * dy) * self.units_per_pixel * speed
            else:
                axis_vector = AXIS_VECTORS[self.axis]
                pixels = self.screen_amount(axis_vector, dx, dy)
                if snap:
                    amount = steps(pixels, speed) * SNAP_DISTANCE
                else:
                    amount = pixels * self.units_per_pixel * speed
                offset = axis_vector * amount
            return Matrix.Translation(offset)
        if self.kind == "resize":
            if snap:
                factor = max(SNAP_SCALE, 1.0 + steps(dx, speed) * SNAP_SCALE)
            else:
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
        for obj, _, verts, originals in self.edit_meshes:
            world = obj.matrix_world
            local = world.inverted() @ matrix @ world
            for vert, co in zip(verts, originals):
                vert.co = local @ co
            bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)
        self.area.tag_redraw()

    def update(self, dx, dy, speed, snap=False):
        """dx, dy は基準の位置（ドラッグの開始、または rebase した位置）からのマウスの移動量"""
        self.current = self.build_matrix(dx, dy, speed, snap) @ self.base
        self.apply_matrix(self.current)
        self.area.header_text_set(self.describe(snap))

    def describe(self, snap):
        """3D ビューの上部に出す、今の変形量の説明（例: 移動 X: +0.050 m）"""
        name = UNDO_NAMES.get(self.kind, self.kind)
        label = "全体" if self.axis is None else DISPLAY_AXIS[self.axis]
        matrix = self.current
        if self.kind == "translate":
            offset = matrix.translation
            if self.axis is None:
                value = f"{offset.length:.3f} m"
            else:
                value = f"{offset.dot(AXIS_VECTORS[self.axis]):+.3f} m"
            step = f"{SNAP_DISTANCE} m"
        elif self.kind == "resize":
            scale = matrix.to_scale()
            factor = scale.x if self.axis is None else scale["XYZ".index(self.axis)]
            value = f"{factor:.2f} 倍"
            step = f"{SNAP_SCALE} 倍"
        else:
            rotation = matrix.to_quaternion()
            axis_vector = self.view_dir if self.axis is None else AXIS_VECTORS[self.axis]
            degrees = math.degrees(rotation.angle)
            if rotation.axis.dot(axis_vector) < 0.0:
                degrees = -degrees
            value = f"{degrees:+.1f}°"
            step = f"{SNAP_DEGREES:.0f}°"
        snap_text = f"Shift: {step} 刻み中" if snap else f"Shift で {step} 刻み"
        return f"Edit Panel  {name} {label}: {value}    （{snap_text}）"

    def clear_header(self):
        self.area.header_text_set(None)

    def rebase(self):
        """今の変形を基準にする。ドラッグ中に Shift を押した・離したとき、動きが飛ばないようにする"""
        self.base = self.current.copy()

    def cancel(self):
        self.clear_header()
        self.apply_matrix(Matrix.Identity(4))

    def finish(self):
        self.clear_header()
        with bpy.context.temp_override(window=self.window, area=self.area, region=self.region):
            bpy.ops.ed.undo_push(message="Edit Panel: " + UNDO_NAMES.get(self.kind, self.kind))
