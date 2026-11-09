/* Menú vertical del celular: ☰ lo abre; se cierra al elegir sección, tocar fuera, ✕ o Escape.
   En escritorio el menú es la barra horizontal de siempre y este script no hace nada visible. */
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

  // Nombre de la sección actual en la cabecera del celular
  document.addEventListener("pestana", e => {
    const a = nav.querySelector(`.pestana[data-pestana="${e.detail}"] span`);
    if (seccion && a) seccion.textContent = a.textContent;
  });

  ajustarInert();
})();
