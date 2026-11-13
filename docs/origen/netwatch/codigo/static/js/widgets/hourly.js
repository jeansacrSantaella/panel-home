import {$, empty} from "../lib/dom.js";

export function createHourly() {
  return {
    update(d) {
      if (!d.hours.some(v => v)) {
        $("hours").innerHTML = empty("Todavía no hay caídas registradas.");
        return;
      }
      const max = Math.max(1, ...d.hours);
      $("hours").innerHTML = `<svg viewBox="0 0 480 70">${d.hours.map((v, h) =>
        `<rect x="${h * 20 + 2}" y="${54 - v / max * 50}" width="16" height="${v / max * 50 || 1}" fill="${v ? "var(--down)" : "var(--none)"}"><title>${h}:00 · ${v} caídas</title></rect>` +
        `<text x="${h * 20 + 10}" y="68" font-size="9" text-anchor="middle" fill="var(--muted)">${h % 3 === 0 ? h : ""}</text>`).join("")}</svg>`;
    },
  };
}
