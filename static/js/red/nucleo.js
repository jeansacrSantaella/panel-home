/* Pestaña Red: carga /api/red/resumen mientras la pestaña está abierta y avisa a las tarjetas (evento "red-datos").
   Expone window.RedPanel con utilidades comunes para estado.js, equipos.js, escaner.js, velocidad.js y eventos.js. */
(function () {
  "use strict";
  const CADA = 30000;
  let temporizador = null;
  let ultimo = null;

  // fetch con sesión: JSON de ida y vuelta; lanza Error con el mensaje del servidor
  async function api(url, opciones = {}) {
    const o = { credentials: "same-origin", ...opciones, headers: { ...(opciones.headers || {}) } };
    if (o.body !== undefined && typeof o.body !== "string") {
      o.body = JSON.stringify(o.body);
      o.headers["Content-Type"] = "application/json";
    }
    const r = await fetch(url, o);
    let datos = null;
    try { datos = await r.json(); } catch (_) { /* sin cuerpo JSON */ }
    if (!r.ok) {
      const e = new Error((datos && datos.error) || `Error ${r.status}`);
      e.status = r.status;
      throw e;
    }
    return datos;
  }

  function el(etiqueta, clase, props) {
    const n = document.createElement(etiqueta);
    if (clase) n.className = clase;
    if (props) Object.assign(n, props);
    return n;
  }

  // "hace 5 s", "hace 3 min", "hace 2 h", "hace 4 d"
  function hace(ts) {
    if (!ts) return "nunca";
    const s = Math.max(0, Math.round(Date.now() / 1000 - ts));
    if (s < 60) return `hace ${s} s`;
    if (s < 3600) return `hace ${Math.round(s / 60)} min`;
    if (s < 86400) return `hace ${Math.round(s / 3600)} h`;
    return `hace ${Math.round(s / 86400)} d`;
  }

  function fecha(ts) {
    return ts ? new Date(ts * 1000).toLocaleString("es-MX", { dateStyle: "short", timeStyle: "short" }) : "—";
  }

  // Paginador común: "‹ 2 / 5 ›" dentro de `cont`; alCambiar(nuevaPagina) con índice desde 0
  function paginador(cont, pagina, paginas, alCambiar) {
    cont.replaceChildren();
    cont.classList.add("paginas");
    if (paginas <= 1) return;
    const ant = el("button", "boton", { type: "button", textContent: "‹", disabled: pagina <= 0 });
    const sig = el("button", "boton", { type: "button", textContent: "›", disabled: pagina >= paginas - 1 });
    ant.setAttribute("aria-label", "Página anterior");
    sig.setAttribute("aria-label", "Página siguiente");
    ant.addEventListener("click", () => alCambiar(pagina - 1));
    sig.addEventListener("click", () => alCambiar(pagina + 1));
    cont.append(ant, el("span", "tenue", { textContent: `${pagina + 1} / ${paginas}` }), sig);
  }

  async function cargar() {
    const noInterna = document.getElementById("red-no-interna");
    const tarjetas = document.querySelectorAll("#pestana-red > .tarjeta:not(#red-no-interna)");
    try {
      ultimo = await api("/api/red/resumen");
      noInterna.hidden = true;
      tarjetas.forEach(t => { t.hidden = false; });
      document.dispatchEvent(new CustomEvent("red-datos", { detail: ultimo }));
    } catch (e) {
      if (e.status === 409) {  // RED_INTERNA no activa: aviso y enlace a NetWatch
        noInterna.hidden = false;
        tarjetas.forEach(t => { t.hidden = true; });
        fetch("/api/panel", { credentials: "same-origin" }).then(r => r.json()).then(d => {
          const a = document.getElementById("red-netwatch");
          if (a && d.netwatch_url) a.href = d.netwatch_url;
        }).catch(() => {});
      }
    }
  }

  function detener() {
    clearInterval(temporizador);
    temporizador = null;
  }

  // Solo pide datos con la pestaña Red abierta
  document.addEventListener("pestana", e => {
    detener();
    if (e.detail === "red") {
      cargar();
      temporizador = setInterval(cargar, CADA);
    }
  });

  window.RedPanel = { api, el, hace, fecha, paginador, recargar: cargar, ultimo: () => ultimo };
})();
