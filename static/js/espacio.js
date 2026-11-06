(function () {
  "use strict";

  // Elementos DOM del panel de espacio
  var avisoEl = document.getElementById("espacio-aviso");
  var kpisEl = document.getElementById("espacio-kpis");
  var donaEl = document.getElementById("espacio-dona");
  var usoEl = document.getElementById("espacio-uso");
  var ultimoTs = null;

  // Auxiliar para vaciar un nodo sin usar innerHTML
  function limpiar(el) {
    if (el) {
      el.textContent = "";
    }
  }

  // Crea un elemento div.kpi con b y span mediante createElement
  function crearKpi(valor, etiqueta, colorB) {
    var div = document.createElement("div");
    div.className = "kpi";

    var b = document.createElement("b");
    b.textContent = valor;
    if (colorB) {
      b.style.color = colorB;
    }

    var span = document.createElement("span");
    span.textContent = etiqueta;

    div.appendChild(b);
    div.appendChild(span);
    return div;
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
      limpiar(donaEl);
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
    limpiar(donaEl);
    limpiar(usoEl);

    var total = espacio.total || 0;
    var usado = espacio.usado || 0;
    var libre = espacio.libre || 0;
    var pctLibre = total > 0 ? Math.round((libre / total) * 100) : 0;

    var colorEstado = null;
    if (pctLibre < 10) {
      colorEstado = "var(--mal)";
    } else if (pctLibre < 20) {
      colorEstado = "var(--alerta)";
    }

    var fotos = espacio.fotos || { bytes: 0, archivos: 0 };
    var clips = espacio.clips || { bytes: 0, archivos: 0 };
    var otrosBytes = Math.max(0, usado - (fotos.bytes || 0) - (clips.bytes || 0));

    // Renderizar KPIs
    if (kpisEl) {
      var lblLibre = "libre de " + HChart.formatoBytes(total) + " (" + pctLibre + "%)";
      kpisEl.appendChild(crearKpi(HChart.formatoBytes(libre), lblLibre, colorEstado));
      kpisEl.appendChild(crearKpi(HChart.formatoBytes(fotos.bytes || 0), (fotos.archivos || 0) + " fotos"));
      kpisEl.appendChild(crearKpi(HChart.formatoBytes(clips.bytes || 0), (clips.archivos || 0) + " clips"));
    }

    // Renderizar gráfico de dona
    if (donaEl) {
      HChart.dona(
        donaEl,
        [
          { etiqueta: "Fotos", valor: fotos.bytes || 0, color: "var(--acento)" },
          { etiqueta: "Clips", valor: clips.bytes || 0, color: "var(--info)" },
          { etiqueta: "Otros archivos", valor: otrosBytes, color: "var(--tenue)" },
          { etiqueta: "Libre", valor: libre, color: "var(--ok)" }
        ],
        { centro: pctLibre + "% libre", etiqueta: "Uso del disco" }
      );
    }

    // Renderizar barra de uso de disco
    if (usoEl) {
      var colorUso = colorEstado || "var(--acento)";
      var textoUso = HChart.formatoBytes(usado) + " de " + HChart.formatoBytes(total);
      HChart.barras(
        usoEl,
        [{ etiqueta: "Disco usado", valor: usado, texto: textoUso, color: colorUso }],
        { max: total, etiqueta: "Disco usado" }
      );
    }
  });
})();
