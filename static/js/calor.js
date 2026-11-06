(function () {
  "use strict";

  // Nombres largos de días para el formato del tooltip
  const DIA_LARGO = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"];
  const FILAS = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"];
  const COLUMNAS = Array.from({ length: 24 }, (_, i) => String(i));

  let ultimoCalorStr = null;

  // Escuchar actualización de datos del panel
  document.addEventListener("panel", (e) => {
    const calor = e.detail ? e.detail.calor : null;
    const calorStr = JSON.stringify(calor);

    if (calorStr === ultimoCalorStr) {
      return;
    }
    ultimoCalorStr = calorStr;

    const subEl = document.getElementById("calor-sub");
    const mapaEl = document.getElementById("calor-mapa");

    if (subEl) {
      subEl.textContent = calor ? "· últimas " + calor.dias + " días · " + calor.total + " detecciones" : "";
    }

    if (!mapaEl) {
      return;
    }

    const matriz = calor && calor.matriz ? calor.matriz : [];

    if (typeof HChart !== "undefined" && typeof HChart.calor === "function") {
      HChart.calor(mapaEl, matriz, {
        filas: FILAS,
        columnas: COLUMNAS,
        cadaColumna: 3,
        etiqueta: "Detecciones de movimiento por día y hora",
        vacio: "Sin detecciones todavía",
        formato: (v, f, c) => DIA_LARGO[f] + " " + String(c).padStart(2, "0") + ":00 · " + v + (v === 1 ? " detección" : " detecciones")
      });
    }
  });
})();
