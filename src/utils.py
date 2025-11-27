import time
import os
import gc
import machine
import json
import random


class GlobalSettings:
    debug_print = False
    save_directory = "Saved_Values"
    files_limit = 1000
    wifi_ssid = ""
    wifi_password = ""
    wifi_auto_connect = False
    mqtt_broker_ip = ""
    mqtt_auto_connect = False


def print_log(message):
    if GlobalSettings.debug_print:
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
            GlobalSettings.mqtt_auto_connect = settings["mqtt_auto_connect"]
            GlobalSettings.debug_print = settings["debug_print"]
    except OSError:
        raise OSError("config file not found in the root directory.")


def get_datetime():
    rtc = machine.RTC()  # time initialization
    year, month, day, _, hour, minute, second, _ = rtc.datetime()
    year = year % 100  # only last 2 digits
    datetime = "{:02d}.{:02d}.{} {:02d}:{:02d}:{:02d}".format(day, month, year, hour, minute, second)
    return datetime


def get_ntp_timestamp():
    rtc = machine.RTC()
    dt = rtc.datetime()
    unix_time = time.mktime((dt[0], dt[1], dt[2], dt[4], dt[5], dt[6], 0, 0))
    ntp_seconds = unix_time + 2208988800
    return ntp_seconds


def ntp_timestamp_to_datetime(ntp_seconds):
    unix_time = ntp_seconds - 2208988800
    tm = time.localtime(unix_time)
    year = tm[0] % 100  # only last 2 digits
    datetime = "{:02d}.{:02d}.{} {:02d}:{:02d}:{:02d}".format(tm[2], tm[1], year, tm[3], tm[4], tm[5])
    return datetime


def load_users_list():
    """Load users from users.json file.
    Returns a dictionary of {id: name} pairs.
    If file doesn't exist or is malformed, creates a default file.

    Returns:
        dict: Dictionary mapping user IDs to names
    """
    filename = "users.json"
    try:
        with open(filename, "r") as file:
            users = json.load(file)
            # Validate structure
            if not isinstance(users, dict):
                raise ValueError("users.json must contain a dictionary")
            for key, value in users.items():
                if not isinstance(key, str) or not isinstance(value, str):
                    raise ValueError("Keys and values must be strings")
            return users
    except Exception as e:
        print_log(f"users.json error ({e})")

def get_user_name_by_id(user_id):
    """Get user name from ID by loading users.json.

    Args:
        user_id (str): The user ID to lookup

    Returns:
        str: The user name, or "Unknown User" if ID not found
    """
    try:
        users = load_users_list()
        return users.get(user_id, "Unknown User")
    except OSError:
        return "Unknown User"