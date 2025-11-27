from src.utils import print_log, get_datetime, get_random_name, GlobalSettings
from math import sqrt
from src.data_structure import Fifo, SlidingWindow
import time
import json


class IBICalculator:
    def __init__(self, sensor_fifo, sampling_rate, min_hr=40, max_hr=180):
        # data store and output
        self.ibi_fifo = Fifo(20, 'H')
        # hardware
        self._sensor_fifo = sensor_fifo
        # init parameters
        self._sampling_rate = sampling_rate
        self._sliding_window = SlidingWindow(size=int(sampling_rate * 1.5))

        self._max_ibi = 60 / min_hr * 1000
        self._min_ibi = 60 / max_hr * 1000
        # data
        self._last_rising_edge_diff = 0
        self._rising_edge_diff = 0
        self._peak = 0
        self._last_peak_index = 0
        self._peak_index = 0
        # settings
        self._debounce_window = 10
        self._debounce_count = 0
        # first state
        self._state = self._state_below_threshold

    """public methods"""

    def reinit(self):
        """Reinitialize the variables to start a new calculation"""
        self._sliding_window.clear()
        self.ibi_fifo.clear()
        self._peak = 0
        self._last_rising_edge_diff = 0
        self._rising_edge_diff = 0
        self._last_peak_index = 0
        self._peak_index = 0
        self._state = self._state_below_threshold

    def run(self):
        self._state()

    def get_window_min(self):
        min_val = self._sliding_window.get_min()
        if self._sliding_window.get_min() is None:
            return 0
        return min_val

    def get_window_max(self):
        max_val = self._sliding_window.get_max()
        if self._sliding_window.get_max() is None:
            return 0
        return max_val

    """private methods"""

    def _get_threshold_and_value(self):
        """Get the value at the center of the window in fifo history, and calculate the threshold"""
        self._sliding_window.push(self._sensor_fifo.get())
        threshold = self._sliding_window.get_average() + (
                self._sliding_window.get_max() - self._sliding_window.get_min()) * 0.3
        value = self._sliding_window.get_mid_index_value()
        return value, threshold

    def _state_below_threshold(self):
        # The while loop is to consume all the data in the fifo at once,
        # not a real "while loop" that will block the system
        while self._sensor_fifo.has_data():
            value, threshold = self._get_threshold_and_value()
            self._rising_edge_diff += 1
            if value > threshold:
                self._debounce_count += 1  # above threshold, start to debounce
            else:
                self._debounce_count = 0  # reset count if below threshold within the debounce window

            # if the debounce window is reached, reset the debounce count and prepare to go to above threshold state
            if self._debounce_count > self._debounce_window:
                self._debounce_count = 0
                self._last_peak_index = self._peak_index
                self._last_rising_edge_diff = self._rising_edge_diff
                self._peak = 0
                self._rising_edge_diff = 0
                self._peak_index = 0
                self._state = self._state_above_threshold
                return

    def _state_above_threshold(self):
        # The while loop is to consume all the data in the fifo at once,
        # not a real "while loop" that will block the system
        while self._sensor_fifo.has_data():
            value, threshold = self._get_threshold_and_value()
            self._rising_edge_diff += 1
            if value > threshold and value > self._peak:
                self._peak = value
                self._peak_index = self._rising_edge_diff

            if value < threshold:
                # last peak is invalid, not calculating but go back and wait for next threshold
                if self._last_peak_index == 0 or self._last_rising_edge_diff == 0:
                    self._state = self._state_below_threshold
                    return
                else:
                    data_points = self._last_rising_edge_diff - self._last_peak_index + self._peak_index
                    ibi = int(data_points * 1000 / self._sampling_rate)
                    if self._min_ibi < ibi < self._max_ibi:
                        self.ibi_fifo.put(ibi)
                    # no need to reset peak_index and rising_edge_diff,
                    # because they will be assigned to last_peak_index and last_rising_edge_diff in the next state
                self._state = self._state_below_threshold
                return


