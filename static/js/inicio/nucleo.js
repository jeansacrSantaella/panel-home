/* Inicio: datos comunes de las tarjetas (luces con habitación, resumen de habitaciones, rutinas y clima).
   Solo pide datos con la pestaña Inicio abierta. Eventos document:
   - "inicio-luces" {luces, habitaciones, nombres, rutinas, configurado, motivo} cada 10 s
   - "inicio-clima" (lo de /api/clima) cada 10 min
   Las cámaras, la red y la salud llegan con el evento "panel" de app.js. */
(function () {
  "use strict";
  const CADA_LUCES = 10000;
  const CADA_CLIMA = 600000;
  let tLuces = null;
  let tClima = null;
  let ultimo = { luces: null, clima: null, panel: null };

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

  function hace(ts) {
    if (!ts) return "nunca";
    const s = Math.max(0, Math.round(Date.now() / 1000 - ts));
    if (s < 60) return `hace ${s} s`;
    if (s < 3600) return `hace ${Math.round(s / 60)} min`;
    if (s < 86400) return `hace ${Math.round(s / 3600)} h`;
    return `hace ${Math.round(s / 86400)} d`;
  }

  // Íconos del clima (SVG fijo, sin datos del servidor dentro): sol, parcial, nubes, niebla, llovizna, lluvia, nieve, tormenta, luna
  const NUBE = '<path d="M7 18h10a4 4 0 0 0 .4-8A6 6 0 0 0 6 11a3.5 3.5 0 0 0 1 7Z"/>';
  const ICONOS = {
    sol: '<circle cx="12" cy="12" r="4.5"/><path d="M12 2v2.5M12 19.5V22M2 12h2.5M19.5 12H22M4.9 4.9l1.8 1.8M17.3 17.3l1.8 1.8M4.9 19.1l1.8-1.8M17.3 6.7l1.8-1.8"/>',
    luna: '<path d="M20 14.5A8 8 0 0 1 9.5 4 8 8 0 1 0 20 14.5Z"/>',
    parcial: '<circle cx="8.5" cy="8.5" r="3.5"/><path d="M8.5 2v1.5M2 8.5h1.5M3.9 3.9l1 1M13.1 3.9l-1 1"/>' + '<path d="M9 20h9a3.5 3.5 0 0 0 .3-7 5 5 0 0 0-9.6 1.4A3 3 0 0 0 9 20Z"/>',
    nubes: NUBE,
    niebla: '<path d="M4 9h16M3 13h18M5 17h14"/>',
    llovizna: NUBE + '<path d="M9 21v.5M13 21v.5M17 21v.5"/>',
    lluvia: NUBE + '<path d="M9 20l-1 2.5M13 20l-1 2.5M17 20l-1 2.5"/>',
    nieve: NUBE + '<path d="M9 21h.01M13 21h.01M17 21h.01"/>',
    tormenta: NUBE + '<path d="m12.5 18-2 3h3l-2 3"/>',
  };
  function iconoClima(nombre, esDia = true) {
    // solo nombres conocidos: el nombre termina dentro del HTML del SVG
    let clave = Object.prototype.hasOwnProperty.call(ICONOS, nombre) ? nombre : "nubes";
    if (clave === "sol" && !esDia) clave = "luna";
    const cuerpo = ICONOS[clave];
    return `<svg class="icono-clima icono-${clave}" viewBox="0 0 24 24" aria-hidden="true" focusable="false">${cuerpo}</svg>`;
  }

  async function cargarLuces() {
    try {
      const [l, h, r] = await Promise.all([api("/api/luces"), api("/api/luces/habitaciones"), api("/api/rutinas")]);
      ultimo.luces = { luces: l.luces || [], configurado: l.configurado, motivo: l.motivo,
                       habitaciones: h.habitaciones || [], nombres: h.nombres || [], rutinas: r.rutinas || [] };
      document.dispatchEvent(new CustomEvent("inicio-luces", { detail: ultimo.luces }));
    } catch (_) { /* se reintenta en la siguiente vuelta */ }
  }

  // Ubicación del dispositivo para el clima: solo en páginas seguras (HTTPS o localhost), con permiso del usuario,
  // redondeada a ~1 km y recordada 1 h. Sin ella, el servidor usa la de la casa (configurada o por IP pública).
  const GEO_CLAVE = "clima-ubicacion";
  function leerGeo() {
    try {
      const g = JSON.parse(localStorage.getItem(GEO_CLAVE) || "null");
      return g && Date.now() - g.ts < 3600000 ? g : null;
    } catch (_) { return null; }
  }
  function pedirGeo() {
    return new Promise(resolver => {
      if (!window.isSecureContext || !navigator.geolocation) return resolver(null);
      const guardada = leerGeo();
      if (guardada) return resolver(guardada);
      navigator.geolocation.getCurrentPosition(p => {
        const g = { lat: Math.round(p.coords.latitude * 100) / 100, lon: Math.round(p.coords.longitude * 100) / 100, ts: Date.now() };
        try { localStorage.setItem(GEO_CLAVE, JSON.stringify(g)); } catch (_) { /* sin almacenamiento */ }
        resolver(g);
      }, () => resolver(null), { enableHighAccuracy: false, timeout: 8000, maximumAge: 1800000 });
    });
  }

  async function cargarClima() {
    try {
      const g = await pedirGeo();
      ultimo.clima = await api(g ? `/api/clima?lat=${g.lat}&lon=${g.lon}` : "/api/clima");
      document.dispatchEvent(new CustomEvent("inicio-clima", { detail: ultimo.clima }));
    } catch (_) { /* idem */ }
  }

  function detener() {
    clearInterval(tLuces);
    clearInterval(tClima);
    tLuces = tClima = null;
  }

  document.addEventListener("panel", e => { ultimo.panel = e.detail; });
  document.addEventListener("pestana", e => {
    detener();
    if (e.detail !== "inicio") return;
    cargarLuces();
    cargarClima();
    tLuces = setInterval(cargarLuces, CADA_LUCES);
    tClima = setInterval(cargarClima, CADA_CLIMA);
    if (ultimo.panel) document.dispatchEvent(new CustomEvent("panel", { detail: ultimo.panel }));
  });

  window.InicioPanel = { api, el, hace, iconoClima, recargarLuces: cargarLuces, ultimo: () => ultimo };
})();
