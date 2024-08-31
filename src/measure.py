from src.utils import print_log
import time
from src.state import State
from src.data_processing import IBICalculator


class MeasureWait(State):
    """Entry point for any measurement: HR, HRV, Kubios"""

    def __init__(self, state_machine):
        super().__init__(state_machine)
        # settings
        self._start_threshold = 200  # threshold that triggers the start of measurement when finger is placed

    def enter(self, args):
        # take arguments: heading_text, hr_text
        if self._state_machine.current_module == self._state_machine.MODULE_HR:
            heading_text = "HR Measure"
            hr_text = "-- BPM"
        elif self._state_machine.current_module == self._state_machine.MODULE_HRV:
            heading_text = "HRV Analysis"
            hr_text = "-- BPM  30s"
        elif self._state_machine.current_module == self._state_machine.MODULE_KUBIOS:
            heading_text = "Kubios Analysis"
            hr_text = "-- BPM  30s"
        else:
            raise ValueError("Invalid module code")
        self._view.remove_all()  # clear screen
        self._view.add_text(text="Put finger on ", x=0, y=14, vid="text_put_finger1")
        self._view.add_text(text="sensor to start", x=0, y=24, vid="text_put_finger2")
        self._view.add_text(text=heading_text, x=0, y=0, invert=True, vid="text_heading")
        self._view.add_text(text=hr_text, x=0, y=64 - 8, vid="text_hr")
        self._rotary_encoder.enable_press()

    def loop(self):
        # check finger on sensor
        value = self._heart_sensor.read()
        event = self._rotary_encoder.get_event()
        if value < self._start_threshold or event == self._rotary_encoder.EVENT_PRESS:
            # keep heading and hr text, remove the rest
            self._view.remove_by_id("text_put_finger1")
            self._view.remove_by_id("text_put_finger2")
            # HR -> HR Measure, HRV
            if self._state_machine.current_module == self._state_machine.MODULE_HR:
                self._state_machine.set(state_code=self._state_machine.STATE_MEASURE)
            # HRV -> HRV Measure
            elif self._state_machine.current_module == self._state_machine.MODULE_HRV:
                self._state_machine.set(state_code=self._state_machine.STATE_MEASURE, args=[30])
            # Kubios -> HRV Measure (same state, but module code will distinguish)
            elif self._state_machine.current_module == self._state_machine.MODULE_KUBIOS:
                self._state_machine.set(state_code=self._state_machine.STATE_MEASURE, args=[30])
            return


class Measure(State):
    def __init__(self, state_machine):
        super().__init__(state_machine)
        # data processing
        self._ibi_calculator = IBICalculator(self._heart_sensor.sensor_fifo, self._heart_sensor.get_sampling_rate())
        self._ibi_fifo = self._ibi_calculator.ibi_fifo  # ref of ibi_fifo
        # data
        self._hr_show_list = []
        self._hr = 0
        self._ibi_list = []
        # placeholders for ui
        self._textview_hr = None
        self._graphview = None
        # settings
        self._hr_update_interval = 5  # number of sample
        self._graph_update_interval = int(60000 / 180 / 10)  # 60000/max_hr/min_pixel_distance
        # timer
        self._countdown = None
        self._last_graph_update_time = 0
        self._last_count_down_time = 0

    def enter(self, args):
        """args: (countdown). countdown: time for counting down, unfilled means unlimited time"""
        self._countdown = args[0] if args is not None else None
        self._last_graph_update_time = 0
        self._last_count_down_time = 0
        # re-init data
        self._hr_show_list.clear()
        self._hr = 0
        self._ibi_list.clear()
        self._ibi_calculator.reinit()  # remember to reinit the calculator before use every time
        # ui
        self._textview_hr = self._view.select_by_id("text_hr")  # assigned to self.xxx, avoid select_by_id in loop()
        self._graphview = self._view.add_graph(y=14, h=64 - 14 - 12)
        self._rotary_encoder.enable_press()
        self._heart_sensor.start()  # start lastly to reduce the chance of data piling, maybe not needed

    def loop(self):
        self._ibi_calculator.run()  # keep calling calculator: sensor_fifo -> ibi_fifo
        # monitor and get data from ibi fifo, calculate hr and put into list
        while self._ibi_fifo.has_data():
            ibi = self._ibi_fifo.get()
            self._hr_show_list.append(int(60000 / ibi))
            if self._countdown is not None:  # countdown mode
                self._ibi_list.append(ibi)

        # for every _hr_update_interval samples, calculate the median value and update the HR display
        if len(self._hr_show_list) >= self._hr_update_interval:
            self._hr = sorted(self._hr_show_list)[len(self._hr_show_list) // 2]
            # use set_text method to update the text, view (screen) will auto refresh
            if self._countdown is not None:  # countdown mode
                hr_text = str(self._hr) + " BPM  " + str(self._countdown) + "s"
            else:
                hr_text = str(self._hr) + " BPM"

            self._textview_hr.set_text(hr_text)
            self._hr_show_list.clear()

        # countdown mode
        if self._countdown is not None:
            if self._last_count_down_time == 0 and len(self._ibi_list) > 2:
                self._last_count_down_time = time.ticks_ms()

            if self._last_count_down_time != 0 and time.ticks_diff(time.ticks_ms(), self._last_count_down_time) >= 1000:
                self._countdown -= 1
                self._last_count_down_time = time.ticks_ms()
                if self._hr == 0:
                    self._textview_hr.set_text("-- BPM  " + str(self._countdown) + "s")
                else:
                    self._textview_hr.set_text(str(self._hr) + " BPM  " + str(self._countdown) + "s")
            if self._countdown <= 0:
                self._heart_sensor.stop()
                self._view.remove(self._graphview)
                self._view.remove(self._textview_hr)
                self._state_machine.set(state_code=self._state_machine.STATE_MEASURE_RESULT_CHECK,
                                        args=[self._ibi_list])
                return

        # set maximum update interval, and skip when sensor fifo reaches 10 to avoid data piling
        if (time.ticks_diff(time.ticks_ms(), self._last_graph_update_time) > self._graph_update_interval and
                self._heart_sensor.sensor_fifo.count() < 10):
            self._last_graph_update_time = time.ticks_ms()
            self._graphview.set_value(self._heart_sensor.read(),
                                      self._ibi_calculator.get_window_min(), self._ibi_calculator.get_window_max())
        # keep watching rotary encoder press event
        event = self._rotary_encoder.get_event()
        if event == self._rotary_encoder.EVENT_PRESS:
            self._heart_sensor.stop()
            self._view.remove_all()
            self._state_machine.set(state_code=self._state_machine.STATE_MENU)
            return
