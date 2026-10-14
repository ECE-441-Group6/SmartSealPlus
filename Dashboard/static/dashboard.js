// Refresh the event table so gateway readings appear without a page reload.
async function refreshEvents() {
	// Request the newest database rows from the Flask API.
	const response = await fetch("/api/events");
	const events = await response.json();
	// Build cells with textContent so stored AI output cannot become markup.
	const rows = events.map((event) => {
		const row = document.createElement("tr");
		const values = [event[1], event[2], event[3], event[4] ? "Yes" : "No", event[5] ? "Yes" : "No"];

		for (const value of values) {
			const cell = document.createElement("td");
			cell.textContent = value ?? "";
			row.appendChild(cell);
		}

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

		const analysisCell = document.createElement("td");
		analysisCell.textContent = event[7] ?? "";
		row.appendChild(analysisCell);
		return row;
	});

	document.querySelector("#events").replaceChildren(...rows);
}

// Poll every two seconds so the dashboard reflects new gateway events.
setInterval(refreshEvents, 2000);