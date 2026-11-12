"""
3D ビューに浮かべて表示するパネルの共通部品。

継承して cells() と on_press() を実装する。タイトルバーのドラッグで移動でき、
位置はアドオン設定（preferences.py）に保存される。
"""

import blf
import bpy
import gpu
from gpu_extras.batch import batch_for_shader

from .preferences import get_prefs

TITLE_HEIGHT = 18
GAP = 2
PANEL_COLOR = (0.12, 0.12, 0.12, 0.85)
TITLE_COLOR = (0.22, 0.22, 0.22, 0.95)
TITLE_TEXT_COLOR = (0.9, 0.9, 0.9, 1.0)
BUTTON_COLOR = (0.28, 0.28, 0.28, 1.0)
BUTTON_HOVER_COLOR = (0.42, 0.42, 0.42, 1.0)
BUTTON_ON_COLOR = (0.20, 0.45, 0.60, 1.0)
PANEL_SCREEN_NAME = "BlenderCustom Panel"
VISIBLE_MODES = {'OBJECT', 'EDIT_MESH', 'EDIT_CURVE', 'EDIT_CURVES', 'EDIT_ARMATURE', 'EDIT_LATTICE',
                 'EDIT_METABALL', 'EDIT_SURFACE', 'EDIT_TEXT', 'POSE', 'SCULPT'}


def show_status(text, seconds=2.0):
    """メインウィンドウ下部のステータスバーに、一時的にメッセージを出す"""
    workspace = bpy.context.workspace
    if workspace is None:
        return
    workspace.status_text_set(text)

    def clear():
        try:
            workspace.status_text_set(None)
        except ReferenceError:
            pass
        return None

    bpy.app.timers.register(clear, first_interval=seconds)


def is_panel_screen(screen):
    """パネル用ウィンドウの画面か（同名があると Blender が「.001」などを付けるので前方一致で判定）"""
    return screen is not None and screen.name.startswith(PANEL_SCREEN_NAME)


class Cell:
    """パネルの 1 ボタン分の表示内容"""

    def __init__(self, label, text_color=(0.95, 0.95, 0.95, 1.0), font_size=11, is_on=False):
        self.label = label
        self.text_color = text_color
        self.font_size = font_size
        self.is_on = is_on


def draw_rect(rect, color):
    x, y, w, h = rect
    shader = gpu.shader.from_builtin('UNIFORM_COLOR')
    coords = [(x, y), (x + w, y), (x + w, y + h), (x, y), (x + w, y + h), (x, y + h)]
    batch = batch_for_shader(shader, 'TRIS', {"pos": coords})
    shader.uniform_float("color", color)
    batch.draw(shader)


def draw_text_centered(rect, text, size, color):
    x, y, w, h = rect
    blf.size(0, size)
    tw, th = blf.dimensions(0, text)
    blf.position(0, x + (w - tw) / 2, y + (h - th) / 2, 0)
    blf.color(0, *color)
    blf.draw(0, text)


def inside(rect, x, y):
    rx, ry, rw, rh = rect
    return rx <= x < rx + rw and ry <= y < ry + rh


def redraw_view3d(window):
    for area in window.screen.areas:
        if area.type == 'VIEW_3D':
            area.tag_redraw()


