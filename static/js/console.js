/**
 * Aetherworks SRE Console — Frontend controller
 * Calls existing API endpoints without modifying backend logic.
 */

const API = {
  health: "/",
  incident: "/webhook/incident",
};

let dispatchCount = 0;

function nowStamp() {
  return new Date().toLocaleTimeString("en-GB", { hour12: false });
}

function log(message, type = "system") {
  const screen = document.getElementById("telegraphOutput");
  const line = document.createElement("p");
  line.className = `telegraph-line ${type}-msg`;
  line.textContent = `[${nowStamp()}] ${message}`;
  screen.appendChild(line);
  screen.scrollTop = screen.scrollHeight;
}

function setNeedle(id, degrees) {
  const needle = document.getElementById(id);
  if (needle) {
    needle.style.transform = `translateX(-50%) rotate(${degrees}deg)`;
  }
}

function versionToAngle(version) {
  const parts = String(version).split(".").map(Number);
  const numeric = (parts[0] || 0) * 100 + (parts[1] || 0) * 10 + (parts[2] || 0);
  return -90 + Math.min(numeric * 3, 90);
}

function triggerSteamBurst(x, y) {
  const burst = document.createElement("div");
  burst.className = "steam-burst";
  burst.style.left = `${x - 60}px`;
  burst.style.top = `${y - 60}px`;
  document.body.appendChild(burst);
  setTimeout(() => burst.remove(), 800);
}

function spinGearsBriefly() {
  document.querySelectorAll(".gear-cluster").forEach((cluster) => {
    cluster.classList.add("spinning");
    setTimeout(() => cluster.classList.remove("spinning"), 1500);
  });
}

async function fetchHealth() {
  log("Recalibrating pressure gauges...", "system");
  try {
    const response = await fetch(API.health);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();

    document.getElementById("healthStatus").textContent = data.status.toUpperCase();
    document.getElementById("versionStatus").textContent = `v${data.version}`;

    setNeedle("healthNeedle", data.status === "healthy" ? 45 : -60);
    setNeedle("versionNeedle", versionToAngle(data.version));
    setNeedle("queueNeedle", Math.min(dispatchCount * 25 - 90, 60));

    log(`Engine ${data.status} · Service: ${data.service} · Version: ${data.version}`, "success");
    spinGearsBriefly();
  } catch (err) {
    document.getElementById("healthStatus").textContent = "OFFLINE";
    setNeedle("healthNeedle", -120);
    log(`Gauge recalibration failed — ${err.message}`, "error");
  }
}

function toISOString(localDatetime) {
  if (!localDatetime) return new Date().toISOString();
  return new Date(localDatetime).toISOString();
}

function setDefaultTimestamp() {
  const field = document.getElementById("timestamp");
  const now = new Date();
  now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
  field.value = now.toISOString().slice(0, 16);
}

function loadDemoPayload() {
  document.getElementById("incidentId").value = `INC-${Date.now().toString(36).toUpperCase()}`;
  document.getElementById("title").value = "Payment API — Database Connection Pool Exhaustion";
  document.getElementById("serviceName").value = "payment-api";
  document.getElementById("severity").value = "critical";
  setDefaultTimestamp();
  log("Demo breakdown scenario loaded into dispatch telegraph.", "dispatch");
  spinGearsBriefly();
}

async function dispatchIncident(event) {
  event.preventDefault();

  const btn = document.getElementById("dispatchBtn");
  btn.disabled = true;

  const payload = {
    incident_id: document.getElementById("incidentId").value.trim(),
    title: document.getElementById("title").value.trim(),
    service_name: document.getElementById("serviceName").value,
    severity: document.getElementById("severity").value,
    timestamp: toISOString(document.getElementById("timestamp").value),
  };

  log(`Dispatching incident ${payload.incident_id} → ${payload.service_name} [${payload.severity}]`, "dispatch");

  const rect = btn.getBoundingClientRect();
  triggerSteamBurst(rect.left + rect.width / 2, rect.top + rect.height / 2);
  spinGearsBriefly();

  try {
    const response = await fetch(API.incident, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    const data = await response.json();

    if (response.status === 202) {
      dispatchCount += 1;
      document.getElementById("queueStatus").textContent = String(dispatchCount);
      setNeedle("queueNeedle", Math.min(dispatchCount * 25 - 90, 60));
      log(`QUEUED: ${data.message}`, "success");
      log("Analysis engine engaged in background. Check server console or Slack for RCA report.", "system");
    } else {
      log(`Dispatch rejected — HTTP ${response.status}: ${JSON.stringify(data)}`, "error");
    }
  } catch (err) {
    log(`Transmission failure — ${err.message}`, "error");
  } finally {
    btn.disabled = false;
  }
}

function clearLog() {
  const screen = document.getElementById("telegraphOutput");
  screen.innerHTML = "";
  log("Telegraph register cleared.", "system");
}

document.addEventListener("DOMContentLoaded", () => {
  setDefaultTimestamp();
  fetchHealth();

  document.getElementById("incidentForm").addEventListener("submit", dispatchIncident);
  document.getElementById("refreshHealthBtn").addEventListener("click", fetchHealth);
  document.getElementById("demoBtn").addEventListener("click", loadDemoPayload);
  document.getElementById("clearLogBtn").addEventListener("click", clearLog);

  setInterval(fetchHealth, 30000);
});
