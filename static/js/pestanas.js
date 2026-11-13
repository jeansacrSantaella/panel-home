/* Pestañas del panel (cada una se muestra u oculta; los scripts reaccionan al evento "pestana"). */
(function () {
  "use strict";
  const NOMBRES = ["inicio", "resumen", "luces", "capturas", "camaras", "red"];

  function mostrar(nombre) {
    if (!NOMBRES.includes(nombre)) nombre = "inicio";  // la portada es Inicio
    NOMBRES.forEach(n => { document.getElementById("pestana-" + n).hidden = n !== nombre; });
    document.querySelectorAll(".pestana").forEach(a => {
      a.classList.toggle("activa", a.dataset.pestana === nombre);
      if (a.dataset.pestana === nombre) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current");
    });
    document.dispatchEvent(new CustomEvent("pestana", { detail: nombre }));
  }

  window.addEventListener("hashchange", () => mostrar(location.hash.slice(1)));
  mostrar(location.hash.slice(1));
})();
