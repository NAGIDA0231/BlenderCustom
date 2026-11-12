"""
QuickPanel と Edit Panel を、Blender の別ウィンドウ（パネル用ウィンドウ）に表示する。

メニュー「ウィンドウ > BlenderCustom パネルを開く」で開く。ウィンドウは小さく作り、
Blender のメインウィンドウの外や別のモニターに置ける。操作はメインウィンドウの 3D ビューに対して行う。

小さいウィンドウは、新しいウィンドウの中で小さいエリアを区切り、そのエリアを切り離して作る
（Python からはウィンドウの大きさを直接指定できないため）。
"""

import bpy
import gpu

from . import edit_panel, quick_panel
from .delta_transform import DeltaTransform
from .floating_panel import PANEL_SCREEN_NAME, draw_rect, inside, is_panel_screen, show_status
from .preferences import get_prefs

WINDOW_WIDTH = 190
WINDOW_HEIGHT = 270
MARGIN = 4
PANEL_SPACING = 6
BACKGROUND_COLOR = (0.09, 0.09, 0.09, 1.0)
CONSUMED_EVENTS = {'LEFTMOUSE', 'MIDDLEMOUSE', 'RIGHTMOUSE', 'WHEELUPMOUSE', 'WHEELDOWNMOUSE', 'TRACKPADPAN',
                   'TRACKPADZOOM', 'MOUSEROTATE', 'MOUSESMARTZOOM', 'MOUSEMOVE', 'INBETWEEN_MOUSEMOVE'}
PANELS = (("quick", quick_panel.PANEL), ("edit", edit_panel.PANEL))


class WindowState:
    hover = None
    drag = None
    draw_handle = None


STATE = WindowState()


def is_panel_window(window):
    return window is not None and is_panel_screen(window.screen)


def main_view():
    """操作対象にするメインウィンドウの 3D ビュー（一番大きいもの）を返す"""
    best = None
    for window in bpy.context.window_manager.windows:
        if is_panel_window(window):
            continue
        for area in window.screen.areas:
            if area.type != 'VIEW_3D':
                continue
            region = next((r for r in area.regions if r.type == 'WINDOW'), None)
            if region is None:
                continue
            size = area.width * area.height
            if best is None or size > best[0]:
                best = (size, (window, area, region))
    return best[1] if best else None


def window_layouts(region):
    """パネル用ウィンドウ内の QuickPanel・Edit Panel の配置"""
    scale = bpy.context.preferences.system.ui_scale
    margin = int(MARGIN * scale)
    width = region.width - margin * 2
    top = region.height - margin
    layouts = []
    for name, panel in PANELS:
        layout = panel.layout(region, origin=(margin, top), total_width=width)
        layouts.append((name, panel, layout))
        top = layout["panel"][1] - int(PANEL_SPACING * scale)
    return layouts


def hit_test(window, mouse_x, mouse_y):
    for area in window.screen.areas:
        if area.type != 'VIEW_3D':
            continue
        region = next((r for r in area.regions if r.type == 'WINDOW'), None)
        if region is None:
            continue
        lx = mouse_x - region.x
        ly = mouse_y - region.y
        if not (0 <= lx < region.width and 0 <= ly < region.height):
            continue
        for name, _, layout in window_layouts(region):
            for index, rect in enumerate(layout["cells"]):
                if inside(rect, lx, ly):
                    return name, index
    return None


def draw_window():
    context = bpy.context
    if not is_panel_screen(context.screen):
        return
    region = context.region
    if region is None or region.type != 'WINDOW':
        return
    gpu.state.blend_set('ALPHA')
    draw_rect((0, 0, region.width, region.height), BACKGROUND_COLOR)
    gpu.state.blend_set('NONE')
    for name, panel, layout in window_layouts(region):
        hover = STATE.hover[1] if STATE.hover is not None and STATE.hover[0] == name else None
        panel.draw_layout(context, layout, hover)


