import array
from src.res.pic_icon import icon_hr, icon_hrv, icon_kubios, icon_history, icon_settings
import framebuf
from src.utils import print_log
import os


class View:
    def __init__(self, display):
        """Args:
        display: the display is the instance of SSD1306, to be used for rendering the views."""
        self._display = display
        self.width = display.width
        self.height = display.height
        self._active_views = {}
        self._inactive_views = {}  # a separate dict with type as key for quicker search

    def add_text(self, text, x, y, invert=False, invert_mode=1, vid=None):
        return self._add_view(TextView, vid, text, x, y, invert, invert_mode)

    def add_list(self, items, y, spacing=2, read_only=False, vid=None):
        return self._add_view(ListView, vid, items, y, spacing, read_only)

    def add_graph(self, y, h, speed=1, vid=None):
        return self._add_view(GraphView, vid, y, h, speed)

    def add_menu(self, vid=None):
        return self._add_view(MenuView, vid)

    def set_update(self, force=False):
        self._display.set_update(force)

    def refresh(self):
        self._display.refresh()

    def remove_by_id(self, vid):
        if vid not in self._active_views.keys():
            raise ValueError("View not found")
        # remove from active views and add to inactive views
        type_str = self._active_views[vid].type
        self._active_views[vid]._clear()
        self._active_views[vid]._active = False
        if self._inactive_views[type_str] is None:
            self._inactive_views[type_str] = [self._active_views.pop(vid)]
        else:
            self._inactive_views[type_str].append(self._active_views.pop(vid))
        print_log(f"View removed: {type_str}, active: {self._active_views}, inactive: {self._inactive_views}")

    def remove(self, view):
        vid = ""
        for key, value in self._active_views.items():
            if value is view:
                vid = key
                break  # get one if enough because vid is unique as key
        if vid == "":
            raise ValueError("View not found")
        self.remove_by_id(vid)

    def remove_all(self):
        for vid in list(self._active_views.keys()):
            self.remove_by_id(vid)

    def select_by_id(self, vid):
        if vid not in self._active_views.keys():
            raise ValueError("View not found")
        return self._active_views[vid]

    def get_stat(self):
        return self._active_views, self._inactive_views

    def _add_view(self, constructor, vid: str, *args, **kwargs):
        self._vid_checker(vid)
        if constructor.type not in self._inactive_views.keys():
            self._inactive_views[constructor.type] = []

        if len(self._inactive_views[constructor.type]) == 0:
            view = constructor(self._display, *args, **kwargs)
            self._active_views[self._vid_checker(vid)] = view
            print_log(f"View added: {constructor.type}, active: {self._active_views}, inactive: {self._inactive_views}")
            return view
        else:
            inactive_views = self._inactive_views[constructor.type]  # get inactive views from the list of the type
            view = inactive_views.pop()  # get one
            self._active_views[self._vid_checker(vid)] = view
            view._reinit(*args, **kwargs)
            print_log(
                f"View reused: {constructor.type}, active: {self._active_views}, inactive: {self._inactive_views}")
            return view

    def _vid_checker(self, vid):
        if vid is None:
            vid = os.urandom(4).hex()
            while vid in self._active_views.keys():
                vid = os.urandom(4).hex()
        else:
            if vid in self._active_views.keys():
                raise ValueError("View ID already exists")
        return vid


