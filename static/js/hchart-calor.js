(function(global) {
  "use strict";

  // Inyecta las reglas CSS necesarias para el mapa de calor en document.head
  function inyectarCSS() {
    if (document.getElementById("hc-calor-css")) return;
    const style = document.createElement("style");
    style.id = "hc-calor-css";
    style.textContent = [
      ".hc-calor { display: grid; gap: 2px; }",
      ".hc-calor-celda { aspect-ratio: 1; min-height: 10px; border-radius: 2px; }",
      ".hc-calor-fila { font-size: 11px; color: var(--hc-tenue); padding-right: 6px; align-self: center; }",
      ".hc-calor-col { font-size: 10px; color: var(--hc-tenue); text-align: left; }",
      ".hc-calor-leyenda { display: flex; align-items: center; gap: 4px; justify-content: flex-end; margin-top: 6px; font-size: 11px; color: var(--hc-tenue); }",
      ".hc-calor-leyenda-cuadro { width: 10px; height: 10px; border-radius: 2px; }"
    ].join("\n");
    document.head.appendChild(style);
  }

  // Dibuja un mapa de calor usando elementos HTML y CSS Grid
  function calor(cont, matriz, opciones) {
    if (!cont) return;
    opciones = opciones || {};
    inyectarCSS();

    cont.textContent = "";
    cont.classList.add("hc");
    cont.setAttribute("role", "img");
    cont.setAttribute("aria-label", opciones.etiqueta || "Mapa de calor");

    const filas = opciones.filas || [];
    const columnas = opciones.columnas || [];
    const cadaCol = opciones.cadaColumna !== undefined ? opciones.cadaColumna : 3;
    const color = opciones.color || "var(--hc-acento)";
    const formato = opciones.formato || function(v) { return String(v); };
    const txtVacio = opciones.vacio || "Sin datos";

    const numFilas = Array.isArray(matriz) ? matriz.length : 0;
    const numCols = numFilas > 0 && Array.isArray(matriz[0]) ? matriz[0].length : 0;

    let max = 0;
    for (let r = 0; r < numFilas; r++) {
      for (let c = 0; c < numCols; c++) {
        const val = Number(matriz[r][c]) || 0;
        if (val > max) max = val;
      }
    }

    // Si la matriz no tiene datos o el máximo es 0, renderiza el mensaje de vacío
    if (numFilas === 0 || numCols === 0 || max === 0) {
      const msg = document.createElement("div");
      msg.className = "hc-vacio-msg";
      msg.textContent = txtVacio;
      cont.appendChild(msg);
      return;
    }

    // Contenedor Grid principal
    const grid = document.createElement("div");
    grid.className = "hc-calor";
    grid.style.gridTemplateColumns = "auto repeat(" + numCols + ", minmax(0, 1fr))";

    // Generar filas de datos y sus celdas
    for (let r = 0; r < numFilas; r++) {
      const etiqFila = document.createElement("div");
      etiqFila.className = "hc-calor-fila";
      etiqFila.textContent = filas[r] || "";
      grid.appendChild(etiqFila);

      for (let c = 0; c < numCols; c++) {
        const celda = document.createElement("div");
        celda.className = "hc-calor-celda";
        const val = Number(matriz[r][c]) || 0;

        if (val > 0) {
          celda.style.backgroundColor = color;
          celda.style.opacity = String(0.15 + 0.85 * (val / max));
        } else {
          celda.style.backgroundColor = "var(--hc-vacio)";
        }

        celda.title = formato(val, r, c);
        grid.appendChild(celda);
      }
    }

    // Fila inferior con las etiquetas de columnas
    const esquinaVacia = document.createElement("div");
    grid.appendChild(esquinaVacia);

    for (let c = 0; c < numCols; c++) {
      const etiqCol = document.createElement("div");
      etiqCol.className = "hc-calor-col";
      if (c % cadaCol === 0) {
        etiqCol.textContent = columnas[c] !== undefined ? columnas[c] : "";
      }
      grid.appendChild(etiqCol);
    }

    cont.appendChild(grid);

    // Leyenda de niveles de opacidad
    const leyenda = document.createElement("div");
    leyenda.className = "hc-calor-leyenda";

    const lblMenos = document.createElement("span");
    lblMenos.textContent = "menos";
    leyenda.appendChild(lblMenos);

    const opacidades = [0.15, 0.36, 0.58, 0.79, 1];
    for (let i = 0; i < opacidades.length; i++) {
      const cuadro = document.createElement("div");
      cuadro.className = "hc-calor-leyenda-cuadro";
      cuadro.style.backgroundColor = color;
      cuadro.style.opacity = String(opacidades[i]);
      leyenda.appendChild(cuadro);
    }

    const lblMas = document.createElement("span");
    lblMas.textContent = "más";
    leyenda.appendChild(lblMas);

    cont.appendChild(leyenda);
  }

  // Asignar función al objeto HChart global
  global.HChart = global.HChart || {};
  global.HChart.calor = calor;
})(typeof window !== "undefined" ? window : this);
