/* Pestañas: Resumen, Capturas y los otros proyectos incrustados desde su dirección. */
(function () {
  "use strict";
  const NOMBRES = ["resumen", "capturas", "camaras", "red"];
  let urls = null;  // camaras_url y netwatch_url, vienen de /api/panel

  // Los iframes se cargan solo al abrir su pestaña (el panel de cámaras limita las sesiones abiertas)
  function cargarMarco(nombre) {
    const sec = document.getElementById("pestana-" + nombre);
    const marco = sec && sec.querySelector(".externa-marco");
    if (!marco || !urls) return;
    const url = urls[marco.dataset.url];
    if (url && marco.getAttribute("src") !== url) marco.src = url;
    sec.querySelector(".externa-enlace").href = url || "#";
  }

  function mostrar(nombre) {
    if (!NOMBRES.includes(nombre)) nombre = "resumen";
    NOMBRES.forEach(n => { document.getElementById("pestana-" + n).hidden = n !== nombre; });
    document.querySelectorAll(".pestana").forEach(a => {
      a.classList.toggle("activa", a.dataset.pestana === nombre);
      if (a.dataset.pestana === nombre) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current");
    });
    // al salir de Cámaras se cierra su iframe para liberar la sesión de video
    const camaras = document.querySelector("#pestana-camaras .externa-marco");
    if (nombre !== "camaras" && camaras.getAttribute("src")) camaras.removeAttribute("src");
    cargarMarco(nombre);
    document.dispatchEvent(new CustomEvent("pestana", { detail: nombre }));
  }

  fetch("/api/panel").then(r => r.json()).then(d => {
    urls = { camaras_url: d.camaras_url, netwatch_url: d.netwatch_url };
    cargarMarco(location.hash.slice(1));
  }).catch(() => {});

  window.addEventListener("hashchange", () => mostrar(location.hash.slice(1)));
  mostrar(location.hash.slice(1));
})();