def calculate_hrv(IBI_list_raw):
    # filter out the outlier by removing the IBI that is 30% lower or higher than the mean ibi, with a minimum of 300ms
    IBI_list = []
    mean_ibi = 0
    for ibi in IBI_list_raw:
        mean_ibi += ibi
    mean_ibi /= len(IBI_list_raw)
    threshold_lower = mean_ibi * 0.7
    if threshold_lower < 300:
        threshold_lower = 300
    threshold_higher = mean_ibi * 1.3
    for i in range(len(IBI_list_raw)):
        if threshold_lower < IBI_list_raw[i] < threshold_higher:
            IBI_list.append(IBI_list_raw[i])

    # HR
    average_HR = 0
    for HR in IBI_list:
        average_HR += HR
    average_HR /= len(IBI_list)
    average_HR = 60000 / average_HR

    # PPI
    mean_ibi = 0
    for ibi in IBI_list:
        mean_ibi += ibi
    mean_ibi /= len(IBI_list)

    # RMSSD
    average = 0
    for i in range(1, len(IBI_list), 1):
        difference = (IBI_list[i] - IBI_list[i - 1]) ** 2
        average += difference
    average /= len(IBI_list) - 1
    RMSSD = sqrt(average)

    # SDNN
    mean_val = 0
    for i in IBI_list:
        mean_val += i
    mean_val /= len(IBI_list)
    variance = 0
    for i in IBI_list:
        variance += (i - mean_val) ** 2
    variance /= (len(IBI_list) - 1)
    variance = variance ** 0.5
    SDNN = variance

    # I could've probably done this all in one go but I decided not to give anybody who will read this nightmares.
    return round(average_HR, 2), round(mean_ibi, 2), round(RMSSD, 2), round(SDNN, 2)


def get_kubios_analysis(ibi_list, pico_network, timeout_ms=10000):
    """
    Perform Kubios analysis via MQTT request-response.

    Args:
        ibi_list: List of inter-beat intervals in milliseconds
        pico_network: Reference to PicoNetwork instance
        timeout_ms: Maximum time to wait for response (default: 10000ms)

    Returns:
        tuple(success: bool, result: dict or None)
    """
    device_mac = pico_network.get_mac_address()
    try:
        # Build and publish request
        request_payload = {
            "mac": device_mac,
            "type": "RRI",
            "data": ibi_list,
            "analysis": {"type": "readiness"}
        }

        topic = "kubios/request"
        message = json.dumps(request_payload)
        success = pico_network.mqtt_publish(topic, message)
        if not success:
            print_log("Kubios MQTT publish failed")
            return False, None

        print_log("Kubios request sent, waiting for response...")

        # Blocking wait for response with timeout
        start_time = time.ticks_ms()
        while time.ticks_diff(time.ticks_ms(), start_time) < timeout_ms:
            # Check for new MQTT messages and try to get response
            response = pico_network.get_mqtt_response("kubios/response")
            if response:
                # Verify MAC address matches
                if response.get("mac") == device_mac:
                    # Verify status is ok
                    if response.get("data", {}).get("status") != "ok":
                        print_log("Kubios analysis failed: status not ok")
                        return False, None

                    # Extract analysis data
                    analysis = response.get("data", {}).get("analysis", {})

                    result = {
                        "NAME": get_random_name(),
                        "DATE": get_datetime(),
                        "HR": str(round(analysis["mean_hr_bpm"], 2)) + "BPM",
                        "IBI": str(round(analysis["mean_rr_ms"], 2)) + "ms",
                        "RMSSD": str(round(analysis["rmssd_ms"], 2)) + "ms",
                        "SDNN": str(round(analysis["sdnn_ms"], 2)) + "ms",
                        "SNS": str(round(analysis["sns_index"], 2)),
                        "PNS": str(round(analysis["pns_index"], 2)),
                        "STRESS": str(round(analysis["stress_index"], 2))
                    }
                    return True, result
                else:
                    # MAC mismatch, ignore
                    print_log(f"MAC mismatch: expected {device_mac}, got {response.get('mac')}")

            # Small delay to reduce CPU usage during wait
            time.sleep_ms(50)

        # Timeout reached
        print_log("Kubios analysis timeout")
        return False, None

    except Exception as e:
        print_log(f"Kubios analysis failed: {e}")
        return False, None
