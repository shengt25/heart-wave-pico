from fifo import Fifo as Fifo_
import array


class Fifo(Fifo_):
    def __init__(self, size, typecode='H'):
        super().__init__(size, typecode)

    def count(self):
        count = ((self.head - self.tail) + self.size) % self.size
        return count

    def clear(self):
        self.tail = self.head

    def peek_history(self, step):
        """Get history data that counting 'step' samples from the current to the past
        If the data is already overwritten, raises an exception."""
        if step >= self.size:
            raise RuntimeError("Step is larger than the fifo size")
        elif step + self.count() > self.size:
            raise RuntimeError("Data has been overwritten")
        else:
            ptr = ((self.tail - step) + self.size) % self.size
            return self.data[ptr]


class Deque:
    """A fixed size circular deque implementation"""

    def __init__(self, size, typecode='H'):
        self.size = size
        self.buffer = array.array(typecode)
        for i in range(size):
            self.buffer.append(0)
        self.tail = 0
        self.head = 0
        self.count = 0

    def append_right(self, value):
        if self.count == self.size:
            raise Exception("Deque is full")
        self.buffer[self.head] = value
        self.head = (self.head + 1) % self.size
        self.count += 1

    def append_left(self, value):
        if self.count == self.size:
            raise Exception("Deque is full")
        self.tail = (self.tail - 1) % self.size
        self.buffer[self.tail] = value
        self.count += 1

    def pop_right(self):
        if self.count == 0:
            raise Exception("Deque is empty")
        self.head = (self.head - 1) % self.size
        value = self.buffer[self.head]
        self.count -= 1
        return value

    def pop_left(self):
        if self.count == 0:
            raise Exception("Deque is empty")
        value = self.buffer[self.tail]
        self.tail = (self.tail + 1) % self.size
        self.count -= 1
        return value

    def peek_right(self):
        if self.count == 0:
            raise Exception("Deque is empty")
        return self.buffer[(self.head - 1) % self.size]

    def peek_left(self):
        if self.count == 0:
            raise Exception("Deque is empty")
        return self.buffer[self.tail]

    def peek(self, index):
        if index >= self.count:
            raise Exception("Index out of range")
        return self.buffer[(self.tail + index) % self.size]

    def has_data(self):
        return self.count > 0

    def clear(self):
        self.tail = 0
        self.head = 0
        self.count = 0


class SlidingWindow:
    def __init__(self, size, typecode='H'):
        self.size = size
        self.deque_max = Deque(size, typecode)
        self.deque_min = Deque(size, typecode)
        self.current_window = Deque(size, typecode)
        self.sum = 0

    def push(self, value):
        if self.current_window.count == self.size:
            expiring_value = self.current_window.pop_left()
            if expiring_value == self.deque_max.peek_left():
                self.deque_max.pop_left()
            if expiring_value == self.deque_min.peek_left():
                self.deque_min.pop_left()
            self.sum -= expiring_value

        while self.deque_max.has_data() and self.deque_max.peek_right() < value:
            self.deque_max.pop_right()
        while self.deque_min.has_data() and self.deque_min.peek_right() > value:
            self.deque_min.pop_right()
        self.deque_max.append_right(value)
        self.deque_min.append_right(value)
        self.current_window.append_right(value)
        self.sum += value

    def get_max(self):
        return self.deque_max.peek_left() if self.deque_max.has_data() else None

    def get_min(self):
        return self.deque_min.peek_left() if self.deque_min.has_data() else None

    def get_average(self):
        return self.sum / self.current_window.count if self.current_window.count > 0 else None

    def get_mid_index_value(self):
        return self.current_window.peek(self.current_window.count // 2)

    def is_window_filled(self):
        return self.current_window.count == self.size

    def clear(self):
        self.deque_max.clear()
        self.deque_min.clear()
        self.current_window.clear()
        self.sum = 0

    def has_data(self):
        return self.current_window.has_data()
