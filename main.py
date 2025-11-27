"""HeartWave Pico"""

"""animation has to be the first, even before any imports, otherwise RAM will be full"""
power_on_animation = True
if power_on_animation:
    import gc

    from src.res.animation_power_on import PowerOnAnimation

    power_on_animation = PowerOnAnimation()
    power_on_animation.play()
    del power_on_animation
    gc.collect()
"""end of animation, resources of animation are freed inside the function"""

from src.utils import GlobalSettings, load_settings
from src.state_machine import StateMachine

if __name__ == "__main__":
    # load settings:
    load_settings("config.json")
    # init state machine
    state_machine = StateMachine()
    state_machine.preload_states()
    # connect wlan
    if GlobalSettings.wifi_auto_connect:
        state_machine.data_network.connect_wlan()
    # start from user selection
    state_machine.set(state_code=state_machine.STATE_USER_SELECT)
    while True:
        state_machine.run()
