import {$, empty, esc, fmtTime} from "../lib/dom.js";

const UP_COLOR = "#3a6ea5";

export function createSpeed() {
  return {
    update(d) {
      const sp = d.speed;
      if (!sp.length) {
        $("speed").innerHTML = empty("La primera prueba corre medio minuto después de iniciar y luego cada hora.");
        return;
      }
      const c = d.contracted || {down: 0, up: 0};
      const last = sp[sp.length - 1];
      const m = Math.max(10, c.down, ...sp.map(s => Math.max(s.down, s.up)));
      const cy = 110 - c.down / m * 100;
      const pts = key => sp.map((s, i) => `${(i / Math.max(1, sp.length - 1) * 880 + 10).toFixed(1)},${(110 - s[key] / m * 100).toFixed(1)}`).join(" ");
      const share = c.down ? " (" + Math.round(last.down / c.down * 100) + " % de lo contratado)" : "";
      const contracted = c.down ? `<line x1="10" x2="890" y1="${cy}" y2="${cy}" stroke="var(--warn)" stroke-dasharray="4 4"/>` : "";
      const contractedLegend = c.down ? `<span><b style="background:var(--warn)"></b>Contratada: ${c.down} Mbps</span>` : "";
      $("speed").innerHTML =
        `<p class="mono">Última prueba (${esc(fmtTime(last.ts))}): bajada ${last.down.toFixed(1)} Mbps${share} · subida ${last.up.toFixed(1)} Mbps</p>` +
        `<svg viewBox="0 0 900 120">${contracted}<polyline points="${pts("down")}" fill="none" stroke="var(--up)" stroke-width="1.8"/><polyline points="${pts("up")}" fill="none" stroke="${UP_COLOR}" stroke-width="1.8"/></svg>` +
        `<div class="legend"><span><b style="background:var(--up)"></b>Bajada</span><span><b style="background:${UP_COLOR}"></b>Subida</span>${contractedLegend}<span>máx. ${Math.round(m)} Mbps</span></div>`;
    },
  };
}
