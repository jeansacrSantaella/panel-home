import {api} from "./lib/api.js";
import {$} from "./lib/dom.js";
import {initLayout} from "./ui/layout.js";
import {initTheme} from "./ui/theme.js";
import {createAvailability} from "./widgets/availability.js";
import {createDevices} from "./widgets/devices.js";
import {createEvents} from "./widgets/events.js";
import {createHourly} from "./widgets/hourly.js";
import {createLatency} from "./widgets/latency.js";
import {createQuality} from "./widgets/quality.js";
import {createScanner} from "./widgets/scanner.js";
import {createSpeed} from "./widgets/speed.js";
import {createStatus} from "./widgets/status.js";

const REFRESH_MS = 5000;

initTheme($("theme-toggle"));
initLayout($("dashboard-grid"), $("reset-layout"));

const status = createStatus();
const events = createEvents({api});
const widgets = [
  status,
  createAvailability(),
  createLatency(),
  createQuality(),
  createSpeed(),
  createDevices({api, onChanged: () => tick()}),
  createHourly(),
  createScanner({api}),
];

async function tick() {
  try {
    const summary = await api.summary();
    widgets.forEach(widget => widget.update(summary));
  } catch (error) {
    status.offline();
  }
  events.refresh().catch(error => console.error("No se pudieron actualizar los eventos:", error));
}

tick();
setInterval(tick, REFRESH_MS);
