# Provides optional local Ollama image analysis with a sensor-only fallback.
import base64
import json
import os
from urllib.request import Request, urlopen

if __package__:
    from .alert_manager import TEMP_HIGH, TEMP_LOW
else:
    from alert_manager import TEMP_HIGH, TEMP_LOW


def analyze_image(filename, packet):
    provider = os.getenv("SMARTSEAL_AI_PROVIDER", "ollama").lower()
    if provider == "ollama":
        return _analyze_with_ollama(filename, packet)
    # "none" and unknown provider values use sensor data only. No image or
    # sensor data is sent to an external AI service.
    return _fallback_analysis(packet)


def _analyze_with_ollama(filename, packet):
    try:
        with open(filename, "rb") as image_file:
            encoded_image = base64.b64encode(
                image_file.read()
            ).decode("ascii")

        prompt = (
            "You are inspecting a medical cold-chain security seal called SmartSeal+. "
            "Analyze the provided event image for visible physical evidence of tampering.\n\n"
            "Look for:\n"
            "1. Broken, disconnected, or damaged optical fiber.\n"
            "2. A missing, detached, or displaced seal component.\n"
            "3. Visible physical damage to the seal or its enclosure.\n"
            "4. Anything unusual that could indicate unauthorized access.\n\n"
            "Return a concise assessment with one of these classifications:\n"
            "- INTACT: No visible physical damage or tampering.\n"
            "- POSSIBLE DAMAGE: Something suspicious is visible, but not conclusive.\n"
            "- DAMAGED: Clear visible physical damage or a disconnected component.\n"
            "- INCONCLUSIVE: The image is unclear or does not show enough detail.\n\n"
            "Do not assume tampering occurred just because a sensor was triggered. "
            "Base the visual assessment only on what is actually visible. "
            "Do not invent details.\n\n"
            f"Additional sensor context: "
            f"Temperature={packet.get('temperature')} C, "
            f"Tamper={packet.get('tamper')}, "
            f"Vibration={packet.get('vibration')}, "
            f"Movement type={packet.get('movement_type', 0)}."
        )

        payload = {
            "model": os.getenv("OLLAMA_VISION_MODEL", "moondream"),
            "prompt": prompt,
            "images": [encoded_image],
            "stream": False,
        }

        request = Request(
            os.getenv(
                "OLLAMA_URL",
                "http://127.0.0.1:11434/api/generate"
            ),
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with urlopen(
            request,
            timeout=float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "60")),
        ) as response:
            result = json.load(response)

        analysis = result.get("response", "").strip()

        if not analysis:
            raise ValueError("Ollama returned an empty response")

        return analysis

    except Exception as error:
        return (
            "AI analysis unavailable; sensor evidence: "
            f"{_fallback_analysis(packet)} ({error})"
        )

def _fallback_analysis(packet):
    # Translate boolean sensor flags into a human-readable local summary.
    events = []
    if packet["tamper"]:
        events.append("possible tampering")
    if packet["vibration"]:
        events.append("movement or impact detected")
    if packet.get("movement_type", 0):
        events.append(
            f"accelerometer movement detected (type {packet['movement_type']})"
        )
    if packet["temperature"] is not None:
        if packet["temperature"] > TEMP_HIGH:
            events.append(f"temperature too high ({packet['temperature']} C)")
        elif packet["temperature"] < TEMP_LOW:
            events.append(f"temperature too low ({packet['temperature']} C)")
    return "; ".join(events) or "sensor alert triggered without a specific tamper or vibration classification"
