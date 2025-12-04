import network
from src.utils import GlobalSettings, print_log, load_users_list
import json
from umqtt.simple import MQTTClient
import ubinascii
import time

class PicoNetwork:
    def __init__(self):
        self._wlan = network.WLAN(network.STA_IF)
        self._mqtt_client = MQTTClient("", GlobalSettings.mqtt_broker_ip)
        self._mac_address = None
        self._mqtt_response_received = False
        self._mqtt_response = None
        self._mqtt_response_topic = None

    def connect_wlan(self):
        if not self._wlan.isconnected():
            self._wlan.active(True)
            self._wlan.connect(GlobalSettings.wifi_ssid, GlobalSettings.wifi_password)

    def connect_mqtt(self):
        try:
            self._mqtt_client.connect(clean_session=True, timeout=0.2)
            if not self.is_mqtt_connected():
                print_log("MQTT connect failed")
                return False
            print_log("MQTT connected")
            print_log("Trying to set MQTT callback")
            self._mqtt_client.set_callback(self._mqtt_message_callback)
            # init subscriptions after connection
            print_log("Trying to init MQTT subscriptions")
            self._init_subscriptions()
            # register device, duplicate registrations are handled by server, no need to check beforehand
            print_log("Trying to register device via MQTT")
            self._register_device()
        except Exception as e:
            print_log(f"MQTT connect failed: {e}")
            return False
        return True

    def mqtt_publish(self, topic, message):
        if GlobalSettings.mqtt_auto_connect:
            if self.is_mqtt_connected():
                print_log("Publishing and MQTT already connected")
            else:
                # try to connect mqtt
                max_retry = 3
                retry = 0
                while not self.is_mqtt_connected() and retry < max_retry:
                    print_log("MQTT not connected, trying to connect...")
                    self.connect_mqtt()
                    retry += 1

                # check connection status again
                if self.is_mqtt_connected():
                    print_log("MQTT connected")
                else:
                    print_log("MQTT not connected after retries")
                    return False
        else:
            if not self.is_mqtt_connected():
                print_log("MQTT not connected and auto connect disabled")
                return False
        try:
            print_log(f"Publishing MQTT message to topic {topic}: {message}")
            self._mqtt_client.publish(topic, message)
            # clean stale response if any
            self._mqtt_response = None
            self._mqtt_response_received = False
            self._mqtt_response_topic = None
        except Exception as e:
            print_log(f"MQTT publish failed: {e}")
            return False
        return True

    def is_wlan_connected(self):
        return self._wlan.isconnected()

    def get_wlan_ip(self):
        return self._wlan.ifconfig()[0]

    def get_mac_address(self):
        if self._mac_address is None:
            mac_bytes = self._wlan.config('mac')
            self._mac_address = ubinascii.hexlify(mac_bytes).decode().upper()
        return self._mac_address

    def get_broker_ip(self):
        return GlobalSettings.mqtt_broker_ip

    def is_mqtt_connected(self):
        try:
            self._mqtt_client.ping()
        except Exception as e:
            print_log(f"MQTT connection check failed: {e}")
            return False
        return True

    def get_mqtt_response(self, expected_topic_str):
        try:
            self._mqtt_client.check_msg()
        except Exception as e:
            print_log(f"MQTT check_msg failed: {e}")
            return None

        if not self._mqtt_response_received:
            return None

        expected_topic = expected_topic_str.encode('utf-8')
        if self._mqtt_response_topic != expected_topic:
            print_log(f"Topic mismatch, skipped. Expected {expected_topic}, got {self._mqtt_response_topic}")
            return None

        response = self._mqtt_response
        # Verify MAC address matches
        if response.get("mac") != self._mac_address:
            print_log(f"MAC mismatch: expected {self._mac_address}, got {response.get('mac')}")
            return None

        self._mqtt_response = None
        self._mqtt_response_received = False
        self._mqtt_response_topic = None
        return response

    def wait_mqtt_response_blocking(self, expected_topic_str, max_retry=3, timeout=5000, polling_interval=500):
        """Blocking wait for MQTT response with retries."""
        retry = 0
        while retry < max_retry:
            start_time = time.ticks_ms()
            while time.ticks_diff(time.ticks_ms(), start_time) < timeout:
                response = self.get_mqtt_response(expected_topic_str)
                if response:
                    return response
                time.sleep_ms(polling_interval)
            retry += 1
            print_log(f"Retry {retry}/{max_retry} for MQTT response...")
        print_log("MQTT response timeout")
        return None

    def check_user_registration(self):
        """Check if users and ids exist or match in the database.
        If not exist, register the user. If exist but not match, give log warning.
        """
        list_topic = "database/patients/list"
        list_message = json.dumps({"mac": self.get_mac_address()})
        self.mqtt_publish(list_topic, list_message)

        print_log("Waiting for database user list response...")
        response = self.wait_mqtt_response_blocking("database/response", max_retry=3, timeout=3000)
        if not response:
            return

        if response.get("message") != "OK":
            print_log(f"Database response error: {response.get('message')}")
            return

        users_in_db = response.get("data")
        local_users = load_users_list()

        print_log(f"response: {response}")
        print_log(f"users_in_db: {users_in_db}")
        print_log(f"local_users: {local_users}")

        # Convert list of user dicts to dict mapping ID -> Name
        users_in_db_dict = {user['ID']: user['Name'] for user in users_in_db}

        # Check each local user against database, register if not present
        # However, due to:
        #   1. the limitation of the database, whose id doesn't monotonically increase,
        #   2. the local user list is also just a simple list, whose id also doesn't monotonically auto-increase,
        # we assume that user list locally and remotely are always in order and no skipped IDs in between.
        for uid, name in enumerate(local_users, start=1):
            if uid in users_in_db_dict:
                if users_in_db_dict[uid] != name:
                    print_log(f"User ID {uid} name mismatch: local '{name}' vs db '{users_in_db_dict[uid]}'."
                              f"Please resolve manually.")
                else:
                    print_log(f"User ID {uid} with name '{name}' already registered, no action needed.")
            else:
                # Register user
                reg_topic = "database/patients/add"
                reg_message = json.dumps({
                    "mac": self.get_mac_address(),
                    "patient_name": name,
                })
                self.mqtt_publish(reg_topic, reg_message)
                reg_response = self.wait_mqtt_response_blocking("database/response", max_retry=3, timeout=3000)
                if reg_response and reg_response.get("message") == "OK":
                    print_log(f"User '{name}' registered successfully.")
                else:
                    print_log(f"Failed to register user '{name}': {reg_response}")

    def _mqtt_message_callback(self, topic, msg):
        """Handle incoming MQTT messages."""
        try:
            self._mqtt_response = json.loads(msg)
            self._mqtt_response_received = True
            self._mqtt_response_topic = topic
        except Exception as e:
            print_log(f"Failed to parse MQTT message: {e}")
            self._mqtt_response = None
            self._mqtt_response_received = False
            self._mqtt_response_topic = None
            return

    def _init_subscriptions(self):
        print_log(f"Subscribing to MQTT topics")
        self._mqtt_client.subscribe(b"kubios/response")
        self._mqtt_client.subscribe(b"database/response")

    def _register_device(self):
        """Register device with the server via MQTT."""
        topic = "database/devices/add"
        message = json.dumps({
            "mac": self.get_mac_address(),
            "device_name": "HeartWave pico"
        })
        print_log(f"Registering device: {message}")
        self.mqtt_publish(topic, message)
        response = self.wait_mqtt_response_blocking("database/response", max_retry=3, timeout=3000)
        # not important to check duplicate registration here, but we need to consume the response
        if response and response.get("message") == "OK":
            print_log("Device registration successful")
        else:
            print_log(f"Device registration failed: {response}")
