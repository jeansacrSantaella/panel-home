import {$, esc, fmtTime} from "../lib/dom.js";
import {Pager} from "../lib/pager.js";

const NETWORKS = ["", "5 GHz", "2.4 GHz", "Cable"];

function latencyCell(x) {
  if (!x.online) return "–";
  if (!x.q) return "…";
  return x.q.loss >= 100 ? "sin respuesta a ping" : x.q.avg + " ms";
}

function row(x) {
  const q = x.q, noReply = q && q.loss >= 100;
  const name = x.alias || x.hostname || "Sin nombre";
  const sub = (x.vendor || (x.random_mac ? "Dirección privada" : "Fabricante desconocido")) + " · " + x.mac;
  return `<tr>` +
    `<td><span class="dot ${x.online ? "on" : ""}"></span><span class="name" data-mac="${esc(x.mac)}" data-alias="${esc(x.alias || "")}">${esc(name)}</span><div class="tag mono">${esc(sub)}</div></td>` +
    `<td class="mono">${esc(x.ip)}</td>` +
    `<td><button class="net ${x.network ? "" : "none"}" data-mac="${esc(x.mac)}" data-net="${esc(x.network || "")}">${esc(x.network || "Sin asignar")}</button></td>` +
    `<td class="mono">${latencyCell(x)}</td>` +
    `<td class="mono">${q && !noReply && q.jitter !== null ? q.jitter + " ms" : "–"}</td>` +
    `<td class="mono">${q ? q.loss + " %" : "–"}</td>` +
    `<td>${x.drops}</td>` +
    `<td>${x.online ? "ahora" : esc(fmtTime(x.last_seen))}</td>` +
    `</tr>`;
}

// Edita el alias desde el nombre y cambia la red desde su etiqueta.
export function createDevices({api, onChanged}) {
  let latest = null;
  const pager = new Pager("devices", () => latest && render());

  function render() {
    const devices = latest.devices;
    $("devices").innerHTML = devices.length
      ? pager.slice(devices).map(row).join("")
      : '<tr><td colspan="8" class="empty">El primer escaneo tarda cerca de un minuto.</td></tr>';
  }

  $("devices").addEventListener("click", async e => {
    const net = e.target.closest(".net");
    if (net) {
      const next = NETWORKS[(NETWORKS.indexOf(net.dataset.net) + 1) % NETWORKS.length];
      await api.setNetwork(net.dataset.mac, next);
      onChanged();
      return;
    }
    const name = e.target.closest(".name");
    if (!name) return;
    const alias = prompt("Nombre para este equipo (vacío para quitarlo):", name.dataset.alias);
    if (alias === null) return;
    await api.setAlias(name.dataset.mac, alias);
    onChanged();
  });

  return {
    update(d) {
      latest = d;
      render();
    },
  };
}
