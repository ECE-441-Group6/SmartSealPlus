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
    const magnitude = Number(value);
    const detected = Number.isFinite(magnitude) && magnitude > 0;

    return detected
        ? `<span class="sensor-status sensor-warning">
            DETECTED (${magnitude.toFixed(2)} V)
        </span>`
        : '<span class="sensor-status sensor-normal">NORMAL</span>';
}

function movementStatus(value) {
    const movementType = Number(value);

    return movementType > 0
        ? `<span class="sensor-status sensor-warning">
            DETECTED (${movementType})
        </span>`
        : '<span class="sensor-status sensor-normal">NORMAL</span>';
}

function formatTimestamp(value) {
    if (!value) {
        return "";
    }

    let timestampValue = String(value).replace(" ", "T");
    if (
        /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?$/.test(
            timestampValue
        )
    ) {
        timestampValue += "Z";
    }

    const timestamp = new Date(timestampValue);
    if (Number.isNaN(timestamp.getTime())) {
        return String(value);
    }

    return timestamp.toLocaleString("en-US", {
        month: "2-digit",
        day: "2-digit",
        year: "2-digit",
        hour: "numeric",
        minute: "2-digit",
        second: "2-digit",
        hour12: true,
    });
}

function formatInitialTimestamps() {
    for (const row of document.querySelectorAll("#events tr")) {
        const timeCell = row.cells[0];
        if (timeCell) {
            timeCell.textContent = formatTimestamp(timeCell.textContent);
        }
    }
}

const TEMPERATURE_CHART_COLORS = [
    "#1769aa", "#c2410c", "#15803d", "#7e22ce", "#be123c",
    "#0e7490", "#a16207", "#4f46e5", "#4d7c0f", "#a21caf"
];
let currentEvents = [];

function chartTimestamp(value) {
    if (!value) {
        return null;
    }
    let normalized = String(value).replace(" ", "T");
    if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?$/.test(normalized)) {
        normalized += "Z";
    }
    const timestamp = new Date(normalized).getTime();
    return Number.isFinite(timestamp) ? timestamp : null;
}

function temperatureChartRows(events) {
    return events.map((event) => ({
        timestamp: chartTimestamp(event[1]),
        sealId: Number(event[2]),
        temperature: event[4] === null || event[4] === ""
            ? null
            : Number(event[4]),
    })).filter((event) => (
        event.timestamp !== null &&
        event.temperature !== null &&
        Number.isInteger(event.sealId) &&
        Number.isFinite(event.temperature)
    ));
}

function updateTemperatureSealOptions(rows) {
    const selector = document.querySelector("#temperature-seal-filter");
    const previousValue = selector.value || "all";
    const sealIds = [...new Set(rows.map((row) => row.sealId))]
        .sort((left, right) => left - right);

    selector.replaceChildren(new Option("All seals", "all"));
    for (const sealId of sealIds) {
        selector.add(new Option(`Seal ${sealId}`, String(sealId)));
    }
    selector.value = sealIds.includes(Number(previousValue))
        ? previousValue
        : "all";
}

function downsampleChartPoints(points, maximum = 500) {
    if (points.length <= maximum) {
        return points;
    }
    const sampled = [];
    const step = (points.length - 1) / (maximum - 1);
    for (let index = 0; index < maximum; index += 1) {
        sampled.push(points[Math.round(index * step)]);
    }
    return sampled;
}

