/* Clases CSS usadas:
   - inicio-tarjeta-camara: contenedor principal de la tarjeta de cámaras.
   - inicio-camara-cuerpo: contenedor en rejilla que separa el visor y la lista.
   - inicio-camara-visor: área donde se muestra el iframe de la cámara activa.
   - inicio-camara-iframe: elemento iframe para el streaming en vivo de go2rtc.
   - inicio-camara-info: barra inferior superpuesta al video con datos de estado.
   - inicio-camara-titulo: nombre de la cámara actual.
   - inicio-camara-estado: indicador y texto descriptivo del estado actual.
   - inicio-camara-latencia: indicador de latencia en milisegundos.
   - inicio-camara-boton-fs: botón para activar pantalla completa en el visor.
   - inicio-camara-lista: columna lateral con la lista de botones de cámaras.
   - inicio-camara-item: botón individual para seleccionar una cámara.
   - inicio-camara-punto: punto de estado (ok / sin_video / sin_red).
   - inicio-camara-vacio: mensaje cuando no hay cámaras disponibles.
*/
(function () {
  "use strict";

  const STORAGE_KEY = "inicio_camara_activa";
  let contenedor = null;
  let camaraActualId = null;
  let datosPanel = null;
  let pestañaVisible = true;
  let visorEl = null;
  let listaEl = null;
  let iframeEl = null;  // contenedor del reproductor
  let repro = null, reproId = null;
  let infoEl = null;

  function obtenerCamaraActivaGuardada(camaras) {
    if (!camaras || camaras.length === 0) return null;
    try {
      const guardada = localStorage.getItem(STORAGE_KEY);
      if (guardada && camaras.some(c => c.id === guardada)) {
        return guardada;
      }
    } catch (_) {
      // localStorage inaccesible
    }
    return camaras[0].id;
  }

  function guardarCamaraActiva(id) {
    try {
      localStorage.setItem(STORAGE_KEY, id);
    } catch (_) {
      // localStorage inaccesible
    }
  }

  function renderizar(panel) {
    if (!contenedor) return;
    datosPanel = panel;
    const camaras = (panel && panel.camaras) || [];

    if (camaras.length === 0) {
      contenedor.innerHTML = "";
      const vacio = InicioPanel.el("div", "inicio-camara-vacio", {
        textContent: "No hay cámaras"
      });
      contenedor.appendChild(vacio);
      camaraActualId = null;
      return;
    }

    if (!camaraActualId || !camaras.some(c => c.id === camaraActualId)) {
      camaraActualId = obtenerCamaraActivaGuardada(camaras);
    }

    const camaraActiva = camaras.find(c => c.id === camaraActualId) || camaras[0];
    camaraActualId = camaraActiva.id;
    guardarCamaraActiva(camaraActualId);

    // Si la estructura base no existe, la creamos
    if (!visorEl || !listaEl || !contenedor.contains(visorEl)) {
      contenedor.innerHTML = "";
      const cuerpo = InicioPanel.el("div", "inicio-camara-cuerpo");
      
      visorEl = InicioPanel.el("div", "inicio-camara-visor");
      iframeEl = InicioPanel.el("div", "inicio-camara-iframe");
      repro = null; reproId = null;
      
      infoEl = InicioPanel.el("div", "inicio-camara-info");
      const infoIzq = InicioPanel.el("div", "inicio-camara-detalles");
      const tituloEl = InicioPanel.el("span", "inicio-camara-titulo");
      const estadoEl = InicioPanel.el("span", "inicio-camara-estado");
      const latenciaEl = InicioPanel.el("span", "inicio-camara-latencia");
      
      infoIzq.append(tituloEl, estadoEl, latenciaEl);

      const botonFs = InicioPanel.el("button", "inicio-camara-boton-fs", {
        type: "button",
        innerHTML: '<svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true" focusable="false"><path fill="currentColor" d="M7 14H5v5h5v-2H7v-3zm-2-4h2V7h3V5H5v5zm12 7h-3v2h5v-5h-2v3zM14 5v2h3v3h2V5h-5z"/></svg>',
        "aria-label": "Pantalla completa"
      });
      botonFs.addEventListener("click", () => {
        if (visorEl.requestFullscreen) {
          visorEl.requestFullscreen();
        } else if (visorEl.webkitRequestFullscreen) {
          visorEl.webkitRequestFullscreen();
        }
      });

      infoEl.append(infoIzq, botonFs);
      visorEl.append(iframeEl, infoEl);

      listaEl = InicioPanel.el("div", "inicio-camara-lista");
      cuerpo.append(visorEl, listaEl);
      contenedor.appendChild(cuerpo);
    }

    // El video solo corre con la pestaña visible y se recrea solo si cambia la cámara
    if (pestañaVisible) {
      if (!repro || reproId !== camaraActualId) {
        if (repro) repro.destruir();
        repro = Reproductor.crear(iframeEl, camaraActiva);
        reproId = camaraActualId;
      }
    } else if (repro) {
      repro.destruir();
      repro = null; reproId = null;
    }

    // Actualizar información inferior
    const tituloEl = infoEl.querySelector(".inicio-camara-titulo");
    const estadoEl = infoEl.querySelector(".inicio-camara-estado");
    const latenciaEl = infoEl.querySelector(".inicio-camara-latencia");

    if (tituloEl) tituloEl.textContent = camaraActiva.nombre || camaraActualId;
    
    if (estadoEl) {
      let textoEstado = "En vivo";
      let claseEstado = "ok";
      if (camaraActiva.estado === "sin_video") {
        textoEstado = "Sin video";
        claseEstado = "alerta";
      } else if (camaraActiva.estado === "sin_red") {
        textoEstado = "Sin red";
        claseEstado = "mal";
      }
      estadoEl.textContent = textoEstado;
      estadoEl.className = `inicio-camara-estado punto`;
      estadoEl.setAttribute("data-estado", claseEstado);
    }

    if (latenciaEl) {
      latenciaEl.textContent = camaraActiva.latencia_ms !== undefined ? `${camaraActiva.latencia_ms} ms` : "";
    }

    // Renderizar lista lateral de botones
    listaEl.innerHTML = "";
    camaras.forEach(c => {
      const btn = InicioPanel.el("button", "inicio-camara-item", {
        type: "button"
      });
      btn.setAttribute("aria-pressed", c.id === camaraActualId ? "true" : "false");

      const punto = InicioPanel.el("span", "punto");
      let estadoPunto = "ok";
      if (c.estado === "sin_video") estadoPunto = "alerta";
      if (c.estado === "sin_red") estadoPunto = "mal";
      punto.setAttribute("data-estado", estadoPunto);

      const nombreSpan = InicioPanel.el("span", null, { textContent: c.nombre || c.id });
      btn.append(punto, nombreSpan);

      btn.addEventListener("click", () => {
        if (camaraActualId !== c.id) {
          camaraActualId = c.id;
          guardarCamaraActiva(camaraActualId);
          renderizar(datosPanel);
        }
      });

      listaEl.appendChild(btn);
    });
  }

  document.addEventListener("DOMContentLoaded", () => {
    contenedor = document.getElementById("inicio-camara");
    if (!contenedor) return;
    contenedor.classList.add("inicio-tarjeta-camara");

    const ultimoPanel = InicioPanel.ultimo().panel;
    if (ultimoPanel) {
      renderizar(ultimoPanel);
    }
  });

  document.addEventListener("panel", e => {
    renderizar(e.detail);
  });

  document.addEventListener("pestana", e => {
    pestañaVisible = (e.detail === "inicio");
    if (datosPanel) {
      renderizar(datosPanel);
    }
  });
})();
