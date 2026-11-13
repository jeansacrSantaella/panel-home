import {$, empty, esc} from "../lib/dom.js";
import {targetName} from "../lib/targets.js";

export function createQuality() {
  return {
    update(d) {
      const keys = Object.keys(d.quality);
      $("quality").innerHTML = keys.length ? keys.map(k => {
        const v = d.quality[k];
        return `<tr><td>${esc(targetName(k))}</td><td class="mono">${v.avg ?? "–"} ms</td><td class="mono">${v.jitter ?? "–"} ms</td><td class="mono">${v.loss} %</td></tr>`;
      }).join("") : `<tr><td colspan="4" class="empty">Aún no hay mediciones.</td></tr>`;
    },
  };
}