class FloatingPanel:
    title = ""
    pref_x = ""
    pref_y = ""
    columns = 1
    cell_width = 30
    cell_height = 30

    def __init__(self):
        self.hover = None
        self.drag = None
        self.swallow = False
        self.draw_handle = None

    # --- 継承先で実装する ---------------------------------------------------
    def cells(self, context):
        return []

    def cell_count(self):
        return 0

    def on_press(self, context, window, area, region, index):
        pass

    # --- 配置 ----------------------------------------------------------------
    def layout(self, region, origin=None, total_width=None):
        """origin=(left, top) と total_width を渡すと、その位置・幅で並べる（パネル用ウィンドウ向け）"""
        scale = bpy.context.preferences.system.ui_scale
        gap = int(GAP * scale)
        title = int(TITLE_HEIGHT * scale)
        if total_width is None:
            cell_w = int(self.cell_width * scale)
        else:
            cell_w = int((total_width - (self.columns + 1) * gap) / self.columns)
        cell_h = int(self.cell_height * scale)
        count = self.cell_count()
        rows = (count + self.columns - 1) // self.columns
        width = self.columns * cell_w + (self.columns + 1) * gap
        height = title + rows * cell_h + (rows + 1) * gap
        if origin is None:
            prefs = get_prefs()
            left = getattr(prefs, self.pref_x)
            top = region.height - getattr(prefs, self.pref_y)
        else:
            left, top = origin
        cells = []
        for index in range(count):
            row, col = divmod(index, self.columns)
            x = left + gap + col * (cell_w + gap)
            y = top - title - gap - (row + 1) * cell_h - row * gap
            cells.append((x, y, cell_w, cell_h))
        return {"panel": (left, top - height, width, height), "title": (left, top - title, width, title),
                "cells": cells}

    def is_visible(self, context, screen, area):
        """3D ビュー内に浮かべて表示するか（パネル用ウィンドウは別に描くので対象外）"""
        if not get_prefs().show_in_viewport:
            return False
        if is_panel_screen(screen):
            return False
        if context.mode not in VISIBLE_MODES:
            return False
        space = area.spaces.active
        return space.type == 'VIEW_3D' and space.overlay.show_overlays

    def hit_test(self, context, window, mouse_x, mouse_y):
        for area in window.screen.areas:
            if area.type != 'VIEW_3D':
                continue
            for region in area.regions:
                if region.type != 'WINDOW':
                    continue
                lx = mouse_x - region.x
                ly = mouse_y - region.y
                if not (0 <= lx < region.width and 0 <= ly < region.height):
                    continue
                if not self.is_visible(context, window.screen, area):
                    return None
                layout = self.layout(region)
                if not inside(layout["panel"], lx, ly):
                    return None
                if inside(layout["title"], lx, ly):
                    return area, region, ("TITLE", None)
                for index, rect in enumerate(layout["cells"]):
                    if inside(rect, lx, ly):
                        return area, region, ("CELL", index)
                return area, region, ("PANEL", None)
        return None

    # --- 描画 ----------------------------------------------------------------
    def draw(self):
        context = bpy.context
        region = context.region
        area = context.area
        if region is None or area is None or region.type != 'WINDOW':
            return
        if not self.is_visible(context, context.screen, area):
            return
        self.draw_layout(context, self.layout(region), self.hover)

    def draw_layout(self, context, layout, hover):
        scale = context.preferences.system.ui_scale
        try:
            cells = self.cells(context)
        except Exception:
            cells = [Cell("(エラー)") for _ in layout["cells"]]
        gpu.state.blend_set('ALPHA')
        draw_rect(layout["panel"], PANEL_COLOR)
        draw_rect(layout["title"], TITLE_COLOR)
        draw_text_centered(layout["title"], self.title, int(10 * scale), TITLE_TEXT_COLOR)
        for index, (rect, cell) in enumerate(zip(layout["cells"], cells)):
            if hover == index:
                color = BUTTON_HOVER_COLOR
            elif cell.is_on:
                color = BUTTON_ON_COLOR
            else:
                color = BUTTON_COLOR
            draw_rect(rect, color)
            draw_text_centered(rect, cell.label, int(cell.font_size * scale), cell.text_color)
        gpu.state.blend_set('NONE')

    # --- マウス操作（listener から呼ばれる） ------------------------------------
    def handle_event(self, context, event):
        window = context.window
        if event.type in {'MOUSEMOVE', 'INBETWEEN_MOUSEMOVE'}:
            if self.drag is not None:
                start_x, start_y, pos_x, pos_y = self.drag
                prefs = get_prefs()
                setattr(prefs, self.pref_x, pos_x + (event.mouse_x - start_x))
                setattr(prefs, self.pref_y, pos_y - (event.mouse_y - start_y))
                redraw_view3d(window)
                return {'RUNNING_MODAL'}
            hit = self.hit_test(context, window, event.mouse_x, event.mouse_y)
            new_hover = hit[2][1] if hit is not None and hit[2][0] == "CELL" else None
            if new_hover != self.hover:
                self.hover = new_hover
                redraw_view3d(window)
            return None

        if event.type != 'LEFTMOUSE':
            return None
        if event.value == 'PRESS':
            hit = self.hit_test(context, window, event.mouse_x, event.mouse_y)
            if hit is None:
                return None
            area, region, (kind, index) = hit
            self.swallow = True
            if kind == "TITLE":
                prefs = get_prefs()
                self.drag = (event.mouse_x, event.mouse_y, getattr(prefs, self.pref_x), getattr(prefs, self.pref_y))
            elif kind == "CELL":
                self.on_press(context, window, area, region, index)
                redraw_view3d(window)
            return {'RUNNING_MODAL'}
        if event.value == 'RELEASE':
            self.drag = None
            if self.swallow:
                self.swallow = False
                return {'RUNNING_MODAL'}
            return None
        if self.swallow and event.value in {'CLICK', 'CLICK_DRAG', 'DOUBLE_CLICK'}:
            return {'RUNNING_MODAL'}
        return None

    # --- 登録 ----------------------------------------------------------------
    def register_draw(self):
        self.draw_handle = bpy.types.SpaceView3D.draw_handler_add(self.draw, (), 'WINDOW', 'POST_PIXEL')

    def unregister_draw(self):
        if self.draw_handle is not None:
            bpy.types.SpaceView3D.draw_handler_remove(self.draw_handle, 'WINDOW')
            self.draw_handle = None
