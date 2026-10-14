/* SmartSeal+ Dashboard
   Live sensor monitoring and color-coded alerts
*/

const TEMP_LOW = 2;
const TEMP_HIGH = 8;

// Convert text to safe HTML before displaying it.
function escapeHTML(value) {
    return String(value ?? "").replace(/[&<>"']/g, (char) => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;"
    }[char]));
}

// Generate a colored temperature indicator.
function temperatureStatus(value) {
    const temperature = Number(value);

    if (value === null || value === "" ||
        !Number.isFinite(temperature)) {
        return '<span class="sensor-status sensor-warning">Unknown</span>';
    }

    if (temperature < TEMP_LOW) {
        return `<span class="sensor-status sensor-danger">
            ${temperature.toFixed(1)}°C - LOW
        </span>`;
    }

    if (temperature > TEMP_HIGH) {
        return `<span class="sensor-status sensor-danger">
            ${temperature.toFixed(1)}°C - HIGH
        </span>`;
    }

    return `<span class="sensor-status sensor-normal">
        ${temperature.toFixed(1)}°C - NORMAL
    </span>`;
}

// Generate a colored tamper indicator.
function tamperStatus(value) {
    const detected = value === true || value === 1;

    return detected
        ? '<span class="sensor-status sensor-danger">DETECTED</span>'
        : '<span class="sensor-status sensor-normal">SECURE</span>';
}

// Generate a colored vibration indicator.
function vibrationStatus(value) {
    const detected = value === true || value === 1;

    return detected
        ? '<span class="sensor-status sensor-warning">DETECTED</span>'
        : '<span class="sensor-status sensor-normal">NORMAL</span>';
}

// Refresh events from the Flask API.
async function refreshEvents() {
    try {
        const response = await fetch("/api/events");

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const events = await response.json();

        document.querySelector("#events").innerHTML = events.map((event) => {
            const imageLink = event[6]
                ? `<a href="/images/${encodeURIComponent(event[6])}"
                      target="_blank" rel="noopener noreferrer">View</a>`
                : "";

            return `
                <tr>
                    <td>${escapeHTML(event[1])}</td>
                    <td>${escapeHTML(event[2])}</td>
                    <td>${temperatureStatus(event[3])}</td>
                    <td>${tamperStatus(event[4])}</td>
                    <td>${vibrationStatus(event[5])}</td>
                    <td>${imageLink}</td>
                    <td>${escapeHTML(event[7])}</td>
                </tr>
            `;
        }).join("");

    } catch (error) {
        console.error("SmartSeal dashboard refresh failed:", error);
    }
}

// Load immediately and refresh every two seconds.
refreshEvents();
setInterval(refreshEvents, 2000);