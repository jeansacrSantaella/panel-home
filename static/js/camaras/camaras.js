/* Pestaña Cámaras: rejilla con video en vivo, PTZ, zoom digital, alta y baja de cámaras. */
(function () {
  "use strict";
  const VELOCIDAD = 0.6, CADA_ORDEN = 500, ZOOM_MAX = 4, ZOOM_PASO = 0.5, CADA_SALUD = 10000;
  const raiz = document.getElementById("pestana-camaras");
  if (!raiz) return;
  const $ = id => document.getElementById(id);
  const rejilla = $("camaras-rejilla"), errorEl = $("camaras-error"), avisoEl = $("camaras-aviso");
  const enlaceResp = $("camaras-respaldo");
  const dlgAlta = $("dlg-camara-alta"), dlgPin = $("dlg-camara-pin");

  let visible = false, camaras = [], salud = {}, config = { protegido: false }, panel = null;
  let grande = null, modo = "grande", pin = "", temporizador = null, tiles = new Map();
  try { modo = localStorage.getItem("camaras_modo") === "dos" ? "dos" : "grande"; } catch (_) {}

  function el(tag, clase, texto, props) {
    const n = document.createElement(tag);
    if (clase) n.className = clase;
    if (texto != null) n.textContent = texto;
    if (props) Object.assign(n, props);
    return n;
  }

  function error(msg) { errorEl.textContent = msg || ""; errorEl.hidden = !msg; }

  async function api(ruta, metodo, cuerpo, cab) {
    const r = await fetch(ruta, {
      method: metodo || "GET",
      headers: Object.assign({ "Content-Type": "application/json" }, cab || {}),
      body: cuerpo ? JSON.stringify(cuerpo) : undefined
    });
    const d = await r.json().catch(() => ({}));
    if (!r.ok) { const e = new Error(d.error || d.detail || `Error ${r.status}`); e.estado = r.status; throw e; }
    return d;
  }

  const ESTADOS = { ok: ["En vivo", "ok"], sin_video: ["Sin video", "alerta"], sin_red: ["Sin red", "mal"] };

  // ---------- PTZ ----------
  const ordenes = {};  // cid -> detener()
  function mantener(cid, x, y) {
    let enCurso = false;
    const enviar = async () => {
      if (enCurso) return;  // no apilar órdenes si la cámara va lenta
      enCurso = true;
      try {
        const sid = await Reproductor.sesion();
        await api(`/api/camaras/${encodeURIComponent(cid)}/mover`, "POST", { x, y }, { "X-Sesion": sid });
        error("");
      } catch (e) { error("La cámara no respondió: " + e.message); }
      enCurso = false;
    };
    enviar();
    const id = setInterval(enviar, CADA_ORDEN);
    return () => {
      clearInterval(id);
      api(`/api/camaras/${encodeURIComponent(cid)}/parar`, "POST", {}).catch(() => {});
    };
  }
  function soltar(cid) { if (ordenes[cid]) { ordenes[cid](); delete ordenes[cid]; } }
  function mover(cid, x, y) { soltar(cid); ordenes[cid] = mantener(cid, x * VELOCIDAD, y * VELOCIDAD); }

  const FLECHAS = { ArrowUp: [0, 1], ArrowDown: [0, -1], ArrowLeft: [-1, 0], ArrowRight: [1, 0] };

  // ---------- tarjeta de una cámara ----------
  function crearTile(cam) {
    const cid = cam.id, nombre = cam.nombre || cid;
    const t = el("article", "cam", null, { tabIndex: 0 });
    t.setAttribute("aria-label", `Cámara ${nombre}. Flechas del teclado para girarla.`);
    t.dataset.id = cid;

    const vista = el("div", "cam-vista");
    t.appendChild(vista);

    const cab = el("div", "cam-cab");
    const titulo = el("button", "cam-nombre", nombre, { type: "button", title: "Ver grande" });
    titulo.addEventListener("click", () => { grande = cid; pintar(); });
    const punto = el("span", "punto"); punto.setAttribute("aria-hidden", "true");
    const estado = el("span", "cam-estado");
    const lat = el("span", "cam-dato tenue");
    const cortes = el("span", "cam-dato tenue");
    cab.append(punto, titulo, estado, lat, cortes);
    t.appendChild(cab);

    const barra = el("div", "cam-barra");
    const boton = (txt, etiqueta, fn) => {
      const b = el("button", "boton cam-btn", txt, { type: "button", title: etiqueta });
      b.setAttribute("aria-label", etiqueta);
      b.addEventListener("click", fn);
      return b;
    };
    const etiquetaZoom = el("span", "cam-zoom-valor", "1×");
    barra.append(
      boton("Foto", "Foto actual de " + nombre, () => window.open(`/api/camaras/${encodeURIComponent(cid)}/foto`, "_blank", "noopener")),
      boton("Pantalla completa", "Pantalla completa de " + nombre, () => {
        (vista.requestFullscreen || vista.webkitRequestFullscreen || (() => {})).call(vista);
      }),
      boton("−", "Alejar", () => zoom(-1)),
      etiquetaZoom,
      boton("+", "Acercar", () => zoom(1)),
      boton("Quitar", "Quitar " + nombre, () => quitar(cam))
    );
    t.appendChild(barra);

    // flechas en cruz: mientras estén presionadas mandan la orden
    const cruz = el("div", "cam-cruz");
    cruz.setAttribute("role", "group"); cruz.setAttribute("aria-label", "Mover " + nombre);
    [["▲", "Arriba", 0, 1, "n"], ["◀", "Izquierda", -1, 0, "o"], ["▶", "Derecha", 1, 0, "e"], ["▼", "Abajo", 0, -1, "s"]].forEach(([s, etq, x, y, pos]) => {
      const b = el("button", "boton cam-flecha cam-" + pos, s, { type: "button", title: etq });
      b.setAttribute("aria-label", etq);
      b.addEventListener("pointerdown", e => { e.preventDefault(); b.setPointerCapture && b.setPointerCapture(e.pointerId); mover(cid, x, y); });
      ["pointerup", "pointercancel", "lostpointercapture"].forEach(ev => b.addEventListener(ev, () => soltar(cid)));
      b.addEventListener("keydown", e => { if (e.key === " " || e.key === "Enter") { e.preventDefault(); if (!e.repeat) mover(cid, x, y); } });
      b.addEventListener("keyup", e => { if (e.key === " " || e.key === "Enter") soltar(cid); });
      cruz.appendChild(b);
    });
    t.appendChild(cruz);

    // teclado: flechas con la cámara enfocada
    t.addEventListener("keydown", e => {
      const d = FLECHAS[e.key];
      if (!d || e.repeat || e.target.closest("button")) return;
      e.preventDefault();
      mover(cid, d[0], d[1]);
    });
    t.addEventListener("keyup", e => { if (FLECHAS[e.key]) soltar(cid); });
    t.addEventListener("blur", () => soltar(cid));

    // zoom digital: rueda, arrastre y doble clic
    let z = 1, dx = 0, dy = 0, arrastrando = false;
    function aplicar() {
      const mx = vista.clientWidth * (z - 1) / (2 * z), my = vista.clientHeight * (z - 1) / (2 * z);
      dx = Math.max(-mx, Math.min(mx, dx)); dy = Math.max(-my, Math.min(my, dy));
      vista.style.setProperty("--zoom", z);
      vista.style.setProperty("--dx", dx + "px");
      vista.style.setProperty("--dy", dy + "px");
      vista.classList.toggle("ampliada", z > 1);
      etiquetaZoom.textContent = z + "×";
    }
    function zoom(paso) {
      z = Math.min(ZOOM_MAX, Math.max(1, z + paso * ZOOM_PASO));
      if (z === 1) dx = dy = 0;
      aplicar();
    }
    vista.addEventListener("wheel", e => { e.preventDefault(); zoom(e.deltaY < 0 ? 1 : -1); }, { passive: false });
    vista.addEventListener("pointerdown", e => { if (z > 1) { arrastrando = true; vista.setPointerCapture(e.pointerId); } });
    vista.addEventListener("pointermove", e => { if (arrastrando) { dx += e.movementX / z; dy += e.movementY / z; aplicar(); } });
    ["pointerup", "pointercancel"].forEach(ev => vista.addEventListener(ev, () => { arrastrando = false; }));
    vista.addEventListener("dblclick", () => { z = 1; dx = dy = 0; aplicar(); });

    const rep = Reproductor.crear(vista, cam);
    return { nodo: t, punto, estado, lat, cortes, rep, vista };
  }

  function destruirTiles() {
    Object.keys(ordenes).forEach(soltar);
    tiles.forEach(t => t.rep.destruir());
    tiles.clear();
    rejilla.replaceChildren();
  }

  function pintarSalud() {
    const cams = (salud && salud.camaras) || {};
    tiles.forEach((t, cid) => {
      const s = cams[cid] || {};
      const [txt, nivel] = ESTADOS[s.estado] || ["Sin datos", "nada"];
      t.punto.dataset.estado = nivel;
      t.estado.textContent = txt;
      t.lat.textContent = s.latencia_ms != null ? s.latencia_ms + " ms" : "";
      t.cortes.textContent = s.cortes_24h != null ? s.cortes_24h + " cortes 24 h" : "";
    });
  }

  // Dibuja la rejilla; los reproductores solo se recrean si cambia el conjunto de cámaras
  function pintar() {
    const ids = camaras.map(c => c.id);
    if (!ids.includes(grande)) grande = ids[0] || null;
    if (ids.join() !== Array.from(tiles.keys()).join()) {
      destruirTiles();
      camaras.forEach(c => { const t = crearTile(c); tiles.set(c.id, t); rejilla.appendChild(t.nodo); });
    }
    rejilla.dataset.modo = modo;
    rejilla.hidden = camaras.length === 0;
    // en modo grande, la elegida va primera y ocupa el espacio principal
    tiles.forEach((t, cid) => {
      t.nodo.classList.toggle("cam-grande", modo === "grande" && cid === grande);
      t.nodo.style.order = cid === grande ? 0 : 1;
    });
    $("camaras-vacio").hidden = camaras.length > 0 || !avisoEl.hidden;
    pintarSalud();
  }

  // ---------- carga ----------
  async function cargar() {
    error("");
    try {
      camaras = await api("/api/camaras");
      avisoEl.hidden = true;
    } catch (e) {
      destruirTiles(); camaras = [];
      if (e.estado === 409 || e.estado === 404) {
        avisoEl.hidden = false;
        const url = panel && panel.camaras_url;
        enlaceResp.hidden = !url;
        if (url) enlaceResp.href = url;
      } else { error("No se pudieron leer las cámaras: " + e.message); }
    }
    api("/api/camaras/config").then(c => { config = c; }).catch(() => {});
    pintar();
    await refrescarSalud();
  }
  async function refrescarSalud() {
    try { salud = await api("/api/camaras/salud"); } catch (_) { return; }
    pintarSalud();
  }

  function iniciar() {
    cargar();
    clearInterval(temporizador);
    temporizador = setInterval(refrescarSalud, CADA_SALUD);
  }
  function detener() {
    clearInterval(temporizador); temporizador = null;
    destruirTiles();
  }

  document.addEventListener("pestana", e => {
    const ahora = e.detail === "camaras";
    if (ahora === visible) return;
    visible = ahora;
    if (visible) iniciar(); else detener();
  });
  document.addEventListener("panel", e => {
    panel = e.detail;
    if (panel && panel.camaras_url && !avisoEl.hidden) { enlaceResp.href = panel.camaras_url; enlaceResp.hidden = false; }
  });

  // ---------- diseño ----------
  document.querySelectorAll("[data-camaras-modo]").forEach(b => {
    b.addEventListener("click", () => {
      modo = b.dataset.camarasModo;
      try { localStorage.setItem("camaras_modo", modo); } catch (_) {}
      document.querySelectorAll("[data-camaras-modo]").forEach(x => x.setAttribute("aria-pressed", String(x === b)));
      pintar();
    });
    b.setAttribute("aria-pressed", String(b.dataset.camarasModo === modo));
  });

  // ---------- PIN, alta y baja ----------
  function pedirPin() {
    if (!config.protegido) return Promise.resolve("");
    if (pin) return Promise.resolve(pin);
    return new Promise(res => {
      const campo = $("camara-pin"); campo.value = "";
      const fin = () => { dlgPin.removeEventListener("close", fin); res(dlgPin.returnValue === "ok" && campo.value ? (pin = campo.value) : null); };
      dlgPin.addEventListener("close", fin);
      dlgPin.returnValue = "";
      dlgPin.showModal();
      campo.focus();
    });
  }
  const cabAdmin = () => (pin ? { "X-Admin": pin } : {});
  function falloPin(e) { if (e.estado === 401) pin = ""; error(e.message); }

  $("camaras-agregar").addEventListener("click", () => { $("camara-alta-error").textContent = ""; dlgAlta.showModal(); $("camara-ips").focus(); });
  $("camara-alta-cancelar").addEventListener("click", () => dlgAlta.close());
  $("camara-alta-form").addEventListener("submit", async ev => {
    ev.preventDefault();
    const v = id => $(id).value.trim();
    const ips = v("camara-ips").split(/[\s,;]+/).filter(Boolean);
    const msg = $("camara-alta-error");
    if (!ips.length) { msg.textContent = "Escribe al menos una IP."; return; }
    if (config.protegido && !(await pedirPin())) return;
    const num = id => (v(id) ? Number(v(id)) : undefined);
    try {
      await api("/api/camaras", "POST", {
        ips, nombre: v("camara-nombre"), puerto_rtsp: num("camara-rtsp"), ruta_rtsp: v("camara-ruta"),
        puerto_onvif: num("camara-onvif"), usuario: v("camara-usuario"), clave: $("camara-clave").value
      }, cabAdmin());
      $("camara-clave").value = "";
      dlgAlta.close();
      cargar();
    } catch (e) { if (e.estado === 401) pin = ""; msg.textContent = e.message; }
  });

  async function quitar(cam) {
    if (config.protegido) { if (!(await pedirPin())) return; }
    else if (!window.confirm(`¿Quitar la cámara ${cam.nombre || cam.id}?`)) return;
    try {
      await api(`/api/camaras/${encodeURIComponent(cam.id)}`, "DELETE", null, cabAdmin());
      cargar();
    } catch (e) { falloPin(e); }
  }

  addEventListener("blur", () => Object.keys(ordenes).forEach(soltar));
})();
