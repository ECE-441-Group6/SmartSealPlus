// Refresh the event table so gateway readings appear without a page reload.
async function refreshEvents() {
	// Request the newest database rows from the Flask API.
	const response = await fetch("/api/events");
	const events = await response.json();
	// Convert each database row into one table row. The numeric indexes match
	// the SELECT * column order in Gateway/database.py.
	document.querySelector("#events").innerHTML = events.map((event) => `
		<tr>
			<td>${event[1]}</td>
			<td>${event[2]}</td>
			<td>${event[3]}</td>
			<td>${event[4] ? "Yes" : "No"}</td>
			<td>${event[5] ? "Yes" : "No"}</td>
			<td>${event[6] ? `<a href="/images/${encodeURIComponent(event[6])}" target="_blank">View</a>` : ""}</td>
			<td>${event[7] || ""}</td>
		</tr>
	`).join("");
}

// Poll every two seconds so the dashboard reflects new gateway events.
setInterval(refreshEvents, 2000);