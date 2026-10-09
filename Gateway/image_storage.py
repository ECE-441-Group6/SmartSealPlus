# Handles naming and storing captured tamper-event images.
from pathlib import Path

IMAGE_FOLDER = Path(__file__).resolve().parent / "images"
# Ensure the dashboard can serve the destination before capture begins.
IMAGE_FOLDER.mkdir(exist_ok=True)


def image_path(name):
    # Keep filename construction in one place for the gateway and dashboard.
    return IMAGE_FOLDER / name