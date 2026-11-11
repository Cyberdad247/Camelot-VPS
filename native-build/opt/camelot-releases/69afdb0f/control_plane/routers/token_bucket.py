import time
import threading

class TokenBucket:
    def __init__(self, capacity, fill_rate):
        self.capacity = capacity
        self.tokens = capacity
        self.fill_rate = fill_rate
        self.timestamp = time.time()
        self.lock = threading.Lock()

    def consume(self, tokens=1):
        with self.lock:
            now = time.time()
            elapsed = now - self.timestamp
            # Refill tokens based on time elapsed
            self.tokens = min(self.capacity, self.tokens + elapsed * self.fill_rate)
            self.timestamp = now
            
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False