class TextView:
    """The instantiation and maintenance should be handled by View class."""
    type = "text"

    def __init__(self, display, text, x, y, invert=False, invert_mode=1):
        """Args:
        text: the text to be displayed
        x: x coordinate
        y: y coordinate
        invert: invert the text or not, default False
        invert_mode: 1. invert background the whole line, useful for heading text. 2: invert background of text only."""
        self._display = display
        self._font_size = display.FONT_SIZE
        self._active = True
        # param
        self._text = text
        self._x = x
        self._y = y
        self._invert = invert
        self._invert_mode = invert_mode
        self._update_framebuffer()

    def set_text(self, text):
        """Set text to be displayed, will automatically clear the previous text"""
        if not self._active:
            raise ValueError("Trying to set an inactive view component")
        self._clear()
        self._text = text
        self._update_framebuffer()

    def _reinit(self, text, x, y, invert=False, invert_mode=1):
        self._active = True
        self._text = text
        self._x = x
        self._y = y
        self._invert = invert
        self._invert_mode = invert_mode
        self._update_framebuffer()

    def _clear(self):
        if self._invert:
            if self._invert_mode == 1:
                self._display.fill_rect(0, self._y, self._display.width, self._font_size + 2, 0)
            elif self._invert_mode == 2:
                self._display.fill_rect(self._x, self._y, self._font_size * len(self._text), self._font_size + 2, 0)
            else:
                raise ValueError("Invalid invert mode")
        else:
            self._display.fill_rect(self._x, self._y, self._font_size * len(self._text), self._font_size, 0)
        self._display.set_update()

    def _update_framebuffer(self):
        if self._invert:
            if self._invert_mode == 1:
                self._display.fill_rect(self._x, self._y, self._display.width - self._x, self._font_size + 2, 1)
            elif self._invert_mode == 2:
                self._display.fill_rect(self._x, self._y, self._font_size * len(self._text), self._font_size + 2, 1)
            else:
                raise ValueError("Invalid invert mode")
            self._display.text(self._text, self._x, self._y + 1, 0)
        else:
            self._display.text(self._text, self._x, self._y, 1)
        self._display.set_update()