def redraw_window(window):
    for area in window.screen.areas:
        area.tag_redraw()


def press_cell(window, name, index, event):
    view = main_view()
    if view is None:
        return
    if name == "quick":
        main_window, area, region = view
        with bpy.context.temp_override(window=main_window, area=area, region=region):
            quick_panel.QUICK_ITEMS[index].execute(bpy.context)
        area.tag_redraw()
        return
    (kind, _), axis = edit_panel.cell_target(index)
    transform = DeltaTransform(kind, axis, view)
    if not transform.is_valid:
        show_status("Edit Panel: 変形するものが選ばれていません")
        return
    STATE.drag = (transform, window.x + event.mouse_x, window.y + event.mouse_y)


def end_drag(confirm):
    """変形を確定（confirm=True）または取り消して、ドラッグ状態を必ず解除する"""
    transform = STATE.drag[0]
    STATE.drag = None
    try:
        if confirm:
            transform.finish()
        else:
            transform.cancel()
    except Exception as error:
        print("BlenderCustom: Edit Panel の変形を終了できませんでした:", repr(error))


def handle_drag_event(window, event):
    """ドラッグ中のイベント。ボタンをパネル用ウィンドウの外で離した場合も受け取るため、全ウィンドウで処理する"""
    transform, start_x, start_y = STATE.drag
    if event.type in {'MOUSEMOVE', 'INBETWEEN_MOUSEMOVE'}:
        # ウィンドウをまたいでも追えるよう、画面全体の座標で差分を取る
        dx = window.x + event.mouse_x - start_x
        dy = window.y + event.mouse_y - start_y
        try:
            transform.update(dx, dy, get_prefs().drag_speed, snap=event.shift)
        except Exception as error:
            print("BlenderCustom: Edit Panel の変形中にエラーが起きたため取り消しました:", repr(error))
            end_drag(confirm=False)
        return {'RUNNING_MODAL'}
    if event.type == 'LEFTMOUSE' and event.value == 'RELEASE':
        end_drag(confirm=True)
        return {'RUNNING_MODAL'}
    if event.type in {'ESC', 'RIGHTMOUSE'} and event.value == 'PRESS':
        end_drag(confirm=False)
        return {'RUNNING_MODAL'}
    if is_panel_window(window) or event.type in CONSUMED_EVENTS:
        return {'RUNNING_MODAL'}
    return None


def handle_event(context, event):
    """パネル用ウィンドウのマウス操作を処理する。ドラッグ中以外は、ほかのウィンドウのイベントは触らない"""
    window = context.window
    if STATE.drag is not None:
        return handle_drag_event(window, event)
    if not is_panel_window(window):
        return None

    if event.type in {'MOUSEMOVE', 'INBETWEEN_MOUSEMOVE'}:
        hover = hit_test(window, event.mouse_x, event.mouse_y)
        if hover != STATE.hover:
            STATE.hover = hover
            redraw_window(window)
        return {'RUNNING_MODAL'}
    if event.type == 'LEFTMOUSE' and event.value == 'PRESS':
        hit = hit_test(window, event.mouse_x, event.mouse_y)
        if hit is not None:
            press_cell(window, hit[0], hit[1], event)
            redraw_window(window)
        return {'RUNNING_MODAL'}
    if event.type in CONSUMED_EVENTS:
        return {'RUNNING_MODAL'}
    return None


# --- パネル用ウィンドウを開く ------------------------------------------------------

def configure_space(area):
    space = area.spaces.active
    space.show_region_header = False
    space.show_region_tool_header = False
    space.show_region_toolbar = False
    space.show_region_ui = False
    space.show_gizmo = False
    space.overlay.show_overlays = False
    space.shading.type = 'WIREFRAME'


def find_window(pointer):
    for window in bpy.context.window_manager.windows:
        if window.as_pointer() == pointer:
            return window
    return None


def window_region(area):
    return next(r for r in area.regions if r.type == 'WINDOW')


