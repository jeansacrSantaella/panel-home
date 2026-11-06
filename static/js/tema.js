(function () {
  "use strict";

  const html = document.documentElement;
  const btnTema = document.getElementById("btn-tema");
  const metaThemeColor = document.querySelector('meta[name="theme-color"]');
  const mediaDark = window.matchMedia("(prefers-color-scheme: dark)");

  const NOMBRES_TEMA = { auto: "automático", light: "claro", dark: "oscuro" };
  const SIGUIENTE_TEMA = { auto: "light", light: "dark", dark: "auto" };

  // Actualiza el valor del meta theme-color según la propiedad --superficie
  function actualizarThemeColor() {
    if (!metaThemeColor) return;
    const color = getComputedStyle(html).getPropertyValue("--superficie").trim();
    if (color) {
      metaThemeColor.setAttribute("content", color);
    }
  }

  // Aplica la preferencia de tema y actualiza almacenamiento y atributos
  function aplicarTema(pref) {
    pref = SIGUIENTE_TEMA[pref] ? pref : "auto";
    html.dataset.temaPref = pref;

    if (pref === "auto") {
      delete html.dataset.theme;
    } else {
      html.dataset.theme = pref;
    }

    try {
      if (pref === "auto") {
        localStorage.removeItem("tema");
      } else {
        localStorage.setItem("tema", pref);
      }
    } catch (e) {
      // Manejo de restricciones de almacenamiento local
    }

    if (btnTema) {
      const nombre = NOMBRES_TEMA[pref];
      btnTema.setAttribute("aria-label", `Tema: ${nombre}`);
      btnTema.setAttribute("title", `Tema: ${nombre} (clic para cambiar)`);
    }

    actualizarThemeColor();
  }

  // Listener para actualizar el color de tema si cambia la preferencia del sistema en modo "auto"
  mediaDark.addEventListener("change", function () {
    if (html.dataset.temaPref === "auto") {
      actualizarThemeColor();
    }
  });

  if (btnTema) {
    btnTema.addEventListener("click", function () {
      const actual = html.dataset.temaPref || "auto";
      aplicarTema(SIGUIENTE_TEMA[actual] || "auto");
    });
  }

  // Aplicar preferencia inicial al cargar
  aplicarTema(html.dataset.temaPref || "auto");

  // Medición de la cabecera y pestañas
  const cabecera = document.querySelector(".cabecera");
  const pestanas = document.querySelector(".pestanas");

  function actualizarMedidas() {
    if (cabecera) {
      const altoC = Math.round(cabecera.getBoundingClientRect().height);
      html.style.setProperty("--alto-cabecera", altoC + "px");
    }
    if (pestanas) {
      const altoN = Math.round(pestanas.getBoundingClientRect().height);
      html.style.setProperty("--alto-nav", altoN + "px");
    }
  }

  if (typeof ResizeObserver !== "undefined") {
    const observer = new ResizeObserver(actualizarMedidas);
    if (cabecera) observer.observe(cabecera);
    if (pestanas) observer.observe(pestanas);
  } else {
    window.addEventListener("resize", actualizarMedidas);
  }

  actualizarMedidas();
})();
