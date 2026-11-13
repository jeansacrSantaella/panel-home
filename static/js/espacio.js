(function () {
  "use strict";

  // Elementos DOM del panel de espacio
  var avisoEl = document.getElementById("espacio-aviso");
  var kpisEl = document.getElementById("espacio-kpis");
  var usoEl = document.getElementById("espacio-uso");
  var ultimoTs = null;

  // Auxiliar para vaciar un nodo sin usar innerHTML
  function limpiar(el) {
    if (el) {
      el.textContent = "";
    }
  }

  document.addEventListener("panel", function (e) {
    var d = e && e.detail;
    var espacio = d ? d.espacio : null;

    if (!espacio) {
      if (avisoEl) {
        avisoEl.textContent =
          "No pude leer el espacio de gestorCamaras: ¿ya está desplegada la versión con /api/espacio?";
        avisoEl.hidden = false;
      }
      limpiar(kpisEl);
      limpiar(usoEl);
      ultimoTs = null;
      return;
    }

    if (avisoEl) {
      avisoEl.hidden = true;
    }

    // Evita repintar si el timestamp no ha cambiado
    if (espacio.ts && espacio.ts === ultimoTs) {
      return;
    }
    ultimoTs = espacio.ts;

    limpiar(kpisEl);
    limpiar(usoEl);

    var total = espacio.total || 0;
    var usado = espacio.usado || 0;
    var libre = espacio.libre || 0;
    var pctLibre = total > 0 ? Math.round((libre / total) * 100) : 0;

    var fotos = espacio.fotos || { bytes: 0, archivos: 0 };
    var clips = espacio.clips || { bytes: 0, archivos: 0 };
    var otrosBytes = Math.max(0, usado - (fotos.bytes || 0) - (clips.bytes || 0));

    // Anillo de % libre
    if (kpisEl) {
      HChart.anillo(kpisEl, {
        valor: total > 0 ? pctLibre : null,
        etiqueta: HChart.formatoBytes(libre) + " libres de " + HChart.formatoBytes(total),
        tamano: 130
      });
    }

    // Fotos, clips y otros sobre el total del disco
    if (usoEl) {
      var pct = function (n) { return total > 0 ? (n / total) * 100 : 0; };
      HChart.progreso(usoEl, [
        { etiqueta: "Fotos", valor: pct(fotos.bytes || 0), texto: HChart.formatoBytes(fotos.bytes || 0) + " · " + (fotos.archivos || 0) + " fotos" },
        { etiqueta: "Clips", valor: pct(clips.bytes || 0), texto: HChart.formatoBytes(clips.bytes || 0) + " · " + (clips.archivos || 0) + " clips" },
        { etiqueta: "Otros archivos", valor: pct(otrosBytes), texto: HChart.formatoBytes(otrosBytes) }
      ]);
    }
  });
})();
