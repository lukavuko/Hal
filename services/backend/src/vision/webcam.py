import logging
from typing import Dict, Generator, Optional

import cv2
from PIL import Image

logger = logging.getLogger(__name__)


class WebcamCapture:
    def __init__(self, device_id: int = None, max_device_index: int = 10):
        """
        Initialize webcam capture.

        Args:
            device_id: Specific device index to use. If None, will auto-detect.
            max_device_index: Maximum index to try when auto-detecting.
        """
        self.device_id = device_id
        self.max_device_index = max_device_index
        self.cap: Optional[cv2.VideoCapture] = None

    def _try_open_device(self, device_id: int) -> bool:
        """Try to open a specific device index."""
        logger.info(f"Trying webcam device index {device_id}...")
        cap = cv2.VideoCapture(device_id)
        if cap.isOpened():
            # Try to read a test frame to confirm it works
            ret, _ = cap.read()
            if ret:
                self.cap = cap
                self.device_id = device_id
                logger.info(f"Successfully opened webcam at index {device_id}")
                return True
            cap.release()
        return False

    def initialize(self) -> bool:
        """Initialize webcam, auto-detecting device if needed."""
        # If specific device_id provided, try only that
        if self.device_id is not None:
            if self._try_open_device(self.device_id):
                return True
            logger.error(f"Failed to open specified webcam device {self.device_id}")
            return False

        # Auto-detect: try indices 0 through max_device_index
        logger.info(
            f"Auto-detecting webcam (trying indices 0-{self.max_device_index})..."
        )
        for idx in range(self.max_device_index + 1):
            if self._try_open_device(idx):
                return True

        logger.error(f"No webcam found after trying indices 0-{self.max_device_index}")
        return False

    def get_dimensions(self) -> Dict[str, int]:
        """
        Get the current webcam dimensions.

        Returns:
            Dict with 'width' and 'height' keys
        """
        if not self.cap or not self.cap.isOpened():
            if not self.initialize():
                return {"width": 640, "height": 480}  # Default fallback

        width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        logger.info(f"Webcam dimensions: {width}x{height}")
        return {"width": width, "height": height}

    def capture_frame(self) -> Optional[Image.Image]:
        if not self.cap or not self.cap.isOpened():
            if not self.initialize():
                return None

        ret, frame = self.cap.read()
        if not ret:
            logger.warning("Failed to read frame from webcam")
            return None

        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        return Image.fromarray(frame_rgb)

    def generate_frames(self) -> Generator[bytes, None, None]:
        """
        Generator that yields JPEG frames for MJPEG streaming.

        Yields:
            bytes: MJPEG frame with boundary markers
        """
        if not self.cap or not self.cap.isOpened():
            if not self.initialize():
                logger.error("Cannot start stream: webcam not available")
                return

        logger.info("Starting MJPEG stream")
        try:
            while True:
                ret, frame = self.cap.read()
                if not ret:
                    logger.warning("Failed to read frame during streaming")
                    break

                # Encode frame as JPEG
                encode_params = [cv2.IMWRITE_JPEG_QUALITY, 80]
                _, buffer = cv2.imencode(".jpg", frame, encode_params)

                # Yield as MJPEG frame with boundary
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n\r\n" + buffer.tobytes() + b"\r\n"
                )
        finally:
            logger.info("MJPEG stream ended")

    def release(self):
        if self.cap:
            self.cap.release()
