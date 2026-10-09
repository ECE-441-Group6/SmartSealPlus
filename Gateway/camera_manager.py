"""Capture real event images from the Raspberry Pi camera."""

import atexit
from datetime import datetime, timezone

from image_storage import image_path


_camera = None


def _get_camera():
    global _camera

    if _camera is None:
        # Initialize the physical camera once and reuse it for each event.
        from picamera2 import Picamera2

        _camera = Picamera2()
        _camera.configure(_camera.create_still_configuration())
        _camera.start()

    return _camera


def _close_camera():
    global _camera

    if _camera is not None:
        _camera.stop()
        _camera.close()
        _camera = None


atexit.register(_close_camera)


def capture_image(packet):
    # Store a unique filename so each sensor event keeps its own evidence.
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    filename = f"seal_{packet['seal_id']}_{timestamp}.jpg"
    path = image_path(filename)

    try:
        # The dashboard serves this file from the gateway image directory.
        _get_camera().capture_file(str(path))
        print(f"Image captured: {path}")
    except ImportError:
        _create_simulated_image(path, packet)
        print(f"Simulated image captured: {path} (picamera2 is unavailable)")

    return filename


def _create_simulated_image(path, packet):
    # Pillow creates a JPEG that looks like camera evidence but contains the
    # sensor packet values instead of a real view of the seal.
    from PIL import Image, ImageDraw

    image = Image.new("RGB", (960, 540), (24, 35, 45))
    draw = ImageDraw.Draw(image)
    draw.text((48, 48), "SmartSeal simulated camera frame", fill=(235, 240, 242))
    draw.text((48, 110), f"Seal: {packet['seal_id']}", fill=(235, 240, 242))
    draw.text((48, 150), f"Tamper: {packet['tamper']}", fill=(255, 184, 77))
    draw.text((48, 190), f"Vibration: {packet['vibration']}", fill=(255, 184, 77))
    draw.text((48, 230), f"Temperature: {packet['temperature']} C", fill=(235, 240, 242))
    image.save(path, "JPEG")