function renderTemperatureChart() {
    const canvas = document.querySelector("#temperature-chart");
    const emptyMessage = document.querySelector("#temperature-chart-empty");
    const legend = document.querySelector("#temperature-chart-legend");
    const chartRows = temperatureChartRows(currentEvents);
    updateTemperatureSealOptions(chartRows);
    const sealFilter = document.querySelector("#temperature-seal-filter").value;
    const rows = chartRows.filter((row) => (
        sealFilter === "all" || row.sealId === Number(sealFilter)
    ));
    const empty = rows.length === 0;
    emptyMessage.hidden = !empty;
    canvas.hidden = empty;
    legend.replaceChildren();
    if (empty) {
        return;
    }

    const grouped = new Map();
    for (const row of rows) {
        if (!grouped.has(row.sealId)) {
            grouped.set(row.sealId, []);
        }
        grouped.get(row.sealId).push(row);
    }
    for (const points of grouped.values()) {
        points.sort((left, right) => left.timestamp - right.timestamp);
    }

    const width = Math.max(320, canvas.clientWidth);
    const height = 320;
    const scale = window.devicePixelRatio || 1;
    canvas.width = Math.round(width * scale);
    canvas.height = Math.round(height * scale);
    canvas.style.height = `${height}px`;
    const context = canvas.getContext("2d");
    context.setTransform(scale, 0, 0, scale, 0, 0);
    context.clearRect(0, 0, width, height);

    const margin = { top: 20, right: 24, bottom: 58, left: 58 };
    const plotWidth = width - margin.left - margin.right;
    const plotHeight = height - margin.top - margin.bottom;
    const allPoints = [...grouped.values()].flat();
    let minTime = Infinity;
    let maxTime = -Infinity;
    let minTemperature = Infinity;
    let maxTemperature = -Infinity;
    for (const point of allPoints) {
        minTime = Math.min(minTime, point.timestamp);
        maxTime = Math.max(maxTime, point.timestamp);
        minTemperature = Math.min(minTemperature, point.temperature);
        maxTemperature = Math.max(maxTemperature, point.temperature);
    }
    const timeRange = Math.max(maxTime - minTime, 1000);
    const minY = Math.floor(Math.min(minTemperature, TEMP_LOW) - 1);
    const maxY = Math.ceil(Math.max(maxTemperature, TEMP_HIGH) + 1);
    const temperatureRange = Math.max(maxY - minY, 1);
    const x = (timestamp) => margin.left + ((timestamp - minTime) / timeRange) * plotWidth;
    const y = (temperature) => margin.top + ((maxY - temperature) / temperatureRange) * plotHeight;

    context.font = "12px Arial, sans-serif";
    context.textAlign = "right";
    context.textBaseline = "middle";
    for (let tick = 0; tick <= 4; tick += 1) {
        const value = minY + (temperatureRange * tick) / 4;
        const tickY = y(value);
        context.strokeStyle = "#dbe3ec";
        context.lineWidth = 1;
        context.beginPath();
        context.moveTo(margin.left, tickY);
        context.lineTo(width - margin.right, tickY);
        context.stroke();
        context.fillStyle = "#526174";
        context.fillText(`${value.toFixed(1)}°C`, margin.left - 8, tickY);
    }

    for (const threshold of [TEMP_LOW, TEMP_HIGH]) {
        const thresholdY = y(threshold);
        context.strokeStyle = "#c62828";
        context.setLineDash([5, 4]);
        context.beginPath();
        context.moveTo(margin.left, thresholdY);
        context.lineTo(width - margin.right, thresholdY);
        context.stroke();
        context.setLineDash([]);
    }

    context.strokeStyle = "#66788a";
    context.beginPath();
    context.moveTo(margin.left, margin.top);
    context.lineTo(margin.left, height - margin.bottom);
    context.lineTo(width - margin.right, height - margin.bottom);
    context.stroke();

    const dateFormatter = new Intl.DateTimeFormat(undefined, {
        month: "short", day: "numeric", hour: "numeric", minute: "2-digit"
    });
    context.fillStyle = "#526174";
    context.textAlign = "center";
    context.textBaseline = "top";
    for (let tick = 0; tick <= 4; tick += 1) {
        const timestamp = minTime + (timeRange * tick) / 4;
        const tickX = margin.left + (plotWidth * tick) / 4;
        context.fillText(dateFormatter.format(new Date(timestamp)), tickX, height - margin.bottom + 10);
    }

    let colorIndex = 0;
    for (const [sealId, originalPoints] of grouped) {
        const color = TEMPERATURE_CHART_COLORS[colorIndex % TEMPERATURE_CHART_COLORS.length];
        colorIndex += 1;
        const points = downsampleChartPoints(originalPoints);
        context.strokeStyle = color;
        context.lineWidth = 2;
        context.beginPath();
        points.forEach((point, index) => {
            const pointX = x(point.timestamp);
            const pointY = y(point.temperature);
            if (index === 0) {
                context.moveTo(pointX, pointY);
            } else {
                context.lineTo(pointX, pointY);
            }
        });
        context.stroke();
        context.fillStyle = color;
        for (const point of points) {
            context.beginPath();
            context.arc(x(point.timestamp), y(point.temperature), 3, 0, Math.PI * 2);
            context.fill();
        }

        const legendItem = document.createElement("span");
        legendItem.className = "chart-legend-item";
        const swatch = document.createElement("span");
        swatch.className = "chart-legend-swatch";
        swatch.style.backgroundColor = color;
        swatch.setAttribute("aria-hidden", "true");
        const label = document.createElement("span");
        label.textContent = `Seal ${sealId}`;
        legendItem.append(swatch, label);
        legend.appendChild(legendItem);
    }
}

