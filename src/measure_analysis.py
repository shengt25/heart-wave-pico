import time
from src.utils import get_datetime
from src.result import dict2show_items
from src.save_system import save_system
from src.state import State
from src.data_processing import calculate_hrv, get_kubios_analysis
from src.res.pic_loading_circle import LoadingCircle
import framebuf


class MeasureResultCheck(State):
    def __init__(self, state_machine):
        super().__init__(state_machine)
        self._listview_retry = None

    def enter(self, args):
        ibi_list = args[0]
        if len(ibi_list) > 10:
            # data ok, go to hrv or kubios
            if self._state_machine.current_module == self._state_machine.MODULE_HRV:
                self._state_machine.set(state_code=self._state_machine.STATE_HRV_ANALYSIS, args=[ibi_list])
            elif self._state_machine.current_module == self._state_machine.MODULE_KUBIOS:
                self._state_machine.set(state_code=self._state_machine.STATE_KUBIOS_ANALYSIS, args=[ibi_list])
            else:
                raise ValueError("Invalid module code")
            return
        else:
            self._view.add_text(text="Not enough data", x=0, y=14, vid="text_check_error")
            self._listview_retry = self._view.add_list(items=["Try again", "Exit"], y=34)
            self._rotary_encoder.enable_rotate(items_count=2, position=0)
            self._rotary_encoder.enable_press()

    def loop(self):
        """if check not enough, then goes here"""
        event = self._rotary_encoder.get_event()
        if event == self._rotary_encoder.EVENT_ROTATE:
            self._listview_retry.set_selection(self._rotary_encoder.get_position())
        elif event == self._rotary_encoder.EVENT_PRESS:
            self._rotary_encoder.disable_rotate()
            self._view.remove_all()  # main menu needs to be re-created, wait measure also will re-create heading
            if self._rotary_encoder.get_position() == 0:
                self._state_machine.set(state_code=self._state_machine.STATE_MEASURE_WAIT)
            elif self._rotary_encoder.get_position() == 1:
                self._state_machine.set(state_code=self._state_machine.STATE_MENU)
            else:
                raise ValueError("Invalid selection index")


class HRVAnalysis(State):
    def __init__(self, state_machine):
        super().__init__(state_machine)

    def enter(self, args):
        ibi_list = args[0]
        """start of loading animation"""
        # the animation now is actually a fake one. It does nothing but block the system for a while
        # also, it is ugly implemented, the reason to do this is just for fun. at least for now.
        loading_circle = LoadingCircle()
        ani_start_time = time.ticks_ms()
        ani_refresh_time = time.ticks_ms()
        ani_index = 0
        self._display.text("loading", 35, 56, 1)
        while time.ticks_diff(time.ticks_ms(), ani_start_time) < 1000:
            if time.ticks_diff(time.ticks_ms(), ani_refresh_time) > 5:
                buf = framebuf.FrameBuffer(loading_circle.seq[ani_index], 32, 32, framebuf.MONO_VLSB)
                self._display.blit(buf, 48, 20)
                self._display.show()
                ani_index = (ani_index + 1) % len(loading_circle.seq)
                ani_refresh_time = time.ticks_ms()
        """end of loading animation"""
        hr, ppi, rmssd, sdnn = calculate_hrv(ibi_list)
        self._display.fill_rect(0, 14, 128, 50, 0)  # clear loading animation
        # save data
        result = {"DATE": get_datetime(),
                  "HR": str(hr) + "BPM",
                  "IBI": str(ppi) + "ms",
                  "RMSSD": str(rmssd) + "ms",
                  "SDNN": str(sdnn) + "ms"}
        save_system(result)
        show_items = dict2show_items(result)
        # send to mqtt
        mqtt_success = self._state_machine.data_network.mqtt_publish(result)
        if not mqtt_success:
            show_items.extend(["---", "MQTT not sent", "Please connect", "in settings"])
        self._state_machine.set(state_code=self._state_machine.STATE_SHOW_RESULT, args=[show_items])
        self._rotary_encoder.enable_press()  # resume after process done

    def loop(self):
        return


class KubiosAnalysis(State):
    def __init__(self, state_machine):
        super().__init__(state_machine)
        self._ibi_list = []
        self._listview_retry = None

    def enter(self, args):
        self._ibi_list = args[0]
        """start of loading animation"""
        # the animation now is actually a fake one. It does nothing but block the system for a while
        # also, it is ugly implemented, the reason to do this is just for fun. at least for now.
        loading_circle = LoadingCircle()
        ani_start_time = time.ticks_ms()
        ani_refresh_time = time.ticks_ms()
        ani_index = 0
        self._display.text("loading", 35, 56, 1)
        while time.ticks_diff(time.ticks_ms(), ani_start_time) < 1000:
            if time.ticks_diff(time.ticks_ms(), ani_refresh_time) > 5:
                buf = framebuf.FrameBuffer(loading_circle.seq[ani_index], 32, 32, framebuf.MONO_VLSB)
                self._display.blit(buf, 48, 20)
                self._display.show()
                ani_index = (ani_index + 1) % len(loading_circle.seq)
                ani_refresh_time = time.ticks_ms()
        """end of loading animation"""
        kubios_success, result = get_kubios_analysis(self._ibi_list)
        self._display.fill_rect(0, 14, 128, 50, 0)  # clear loading animation
        if kubios_success:
            # success, save and goto show result
            save_system(result)
            show_items = dict2show_items(result)
            # send to mqtt
            mqtt_success = self._state_machine.data_network.mqtt_publish(result)
            if not mqtt_success:
                show_items.extend(["---", "MQTT not sent", "Please connect", "in settings"])
            self._state_machine.set(state_code=self._state_machine.STATE_SHOW_RESULT, args=[show_items])
            return
        else:
            # failed, retry or show HRV result
            self._rotary_encoder.enable_rotate(items_count=2, position=0)
            self._view.add_text(text="Failed, check", x=0, y=14, vid="text_kubios_failed1")
            self._view.add_text(text="network or API", x=0, y=24, vid="text_kubios_failed2")
            self._listview_retry = self._view.add_list(items=["Try again", "Show HRV result"], y=44)
        self._rotary_encoder.enable_press()

    def loop(self):
        # send failed, retry or show HRV result
        event = self._rotary_encoder.get_event()
        if event == self._rotary_encoder.EVENT_ROTATE:
            self._listview_retry.set_selection(self._rotary_encoder.get_position())
        if event == self._rotary_encoder.EVENT_PRESS:
            self._state_machine.rotary_encoder.disable_rotate()
            self._view.remove_by_id("text_kubios_failed1")
            self._view.remove_by_id("text_kubios_failed2")
            self._view.remove(self._listview_retry)
            if self._rotary_encoder.get_position() == 0:
                self._state_machine.set(state_code=self._state_machine.STATE_KUBIOS_ANALYSIS, args=[self._ibi_list])
            elif self._rotary_encoder.get_position() == 1:
                self._state_machine.set(state_code=self._state_machine.STATE_HRV_ANALYSIS, args=[self._ibi_list])
            else:
                raise ValueError("Invalid selection index")
