
"""
SmartSeal+ Raspberry Pi Gateway Camera
Camera: Raspberry Pi Camera Module 2 (IMX219)

Features:
- Initializes the camera
- Captures timestamped JPEG images
- Saves images in the camera_test folder
- Can be imported by the main gateway program
"""

from datetime import datetime
from pathlib import Path
from time import sleep
from picamera2 import Picamera2

# Project image storage directory
IMAGE_DIR = Path.home() / "SmartSealPlus" / "TestFiles" / "camera_test"


class SmartSealCamera:
    def __init__(self, image_dir=IMAGE_DIR):
        self.image_dir = Path(image_dir)
        self.image_dir.mkdir(parents=True, exist_ok=True)

        self.camera = Picamera2()
        config = self.camera.create_still_configuration(
            main={"size": (3280, 2464)}
        )
        self.camera.configure(config)
        self.camera.start()

        # Allow the camera to adjust exposure and white balance
        sleep(2)

        print("SmartSeal+ camera initialized.")
        print(f"Image directory: {self.image_dir}")

    def capture_image(self, event="manual"):
        """Capture an image and return its saved file path."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        safe_event = "".join(
            c if c.isalnum() or c in "-_" else "_"
            for c in event
        )

        filename = f"{safe_event}_{timestamp}.jpg"
        image_path = self.image_dir / filename

        self.camera.capture_file(str(image_path))

        print(f"Image captured: {image_path}")
        return image_path

    def close(self):
        """Release the camera."""
        self.camera.stop()
        self.camera.close()
        print("Camera stopped.")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()


def main():
    print("SmartSeal+ Gateway Camera Test")
    print("------------------------------")

    with SmartSealCamera() as camera:
        while True:
            print("\nOptions:")
            print("1. Capture test image")
            print("2. Capture tamper-event image")
            print("3. Exit")

            choice = input("Select an option: ").strip()

            if choice == "1":
                camera.capture_image("manual_test")

            elif choice == "2":
                # Demonstration only: no real tamper sensor is connected here.
                camera.capture_image("tamper_demo")

            elif choice == "3":
                break

            else:
                print("Invalid choice. Enter 1, 2, or 3.")


if __name__ == "__main__":
    main()
