from hardware import Display, RotaryEncoder, HeartSensor
from view import View
from pico_network import PicoNetwork
from main_menu import MainMenu
from measure import MeasureWait, Measure
from measure_analysis import MeasureResultCheck, HRVAnalysis, KubiosAnalysis
from result import ShowHistory, ShowResult
from settings import Settings, SettingsDebugInfo, SettingsWifi, SettingsMqtt, SettingsAbout


class StateMachine:
    # enum for each module and state
    MODULE_MENU = 0
    MODULE_HR = 1
    MODULE_HRV = 2
    MODULE_KUBIOS = 3
    MODULE_HISTORY = 4
    MODULE_SETTINGS = 5

    STATE_MENU = 6
    STATE_MEASURE_WAIT = 7
    STATE_MEASURE = 8
    STATE_MEASURE_RESULT_CHECK = 9
    STATE_HRV_ANALYSIS = 10
    STATE_KUBIOS_ANALYSIS = 11
    STATE_SHOW_HISTORY = 12
    STATE_SHOW_RESULT = 13
    STATE_SETTINGS = 14
    STATE_SETTINGS_DEBUG_INFO = 15
    STATE_SETTINGS_WIFI = 16
    STATE_SETTINGS_MQTT = 17
    STATE_SETTINGS_ABOUT = 18

    # map the state code to each class object
    state_dict = {STATE_MENU: MainMenu,
                  STATE_MEASURE_WAIT: MeasureWait,
                  STATE_MEASURE: Measure,
                  STATE_MEASURE_RESULT_CHECK: MeasureResultCheck,
                  STATE_HRV_ANALYSIS: HRVAnalysis,
                  STATE_KUBIOS_ANALYSIS: KubiosAnalysis,
                  STATE_SHOW_HISTORY: ShowHistory,
                  STATE_SHOW_RESULT: ShowResult,
                  STATE_SETTINGS: Settings,
                  STATE_SETTINGS_DEBUG_INFO: SettingsDebugInfo,
                  STATE_SETTINGS_WIFI: SettingsWifi,
                  STATE_SETTINGS_MQTT: SettingsMqtt,
                  STATE_SETTINGS_ABOUT: SettingsAbout,
                  }

    def __init__(self):
        self.display = Display()
        self.rotary_encoder = RotaryEncoder()
        self.heart_sensor = HeartSensor()
        self.view = View(self.display)
        self.data_network = PicoNetwork()
        self.current_module = self.MODULE_MENU
        self._args = None
        self._states = {}
        self._state = None
        self._switched = False

    def get_state(self, state_class_obj):
        if state_class_obj not in self._states:
            self._states[state_class_obj] = state_class_obj(self)  # pass self to state class, to give property access
        return self._states[state_class_obj]

    def preload_states(self):
        for state_class_obj in self.state_dict.values():
            self.get_state(state_class_obj)

    def set(self, state_code, args=None):
        # store additional arguments for the next state.enter()
        if args is not None and not isinstance(args, list):
            raise ValueError("args must be a list")
        try:
            self._args = args
            state = self.state_dict[state_code]
            self._state = self.get_state(state)
            self._switched = True
        except KeyError:
            raise ValueError("Invalid state code to switch to")

    def run(self):
        if self._switched:
            # disable all irq automatically in case of fifo overflow
            self.heart_sensor.stop()
            self.rotary_encoder.disable_press()
            self.rotary_encoder.disable_rotate()
            self._switched = False
            self._state.enter(self._args)
            return
            # skip loop() in the first run, because state can be changed again during enter()
        self._state.loop()
        self.view.refresh()

    def set_module(self, module):
        """The module is used to determine the next state accordingly,
        it's set up only by the main menu"""
        self.current_module = module

    def get_states_info(self):
        return self._states
