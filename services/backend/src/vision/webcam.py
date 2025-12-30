from typing import Optional

import cv2
from PIL import Image


class WebcamCapture:
    def __init__(self, device_id: int = 0):
        self.device_id = device_id
        self.cap: Optional[cv2.VideoCapture] = None

    def initialize(self) -> bool:
        self.cap = cv2.VideoCapture(self.device_id)
        if not self.cap.isOpened():
            return False
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        return True

    def capture_frame(self) -> Optional[Image.Image]:
        if not self.cap or not self.cap.isOpened():
            if not self.initialize():
                return None

        ret, frame = self.cap.read()
        if not ret:
            return None

        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        return Image.fromarray(frame_rgb)

    def release(self):
        if self.cap:
            self.cap.release()
