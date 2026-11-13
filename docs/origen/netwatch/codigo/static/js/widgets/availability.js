import {$, esc, fmtTime} from "../lib/dom.js";

const BUCKET = 600;  // segundos por celda de la cinta

const cellClass = v => v === null ? "" : v >= 0.99 ? "u" : v >= 0.9 ? "w" : "d";

// Cada celda cubre diez minutos; null indica que no hay mediciones.
export function createAvailability() {
  return {
    update(d) {
      $("ribbons").innerHTML = Object.keys(d.checks).map(k => {
        const cells = d.ribbon[k].map((v, i) => {
          const t = fmtTime(d.ribbon_start + i * BUCKET) + (v === null ? " · sin datos" : " · " + Math.round(v * 100) + "% ok");
          return `<i class="${cellClass(v)}" title="${esc(t)}"></i>`;
        }).join("");
        const u = d.uptime[k];
        return `<div class="ribbon-row"><div>${esc(d.checks[k].label)}</div><div class="ribbon">${cells}</div><div class="pct">${u === null ? "–" : u + " %"}</div></div>`;
      }).join("");
    },
  };
}