function refreshTemperatureChart(events) {
    currentEvents = events;
    if (!document.querySelector("#temperature-chart-panel").hidden) {
        renderTemperatureChart();
    }
    refreshVibrationChart(events);
}

function vibrationChartRows(events) {
    return events.map((event) => ({
        timestamp: chartTimestamp(event[1]),
        sealId: Number(event[2]),
        magnitude: event[6] === null || event[6] === ""
            ? null
            : Number(event[6]),
    })).filter((event) => (
        event.timestamp !== null &&
        event.magnitude !== null &&
        Number.isInteger(event.sealId) &&
        Number.isFinite(event.magnitude) &&
        event.magnitude >= 0
    ));
}

function renderVibrationChart() {
    const canvas = document.querySelector("#vibration-chart");
    const emptyMessage = document.querySelector("#vibration-chart-empty");
    const legend = document.querySelector("#vibration-chart-legend");
    const rows = vibrationChartRows(currentEvents);
    const selector = document.querySelector("#vibration-seal-filter");
    const previousValue = selector.value || "all";
    const sealIds = [...new Set(rows.map((row) => row.sealId))]
        .sort((left, right) => left - right);
    selector.replaceChildren(new Option("All seals", "all"));
    for (const sealId of sealIds) {
        selector.add(new Option(`Seal ${sealId}`, String(sealId)));
    }
    selector.value = sealIds.includes(Number(previousValue))
        ? previousValue
        : "all";

    const selectedRows = rows.filter((row) => (
        selector.value === "all" || row.sealId === Number(selector.value)
    ));
    legend.replaceChildren();
    emptyMessage.hidden = selectedRows.length > 0;
    canvas.hidden = selectedRows.length === 0;
    if (selectedRows.length === 0) {
        return;
    }

    const grouped = new Map();
    for (const row of selectedRows) {
        if (!grouped.has(row.sealId)) grouped.set(row.sealId, []);
        grouped.get(row.sealId).push(row);
    }
    for (const points of grouped.values()) {
        points.sort((left, right) => left.timestamp - right.timestamp);
    }

    const width = Math.max(320, canvas.clientWidth);
    const height = 320;
    const scale = window.devicePixelRatio || 1;
    canvas.width = Math.round(width * scale);
    canvas.height = Math.round(height * scale);
    canvas.style.height = `${height}px`;
    const context = canvas.getContext("2d");
    context.setTransform(scale, 0, 0, scale, 0, 0);
    context.clearRect(0, 0, width, height);

    const margin = { top: 20, right: 24, bottom: 58, left: 58 };
    const plotWidth = width - margin.left - margin.right;
    const plotHeight = height - margin.top - margin.bottom;
    const allPoints = [...grouped.values()].flat();
    const timeBounds = allPoints.reduce((bounds, point) => ({
        min: Math.min(bounds.min, point.timestamp),
        max: Math.max(bounds.max, point.timestamp),
    }), { min: Infinity, max: -Infinity });
    const minTime = timeBounds.min;
    const maxTime = timeBounds.max;
    const maxMagnitude = allPoints.reduce(
        (maximum, point) => Math.max(maximum, point.magnitude),
        0.1
    );
    const maxY = Math.ceil(maxMagnitude * 10) / 10 || 0.1;
    const timeRange = Math.max(maxTime - minTime, 1000);
    const x = (timestamp) => margin.left + ((timestamp - minTime) / timeRange) * plotWidth;
    const y = (magnitude) => margin.top + ((maxY - magnitude) / maxY) * plotHeight;

    context.font = "12px Arial, sans-serif";
    context.textAlign = "right";
    context.textBaseline = "middle";
    for (let tick = 0; tick <= 4; tick += 1) {
        const value = (maxY * tick) / 4;
        const tickY = y(value);
        context.strokeStyle = "#dbe3ec";
        context.lineWidth = 1;
        context.beginPath();
        context.moveTo(margin.left, tickY);
        context.lineTo(width - margin.right, tickY);
        context.stroke();
        context.fillStyle = "#526174";
        context.fillText(`${value.toFixed(2)} V`, margin.left - 8, tickY);
    }
    context.strokeStyle = "#66788a";
    context.beginPath();
    context.moveTo(margin.left, margin.top);
    context.lineTo(margin.left, height - margin.bottom);
    context.lineTo(width - margin.right, height - margin.bottom);
    context.stroke();

    const dateFormatter = new Intl.DateTimeFormat(undefined, {
        month: "short", day: "numeric", hour: "numeric", minute: "2-digit"
    });
    context.fillStyle = "#526174";
    context.textAlign = "center";
    context.textBaseline = "top";
    for (let tick = 0; tick <= 4; tick += 1) {
        const timestamp = minTime + (timeRange * tick) / 4;
        const tickX = margin.left + (plotWidth * tick) / 4;
        context.fillText(dateFormatter.format(new Date(timestamp)), tickX, height - margin.bottom + 10);
    }

    let colorIndex = 0;
    for (const [sealId, originalPoints] of grouped) {
        const color = TEMPERATURE_CHART_COLORS[colorIndex % TEMPERATURE_CHART_COLORS.length];
        colorIndex += 1;
        const points = downsampleChartPoints(originalPoints);
        context.strokeStyle = color;
        context.lineWidth = 2;
        context.beginPath();
        points.forEach((point, index) => {
            if (index === 0) context.moveTo(x(point.timestamp), y(point.magnitude));
            else context.lineTo(x(point.timestamp), y(point.magnitude));
        });
        context.stroke();
        context.fillStyle = color;
        for (const point of points) {
            context.beginPath();
            context.arc(x(point.timestamp), y(point.magnitude), 3, 0, Math.PI * 2);
            context.fill();
        }
        const item = document.createElement("span");
        item.className = "chart-legend-item";
        const swatch = document.createElement("span");
        swatch.className = "chart-legend-swatch";
        swatch.style.backgroundColor = color;
        swatch.setAttribute("aria-hidden", "true");
        const label = document.createElement("span");
        label.textContent = `Seal ${sealId}`;
        item.append(swatch, label);
        legend.appendChild(item);
    }
}

