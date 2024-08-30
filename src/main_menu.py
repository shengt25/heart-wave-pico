import time
from src.state import State
from src.utils import print_log


class MainMenu(State):
    def __init__(self, state_machine):
        # take common resources:
        # state_machine, rotary_encoder, heart_sensor, ibi_calculator, view
        super().__init__(state_machine)
        # ui placeholder
        self._menu = None
        # data
        self._selection = 0  # to preserve selected index, resume when exit and re-enter

    def enter(self, args):
        self._view.remove_all()  # clear screen
        self._menu = self._view.add_menu()
        self._rotary_encoder.enable_rotate(items_count=5, position=self._selection, loop_mode=False)
        self._rotary_encoder.enable_press()
        self._menu.set_selection(self._selection)  # resume selected index from last time

    def loop(self):
        event = self._rotary_encoder.get_event()
        if event == self._rotary_encoder.EVENT_ROTATE:
            self._selection = self._rotary_encoder.get_position()
            self._menu.set_selection(self._selection)
        elif event == self._rotary_encoder.EVENT_PRESS:
            if self._selection == 0:
                self._state_machine.set_module(self._state_machine.MODULE_HR)
                self._state_machine.set(self._state_machine.STATE_MEASURE_WAIT)
            elif self._selection == 1:
                self._state_machine.set_module(self._state_machine.MODULE_HRV)
                self._state_machine.set(self._state_machine.STATE_MEASURE_WAIT)
            elif self._selection == 2:
                self._state_machine.set_module(self._state_machine.MODULE_KUBIOS)
                self._state_machine.set(self._state_machine.STATE_MEASURE_WAIT)
            elif self._selection == 3:
                self._state_machine.set_module(self._state_machine.MODULE_HISTORY)
                self._state_machine.set(self._state_machine.STATE_SHOW_HISTORY)
            elif self._selection == 4:
                self._state_machine.set_module(self._state_machine.MODULE_SETTINGS)
                self._state_machine.set(self._state_machine.STATE_SETTINGS)
            else:
                raise ValueError("Invalid selection index")
            self._rotary_encoder.disable_rotate()
            self._view.remove_all()
