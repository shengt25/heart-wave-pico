import time
import os
import gc
import machine
import json


class GlobalSettings:
    print_log = False
    save_directory = "Saved_Values"
    files_limit = 1000
    wifi_ssid = ""
    wifi_password = ""
    wifi_auto_connect = False
    mqtt_broker_ip = ""
    kubios_apikey = ""
    kubios_client_id = ""
    kubios_client_secret = ""


def print_log(message):
    if GlobalSettings.print_log:
        print(time.ticks_ms(), message)


def pico_stat():
    """Return a tuple of used ram, free ram, total ram, free storage, all in KB.
    Note: If the result is going to be printed out in Thonny, the ram usage is inaccurate.
    Because every time Thonny prints to the console, it uses some memory as print history buffer.
    Those part of memory will be freed automatically after buffer is full.
    The result is accurate when running on the board itself."""
    ram_free = round(gc.mem_free() / 1024, 2)
    ram_used = round(gc.mem_alloc() / 1024, 2)
    ram_total = round(ram_free + ram_used, 2)
    s = os.statvfs('/')
    storage_free = s[0] * s[3] / 1024
    return ram_used, ram_free, ram_total, storage_free


def pico_rom_stat():
    """Return free storage in KB. The total storage is 2MB, but approx 832KB is usable with MicroPython firmware."""
    s = os.statvfs('/')
    storage_free = s[0] * s[3] / 1024
    return storage_free


def load_settings(filename):
    """Parse settings from config file(*.json), saved as json format."""
    try:
        with open(filename, "r") as file:
            settings = json.load(file)
            GlobalSettings.files_limit = settings["files_limit"]
            GlobalSettings.wifi_ssid = settings["wifi_ssid"]
            GlobalSettings.wifi_password = settings["wifi_password"]
            GlobalSettings.wifi_auto_connect = settings["wifi_auto_connect"]
            GlobalSettings.mqtt_broker_ip = settings["mqtt_broker_ip"]
            GlobalSettings.kubios_apikey = settings["kubios_apikey"]
            GlobalSettings.kubios_client_id = settings["kubios_client_id"]
            GlobalSettings.kubios_client_secret = settings["kubios_client_secret"]
    except OSError:
        raise OSError("config file not found in the root directory.")


def get_datetime():
    rtc = machine.RTC()  # time initialization
    year, month, day, _, hour, minute, second, _ = rtc.datetime()
    year = year % 100  # only last 2 digits
    datetime = "{:02d}.{:02d}.{} {:02d}:{:02d}:{:02d}".format(day, month, year, hour, minute, second)
    return datetime


