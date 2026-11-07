(function () {
  "use strict";

  // Ayudante global de estado de carga
  window.OrionCarga = {
    en: function (cont, texto) {
      if (!cont) return;
      cont.textContent = "";
      var div = document.createElement("div");
      div.className = "carga-orion";
      div.setAttribute("role", "status");

      ["6px", "0px", "-6px"].forEach(function (y) {
        var i = document.createElement("i");
        i.style.setProperty("--y", y);
        div.appendChild(i);
      });

      var span = document.createElement("span");
      span.textContent = texto || "Cargando…";
      div.appendChild(span);

      cont.appendChild(div);
      return div;
    }
  };

  // Control de pantalla de inicio (splash)
  // Tarjetas del Resumen: muestran tres estrellas de las Pléyades hasta que llegan los primeros datos
  document.addEventListener("panel", function () {
    var resumen = document.getElementById("pestana-resumen");
    if (resumen) resumen.classList.remove("esperando");
  }, { once: true });

  var splash = document.getElementById("splash");
  if (!splash) return;

  document.body.classList.add("iniciando");

  var visto = false;
  try {
    visto = !!sessionStorage.getItem("orion-visto");
    if (visto) splash.classList.add("splash-rapido");
    sessionStorage.setItem("orion-visto", "1");
  } catch (e) {}

  var movReducido = matchMedia("(prefers-reduced-motion: reduce)").matches;
  var minTiempo = (visto || movReducido) ? 300 : 2600;
  var tInicio = Date.now();
  var datosListos = false;
  var salio = false;

  function salir() {
    if (salio) return;
    salio = true;
    window.removeEventListener("keydown", salir);
    splash.classList.add("splash-salir");
    document.body.classList.remove("iniciando");
    setTimeout(function () {
      splash.remove();
    }, 700);
  }

  function intentarSalir() {
    if (!datosListos) return;
    var faltante = minTiempo - (Date.now() - tInicio);
    if (faltante <= 0) {
      salir();
    } else {
      setTimeout(salir, faltante);
    }
  }

  document.addEventListener("panel", function () {
    datosListos = true;
    intentarSalir();
  }, { once: true });

  splash.addEventListener("click", salir);
  window.addEventListener("keydown", salir);

  setTimeout(salir, 9000);

  var estado = document.getElementById("splash-estado");
  if (estado) {
    setTimeout(function () {
      if (!datosListos && !salio) estado.textContent = "Leyendo NetWatch y las cámaras…";
    }, 2500);
    setTimeout(function () {
      if (!datosListos && !salio) estado.textContent = "La casa tarda en responder…";
    }, 6000);
  }
})();
