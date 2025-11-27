import network
from src.utils import GlobalSettings, print_log
import json
from umqtt.simple import MQTTClient
import ubinascii


class PicoNetwork:
    def __init__(self):
        self._wlan = network.WLAN(network.STA_IF)
        self._mqtt_client = MQTTClient("", GlobalSettings.mqtt_broker_ip)
        self._kubios_response = None
        self._response_received = False
        self._mac_address = None

    def connect_wlan(self):
        if not self._wlan.isconnected():
            self._wlan.active(True)
            self._wlan.connect(GlobalSettings.wifi_ssid, GlobalSettings.wifi_password)

    def connect_mqtt(self):
        try:
            self._mqtt_client.connect(clean_session=True)
            self._mqtt_client.set_callback(self._mqtt_message_callback)
            self._mqtt_client.subscribe(b"kubios/response")
            self._kubios_response = None
            self._response_received = False
        except:
            return False
        return True

    def mqtt_publish(self, result):
        measurement = {"mean_hr": result["HR"], "mean_ppi": result["IBI"],
                       "rmssd": result["RMSSD"], "sdnn": result["SDNN"]}
        topic = "hwp/measurement"
        message = json.dumps(measurement)
        try:
            self._mqtt_client.publish(topic, message)
        except:
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
            self._mqtt_client.publish("hwp/test", "test connection")
        except:
            return False
        return True

    def _mqtt_message_callback(self, topic, msg):
        """Handle incoming MQTT messages."""
        if topic == b"kubios/response":
            try:
                self._kubios_response = json.loads(msg)
                self._response_received = True
            except:
                self._kubios_response = None
                self._response_received = False

    def send_kubios_request(self, payload):
        """
        Publish Kubios analysis request.

        Args:
            payload: dict with keys: mac, type, data, analysis

        Returns:
            bool: True if published successfully

        Note: An example of payload:
        {
          "mac": "AABBCCDDEEFF",
          "type": "RRI",
          "data": [
            828, 836, 852, 760, 800, 796, 856, 824, 808, 776, 724, 816, 800, 812, 812,
            812, 756, 820, 812, 800
          ],
          "analysis": { "type": "readiness" }
        }
        """
        topic = "kubios/request"
        message = json.dumps(payload)
        try:
            self._mqtt_client.publish(topic, message)
            # Clear stale response if any
            self._kubios_response = None
            self._response_received = False
        except:
            return False
        return True

    def get_kubios_response(self):
        """
        Check for new MQTT messages and return Kubios response if available.
        Returns None if no response yet.
        """
        # Check for new MQTT messages (triggers callback)
        try:
            self._mqtt_client.check_msg()
        except:
            pass

        # Return and consume response if available
        if self._response_received:
            response = self._kubios_response
            self._kubios_response = None
            self._response_received = False
            return response
        return None