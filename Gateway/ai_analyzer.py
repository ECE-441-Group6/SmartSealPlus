# Provides optional image analysis with a local fallback for simulation.
# A configured API key enables remote vision analysis; otherwise the gateway
# produces a short explanation from the sensor readings alone.
import base64
import json
import os
from urllib.request import Request, urlopen


def analyze_image(filename, packet):
    # Read configuration from the environment so credentials are not stored in
    # the repository.
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return _fallback_analysis(packet)

    with open(filename, "rb") as image_file:
        # The image API receives the JPEG as a base64 data URL.
        encoded_image = base64.b64encode(image_file.read()).decode("ascii")

    payload = {
        "model": os.getenv("OPENAI_VISION_MODEL", "gpt-4o-mini"),
        "max_tokens": 120,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": "Describe what happened in this SmartSeal event image in one concise sentence."},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{encoded_image}"}},
            ],
        }],
    }
    request = Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )

    try:
        # Send the image and event context to the configured vision model.
        with urlopen(request, timeout=30) as response:
            result = json.load(response)
        return result["choices"][0]["message"]["content"].strip()
    except Exception as error:
        # Keep the event usable when the network or vision service is down.
        return f"AI analysis unavailable; sensor evidence: {_fallback_analysis(packet)} ({error})"


def _fallback_analysis(packet):
    # Translate boolean sensor flags into a human-readable local summary.
    events = []
    if packet["tamper"]:
        events.append("possible tampering")
    if packet["vibration"]:
        events.append("movement or impact detected")
    return "; ".join(events) or "sensor alert triggered without a specific tamper or vibration classification"