import {$, empty, esc, fmtTime} from "../lib/dom.js";

function summaryRows(r) {
  const p = r.ping || {};
  const known = r.known;
  return [
    ["IP", r.ip + (r.host !== r.ip ? " (" + r.host + ")" : "")],
    ["Nombre", known?.alias || r.hostname || "–"],
    ["MAC", r.mac ? r.mac + (r.random_mac ? " · privada" : "") : "Fuera de la red local"],
    ["Fabricante", r.vendor || "–"],
    ["Ping", p.loss >= 100 ? "Sin respuesta" : `${p.avg ?? "–"} ms · jitter ${p.jitter ?? "–"} ms · pérdida ${p.loss} %`],
    ["Sistema probable", r.os_hint ? `${r.os_hint} (TTL ${r.ttl})` : "–"],
    ["Servidor DNS", r.dns.ok ? `Sí, ${r.dns.ms} ms` : "No"],
    ["En el inventario", known ? "Sí, desde " + fmtTime(known.first_seen) + (known.network ? " · " + known.network : "") : "No"],
  ];
}

function portsTable(open) {
  if (!open.length) return empty("No hay puertos TCP abiertos en el rango probado.");
  const rows = open.map(o =>
    `<tr><td class="mono">${o.port}</td><td>${esc(o.service || "–")}</td><td class="mono">${esc(o.banner || "–")}</td></tr>`).join("");
  return `<table><thead><tr><th>Puerto</th><th>Servicio</th><th>Respuesta</th></tr></thead><tbody>${rows}</tbody></table>`;
}

function renderResult(r) {
  const rows = summaryRows(r).map(([k, v]) => `<tr><th>${k}</th><td>${esc(v)}</td></tr>`).join("");
  const steps = r.steps.map(s => `<li>${esc(s)}</li>`).join("");
  $("scan-result").innerHTML =
    `<table><tbody>${rows}</tbody></table>` +
    `<h3>Puertos abiertos (${r.open.length} de ${r.ports_scanned})</h3>${portsTable(r.open)}` +
    `<details><summary>Pasos del análisis · ${r.elapsed} s</summary><ul>${steps}</ul></details>`;
}

// Sugiere equipos del inventario para agilizar el análisis.
export function createScanner({api}) {
  $("scan-preset").addEventListener("change", e => {
    $("scan-ports").hidden = e.target.value !== "custom";
  });

  $("scan-form").addEventListener("submit", async e => {
    e.preventDefault();
    const preset = $("scan-preset").value;
    const ports = preset === "custom" ? $("scan-ports").value : preset;
    $("scan-run").disabled = true;
    $("scan-result").innerHTML = empty("Escaneando… puede tardar unos segundos.");
    try {
      renderResult(await api.scan($("scan-host").value, ports));
    } catch (error) {
      $("scan-result").innerHTML = empty("No se pudo escanear: " + error.message);
    } finally {
      $("scan-run").disabled = false;
    }
  });

  return {
    update(d) {
      $("scan-hosts").innerHTML = d.devices.filter(x => x.ip).map(x =>
        `<option value="${esc(x.ip)}">${esc(x.alias || x.hostname || x.vendor || x.mac)}</option>`).join("");
    },
  };
}
