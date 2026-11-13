/* Reloj para la pestaña Inicio.
   Clases usadas:
   - #inicio-reloj: contenedor principal
   - .inicio-hora: hora grande (HH:MM)
   - .inicio-seg: segundos pequeños
   - .inicio-fecha: fecha larga en español
   - .inicio-saludo: texto de saludo según la hora
*/
(function () {
  "use strict";

  const DIAS = ["domingo", "lunes", "martes", "miércoles", "jueves", "viernes", "sábado"];
  const MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"];

  let contenedor = null;
  let timerReloj = null;
  let visible = false;

  function obtenerSaludo(hora) {
    if (hora >= 6 && hora < 12) return "Buenos días";
    if (hora >= 12 && hora < 20) return "Buenas tardes";
    return "Buenas noches";
  }

  function actualizar() {
    if (!contenedor || !visible) return;
    const ahora = new Date();
    const h = ahora.getHours();
    const m = ahora.getMinutes();
    const s = ahora.getSeconds();

    const hhStr = String(h).padStart(2, "0");
    const mmStr = String(m).padStart(2, "0");
    const ssStr = String(s).padStart(2, "0");

    const diaSemana = DIAS[ahora.getDay()];
    const diaNum = ahora.getDate();
    const mesStr = MESES[ahora.getMonth()];
    const fechaTexto = `${diaSemana} ${diaNum} de ${mesStr}`;

    const saludoTexto = obtenerSaludo(h);
    const isoTime = `${hhStr}:${mmStr}:${ssStr}`;

    let timeEl = contenedor.querySelector("time");
    if (!timeEl) {
      contenedor.innerHTML = "";
      timeEl = InicioPanel.el("time", "", { ariaLive: "off" });
      
      const horaWrap = InicioPanel.el("div", "inicio-hora-wrap");
      const horaEl = InicioPanel.el("span", "inicio-hora");
      const segEl = InicioPanel.el("span", "inicio-seg");
      horaWrap.appendChild(horaEl);
      horaWrap.appendChild(segEl);

      const fechaEl = InicioPanel.el("div", "inicio-fecha");
      const saludoEl = InicioPanel.el("div", "inicio-saludo");

      timeEl.appendChild(horaWrap);
      timeEl.appendChild(fechaEl);
      timeEl.appendChild(saludoEl);
      contenedor.appendChild(timeEl);
    }

    timeEl.setAttribute("datetime", ahora.toISOString());
    timeEl.querySelector(".inicio-hora").textContent = `${hhStr}:${mmStr}`;
    timeEl.querySelector(".inicio-seg").textContent = ssStr;
    timeEl.querySelector(".inicio-fecha").textContent = fechaTexto;
    timeEl.querySelector(".inicio-saludo").textContent = saludoTexto;
  }

  function iniciar() {
    contenedor = document.getElementById("inicio-reloj");
    if (!contenedor) return;

    actualizar();
    if (timerReloj) clearInterval(timerReloj);
    timerReloj = setInterval(actualizar, 1000);
  }

  function detener() {
    if (timerReloj) {
      clearInterval(timerReloj);
      timerReloj = null;
    }
  }

  document.addEventListener("pestana", e => {
    visible = (e.detail === "inicio");
    if (visible) {
      iniciar();
    } else {
      detener();
    }
  });

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => {
      contenedor = document.getElementById("inicio-reloj");
    });
  } else {
    contenedor = document.getElementById("inicio-reloj");
  }
})();
