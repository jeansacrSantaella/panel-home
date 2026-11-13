/* Inicio: arco tipo termostato para las luces de una habitación.
   Clases usadas (prefijo inicio-hab-):
   - .inicio-hab-cabeza / .inicio-hab-nav (botones ‹ ›) / .inicio-hab-nombre (nombre de la habitación elegida)
   - .inicio-hab-arco: contenedor del arco (position:relative inline) con el SVG .inicio-hab-svg
   - .inicio-hab-pista (trazo tenue), .inicio-hab-relleno (trazo con degradado), .inicio-hab-punto (extremo)
   - .inicio-hab-centro: capa central con .inicio-hab-estado, .inicio-hab-valor y .inicio-hab-focos
   - .inicio-hab-ajuste: fila con los botones .inicio-hab-menos y .inicio-hab-mas
   - .inicio-hab-acciones: fila de botones redondos .inicio-hab-accion (+ .activo si la habitación está encendida)
     con .inicio-hab-accion-etq (texto bajo el ícono)
   - .inicio-hab-error: texto breve de error; .inicio-hab-vacio: mensaje sin habitaciones o sin luces
   Escucha document "inicio-luces" y "inicio-elegir-hab" (detail = nombre de habitación). */
(function () {
  "use strict";
  const RAIZ = document.getElementById("inicio-hab");
  if (!RAIZ || !window.InicioPanel) return;
  const { api, el } = window.InicioPanel;
  const NS = "http://www.w3.org/2000/svg";
  const CLAVE = "inicio-hab-elegida";
  const SIN_HAB = "Sin habitación";
  const PASO = 10;
  const R = 80, C = 100, INI = 225, BARRIDO = 270;

  let datos = null;
  let elegida = null;
  let error = "";
  let pendiente = null;   // brillo objetivo acumulado
  let temporizador = null;

  try { elegida = localStorage.getItem(CLAVE); } catch (_) { /* sin almacenamiento */ }

  function punto(grados) {
    const a = grados * Math.PI / 180;
    return [C + R * Math.sin(a), C - R * Math.cos(a)];
  }
  function ruta(desde, hasta) {
    const [x1, y1] = punto(desde);
    const [x2, y2] = punto(hasta);
    const grande = (hasta - desde) > 180 ? 1 : 0;
    return `M${x1.toFixed(2)} ${y1.toFixed(2)}A${R} ${R} 0 ${grande} 1 ${x2.toFixed(2)} ${y2.toFixed(2)}`;
  }
  function svg(etq, attrs, clase) {
    const n = document.createElementNS(NS, etq);
    for (const k in attrs) n.setAttribute(k, attrs[k]);
    if (clase) n.setAttribute("class", clase);
    return n;
  }

  const ICONOS = {
    energia: '<path d="M12 3v8M6.5 6.8a7.5 7.5 0 1 0 11 0"/>',
    todo: '<rect x="4" y="4" width="6.5" height="6.5" rx="1.5"/><rect x="13.5" y="4" width="6.5" height="6.5" rx="1.5"/><rect x="4" y="13.5" width="6.5" height="6.5" rx="1.5"/><rect x="13.5" y="13.5" width="6.5" height="6.5" rx="1.5"/>',
    noche: '<path d="M20 14.5A8 8 0 0 1 9.5 4 8 8 0 1 0 20 14.5Z"/>',
    calida: '<circle cx="12" cy="12" r="4.5"/><path d="M12 2v2.5M12 19.5V22M2 12h2.5M19.5 12H22M4.9 4.9l1.8 1.8M17.3 17.3l1.8 1.8M4.9 19.1l1.8-1.8M17.3 6.7l1.8-1.8"/>',
  };
  function icono(clave) {
    const s = document.createElement("span");
    s.className = "inicio-hab-ico";
    s.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">${ICONOS[clave]}</svg>`; // constante
    return s;
  }

  function habitaciones() {
    return ((datos && datos.habitaciones) || []).filter(h => h.habitacion !== SIN_HAB && h.total > 0);
  }
  function actual() {
    const hs = habitaciones();
    return hs.find(h => h.habitacion === elegida) || hs[0] || null;
  }
  function elegir(nombre) {
    elegida = nombre;
    try { localStorage.setItem(CLAVE, nombre); } catch (_) { /* ignorar */ }
    error = "";
    dibujar();
  }
  function mover(d) {
    const hs = habitaciones();
    const h = actual();
    if (!h || hs.length < 2) return;
    const i = hs.indexOf(h);
    elegir(hs[(i + d + hs.length) % hs.length].habitacion);
  }

  async function enviar(cuerpo) {
    error = "";
    try {
      await api("/api/luces/habitacion", { method: "POST", body: cuerpo });
    } catch (e) { error = e.message || "No se pudo aplicar"; }
    await window.InicioPanel.recargarLuces();
    dibujar();
  }

  function cambiarBrillo(h, delta) {
    const base = pendiente !== null ? pendiente : (h.encendidos > 0 && h.brillo ? h.brillo : 0);
    pendiente = Math.max(10, Math.min(100, Math.round((base + delta) / PASO) * PASO));
    const nombre = h.habitacion;
    const encendida = h.encendidos > 0;
    dibujar();
    clearTimeout(temporizador);
    temporizador = setTimeout(() => {
      const brillo = pendiente;
      pendiente = null;
      enviar(encendida ? { habitacion: nombre, brillo } : { habitacion: nombre, encendida: true, brillo });
    }, 400);
  }

  function boton(clase, texto, etiqueta, alClic) {
    const b = el("button", clase, { type: "button", textContent: texto });
    b.setAttribute("aria-label", etiqueta);
    b.addEventListener("click", alClic);
    return b;
  }
  function accion(clave, texto, etiqueta, alClic, activo) {
    const b = el("button", "inicio-hab-accion" + (activo ? " activo" : ""), { type: "button" });
    b.setAttribute("aria-label", etiqueta);
    if (activo !== undefined) b.setAttribute("aria-pressed", activo ? "true" : "false");
    b.appendChild(icono(clave));
    b.appendChild(el("span", "inicio-hab-accion-etq", { textContent: texto }));
    b.addEventListener("click", alClic);
    return b;
  }

  function vacio(texto, enlace) {
    const p = el("p", "inicio-hab-vacio", { textContent: texto });
    if (enlace) {
      p.appendChild(document.createTextNode(" "));
      p.appendChild(el("a", "", { href: "#luces", textContent: enlace }));
    }
    RAIZ.replaceChildren(p);
  }

  function dibujar() {
    if (!datos) return vacio("Cargando luces…");
    if (!datos.configurado) return vacio(datos.motivo || "Las luces no están configuradas");
    const h = actual();
    if (!h) {
      RAIZ.replaceChildren();
      vacio("Asigna una habitación a tus focos en la pestaña", "Luces");
      return;
    }

    const encendida = h.encendidos > 0;
    const sinRespuesta = h.en_linea === 0;
    const brillo = pendiente !== null ? pendiente : (encendida ? (h.brillo || 0) : 0);
    const estado = sinRespuesta ? "Sin respuesta" : (encendida ? "Encendida" : "Apagada");

    // Cabecera con selector
    const cabeza = el("div", "inicio-hab-cabeza");
    cabeza.appendChild(boton("inicio-hab-nav", "‹", "Habitación anterior", () => mover(-1)));
    const nom = el("h2", "inicio-hab-nombre", { textContent: h.habitacion });
    cabeza.appendChild(nom);
    cabeza.appendChild(boton("inicio-hab-nav", "›", "Habitación siguiente", () => mover(1)));

    // Arco
    const grados = INI + BARRIDO * brillo / 100;
    const s = svg("svg", { viewBox: "0 0 200 200", role: "img", "aria-label": `${h.habitacion}: brillo ${brillo} %` }, "inicio-hab-svg");
    s.style.width = "100%"; s.style.height = "auto"; s.style.display = "block";
    const defs = svg("defs", {});
    const g = svg("linearGradient", { id: "inicio-hab-grad", gradientUnits: "userSpaceOnUse", x1: "20", y1: "180", x2: "180", y2: "20" });
    [["0", "#8B5CF6"], ["0.55", "#5aa8ff"], ["1", "#00E5FF"]].forEach(([o, c]) => g.appendChild(svg("stop", { offset: o, "stop-color": c })));
    defs.appendChild(g);
    s.appendChild(defs);
    s.appendChild(svg("path", { d: ruta(INI, INI + BARRIDO - 0.01), fill: "none", "stroke-width": "14", "stroke-linecap": "round", stroke: "currentColor", "stroke-opacity": "0.14" }, "inicio-hab-pista"));
    if (brillo > 0) {
      s.appendChild(svg("path", { d: ruta(INI, grados), fill: "none", "stroke-width": "14", "stroke-linecap": "round", stroke: "url(#inicio-hab-grad)" }, "inicio-hab-relleno"));
      const [px, py] = punto(grados);
      s.appendChild(svg("circle", { cx: px.toFixed(2), cy: py.toFixed(2), r: "5", fill: "#fff" }, "inicio-hab-punto"));
    }
    const centro = el("div", "inicio-hab-centro");
    centro.style.position = "absolute"; centro.style.inset = "0";
    centro.style.display = "flex"; centro.style.flexDirection = "column";
    centro.style.alignItems = "center"; centro.style.justifyContent = "center";
    centro.style.pointerEvents = "none";
    centro.appendChild(el("span", "inicio-hab-estado", { textContent: estado }));
    centro.appendChild(el("span", "inicio-hab-valor", { textContent: `${brillo} %` }));
    centro.appendChild(el("span", "inicio-hab-focos", { textContent: `${h.encendidos} de ${h.total} ${h.total === 1 ? "foco" : "focos"}` }));
    const arco = el("div", "inicio-hab-arco");
    arco.style.position = "relative";
    arco.appendChild(s);
    arco.appendChild(centro);

    // − y +
    const ajuste = el("div", "inicio-hab-ajuste");
    const menos = boton("inicio-hab-menos", "−", "Bajar brillo 10 %", () => cambiarBrillo(h, -PASO));
    const mas = boton("inicio-hab-mas", "+", "Subir brillo 10 %", () => cambiarBrillo(h, PASO));
    ajuste.append(menos, mas);

    // Acciones
    const acciones = el("div", "inicio-hab-acciones");
    acciones.appendChild(accion("energia", encendida ? "Apagar" : "Encender", encendida ? "Apagar la habitación" : "Encender la habitación",
      () => enviar({ habitacion: h.habitacion, encendida: !encendida }), encendida));
    acciones.appendChild(accion("todo", "Todo", "Ir a todas las luces", () => { location.hash = "#luces"; }));
    const noche = ((datos.rutinas) || []).find(r => /noche/i.test(r.nombre || ""));
    if (noche) {
      acciones.appendChild(accion("noche", "Noche", `Ejecutar rutina ${noche.nombre}`, async () => {
        error = "";
        try { await api(`/api/rutinas/${encodeURIComponent(noche.id)}/ejecutar`, { method: "POST", body: {} }); }
        catch (e) { error = e.message || "No se pudo ejecutar"; }
        await window.InicioPanel.recargarLuces();
        dibujar();
      }));
    }
    acciones.appendChild(accion("calida", "Cálida", "Luz cálida", () => enviar({ habitacion: h.habitacion, temperatura: 0 })));

    const nodos = [cabeza, arco, ajuste, acciones];
    const err = el("p", "inicio-hab-error", { textContent: error });
    err.setAttribute("role", "alert");
    err.hidden = !error;
    nodos.splice(3, 0, err);
    RAIZ.replaceChildren(...nodos);
  }

  document.addEventListener("inicio-luces", e => {
    datos = e.detail;
    if (pendiente === null) dibujar();
  });
  document.addEventListener("inicio-elegir-hab", e => { if (typeof e.detail === "string") elegir(e.detail); });
  dibujar();
})();
