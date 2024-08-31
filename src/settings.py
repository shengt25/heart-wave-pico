import time
from src.utils import pico_stat
from src.state import State
from src.res.pic_loading_circle import LoadingCircle
import framebuf


class Settings(State):
    def __init__(self, state_machine):
        super().__init__(state_machine)
        self._selection = 0  # to preserve selected index, resume when exit and re-enter
        self._page = 0  # to preserve page index, resume when exit and re-enter
        self._listview_settings_list = None

    def enter(self, args):
        self._view.remove_all()  # clear screen
        self._view.add_text(text="Settings", x=0, y=0, invert=True)
        self._listview_settings_list = self._view.add_list(items=["Back", "About", "Debug Info", "Connect Wi-Fi",
                                                                  "Connect MQTT", "???"], y=14)
        self._listview_settings_list.set_page(self._page)
        self._listview_settings_list.set_selection(self._selection)
        self._rotary_encoder.enable_rotate(items_count=6, position=self._selection)
        self._rotary_encoder.enable_press()

    def loop(self):
        event = self._rotary_encoder.get_event()
        if event == self._rotary_encoder.EVENT_ROTATE:
            self._listview_settings_list.set_selection(self._rotary_encoder.get_position())
        elif event == self._rotary_encoder.EVENT_PRESS:
            self._selection = self._rotary_encoder.get_position()
            self._page = self._listview_settings_list.get_page()
            self._rotary_encoder.disable_rotate()
            self._view.remove_all()
            if self._selection == 0:
                self._state_machine.set(state_code=self._state_machine.STATE_MENU)
            elif self._selection == 1:
                self._state_machine.set(state_code=self._state_machine.STATE_SETTINGS_ABOUT)
            elif self._selection == 2:
                self._state_machine.set(state_code=self._state_machine.STATE_SETTINGS_DEBUG_INFO)
            elif self._selection == 3:
                self._state_machine.set(state_code=self._state_machine.STATE_SETTINGS_WIFI)
            elif self._selection == 4:
                self._state_machine.set(state_code=self._state_machine.STATE_SETTINGS_MQTT)
            elif self._selection == 5:
                dino(self._display, self._rotary_encoder)
                self._state_machine.set(state_code=self._state_machine.STATE_SETTINGS)
            else:
                raise ValueError("Invalid selection index")


class SettingsAbout(State):
    def __init__(self, state_machine):
        super().__init__(state_machine)
        self._listview_about = None

    def enter(self, args):
        self._view.remove_all()  # clear screen
        self._view.add_text(text="About", x=0, y=0, invert=True)
        show_items = ["[HeartWave Pico]",
                      "Sheng Tai", "Alex Pop", "Vitalii Virronen",
                      "Made by Group3"]
        self._listview_about = self._view.add_list(items=show_items, y=14, read_only=True)
        self._rotary_encoder.enable_press()

    def loop(self):
        event = self._rotary_encoder.get_event()
        if event == self._rotary_encoder.EVENT_PRESS:
            self._view.remove_all()
            self._state_machine.set(state_code=self._state_machine.STATE_SETTINGS)


