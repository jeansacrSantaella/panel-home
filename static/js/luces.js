/* Luces: focos Tuya por la red local (API /api/luces).
   - Resumen (#luces-resumen): solo nombre e interruptor.
   - Pestaña Luces (#luces-lista): brillo, blanco, color y estado de conexión de cada foco. */
(function () {
  "use strict";

  const lista = document.getElementById("luces-lista");
  const listaResumen = document.getElementById("luces-resumen");
  const aviso = document.getElementById("luces-aviso");
  const avisoResumen = document.getElementById("luces-aviso-resumen");
  const todas = document.getElementById("luces-todas");
  const subs = [document.getElementById("luces-sub"), document.getElementById("luces-sub-vista")].filter(Boolean);
  if (!lista || !listaResumen) return;

  const PRESETS = [["#ff3b30", "rojo"], ["#ff9500", "naranja"], ["#ffcc00", "amarillo"],
                   ["#34c759", "verde"], ["#0a84ff", "azul"], ["#bf5af2", "morado"]];
  let luces = [];
  let ocupado = false;          // el usuario arrastra un deslizador: no repintar
  const abiertos = new Set();   // <details> abiertos, por id de foco
  let avisoTemporal = null;

  function mostrarError(texto) {
    [aviso, avisoResumen].forEach(a => { a.textContent = texto; a.hidden = false; });
    clearTimeout(avisoTemporal);
    avisoTemporal = setTimeout(() => { aviso.hidden = true; avisoResumen.hidden = true; avisoTemporal = null; }, 4000);
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

  function colorDe(luz) {
    return luz.modo === "colour" && luz.color ? luz.color : blanco(luz.temperatura);
  }

  function interruptor(luz, li) {
    const prendida = luz.en_linea && luz.encendida;
    const sw = el("button", "luz-switch", { type: "button", disabled: !luz.en_linea });
    sw.setAttribute("role", "switch");
    sw.setAttribute("aria-checked", String(!!prendida));
    sw.setAttribute("aria-label", (prendida ? "Apagar " : "Encender ") + luz.nombre);
    sw.addEventListener("click", () => cambiar(luz, li, { encendida: !prendida }));
    return sw;
  }

  // Resumen: punto de color, nombre e interruptor
  function filaMini(luz) {
    const prendida = luz.en_linea && luz.encendida;
    const li = el("li", "luz-mini" + (prendida ? "" : " apagada") + (luz.en_linea ? "" : " sin-red"));
    const punto = el("span", "luz-punto");
    punto.setAttribute("aria-hidden", "true");
    if (prendida) punto.style.setProperty("--luz", colorDe(luz));
    const nombre = el("b", "", { textContent: luz.nombre, title: luz.en_linea ? "" : "Sin respuesta" });
    li.append(punto, nombre, interruptor(luz, li));
    return li;
  }

  // Blanco según temperatura: 0 = cálido, 100 = frío
  function blanco(t) {
    const a = [0xff, 0xb4, 0x6b], b = [0xdf, 0xf1, 0xff], k = Math.max(0, Math.min(100, t ?? 50)) / 100;
    return "#" + a.map((v, i) => Math.round(v + (b[i] - v) * k).toString(16).padStart(2, "0")).join("");
  }

  function el(tag, clase, props) {
    const n = document.createElement(tag);
    if (clase) n.className = clase;
    Object.assign(n, props || {});
    return n;
  }

  async function enviar(url, cuerpo) {
    const r = await fetch(url, {
      method: "POST", credentials: "same-origin",
      headers: { "Content-Type": "application/json" }, body: JSON.stringify(cuerpo),
    });
    const datos = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(datos.error || "No se pudo cambiar el foco");
    return datos;
  }

  async function cambiar(luz, li, cambios) {
    li.classList.add("ocupada");
    try {
      const nueva = await enviar("/api/luces/" + encodeURIComponent(luz.id), cambios);
      luces = luces.map(x => (x.id === nueva.id ? nueva : x));
    } catch (e) {
      mostrarError(luz.nombre + ": " + e.message);
    }
    pintar();
  }

  // Deslizadores: no repintar mientras se arrastran
  function rango(input, alCambiar) {
    input.addEventListener("pointerdown", () => { ocupado = true; });
    input.addEventListener("focus", () => { ocupado = true; });
    input.addEventListener("blur", () => { ocupado = false; });
    input.addEventListener("change", () => { ocupado = false; alCambiar(Number(input.value)); });
  }

  function fila(luz) {
    const prendida = luz.en_linea && luz.encendida;
    const li = el("li", "luz" + (prendida ? "" : " apagada") + (luz.en_linea ? "" : " sin-red"));

    const icono = el("span", "luz-icono");
    icono.setAttribute("aria-hidden", "true");
    if (prendida) icono.style.setProperty("--luz", colorDe(luz));

    const info = el("div", "luz-info");
    info.append(el("b", "", { textContent: luz.nombre }),
      el("span", "tenue", { textContent: !luz.en_linea ? "Sin respuesta" : prendida ? `Encendida · ${luz.brillo ?? "–"}%` : "Apagada" }));

    const sw = interruptor(luz, li);

    // Conexión: en línea / sin respuesta, IP y última vez que contestó
    const conexion = el("div", "luz-conexion");
    const estado = el("span", "luz-estado " + (luz.en_linea ? "ok" : "mal"), { textContent: luz.en_linea ? "Conectado" : "Sin respuesta" });
    const partes = [luz.ip ? "IP " + luz.ip : "sin IP", luz.en_linea ? "contestó " + hace(luz.visto) : "último contacto " + hace(luz.visto)];
    if (!luz.en_linea && luz.error) partes.push(luz.error);
    conexion.append(estado, el("span", "tenue", { textContent: partes.join(" · ") }));

    const brillo = el("input", "luz-brillo", { type: "range", min: 1, max: 100, value: luz.brillo ?? 50, disabled: !luz.en_linea });
    brillo.setAttribute("aria-label", "Brillo de " + luz.nombre);
    rango(brillo, v => cambiar(luz, li, prendida ? { brillo: v } : { encendida: true, brillo: v }));

    li.append(icono, info, sw, conexion, brillo);

    if (luz.en_linea && (luz.tiene_color || luz.tiene_temperatura)) {
      const mas = el("details", "luz-mas", { open: abiertos.has(luz.id) });
      mas.addEventListener("toggle", () => { mas.open ? abiertos.add(luz.id) : abiertos.delete(luz.id); });
      mas.append(el("summary", "", { textContent: "Color" }));
      if (luz.tiene_temperatura) {
        const lab = el("label", "", { textContent: "Blanco " });
        const temp = el("input", "luz-temp", { type: "range", min: 0, max: 100, value: luz.temperatura ?? 50 });
        temp.setAttribute("aria-label", "Blanco cálido a frío de " + luz.nombre);
        rango(temp, v => cambiar(luz, li, prendida ? { temperatura: v } : { encendida: true, temperatura: v }));
        lab.append(temp, el("span", "tenue", { textContent: "cálido ←→ frío" }));
        mas.append(lab);
      }
      if (luz.tiene_color) {
        const lab = el("label", "", { textContent: "Color " });
        const color = el("input", "luz-color", { type: "color", value: luz.color || "#ffffff" });
        color.setAttribute("aria-label", "Color de " + luz.nombre);
        color.addEventListener("change", () => cambiar(luz, li, prendida ? { color: color.value } : { encendida: true, color: color.value }));
        lab.append(color);
        const presets = el("div", "luz-presets");
        PRESETS.forEach(([hex, nombre]) => {
          const b = el("button", "", { type: "button" });
          b.style.background = hex;
          b.setAttribute("aria-label", "Color " + nombre);
          b.addEventListener("click", () => cambiar(luz, li, prendida ? { color: hex } : { encendida: true, color: hex }));
          presets.append(b);
        });
        mas.append(lab, presets);
      }
      li.append(mas);
    }
    return li;
  }

  function pintar() {
    lista.textContent = "";
    listaResumen.textContent = "";
    luces.forEach(l => { lista.append(fila(l)); listaResumen.append(filaMini(l)); });
    const enc = luces.filter(l => l.en_linea && l.encendida).length;
    const caidos = luces.filter(l => !l.en_linea).length;
    const texto = luces.length ? `· ${enc} de ${luces.length} encendidas` + (caidos ? ` · ${caidos} sin respuesta` : "") : "";
    subs.forEach(s => { s.textContent = texto; });
  }

  async function cargar() {
    if (ocupado) return;
    try {
      const r = await fetch("/api/luces", { credentials: "same-origin" });
      const d = await r.json();
      if (!d.configurado) {
        [aviso, avisoResumen].forEach(a => {
          a.textContent = (d.motivo || "Las luces no están configuradas.") + " Sigue los pasos de docs/LUCES.md.";
          a.hidden = false;
        });
        todas.hidden = true;
        luces = [];
        pintar();
        return;
      }
      if (!avisoTemporal) { aviso.hidden = true; avisoResumen.hidden = true; }
      todas.hidden = false;
      luces = d.luces || [];
      pintar();
    } catch (e) {
      // sin conexión: se reintenta en la siguiente vuelta
    }
  }

  todas.addEventListener("click", async (e) => {
    const b = e.target.closest("[data-todas]");
    if (!b) return;
    b.disabled = true;
    try {
      const r = await enviar("/api/luces/todas", { encendida: b.dataset.todas === "1" });
      if (r.respondieron < luces.length) mostrarError(`Respondieron ${r.respondieron} de ${luces.length} focos`);
    } catch (err) {
      mostrarError(err.message);
    }
    b.disabled = false;
    cargar();
  });

  cargar();
  setInterval(cargar, 20000);
  // al ejecutar una rutina los focos cambian: refrescar enseguida
  document.addEventListener("rutina-ejecutada", () => setTimeout(cargar, 300));
})();
