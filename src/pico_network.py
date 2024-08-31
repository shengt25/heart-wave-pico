import network
from src.utils import GlobalSettings, print_log
import json
from umqtt.simple import MQTTClient


class PicoNetwork:
    def __init__(self):
        self._wlan = network.WLAN(network.STA_IF)
        self._mqtt_client = MQTTClient("", GlobalSettings.mqtt_broker_ip)

    def connect_wlan(self):
        if not self._wlan.isconnected():
            self._wlan.active(True)
            self._wlan.connect(GlobalSettings.wifi_ssid, GlobalSettings.wifi_password)

    def connect_mqtt(self):
        try:
            self._mqtt_client.connect(clean_session=True)
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

    def get_broker_ip(self):
        return GlobalSettings.mqtt_broker_ip

    def is_mqtt_connected(self):
        try:
            self._mqtt_client.publish("hwp/test", "test connection")
        except:
            return False
        return True