class SettingsDebugInfo(State):
    def __init__(self, state_machine):
        super().__init__(state_machine)
        self._listview_info = None

    def enter(self, args):
        self._view.remove_all()  # clear screen
        self._view.add_text(text="Debug Info", x=0, y=0, invert=True)
        # system info
        ram_used, ram_free, ram_total, storage_free = pico_stat()
        # network
        if self._data_network.is_wlan_connected():
            wlan_status = "Connected"
            wlan_ip = self._data_network.get_wlan_ip()
        else:
            wlan_status = "Not connected"
            wlan_ip = "IP: N/A"
        if self._data_network.is_mqtt_connected():
            mqtt_connected = "Connected"
            mqtt_broker_ip = self._data_network.get_broker_ip()
        else:
            mqtt_connected = "Not connected"
            mqtt_broker_ip = "IP: N/A"
        # state info
        state_count = len(self._state_machine.get_states_info())
        # view info
        active_view, inactive_view = self._view.get_stat()
        show_items = ["[RAM]", f"Used:{ram_used}KB", f"Free:{ram_free}KB", f"Total:{ram_total}KB",
                      "",
                      "[Storage]", f"Free:{storage_free}KB",
                      "",
                      "[Wi-Fi]", wlan_status, wlan_ip,
                      "",
                      "[MQTT]", mqtt_connected, mqtt_broker_ip,
                      "",
                      "[State in RAM]", str(state_count),
                      "",
                      "[View]", f"Active:{len(active_view) + 1}", f"Inactive:{len(inactive_view)}"]
        # active_view plus 1 because the view next line not yet activated
        self._listview_info = self._view.add_list(items=show_items, y=14, read_only=True)
        self._rotary_encoder.enable_rotate(items_count=self._listview_info.get_page_max() + 1, position=0)
        self._rotary_encoder.enable_press()

    def loop(self):
        event = self._rotary_encoder.get_event()
        if event == self._rotary_encoder.EVENT_ROTATE:
            self._listview_info.set_page(self._rotary_encoder.get_position())
        elif event == self._rotary_encoder.EVENT_PRESS:
            self._rotary_encoder.disable_rotate()
            self._view.remove_all()
            self._state_machine.set(state_code=self._state_machine.STATE_SETTINGS)


class SettingsWifi(State):
    def __init__(self, state_machine):
        super().__init__(state_machine)
        self._textview_info = None
        self._textview_ip = None
        self._last_check_time = 0
        self._connecting = False

        # for animation
        self._animation_refresh_time = time.ticks_ms()
        self._animation_index = 0
        self._loading_circle = LoadingCircle()

    def enter(self, args):
        self._view.remove_all()  # clear screen
        self._view.add_text(text="Wi-Fi", x=0, y=0, invert=True)
        self._display.show()

        self._textview_info = self._view.add_text(text="", x=0, y=14)
        self._textview_ip = self._view.add_text(text="", x=0, y=24)
        self._last_check_time = 0
        self._connecting = False

        # for animation
        self._animation_refresh_time = time.ticks_ms()
        self._animation_index = 0

        if self._data_network.is_wlan_connected():
            self._textview_info.set_text("Connected")
            self._textview_ip.set_text(self._data_network.get_wlan_ip())
        self._rotary_encoder.enable_press()

    def loop(self):
        # check Wi-Fi every 1s
        if time.ticks_diff(time.ticks_ms(), self._last_check_time) > 1000:
            self._last_check_time = time.ticks_ms()
            if self._data_network.is_wlan_connected() and self._connecting:
                self._connecting = False
                self._display.fill_rect(0, 20, 128, 44, 0)
                self._textview_info.set_text("Connected")
                self._textview_ip.set_text(self._data_network.get_wlan_ip())
                return

            # when not connected, try to connect, init animation
            if not self._data_network.is_wlan_connected() and not self._connecting:
                self._connecting = True
                self._textview_info.set_text("")
                self._textview_ip.set_text("")
                self._display.text("Connecting", 24, 56, 1)
                self._data_network.connect_wlan()

        # display loading animation when connecting
        if self._connecting:
            if time.ticks_ms() - self._animation_refresh_time > 5:
                buf = framebuf.FrameBuffer(self._loading_circle.seq[self._animation_index], 32, 32, framebuf.MONO_VLSB)
                self._display.blit(buf, 48, 20)
                self._display.show()
                self._animation_index = (self._animation_index + 1) % len(self._loading_circle.seq)
                self._animation_refresh_time = time.ticks_ms()

        event = self._rotary_encoder.get_event()
        if event == self._rotary_encoder.EVENT_PRESS:
            self._view.remove_all()
            self._state_machine.set(state_code=self._state_machine.STATE_SETTINGS)