function refreshVibrationChart(events) {
    currentEvents = events;
    if (!document.querySelector("#vibration-chart-panel").hidden) {
        renderVibrationChart();
    }
}

let locationMap = null;
let locationLayers = null;
let previousLocationSignature = null;
const locationMapEmpty = document.querySelector("#location-map-empty");

if (window.L) {
    locationMap = L.map("location-map").setView([0, 0], 2);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19,
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>',
        referrerPolicy: "strict-origin-when-cross-origin",
    }).addTo(locationMap);
    locationLayers = L.featureGroup().addTo(locationMap);
} else {
    locationMapEmpty.textContent =
        "The map library could not load. Event coordinates remain available in the table.";
}

function eventLocation(event) {
    const latitude = Number(event[10]);
    const longitude = Number(event[11]);
    if (
        event[10] === null || event[10] === "" ||
        event[11] === null || event[11] === "" ||
        !Number.isFinite(latitude) || !Number.isFinite(longitude) ||
        latitude < -90 || latitude > 90 ||
        longitude < -180 || longitude > 180
    ) {
        return null;
    }
    return { latitude, longitude };
}

function refreshLocationMap(events) {
    const locatedEvents = events
        .map((event) => ({ event, location: eventLocation(event) }))
        .filter((row) => row.location !== null);
    // Keep map rendering responsive when a long shipment history contains
    // many events. Every row still retains its own location in the table.
    const mapEvents = locatedEvents.slice(0, 500);
    const signature = JSON.stringify(mapEvents.map(({ event, location }) => [
        event[0], event[1], event[2], event[3],
        location.latitude, location.longitude,
    ]));

    locationMapEmpty.hidden = locatedEvents.length > 0;
    if (!locationMap || signature === previousLocationSignature) {
        return;
    }
    previousLocationSignature = signature;
    locationLayers.clearLayers();

    const routePoints = [...mapEvents]
        .sort((left, right) => chartTimestamp(left.event[1]) - chartTimestamp(right.event[1]))
        .map(({ location }) => [location.latitude, location.longitude]);

    for (const { event, location } of mapEvents) {
        const marker = L.marker([location.latitude, location.longitude]);
        const popup = document.createElement("div");
        const title = document.createElement("strong");
        title.textContent = `Seal ${event[2]} — ${formatTimestamp(event[1])}`;
        const coordinates = document.createElement("div");
        coordinates.textContent =
            `Approx. location: ${location.latitude.toFixed(6)}, ${location.longitude.toFixed(6)}`;
        popup.append(title, coordinates);
        marker.bindPopup(popup);
        locationLayers.addLayer(marker);
    }

    if (routePoints.length > 1) {
        locationLayers.addLayer(L.polyline(routePoints, {
            color: "#1261a0",
            weight: 3,
            opacity: 0.7,
        }));
    }

    if (routePoints.length === 1) {
        locationMap.setView(routePoints[0], 15);
    } else if (routePoints.length > 1) {
        locationMap.fitBounds(locationLayers.getBounds().pad(0.12), { maxZoom: 15 });
    }
    window.setTimeout(() => locationMap.invalidateSize(), 0);
}

