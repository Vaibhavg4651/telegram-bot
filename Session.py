import asyncio
import threading


class UserSession:
    def __init__(self):
        self.policy_messages: list = []
        self.capturing_policies: bool = False
        self.policy_start_time: float = 0
        self.min_messages_reached: bool = False
        self.lock = threading.Lock()

    def start_capture(self):
        with self.lock:
            self.policy_messages = []
            self.capturing_policies = True
            self.policy_start_time = asyncio.get_event_loop().time()
            self.min_messages_reached = False

    def end_capture(self):
        with self.lock:
            self.capturing_policies = False
            self.policy_start_time = 0
            self.min_messages_reached = False

    def add_message(self, message: str):
        with self.lock:
            self.policy_messages.append(message)
            if len(self.policy_messages) >= 5:
                self.min_messages_reached = True
