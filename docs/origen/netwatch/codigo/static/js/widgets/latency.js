import {$, empty, esc, fmtTime} from "../lib/dom.js";
import {targetColor, targetName} from "../lib/targets.js";

const W = 900, H = 170, P = 28, WINDOW = 3600;

export function createLatency() {
  return {
    update(d) {
      const keys = Object.keys(d.series);
      if (!keys.length) {
        $("chart").innerHTML = empty("Aún no hay mediciones.");
        $("legend").innerHTML = "";
        return;
      }
      const t0 = d.now - WINDOW;
      let max = 20;
      keys.forEach(k => d.series[k].forEach(p => { if (p[1]) max = Math.max(max, p[1]); }));
      max = Math.min(Math.ceil(max / 20) * 20, 400);
      const x = t => P + (t - t0) / WINDOW * (W - P - 6);
      const y = v => H - 18 - Math.min(v, max) / max * (H - 30);

      let svg = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Latencia por minuto">`;
      [0, .5, 1].forEach(f => {
        const yy = y(max * f);
        svg += `<line x1="${P}" x2="${W - 6}" y1="${yy}" y2="${yy}" stroke="var(--line)"/><text x="0" y="${yy + 4}" font-size="11" fill="var(--muted)">${Math.round(max * f)}</text>`;
      });
      keys.forEach(k => {
        let path = "", pen = false;
        d.series[k].forEach(p => {
          if (p[1] === null) { pen = false; return; }
          path += (pen ? "L" : "M") + x(p[0]).toFixed(1) + " " + y(p[1]).toFixed(1) + " ";
          pen = true;
        });
        svg += `<path d="${path}" fill="none" stroke="${targetColor(k)}" stroke-width="1.6"/>`;
        d.series[k].forEach(p => {
          if (p[2] === 0) svg += `<rect x="${x(p[0]) - 1.5}" y="${H - 14}" width="3" height="10" fill="var(--down)"><title>Paquetes perdidos · ${esc(fmtTime(p[0]))}</title></rect>`;
        });
      });
      $("chart").innerHTML = svg + "</svg>";
      $("legend").innerHTML = keys.map(k => `<span><b style="background:${targetColor(k)}"></b>${esc(targetName(k))}</span>`).join("") +
        '<span><b style="background:var(--down)"></b>Pérdida de paquetes</span><span>ms</span>';
    },
  };
}
