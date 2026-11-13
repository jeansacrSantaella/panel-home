/* Reproductor común de cámaras (window.Reproductor).
   Internas: <video-stream> de go2rtc por el WebSocket del panel, con una sesión de video compartida por toda la página.
   Externas: iframe a stream.html de go2rtc. */
(function () {
  "use strict";
  let cfg = { internas: false, go2rtc_url: "" };
  const vivos = new Set();           // reproductores montados
  let sid = null, pendiente = null, latido = null, cierre = null, modulo = null;

  function configurar(c) { cfg = Object.assign(cfg, c || {}); }

  async function pedir(url, cuerpo) {
    const r = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(cuerpo || {}) });
    const d = await r.json().catch(() => ({}));
    return { ok: r.ok, estado: r.status, datos: d };
  }

  // Abre (una vez) la sesión de video; rechaza con {sesiones:[...]} si no hay lugar
  function asegurarSesion() {
    if (sid) return Promise.resolve(sid);
    if (pendiente) return pendiente;
    pendiente = pedir("/api/camaras/sesion").then(r => {
      if (!r.ok) {
        const e = new Error(r.datos.error || "No se pudo abrir la sesión de video");
        e.sesiones = r.datos.sesiones || [];
        e.codigo = r.estado;
        throw e;
      }
      sid = r.datos.id;
      if (!latido) latido = setInterval(darLatido, 20000);
      return sid;
    }).finally(() => { pendiente = null; });
    return pendiente;
  }

  async function darLatido() {
    if (!sid) return;
    try {
      const r = await pedir(`/api/camaras/sesion/${encodeURIComponent(sid)}/latido`);
      if (r.ok && r.datos.estado === "ok") return;
      if (!r.ok && r.estado !== 404 && r.estado !== 410) return;
    } catch (_) { return; }
    // Expulsada: se renueva y se recrean los reproductores
    sid = null;
    vivos.forEach(v => v.montar());
  }

  function cerrarSesion() {
    if (latido) { clearInterval(latido); latido = null; }
    if (!sid) return;
    const url = `/api/camaras/sesion/${encodeURIComponent(sid)}/salir`;
    sid = null;
    try { if (!(navigator.sendBeacon && navigator.sendBeacon(url, new Blob(["{}"], { type: "application/json" })))) throw 0; }
    catch (_) { fetch(url, { method: "POST", keepalive: true, headers: { "Content-Type": "application/json" }, body: "{}" }).catch(() => {}); }
  }

  function programarCierre() {
    clearTimeout(cierre);
    if (vivos.size === 0) cierre = setTimeout(() => { if (vivos.size === 0) cerrarSesion(); }, 1500);
  }

  // El módulo de go2rtc se carga una sola vez
  function cargarModulo() {
    if (modulo) return modulo;
    modulo = new Promise((ok, mal) => {
      if (customElements.get("video-stream")) return ok();
      const s = document.createElement("script");
      s.type = "module";
      s.src = "/api/camaras/go2rtc/video-stream.js";
      s.onload = () => customElements.whenDefined("video-stream").then(ok);
      s.onerror = () => { modulo = null; mal(new Error("No se pudo cargar el reproductor de go2rtc")); };
      document.head.appendChild(s);
    });
    return modulo;
  }

  function aviso(contenedor, texto, reintentar) {
    const d = document.createElement("div");
    d.className = "reproductor-aviso";
    d.setAttribute("role", "status");
    const p = document.createElement("p");
    p.textContent = texto;
    d.appendChild(p);
    if (reintentar) {
      const b = document.createElement("button");
      b.type = "button"; b.className = "boton"; b.textContent = "Reintentar";
      b.addEventListener("click", reintentar);
      d.appendChild(b);
    }
    contenedor.replaceChildren(d);
  }

  function crearIframe(camara) {
    const base = cfg.go2rtc_url || `${location.protocol}//${location.hostname}:1984`;
    const f = document.createElement("iframe");
    f.className = "reproductor-nodo";
    f.src = `${base}/stream.html?src=${encodeURIComponent(camara.id)}&mode=mse`;
    f.title = `Video de ${camara.nombre || camara.id}`;
    f.setAttribute("allow", "fullscreen");  // sin autoplay: arranca en silencio
    return f;
  }

  function crear(contenedor, camara, opciones) {
    opciones = opciones || {};
    const v = { destruido: false };
    let conAudio = false, botonAudio = null;
    // Alterna el audio; el play() va dentro del gesto del usuario
    function aplicarAudio() {
      if (botonAudio) {
        botonAudio.textContent = conAudio ? "🔊" : "🔇";
        botonAudio.setAttribute("aria-pressed", String(conAudio));
        botonAudio.setAttribute("aria-label", conAudio ? "Silenciar" : "Activar audio");
        botonAudio.title = conAudio ? "Silenciar" : "Activar audio";
      }
      const vid = contenedor.querySelector("video-stream");
      if (vid && vid.video) {
        vid.video.muted = !conAudio;
        if (conAudio) { const r = vid.video.play(); if (r && r.catch) r.catch(() => {}); }
      }
    }
    v.audio = function (si) { conAudio = !!si; aplicarAudio(); };
    v.conAudio = () => conAudio;
    v.montar = async function () {
      if (v.destruido) return;
      contenedor.classList.add("reproductor");
      if (!cfg.internas) { contenedor.replaceChildren(crearIframe(camara)); return; }
      aviso(contenedor, "Conectando…");
      try {
        const id = await asegurarSesion();
        await cargarModulo();
        if (v.destruido) return;
        const p = document.createElement("video-stream");
        p.className = "reproductor-nodo";
        p.mode = "mse";
        p.background = true;
        p.setAttribute("aria-label", `Video de ${camara.nombre || camara.id}`);
        const proto = location.protocol === "https:" ? "wss:" : "ws:";
        p.src = `${proto}//${location.host}/api/camaras/video?src=${encodeURIComponent(camara.id)}&sesion=${encodeURIComponent(id)}`;
        contenedor.replaceChildren(p);
        // Siempre arranca en silencio
        conAudio = false;
        if (opciones.audio) {
          botonAudio = document.createElement("button");
          botonAudio.type = "button";
          botonAudio.className = "reproductor-audio";
          botonAudio.addEventListener("click", () => v.audio(!conAudio));
          contenedor.appendChild(botonAudio);
        }
        requestAnimationFrame(() => {
          if (p.video) { p.video.muted = true; p.video.controls = false; p.video.playsInline = true; }
          aplicarAudio();
        });
        if (opciones.alListo) opciones.alListo(id);
      } catch (e) {
        if (v.destruido) return;
        const n = e.sesiones ? e.sesiones.length : 0;
        aviso(contenedor, e.codigo === 409
          ? `No hay lugar para otra sesión de video${n ? `. Hay ${n} sesiones abiertas` : ""}.`
          : e.message, v.montar);
        if (opciones.alError) opciones.alError(e);
      }
    };
    v.destruir = function () {
      v.destruido = true;
      vivos.delete(v);
      contenedor.replaceChildren();
      programarCierre();
    };
    clearTimeout(cierre);
    vivos.add(v);
    v.montar();
    return v;
  }

  // La configuración llega con /api/panel
  document.addEventListener("panel", e => {
    if (e.detail) configurar({ internas: !!e.detail.camaras_internas, go2rtc_url: e.detail.go2rtc_url || "" });
  });
  addEventListener("pagehide", cerrarSesion);

  window.Reproductor = { configurar, crear, sesion: asegurarSesion, sesionId: () => sid, internas: () => cfg.internas };
})();
