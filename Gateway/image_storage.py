# Handles naming, saving, and retrieving captured tamper-event images.
import os

IMAGE_FOLDER = "images"

os.makedirs(IMAGE_FOLDER, exist_ok=True)


def save_image(name):

    path = os.path.join(
        IMAGE_FOLDER,
        name
    )

    return path