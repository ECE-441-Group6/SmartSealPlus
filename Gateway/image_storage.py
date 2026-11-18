# Handles naming and storing captured tamper-event images.
import os
from pathlib import Path

STORAGE_DIRECTORY = Path(__file__).resolve().parent
if os.getenv("SMARTSEAL_SIMULATION", "0") == "1":
    STORAGE_DIRECTORY = STORAGE_DIRECTORY / "simulation"

IMAGE_FOLDER = STORAGE_DIRECTORY / "images"
# Ensure the dashboard can serve the destination before capture begins.
IMAGE_FOLDER.mkdir(mode=0o700, parents=True, exist_ok=True)
if os.name == "posix":
    IMAGE_FOLDER.chmod(0o700)


def image_path(name):
    # Keep filename construction in one place for the gateway and dashboard.
    return IMAGE_FOLDER / name
