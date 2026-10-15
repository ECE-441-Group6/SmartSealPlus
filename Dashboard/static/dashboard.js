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
        // Request the newest database rows from Flask.
        const response = await fetch("/api/events");

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const events = await response.json();

        // Build the table using safe DOM operations.
        const rows = events.map((event) => {
            const row = document.createElement("tr");

            // Time and Seal ID
            for (const value of [event[1], event[2]]) {
                const cell = document.createElement("td");
                cell.textContent = value ?? "";
                row.appendChild(cell);
            }

            // Temperature indicator
            const tempCell = document.createElement("td");
            tempCell.innerHTML = temperatureStatus(event[3]);
            row.appendChild(tempCell);

            // Tamper indicator
            const tamperCell = document.createElement("td");
            tamperCell.innerHTML = tamperStatus(event[4]);
            row.appendChild(tamperCell);

            // Vibration indicator
            const vibrationCell = document.createElement("td");
            vibrationCell.innerHTML = vibrationStatus(event[5]);
            row.appendChild(vibrationCell);

            // Camera evidence link
            const imageCell = document.createElement("td");

            if (event[6]) {
                const link = document.createElement("a");
                link.href = `/images/${encodeURIComponent(event[6])}`;
                link.target = "_blank";
                link.rel = "noopener noreferrer";
                link.textContent = "View";
                imageCell.appendChild(link);
            }

            row.appendChild(imageCell);

            // AI analysis: textContent prevents HTML injection.
            const analysisCell = document.createElement("td");
            analysisCell.textContent = event[7] ?? "";
            row.appendChild(analysisCell);

            return row;
        });

        document.querySelector("#events").replaceChildren(...rows);

    } catch (error) {
        console.error("SmartSeal dashboard refresh failed:", error);
    }
}

// Load immediately and refresh every two seconds.
refreshEvents();
setInterval(refreshEvents, 2000);