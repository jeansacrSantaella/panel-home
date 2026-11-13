import {$, dur} from "../lib/dom.js";

export function createStatus() {
  return {
    update(d) {
      const down = Object.values(d.checks).filter(c => c.down_since);
      if (down.length) {
        $("headline").textContent = down[0].label + " caída";
        $("sub").textContent = "Sin respuesta desde hace " + dur(d.now - down[0].down_since) + ".";
        return;
      }
      $("headline").textContent = "Todo en orden";
      const online = d.devices.filter(x => x.online).length;
      $("sub").textContent = online + " equipos conectados" + (d.public_ip ? " · IP pública " + d.public_ip : "");
    },
    offline() {
      $("headline").textContent = "Sin conexión con el monitor";
    },
  };
}
