import {$, esc, fmtTime} from "../lib/dom.js";
import {Pager} from "../lib/pager.js";

const EVENT_NAMES = {
  lan_down: "Red local caída", lan_up: "Red local recuperada",
  wan_down: "Internet caído", wan_up: "Internet recuperado",
  dns_down: "DNS caído", dns_up: "DNS recuperado",
  new_device: "Equipo nuevo", device_online: "Equipo conectado",
  device_offline: "Equipo desconectado", monitor_gap: "Pausa del monitor",
  ip_first: "IP pública inicial", ip_change: "Cambio de IP pública",
};

const eventName = kind => EVENT_NAMES[kind] || kind.replaceAll("_", " ");
const eventClass = kind => /_down$|offline|gap/.test(kind) ? "bad" : /_up$|online/.test(kind) ? "good" : "";

// Filtra el historial por fecha y tipo; pide cada página al servidor.
export function createEvents({api}) {
  let requestId = 0;
  const pager = new Pager("events", () => refresh().catch(console.error));
  const filters = ["events-from", "events-to", "events-kind"].map($);

  function render(data) {
    pager.showServerPage(data);
    const select = $("events-kind");
    const selected = select.value;
    select.innerHTML = '<option value="">Todos</option>' +
      data.kinds.map(kind => `<option value="${esc(kind)}">${esc(eventName(kind))}</option>`).join("");
    select.value = data.kinds.includes(selected) ? selected : "";

    $("events").innerHTML = data.events.length ? data.events.map(event =>
      `<li class="${eventClass(event.kind)}"><time>${esc(fmtTime(event.ts))}</time><span><b class="event-kind">${esc(eventName(event.kind))}:</b> ${esc(event.detail)}</span></li>`
    ).join("") : '<li class="empty">No hay eventos con esos filtros.</li>';
  }

  // Ignora respuestas antiguas cuando el usuario cambia los filtros durante la petición.
  async function refresh() {
    const id = ++requestId;
    const [from, to, kind] = filters.map(input => input.value);
    try {
      const data = await api.events({page: pager.page, size: pager.size, from, to, kind});
      if (id === requestId) render(data);
    } catch (error) {
      if (id === requestId) $("events").innerHTML = '<li class="empty">No se pudieron cargar los eventos.</li>';
      throw error;
    }
  }

  filters.forEach(input => input.addEventListener("change", () => {
    pager.reset();
    refresh().catch(console.error);
  }));

  $("events-clear").addEventListener("click", () => {
    filters.forEach(input => { input.value = ""; });
    pager.reset();
    refresh().catch(console.error);
  });

  return {refresh};
}
