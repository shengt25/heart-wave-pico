import network
from src.utils import GlobalSettings, print_log
import json
from umqtt.simple import MQTTClient
import ubinascii


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
            self._mqtt_client.set_callback(self._mqtt_message_callback)
            # init subscriptions after connection
            self._init_subscriptions()
        except Exception as e:
            print_log(f"MQTT connect failed: {e}")
            return False
        return True

    def mqtt_publish(self, topic, message):
        if GlobalSettings.mqtt_auto_connect:
            if self.is_mqtt_connected():
                print_log("MQTT already connected")
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
            pass

        expected_topic = expected_topic_str.encode('utf-8')
        if self._mqtt_response_received:
            if self._mqtt_response_topic != expected_topic:
                print_log(f"Topic mismatch, skipped. Expected {expected_topic}, got {self._mqtt_response_topic}")
                return None
            else:
                response = self._mqtt_response
                self._mqtt_response = None
                self._mqtt_response_received = False
                self._mqtt_response_topic = None
                return response
        else:
            return None

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
        self._mqtt_client.subscribe(b"kubios/response")