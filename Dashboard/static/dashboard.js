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
let refreshInProgress = false;
let refreshRequested = false;
let selectedArchive = "live";

async function refreshEvents() {
    if (refreshInProgress) {
        refreshRequested = true;
        return;
    }

    refreshInProgress = true;
    const status = document.querySelector("#gateway-status");
    try {
        const endpoint = selectedArchive === "live"
            ? "/api/events"
            : `/api/archives/${encodeURIComponent(selectedArchive)}`;
        const response = await fetch(endpoint, { cache: "no-store" });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const events = await response.json();

        // Build the table using safe DOM operations.
        const rows = events.map((event) => {
            const row = document.createElement("tr");

            // Time and Seal ID
            for (const value of [event[1], event[2], event[3]]) {
                const cell = document.createElement("td");
                cell.textContent = value ?? "";
                row.appendChild(cell);
            }

            // Temperature indicator
            const tempCell = document.createElement("td");
            tempCell.innerHTML = temperatureStatus(event[4]);
            row.appendChild(tempCell);

            // Tamper indicator
            const tamperCell = document.createElement("td");
            tamperCell.innerHTML = tamperStatus(event[5]);
            row.appendChild(tamperCell);

            // Vibration indicator
            const vibrationCell = document.createElement("td");
            vibrationCell.innerHTML = vibrationStatus(event[6]);
            row.appendChild(vibrationCell);

            // Camera evidence link
            const imageCell = document.createElement("td");

            if (event[7]) {
                const link = document.createElement("a");
                link.href = `/images/${encodeURIComponent(event[7])}`;
                link.target = "_blank";
                link.rel = "noopener noreferrer";
                link.textContent = "View";
                imageCell.appendChild(link);
            }

            row.appendChild(imageCell);

            // AI analysis: textContent prevents HTML injection.
            const analysisCell = document.createElement("td");
            analysisCell.textContent = event[8] ?? "";
            row.appendChild(analysisCell);

            return row;
        });

        document.querySelector("#events").replaceChildren(...rows);
        status.textContent = selectedArchive === "live"
            ? `Synchronized with gateway at ${new Date().toLocaleTimeString()} ` +
                `(${events.length} events)`
            : `Viewing ${selectedArchive} (${events.length} events)`;

    } catch (error) {
        console.error("SmartSeal dashboard refresh failed:", error);
        status.textContent = "Gateway sync failed; retrying...";
    } finally {
        refreshInProgress = false;
        if (refreshRequested) {
            refreshRequested = false;
            refreshEvents();
        }
    }
}

let archivesRequestInProgress = false;

async function loadArchives() {
    if (archivesRequestInProgress) {
        return;
    }

    archivesRequestInProgress = true;
    const selector = document.querySelector("#event-source");
    try {
        const response = await fetch("/api/archives", { cache: "no-store" });
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        const archives = await response.json();
        for (const archive of archives) {
            if ([...selector.options].some((option) => option.value === archive)) {
                continue;
            }
            const option = document.createElement("option");
            option.value = archive;
            option.textContent = archive;
            selector.appendChild(option);
        }
    } catch (error) {
        console.error("Could not load gateway archives:", error);
        document.querySelector("#gateway-status").textContent =
            "Could not load archived event list.";
    } finally {
        archivesRequestInProgress = false;
    }
}

document.querySelector("#event-source").addEventListener("change", (event) => {
    selectedArchive = event.target.value;
    refreshEvents();
});

// Keep live events synchronized; archived snapshots only refresh on selection.
loadArchives();
refreshEvents();
setInterval(() => {
    if (selectedArchive === "live") {
        refreshEvents();
    }
}, 2000);
setInterval(loadArchives, 10000);