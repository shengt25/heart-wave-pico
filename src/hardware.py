from machine import Pin, I2C, ADC
from ssd1306 import SSD1306_I2C as SSD1306_I2C_
import time
from piotimer import Piotimer
from src.utils import print_log
from src.data_processing import Fifo


class EncoderEvent:
    NONE = 0
    ROTATE = 1
    PRESS = 2


class HeartSensor:
    def __init__(self, pin=26, sampling_rate=250):
        self._adc = ADC(Pin(pin))
        self._sampling_rate = sampling_rate
        self._timer = None
        self.sensor_fifo = Fifo(100, 'H')
        self._started = False

    def start(self):
        if self._started:
            return
        self._timer = Piotimer(freq=self._sampling_rate, callback=self._sensor_handler)
        self._started = True

    def stop(self):
        if not self._started:
            return
        self._timer.deinit()
        self.sensor_fifo.clear()
        self._started = False

    def get_sampling_rate(self):
        return self._sampling_rate

    def read(self):
        """Read the current sensor value directly."""
        return self._adc.read_u16() >> 2

    def _sensor_handler(self, tid):
        # The sensor actually only has 14-bit resolution, but the ADC is set to 16-bit,
        # so the value is shifted right by 2 to get the 14-bit value to reduce calculation
        self.sensor_fifo.put(self._adc.read_u16() >> 2)


class RotaryEncoder:
    EVENT_NONE = 0
    EVENT_ROTATE = 1
    EVENT_PRESS = 2

    def __init__(self, clk_pin=10, dt_pin=11, btn_pin=12, btn_debounce_ms=50):
        self._clk = Pin(clk_pin, Pin.IN, Pin.PULL_UP)
        self._dt = Pin(dt_pin, Pin.IN, Pin.PULL_UP)
        self._button = Pin(btn_pin, Pin.IN, Pin.PULL_UP)
        self._btn_debounce_ms = btn_debounce_ms
        self._last_press_time = time.ticks_ms()
        self._event_fifo = Fifo(20, 'h')
        # register press interrupt by default (because every state needs it)
        self._button.irq(trigger=Pin.IRQ_RISING, handler=self._press_handler, hard=True)

        self._items_count = 0
        self._loop_mode = False
        self._position = 0

    """public methods"""

    def enable_rotate(self, items_count, position=0, loop_mode=False):
        """Set irq, max index, current position, and whether loop back at limit, or stop."""
        self._items_count = items_count
        self._loop_mode = loop_mode
        self._position = position
        self._dt.irq(trigger=Pin.IRQ_RISING, handler=self._rotate_handler, hard=True)

    def disable_rotate(self):
        self._dt.irq(handler=None)

    def enable_press(self):
        self._button.irq(trigger=Pin.IRQ_RISING, handler=self._press_handler, hard=True)

    def disable_press(self):
        self._button.irq(handler=None)

    def get_position(self):
        """Get the current absolute position of the encoder."""
        print_log("Encoder position:" + str(self._position))
        return self._position

    def get_event(self):
        """Event needs to be got in the main loop and fast, to avoid fifo overflow."""
        if self._event_fifo.has_data():
            while self._event_fifo.has_data():
                value = self._event_fifo.get()
                if value == 0:  # return press event, ignore the rest of the fifo (usually rotate event)
                    self._event_fifo.clear()
                    return self.EVENT_PRESS
                else:  # return rotate event
                    self._cal_position(value)
            return self.EVENT_ROTATE
        else:
            return self.EVENT_NONE

    """private methods"""

    def _cal_position(self, value):
        if self._loop_mode:
            self._position = (self._position + value) % self._items_count
        else:
            self._position = max(0, min(self._items_count - 1, self._position + value))

    def _rotate_handler(self, pin):
        if self._clk.value():
            self._event_fifo.put(1)
        else:
            self._event_fifo.put(-1)

    def _press_handler(self, pin):
        current_time = time.ticks_ms()
        if current_time - self._last_press_time > self._btn_debounce_ms:
            self._event_fifo.put(0)
            self._last_press_time = time.ticks_ms()


class Display(SSD1306_I2C_):
    FONT_SIZE = 8  # font size in pixel

    def __init__(self, width=128, height=64, scl=15, sda=14, refresh_rate=40):
        self.width = width
        self.height = height
        self._updated = False
        self._update_force = False  # force update once regardless of refresh rate
        self._last_update_time = 0
        self._refresh_period = 1000 // refresh_rate
        super().__init__(width, height, I2C(1, scl=Pin(scl), sda=Pin(sda), freq=400000))

    def refresh(self):
        """
        Refresh the screen, call this in the main loop.
        It will only update the screen if the screen has been marked as updated by set_update() method.
        And the screen will only be updated at the refresh rate"""
        if (time.ticks_diff(time.ticks_ms(),
                            self._last_update_time) > self._refresh_period and self._updated) or self._update_force:
            super().show()
            print_log("screen updated")
            self._last_update_time = time.ticks_ms()
            self._updated = False
            self._update_force = False

    def set_update(self, force=False):
        """Mark the screen as updated.
        The option 'force' will update the screen at next 'refresh' regardless of the refresh rate, but only once."""
        if force:
            self._update_force = True
        else:
            self._updated = True