class ListView:
    """Methods: set_items, set_selection, set_page, get_page_max, get_page, get_selection_max.
    Note: current selection is got from rotary encoder get_position() method, which is absolute position
    ListView doesn't remember index of current selection, it should be managed by the caller."""
    type = "list"
    _arrow_top = array.array('H', [3, 0, 0, 5, 6, 5])  # coordinates array of the poly vertex
    _arrow_bottom = array.array('H', [0, 0, 6, 0, 3, 5])

    def __init__(self, display, items, y, spacing=2, read_only=False):
        self._display = display
        self._font_size = display.FONT_SIZE
        self._active = True

        self._page = 0
        self._display_count = 0  # number of items WILL BE shown on screen, not max possible number of items
        self._slider_height = 0
        self._show_scrollbar = False
        self._slider_min_height = 2
        # param
        self._items = items
        self._y = y
        self._spacing = spacing
        self._read_only = read_only

        self._scrollbar_top = self._y + 5 + 3  # 5 is height of arrow, 3 is margin between arrow and scrollbar
        self._scrollbar_bottom = self._display.height - 5 - 3
        self._slider_top = self._scrollbar_top + 1  # offset 1 pixel from scrollbar outline
        self._slider_bottom = self._scrollbar_bottom - 1
        self.set_items(items)

    def get_page(self):
        """Get the current page index, starting from 0"""
        return self._page

    def get_page_max(self):
        """Get the max page index, starting from 0"""
        return len(self._items) - self._display_count

    def get_selection_max(self):
        """Get the max selection index, starting from 0"""
        return len(self._items) - 1

    def need_scrollbar(self):
        """Return True if the list view needs a scrollbar, the caller can decide to set rotation irq of encoder"""
        return self._show_scrollbar

    def set_selection(self, index):
        """Handle by the caller, the caller can set the selection index by rotary encoder get_position() method."""
        if not self._active:
            raise ValueError("Trying to set an inactive view component")
        if index < 0 or index > self.get_selection_max():
            raise ValueError("Invalid selection index")
        self._clear()
        # update page start index
        if index < self._page:
            self._page = index
        elif index > self._page + self._display_count - 1:
            self._page = index - (self._display_count - 1)
        self._update_framebuffer(index)

    def set_page(self, index):
        """Handle by the caller, useful when it needs to be scrolled to a specific page.
         Also, in read-only mode, this should be set instead of set_selection.
         Because in read-only mode there is no 'selection', but scrolling page to view items only."""
        if not self._active:
            raise ValueError("Trying to set an inactive view component")
        if index < 0 or index > self.get_page_max():
            raise ValueError("Invalid page index")
        self._page = index
        self.set_selection(self._page)

    def set_items(self, items):
        """Set items to be displayed, this will also set up everything"""
        if not self._active:
            raise ValueError("Trying to set an inactive view component")
        self._clear()
        self._items = items
        # get max display count at once
        available_height = self._display.height - self._y
        item_height = self._font_size + self._spacing
        max_display_count = available_height // item_height
        if available_height % item_height > self._font_size:
            max_display_count += 1
        print_log(f"List view item per page: {max_display_count}, total: {len(self._items)}")

        # set scrollbar
        if max_display_count >= len(self._items):
            self._show_scrollbar = False
        else:
            self._show_scrollbar = True
            self._slider_height = int(max_display_count / len(self._items) * (
                    self._slider_bottom - self._slider_top - self._slider_min_height) + self._slider_min_height)
        # display count at once
        self._display_count = min(max_display_count, len(self._items))
        self._page = 0  # set view index to first item
        self.set_selection(0)

    def _reinit(self, items, y, spacing=2, read_only=False):
        self._active = True
        self._items = items
        self._read_only = read_only
        self._y = y
        self._spacing = spacing

        self._scrollbar_top = self._y + 5 + 3
        self._slider_top = self._scrollbar_top + 1  # offset 1 pixel from scrollbar outline
        self.set_items(items)

    def _clear(self):
        self._display.fill_rect(0, self._y, self._display.width, self._display.height - self._y, 0)
        self._display.set_update()

    def _draw_scrollbar(self):
        scrollbar_width = 5
        slider_width = scrollbar_width - 2
        assert self._display_count <= len(self._items), "No need to draw scroll bar"

        slider_y = round(self._page / (len(self._items) - self._display_count) * (
                self._slider_bottom - self._slider_top - self._slider_height) + self._slider_top)
        # scrollbar outline
        self._display.rect(self._display.width - scrollbar_width - 1, self._scrollbar_top, scrollbar_width,
                           self._scrollbar_bottom - self._scrollbar_top, 1)
        # scrollbar slider
        self._display.fill_rect(self._display.width - slider_width - 2, slider_y, slider_width,
                                self._slider_height, 1)
        # draw arrow on top, 7 is the width of the arrow
        if self._page == 0:
            self._display.poly(self._display.width - 7, self._y, self._arrow_top, 1, 0)
        else:
            self._display.poly(self._display.width - 7, self._y, self._arrow_top, 1, 1)
        # draw arrow on bottom, 6 is the height of the arrow
        if self._page == len(self._items) - self._display_count:
            self._display.poly(self._display.width - 7, self._display.height - 6, self._arrow_bottom, 1, 0)
        else:
            self._display.poly(self._display.width - 7, self._display.height - 6, self._arrow_bottom, 1, 1)

    def _update_framebuffer(self, selection):
        for i in range(self._page, self._page + self._display_count):
            print_log(f"List view showing: {i} / {len(self._items) - 1}")
            text_y = self._y + (i - self._page) * (self._font_size + self._spacing)
            # truncate text if too long
            text = self._items[i]
            max_text_length = self._display.width // self._font_size - 1 * (
                not self._read_only) - 1 * self._show_scrollbar
            if len(text) > max_text_length:
                text = text[:max_text_length]
            # display text
            if self._read_only:
                self._display.text(text, 0, text_y)
            else:
                if i == selection:
                    self._display.text(">" + text, 0, text_y)
                else:
                    self._display.text(" " + text, 0, text_y)
        if self._show_scrollbar:
            self._draw_scrollbar()
        self._display.set_update()


