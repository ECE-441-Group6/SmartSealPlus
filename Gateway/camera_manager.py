# Controls the Raspberry Pi camera and provides a desktop-friendly simulator.
# The gateway calls this module only when a tamper or vibration event needs
# image evidence.
from datetime import datetime, timezone

from image_storage import image_path

def capture_image(packet):
    # Use the seal ID and UTC time to create a unique, traceable image name.
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    filename = f"seal_{packet['seal_id']}_{timestamp}.jpg"
    path = image_path(filename)

    try:
        # This import is kept inside the function so the desktop simulation can
        # run without installing Raspberry Pi camera libraries.
        from picamera2 import Picamera2

        # Configure the physical camera for one still image and save it locally.
        camera = Picamera2()
        camera.configure(camera.create_still_configuration())
        camera.start()
        camera.capture_file(str(path))
        camera.stop()
        print(f"Image captured: {path}")
    except Exception as error:
        # Development fallback: create a labeled image when camera hardware or
        # the Picamera2 package is unavailable.
        _create_simulated_image(path, packet)
        print(f"Simulated image captured: {path} ({error})")

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
