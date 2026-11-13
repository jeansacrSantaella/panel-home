/* Navegación del tablero. Celular: ☰ abre el menú deslizante (se cierra al elegir sección, tocar fuera, ✕ o Escape).
   Escritorio (≥1024 px): ☰ contrae la lateral a solo íconos. También: ruta, buscador global y lista de servicios. */
(function () {
  "use strict";
  const html = document.documentElement;
  const nav = document.getElementById("menu-principal");
  const abrirBtn = document.getElementById("btn-menu");
  const cerrarBtn = document.getElementById("btn-menu-cerrar");
  const fondo = document.getElementById("menu-fondo");
  const seccion = document.getElementById("seccion-actual");
  if (!nav || !abrirBtn) return;
  const movil = window.matchMedia("(max-width: 759.98px)");

  // Cerrado en el celular, el menú queda fuera de la pantalla: que no reciba foco ni lo lea el lector de pantalla
  function ajustarInert() {
    nav.inert = movil.matches && !html.classList.contains("menu-abierto");
  }

  function abrir() {
    html.classList.add("menu-abierto");
    fondo.hidden = false;
    abrirBtn.setAttribute("aria-expanded", "true");
    ajustarInert();
    const activa = nav.querySelector(".pestana.activa") || nav.querySelector(".pestana");
    if (activa) activa.focus();
  }

  function cerrar(devolverFoco) {
    if (!html.classList.contains("menu-abierto")) return;
    html.classList.remove("menu-abierto");
    abrirBtn.setAttribute("aria-expanded", "false");
    setTimeout(() => { if (!html.classList.contains("menu-abierto")) fondo.hidden = true; }, 260);
    ajustarInert();
    if (devolverFoco) abrirBtn.focus();
  }

  abrirBtn.addEventListener("click", () => (html.classList.contains("menu-abierto") ? cerrar(true) : abrir()));
  if (cerrarBtn) cerrarBtn.addEventListener("click", () => cerrar(true));
  fondo.addEventListener("click", () => cerrar(true));
  nav.addEventListener("click", e => { if (e.target.closest(".pestana")) cerrar(false); });
  document.addEventListener("keydown", e => { if (e.key === "Escape") cerrar(true); });
  movil.addEventListener("change", () => { if (!movil.matches) cerrar(false); ajustarInert(); });

  // Escritorio: ☰ contrae/expande la lateral (recordado; try/catch por si el almacenamiento está bloqueado)
  const ancho = window.matchMedia("(min-width: 1024px)");
  try { if (localStorage.getItem("lateral-mini") === "1") html.classList.add("lateral-mini"); } catch (e) { /* sin almacenamiento */ }
  abrirBtn.addEventListener("click", () => {
    if (!ancho.matches) return;
    const mini = html.classList.toggle("lateral-mini");
    try { localStorage.setItem("lateral-mini", mini ? "1" : "0"); } catch (e) { /* sin almacenamiento */ }
  });

  // Nombre de la sección actual: cabecera del celular y ruta "PANEL / SECCIÓN"
  const ruta = document.getElementById("ruta");
  document.addEventListener("pestana", e => {
    const a = nav.querySelector(`.pestana[data-pestana="${e.detail}"] span`);
    if (!a) return;
    if (seccion) seccion.textContent = a.textContent;
    if (ruta) {
      const b = ruta.querySelector("b");
      if (b) b.textContent = a.textContent;
    }
  });

  // Buscador global: Enter abre Red y avisa a la tabla de equipos
  const form = document.getElementById("buscar-global");
  if (form) {
    form.addEventListener("submit", e => {
      e.preventDefault();
      const texto = (form.querySelector("input").value || "").trim();
      if (location.hash !== "#red") location.hash = "#red";
      document.dispatchEvent(new CustomEvent("buscar-red", { detail: texto }));
    });
  }

  // Servicios (grupo inferior de la lateral): un punto de estado por servicio, con los datos de /api/panel
  const lista = document.querySelector("#lateral-servicios ul");
  function estadoCamaras(cams) {
    if (!Array.isArray(cams) || !cams.length) return "nada";
    const ok = cams.filter(c => c.estado === "ok").length;
    return ok === cams.length ? "ok" : ok ? "alerta" : "mal";
  }
  function pintarServicios(d) {
    if (!lista || !d) return;
    const servicios = [
      ["Red", d.red !== null && d.red !== undefined ? "ok" : "nada", "#red"],
      ["Cámaras", estadoCamaras(d.camaras), "#camaras"],
      ["go2rtc", d.go2rtc_ok === true ? "ok" : d.go2rtc_ok === false ? "mal" : "nada", null],
      ["Servidor", d.sistema ? "ok" : "nada", "#resumen"],
    ];
    lista.textContent = "";
    for (const [nombre, estado, destino] of servicios) {
      const li = document.createElement("li");
      const el = document.createElement(destino ? "a" : "span");
      if (destino) el.href = destino;
      el.className = "servicio";
      el.title = nombre;
      const punto = document.createElement("span");
      punto.className = "punto " + estado;
      punto.dataset.estado = estado;
      punto.setAttribute("aria-hidden", "true");
      const txt = document.createElement("span");
      txt.className = "servicio-nombre";
      txt.textContent = nombre;
      el.append(punto, txt);
      li.append(el);
      lista.append(li);
    }
  }
  document.addEventListener("panel", e => pintarServicios(e.detail));

  // Nombre como title: en la lateral de solo íconos es la única pista visible
  nav.querySelectorAll(".pestana").forEach(a => { const t = a.querySelector("span"); if (t) a.title = t.textContent; });

  ajustarInert();
})();