class SettingsMqtt(State):
    def __init__(self, state_machine):
        super().__init__(state_machine)
        self._textview_info = None
        self._textview_ip = None

    def enter(self, args):
        self._view.remove_all()  # clear screen
        self._view.add_text(text="MQTT", x=0, y=0, invert=True)
        self._textview_info = self._view.add_text(text="", x=0, y=14)
        self._textview_ip = self._view.add_text(text="", x=0, y=24)
        # try to connect at first run
        if not self._data_network.is_mqtt_connected():
            self._textview_info.set_text("Connecting...")
            self._textview_ip.set_text("IP: N/A")
            self._display.show()
            # force update display directly, because the next line blocks the program!
            self._rotary_encoder.disable_press()  # just in case user press button a lot while sending
            self._data_network.connect_mqtt()
            self._rotary_encoder.enable_press()
        # update status
        if not self._data_network.is_mqtt_connected():
            self._textview_info.set_text("Failed")
            self._textview_ip.set_text("IP: N/A")
        else:
            self._textview_info.set_text("Connected")
            self._textview_ip.set_text(self._data_network.get_broker_ip())
        self._rotary_encoder.enable_press()

    def loop(self):
        event = self._rotary_encoder.get_event()
        if event == self._rotary_encoder.EVENT_PRESS:
            self._view.remove_all()
            self._state_machine.set(state_code=self._state_machine.STATE_SETTINGS)


def dino(display, rotary_encoder):
    dino_img = bytearray([
        # // font edit begin : monovlsb : 30 : 32 : 30
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0xFC,
        0xFC, 0xFF, 0xFF, 0xF3, 0xFF, 0xFF, 0xFF, 0xFF,
        0xFF, 0xFF, 0xFF, 0xFF, 0xFC, 0xFC, 0xFE, 0xFE,
        0xE0, 0xE0, 0x80, 0x00, 0x00, 0x00, 0x00, 0x80,
        0x80, 0xE0, 0xE0, 0xF8, 0xF8, 0xFF, 0xFF, 0xFF,
        0xFF, 0xFF, 0x87, 0x87, 0x86, 0x86, 0x06, 0x06,
        0x06, 0x06, 0x00, 0x00, 0x07, 0x07, 0x1F, 0x1F,
        0x7F, 0x7E, 0xFE, 0xFE, 0xFE, 0xFF, 0xFF, 0xFF,
        0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0x7F, 0x3F, 0x1F,
        0x01, 0x01, 0x07, 0x07, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        0x00, 0xFF, 0xFF, 0xCF, 0xCF, 0x03, 0x03, 0x0F,
        0x0F, 0xFF, 0xFF, 0xC0, 0xC0, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00
        # // font edit end
    ])
    dino = framebuf.FrameBuffer(dino_img, 30, 32, framebuf.MONO_VLSB)

    y = 63 - 32
    v0 = 40
    g = 30
    t = 0
    dt = 0.1
    h = 63
    display.blit(dino, 0, y)
    display.text("Press", 40, 14, 1)
    display.show()
    press_count = 0
    while True:
        event = rotary_encoder.get_event()
        if event == rotary_encoder.EVENT_PRESS:
            press_count += 1
            while y <= h - 32:
                display.fill_rect(0, 0, 30, 63, 0)
                display.blit(dino, 0, int(y))
                display.show()
                t += dt
                y = 63 - 32 - v0 * t + 0.5 * g * t ** 2
                # self.y = max(0, min(self.h, self.y))
            y = 63 - 32
            t = 0

            if press_count == 1:
                display.text("Where am I?", 40, 24, 1)
                display.show()
            elif press_count == 2:
                display.text("Alright.", 40, 34, 1)
                display.show()
            elif press_count == 3:
                display.text("See you...", 40, 44, 1)
                display.text("soon...", 40, 54, 1)
                display.show()
            elif press_count == 4:
                break