function appendLocationCell(row, event) {
    const cell = document.createElement("td");
    const location = eventLocation(event);
    if (location) {
        const link = document.createElement("a");
        const lat = location.latitude.toFixed(6);
        const lon = location.longitude.toFixed(6);
        link.href = `https://www.openstreetmap.org/?mlat=${lat}&mlon=${lon}#map=16/${lat}/${lon}`;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        link.textContent = `${lat}, ${lon}`;
        cell.appendChild(link);
    } else {
        cell.textContent = "Unavailable";
    }
    row.appendChild(cell);
}

document.querySelector("#toggle-temperature-chart").addEventListener("click", (event) => {
    const button = event.currentTarget;
    const panel = document.querySelector("#temperature-chart-panel");
    panel.hidden = !panel.hidden;
    button.setAttribute("aria-expanded", String(!panel.hidden));
    button.textContent = panel.hidden
        ? "Show temperature graph"
        : "Hide temperature graph";
    if (!panel.hidden) {
        renderTemperatureChart();
    }
});

document.querySelector("#temperature-seal-filter").addEventListener("change", () => {
    renderTemperatureChart();
});

document.querySelector("#toggle-vibration-chart").addEventListener("click", (event) => {
    const button = event.currentTarget;
    const panel = document.querySelector("#vibration-chart-panel");
    panel.hidden = !panel.hidden;
    button.setAttribute("aria-expanded", String(!panel.hidden));
    button.textContent = panel.hidden
        ? "Show vibration graph"
        : "Hide vibration graph";
    if (!panel.hidden) renderVibrationChart();
});

