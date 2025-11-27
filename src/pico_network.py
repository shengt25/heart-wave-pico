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
            self._mqtt_client.connect(clean_session=True, timeout=0.2)
            self._mqtt_client.set_callback(self._mqtt_message_callback)
            self._mqtt_client.subscribe(b"kubios/response")
            self._kubios_response = None
            self._response_received = False
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

    def _mqtt_message_callback(self, topic, msg):
        """Handle incoming MQTT messages."""
        if topic == b"kubios/response":
            try:
                self._kubios_response = json.loads(msg)
                self._response_received = True
            except Exception as e:
                print_log(f"Failed to parse Kubios response: {e}")
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
        except Exception as e:
            print_log(f"Kubios request publish failed: {e}")
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
        except Exception as e:
            print_log(f"MQTT check_msg failed: {e}")
            pass

        # Return and consume response if available
        if self._response_received:
            response = self._kubios_response
            self._kubios_response = None
            self._response_received = False
            return response
        return None