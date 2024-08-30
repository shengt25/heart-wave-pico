"""HeartWave Pico"""

"""animation has to be the first, even before any imports, otherwise RAM will be full"""
power_on_animation = True
if power_on_animation:
    import gc

    from resources.animation_power_on import PowerOnAnimation

    power_on_animation = PowerOnAnimation()
    power_on_animation.play()
    del power_on_animation
    gc.collect()
"""end of animation, resources of animation are freed inside the function"""

from utils import GlobalSettings, load_settings
from state_machine import StateMachine
from save_system import check_home_dir

if __name__ == "__main__":
    # load settings:
    load_settings("config.json")
    GlobalSettings.print_log = False
    # init state machine
    state_machine = StateMachine()
    state_machine.preload_states()
    # connect wlan
    if GlobalSettings.wifi_auto_connect:
        state_machine.data_network.connect_wlan()
    # start from main menu
    state_machine.set(state_code=state_machine.STATE_MENU)
    # check for save directory
    check_home_dir()
    while True:
        state_machine.run()