document.querySelector("#vibration-seal-filter").addEventListener("change", () => {
    renderVibrationChart();
});

window.addEventListener("resize", () => {
    if (!document.querySelector("#temperature-chart-panel").hidden) {
        renderTemperatureChart();
    }
    if (!document.querySelector("#vibration-chart-panel").hidden) {
        renderVibrationChart();
    }
});

// Refresh events from the Flask API.
let refreshInProgress = false;
let refreshRequested = false;
let selectedArchive = "live";
const deleteArchiveButton = document.querySelector("#delete-archive");
const canDeleteArchives = document.querySelector(
    'meta[name="csrf-token"]'
).dataset.canDelete === "true";

function updateDeleteArchiveButton() {
    deleteArchiveButton.disabled = !canDeleteArchives || selectedArchive === "live";
}

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
        refreshTemperatureChart(events);
        refreshLocationMap(events);

        // Build the table using safe DOM operations.
        const rows = events.map((event) => {
            const row = document.createElement("tr");

            // Time and Seal ID
            for (const value of [formatTimestamp(event[1]), event[2], event[3]]) {
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

            const movementCell = document.createElement("td");
            movementCell.innerHTML = movementStatus(event[7]);
            row.appendChild(movementCell);

            appendLocationCell(row, event);

            // Camera evidence link
            const imageCell = document.createElement("td");

            if (event[8]) {
                const link = document.createElement("a");
                link.href = `/images/${encodeURIComponent(event[8])}`;
                link.target = "_blank";
                link.rel = "noopener noreferrer";
                link.textContent = "View";
                imageCell.appendChild(link);
            }

            row.appendChild(imageCell);

            // AI analysis: textContent prevents HTML injection.
            const analysisCell = document.createElement("td");
            analysisCell.textContent = event[9] ?? "";
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
        const archiveNames = new Set(archives);
        for (const option of [...selector.options]) {
            if (option.value !== "live" && !archiveNames.has(option.value)) {
                option.remove();
            }
        }
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
    updateDeleteArchiveButton();
    refreshEvents();
});

deleteArchiveButton.addEventListener("click", async () => {
    if (selectedArchive === "live") {
        return;
    }

    if (!window.confirm(`Delete archive ${selectedArchive}?`)) {
        return;
    }

    try {
        const response = await fetch(
            `/api/archives/${encodeURIComponent(selectedArchive)}`,
            {
                method: "DELETE",
                headers: {
                    "X-CSRF-Token": document.querySelector(
                        'meta[name="csrf-token"]'
                    ).content,
                },
            }
        );
        if (!response.ok) {
            if (response.status === 401) {
                throw new Error("Sign in to delete archives.");
            }
            throw new Error(`HTTP ${response.status}`);
        }

        const deletedArchive = selectedArchive;
        selectedArchive = "live";
        const selector = document.querySelector("#event-source");
        selector.value = "live";
        updateDeleteArchiveButton();
        await loadArchives();
        await refreshEvents();
        document.querySelector("#gateway-status").textContent =
            `Deleted archive ${deletedArchive}.`;
    } catch (error) {
        console.error("Could not delete gateway archive:", error);
        document.querySelector("#gateway-status").textContent =
            error.message || "Could not delete the selected archive.";
    }
});

// Keep live events synchronized; archived snapshots only refresh on selection.
formatInitialTimestamps();
updateDeleteArchiveButton();
loadArchives();
refreshEvents();
setInterval(() => {
    if (selectedArchive === "live") {
        refreshEvents();
    }
}, 2000);
setInterval(loadArchives, 2000);
window.addEventListener("focus", loadArchives);