def open_steps(main_pointer, width, height):
    """タイマーで 1 段ずつ進める手順（エリアの大きさは描画のたびに更新されるため）"""
    wm = bpy.context.window_manager
    main_window = find_window(main_pointer)
    if main_window is None:
        return
    before = {w.as_pointer() for w in wm.windows}
    with bpy.context.temp_override(window=main_window):
        bpy.ops.wm.window_new()
    work = next((w for w in wm.windows if w.as_pointer() not in before), None)
    if work is None:
        return
    work_pointer = work.as_pointer()
    yield

    work = find_window(work_pointer)
    area = work.screen.areas[0]
    with bpy.context.temp_override(window=work, area=area, region=window_region(area)):
        bpy.ops.screen.area_split(direction='VERTICAL', factor=min(0.9, width / max(area.width, 1)))
    yield

    work = find_window(work_pointer)
    area = min(work.screen.areas, key=lambda a: a.width)
    with bpy.context.temp_override(window=work, area=area, region=window_region(area)):
        bpy.ops.screen.area_split(direction='HORIZONTAL', factor=max(0.1, 1.0 - height / max(area.height, 1)))
    yield

    work = find_window(work_pointer)
    area = min(work.screen.areas, key=lambda a: a.width * a.height)
    before = {w.as_pointer() for w in wm.windows}
    with bpy.context.temp_override(window=work, area=area, region=window_region(area)):
        bpy.ops.screen.area_dupli('INVOKE_DEFAULT')
    panel = next((w for w in wm.windows if w.as_pointer() not in before), None)
    if panel is not None:
        panel.screen.name = PANEL_SCREEN_NAME
        configure_space(panel.screen.areas[0])
    yield

    work = find_window(work_pointer)
    if work is not None:
        with bpy.context.temp_override(window=work):
            bpy.ops.wm.window_close()


def run_steps(steps):
    def step():
        try:
            next(steps)
        except StopIteration:
            return None
        except Exception as error:
            print("BlenderCustom: パネル用ウィンドウを開けませんでした:", repr(error))
            return None
        return 0.05
    bpy.app.timers.register(step, first_interval=0.01)


class BLENDERCUSTOM_OT_open_panel_window(bpy.types.Operator):
    """QuickPanel と Edit Panel を、別の小さいウィンドウに表示する"""
    bl_idname = "blendercustom.open_panel_window"
    bl_label = "BlenderCustom パネルを開く"

    def execute(self, context):
        if any(is_panel_window(w) for w in context.window_manager.windows):
            self.report({'INFO'}, "パネル用ウィンドウはすでに開いています")
            return {'CANCELLED'}
        scale = context.preferences.system.ui_scale
        run_steps(open_steps(context.window.as_pointer(), int(WINDOW_WIDTH * scale), int(WINDOW_HEIGHT * scale)))
        return {'FINISHED'}


def draw_window_menu(self, context):
    self.layout.separator()
    self.layout.operator(BLENDERCUSTOM_OT_open_panel_window.bl_idname, icon='WINDOW')


def register():
    from . import listener
    bpy.utils.register_class(BLENDERCUSTOM_OT_open_panel_window)
    bpy.types.TOPBAR_MT_window.append(draw_window_menu)
    STATE.draw_handle = bpy.types.SpaceView3D.draw_handler_add(draw_window, (), 'WINDOW', 'POST_PIXEL')
    listener.add_handler(handle_event)


def unregister():
    from . import listener
    listener.remove_handler(handle_event)
    if STATE.drag is not None:
        STATE.drag[0].cancel()
        STATE.drag = None
    if STATE.draw_handle is not None:
        bpy.types.SpaceView3D.draw_handler_remove(STATE.draw_handle, 'WINDOW')
        STATE.draw_handle = None
    bpy.types.TOPBAR_MT_window.remove(draw_window_menu)
    bpy.utils.unregister_class(BLENDERCUSTOM_OT_open_panel_window)