class GraphView:
    type = "graph"

    def __init__(self, display, y, h, speed=1):
        self._display = display
        self._WIDTH = display.width
        self._HEIGHT = display.height
        self._active = True

        self._last_x = -1
        self._last_y = -1
        self._x = 0
        self._box_y = y
        self._box_h = h
        self._speed = speed

    def _reinit(self, y, h, speed=1):
        self._active = True
        self._last_x = -1
        self._last_y = -1
        self._x = 0
        self._box_y = y
        self._box_h = h
        self._speed = speed

    def set_value(self, value, min_val, max_val):
        """Set value to be displayed, will automatically update the frame buffer with force=True.
        That means the interval of updating should be handled by the caller,
        so refresh rate of graph can be different from the screen."""
        if not self._active:
            raise ValueError("Trying to set an inactive view component")
        self._update_framebuffer(value, min_val, max_val)

    def _clear(self):
        self._display.fill_rect(0, self._box_y, self._WIDTH, self._box_h, 0)
        self._display.set_update()

    def _clear_ahead(self):
        # if: within the box's width
        # else: exceed the box's width: clean the part inside box, take the rest at the start and clean it
        clean_width = int(self._WIDTH / 7)
        if self._x + clean_width < self._WIDTH:
            self._display.fill_rect(self._x + 1, self._box_y, clean_width, self._box_h, 0)
        else:
            exceed_width = self._x + clean_width - self._WIDTH
            self._display.fill_rect(self._x + 1, self._box_y, clean_width - exceed_width, self._box_h, 0)
            self._display.fill_rect(0, self._box_y, exceed_width, self._box_h, 0)

    def _update_framebuffer(self, value, min_val, max_val):
        self._clear_ahead()

        if max_val - min_val == 0:
            y = self._box_y + self._box_h // 2
        else:
            y = int((max_val - value) / (max_val - min_val) * self._box_h + self._box_y)

        if y >= self._box_y + self._box_h:
            y = self._box_y + self._box_h - 1
        elif y <= self._box_y:
            y = self._box_y + 1

        self._x = (self._x + self._speed) % self._WIDTH
        if self._x == 0:
            self._last_x = -1
            self._last_y = -1

        if self._last_x != -1 and self._last_y != -1:
            self._display.line(self._last_x, self._last_y, self._x, y, 1)

        self._last_x = self._x
        self._last_y = y

        # self._display.set_update()
        self._display.set_update(force=True)


class MenuView:
    type = "menu"
    _icon_buf_hr = framebuf.FrameBuffer(icon_hr, 32, 32, framebuf.MONO_VLSB)
    _icon_buf_hrv = framebuf.FrameBuffer(icon_hrv, 32, 32, framebuf.MONO_VLSB)
    _icon_buf_kubios = framebuf.FrameBuffer(icon_kubios, 32, 32, framebuf.MONO_VLSB)
    _icon_buf_history = framebuf.FrameBuffer(icon_history, 32, 32, framebuf.MONO_VLSB)
    _icon_buf_settings = framebuf.FrameBuffer(icon_settings, 32, 32, framebuf.MONO_VLSB)

    def __init__(self, display):
        self._display = display
        self._active = True

    def set_selection(self, selection):
        if not self._active:
            raise ValueError("Trying to set an inactive view component")
        self._update_framebuffer(selection)

    def _reinit(self):
        self._active = True

    def _clear(self):
        self._display.fill(0)
        self._display.set_update()

    def _update_framebuffer(self, selection):
        if selection == 0:
            icon_buf = self._icon_buf_hr
            text = "HR Measure"
        elif selection == 1:
            icon_buf = self._icon_buf_hrv
            text = "HRV Analysis"
        elif selection == 2:
            icon_buf = self._icon_buf_kubios
            text = "Kubios Analysis"
        elif selection == 3:
            icon_buf = self._icon_buf_history
            text = "History"
        elif selection == 4:
            icon_buf = self._icon_buf_settings
            text = "Settings"
        else:
            raise ValueError("Invalid index")

        self._display.fill(0)
        self._display.text(text, int((128 - len(text) * 8) / 2), 38, 1)
        self._display.blit(icon_buf, int((128 - 32) / 2), 0)
        # draw selection indicator
        for x in range(5):
            self._display.rect(36 + 12 * x, 61, 2, 2, 1)
        self._display.fill_rect(36 + 12 * selection, 60, 4, 4, 1)
        self._display.set_update()
