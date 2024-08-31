"""
State is a base class for all states.

Every state class must have the following methods:
- enter(): to initialize variables, set ui, set rotary encoder(press, rotate), etc. called when the state is entered
- loop(): called repeatedly until the state is changed

Setting next state:
- To set the next state, call state_machine.set(state_code, args)
- The state_code is defined in the StateMachine class, the data type is int
- The args is a list of arguments to pass to the next state. (to method enter())
"""


class State:
    """common resources:
    state_machine, rotary_encoder, heart_sensor, ibi_calculator, view"""

    def __init__(self, state_machine):
        self._state_machine = state_machine
        self._rotary_encoder = state_machine.rotary_encoder
        self._heart_sensor = state_machine.heart_sensor
        self._view = state_machine.view
        self._data_network = state_machine.data_network
        self._display = state_machine.display

    def enter(self, args):
        raise NotImplementedError("This method must be defined and overridden")

    def loop(self):
        raise NotImplementedError("This method must be defined and overridden")
