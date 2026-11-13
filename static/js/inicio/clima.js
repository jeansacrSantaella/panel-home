/* Clima en la pestaña Inicio: temperatura actual, descripción, máximas/mínimas,
   sensación, humedad, ciudad, tiempo desde la última actualización y fila de 4 días.
   Clases usadas:
   - .inicio-clima: contenedor de la tarjeta
   - .inicio-clima-arriba: fila superior con ícono grande y temperatura
   - .inicio-clima-temp: número grande de temperatura
   - .inicio-clima-desc: descripción y métricas en tenue
   - .inicio-clima-pie: ciudad y aviso de actualización o error
   - .inicio-clima-dias: fila de días futuros
   - .inicio-clima-dia: contenedor individual de cada día
   - .inicio-clima-aviso: mensaje pequeño para errores o configuración
*/
(function () {
  "use strict";

  function redondear(val) {
    if (val === null || val === undefined || isNaN(val)) return "—";
    return Math.round(val);
  }

  function renderizar(contenedor, datos) {
    contenedor.innerHTML = "";

    if (!datos) {
      contenedor.appendChild(
        InicioPanel.el("div", "inicio-clima-aviso", { textContent: "Cargando clima…" })
      );
      return;
    }

    if (datos.configurado === false) {
      const msg = document.createElement("div");
      msg.className = "inicio-clima-aviso";
      msg.innerHTML = 'No pude ubicar la casa para el clima: permite la ubicación del navegador o pon <code>CLIMA_CIUDAD</code> en el <code>.env</code>';
      contenedor.appendChild(msg);
      return;
    }

    const actual = datos.actual || {};
    const hoy = datos.hoy || {};
    const dias = datos.dias || [];

    // Fila superior: ícono grande + temperatura grande
    const arriba = InicioPanel.el("div", "inicio-clima-arriba");
    const iconoCont = InicioPanel.el("div");
    iconoCont.innerHTML = InicioPanel.iconoClima(actual.icono, actual.es_dia);
    arriba.appendChild(iconoCont);

    const tempSpan = InicioPanel.el("span", "inicio-clima-temp", {
      textContent: `${redondear(actual.temp)}°`,
    });
    arriba.appendChild(tempSpan);
    contenedor.appendChild(arriba);

    // Descripción y métricas (hoy, sensación, humedad)
    const descCont = InicioPanel.el("div", "inicio-clima-desc");
    const textoDesc = actual.descripcion ? `${actual.descripcion}. ` : "";
    const textoMaxMin = `MÁX ${redondear(hoy.max)}° MÍN ${redondear(hoy.min)}°`;
    const parrafo1 = InicioPanel.el("div", "", { textContent: textoDesc + textoMaxMin });
    descCont.appendChild(parrafo1);

    const textoDetalle = `Sensación ${redondear(actual.sensacion)}° · Humedad ${redondear(actual.humedad)} %`;
    const parrafo2 = InicioPanel.el("div", "tenue", { textContent: textoDetalle });
    descCont.appendChild(parrafo2);
    contenedor.appendChild(descCont);

    // Fila de 4 días
    if (dias.length > 0) {
      const diasCont = InicioPanel.el("div", "inicio-clima-dias");
      dias.slice(0, 4).forEach(d => {
        const diaItem = InicioPanel.el("div", "inicio-clima-dia");
        
        const nombreDia = InicioPanel.el("span", "", { textContent: d.dia || "" });
        diaItem.appendChild(nombreDia);

        const iconoDia = InicioPanel.el("div");
        iconoDia.innerHTML = InicioPanel.iconoClima(d.icono, true);
        diaItem.appendChild(iconoDia);

        const tempDia = InicioPanel.el("span", "tenue", {
          textContent: `${redondear(d.max)}° / ${redondear(d.min)}°`,
        });
        diaItem.appendChild(tempDia);

        diasCont.appendChild(diaItem);
      });
      contenedor.appendChild(diasCont);
    }

    // Pie: ciudad y tiempo actualizado / error
    const pie = InicioPanel.el("div", "inicio-clima-pie tenue");
    const partes = [];
    if (datos.ciudad) partes.push(datos.ciudad);
    partes.push(`actualizado ${InicioPanel.hace(datos.actualizado)}`);
    pie.textContent = partes.join(" · ");
    contenedor.appendChild(pie);

    // Si hay datos viejos pero un error reciente
    if (datos.error) {
      const aviso = InicioPanel.el("div", "inicio-clima-aviso tenue", {
        textContent: `sin actualizar: ${datos.error}`,
      });
      contenedor.appendChild(aviso);
    }
  }

  function inicializar() {
    const contenedor = document.getElementById("inicio-clima");
    if (!contenedor) return;

    const u = InicioPanel.ultimo();
    if (u && u.clima) {
      renderizar(contenedor, u.clima);
    } else {
      renderizar(contenedor, null);
    }

    document.addEventListener("inicio-clima", e => {
      renderizar(contenedor, e.detail);
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", inicializar);
  } else {
    inicializar();
  }
})();
