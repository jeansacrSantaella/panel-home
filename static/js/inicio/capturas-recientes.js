/* Carrusel de capturas de la última hora en la pestaña Inicio.
   Clases CSS: inicio-car-contenedor, inicio-car-slide, inicio-car-img, inicio-car-pie,
   inicio-car-chip, inicio-car-hace, inicio-car-clases, inicio-car-btn, inicio-car-tira,
   inicio-car-punto, inicio-car-vacio, inicio-car-enlace, inicio-car-error. */
(function () {
  "use strict";

  const CADA_CAPTURA = 60000;
  let timer = null;
  let autoplayTimer = null;
  let indiceActual = 0;
  let capturasUltimaHora = [];
  let pausado = false;
  let fechaActual = "";

  function obtenerFechaLocal() {
    const d = new Date();
    const anio = d.getFullYear();
    const mes = String(d.getMonth() + 1).padStart(2, "0");
    const dia = String(d.getDate()).padStart(2, "0");
    return `${anio}-${mes}-${dia}`;
  }

  function formatearHora(ts) {
    if (!ts) return "";
    const d = new Date(ts * 1000);
    return d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
  }

  async function cargarCapturas() {
    const cuerpo = document.getElementById("inicio-capturas-cuerpo");
    const sub = document.getElementById("inicio-capturas-sub");
    if (!cuerpo) return;

    try {
      const hoy = obtenerFechaLocal();
      fechaActual = hoy;
      const datos = await InicioPanel.api(`/api/capturas?fecha=${hoy}`);
      if (datos.error) throw new Error(datos.error);

      let lista = datos.capturas || [];
      const ahora = Math.floor(Date.now() / 1000);

      // Si estamos en la primera hora del día, pedir también el día anterior
      const inicioDia = new Date().setHours(0, 0, 0, 0) / 1000;
      if (ahora - inicioDia < 3600 && datos.dias && datos.dias.length > 1) {
        const ayer = datos.dias.find(d => d !== hoy);
        if (ayer) {
          const datosAyer = await InicioPanel.api(`/api/capturas?fecha=${ayer}`);
          if (datosAyer && datosAyer.capturas) {
            lista = lista.concat(datosAyer.capturas);
          }
        }
      }

      // Filtrar últimos 60 minutos
      capturasUltimaHora = lista.filter(c => c.ts >= ahora - 3600);
      
      // Conservar posición si la captura actual sigue en la lista
      const refActual = capturasUltimaHora[indiceActual]?.ref;
      if (refActual) {
        const nuevoIndice = capturasUltimaHora.findIndex(c => c.ref === refActual);
        if (nuevoIndice !== -1) indiceActual = nuevoIndice;
        else indiceActual = 0;
      } else {
        indiceActual = 0;
      }

      renderizar(capturasUltimaHora, lista);
    } catch (err) {
      renderizarError(err.message || "Error al cargar capturas");
    }
  }

  function renderizar(capturas, todasHoy) {
    const cuerpo = document.getElementById("inicio-capturas-cuerpo");
    const sub = document.getElementById("inicio-capturas-sub");
    if (!cuerpo) return;

    cuerpo.innerHTML = "";

    if (capturas.length === 0) {
      if (sub) sub.textContent = "sin movimiento";
      const divVacio = InicioPanel.el("div", "inicio-car-vacio");
      divVacio.textContent = "Sin movimiento en la última hora";

      const ultima = todasHoy && todasHoy.length > 0 ? todasHoy[0] : null;
      if (ultima) {
        const enlace = InicioPanel.el("a", "inicio-car-enlace", {
          href: "#capturas",
          textContent: `Última: ${ultima.nombre_camara || ultima.camara} ${InicioPanel.hace(ultima.ts)}`
        });
        divVacio.appendChild(document.createElement("br"));
        divVacio.appendChild(enlace);
      }
      cuerpo.appendChild(divVacio);
      detenerAutoplay();
      return;
    }

    // Actualizar subtítulo
    if (sub) {
      const camarasSet = new Set(capturas.map(c => c.nombre_camara || c.camara));
      const listaCamaras = Array.from(camarasSet);
      let textoCamaras = listaCamaras.join(" y ");
      if (listaCamaras.length > 2) {
        textoCamaras = `${listaCamaras.slice(0, -1).join(", ")} y ${listaCamaras[listaCamaras.length - 1]}`;
      }
      sub.textContent = `${capturas.length} captura${capturas.length === 1 ? "" : "s"} · ${textoCamaras}`;
    }

    const contenedor = InicioPanel.el("div", "inicio-car-contenedor");
    contenedor.tabIndex = 0;

    // Slide actual
    const slide = InicioPanel.el("div", "inicio-car-slide");
    const cap = capturas[indiceActual];

    const img = InicioPanel.el("img", "inicio-car-img", {
      src: `/api/foto?ref=${encodeURIComponent(cap.ref)}`,
      alt: `Movimiento en ${cap.nombre_camara || cap.camara} a las ${formatearHora(cap.ts)}`,
      loading: "lazy"
    });

    img.addEventListener("click", () => {
      if (typeof window.abrirFoto === "function") {
        const listaVisor = capturas.map(c => ({
          ref: c.ref,
          texto: `${c.nombre_camara || c.camara} - ${formatearHora(c.ts)}`
        }));
        window.abrirFoto(cap.ref, `${cap.nombre_camara || cap.camara} a las ${formatearHora(cap.ts)}`, listaVisor);
      }
    });

    const pie = InicioPanel.el("div", "inicio-car-pie");
    const chipCam = InicioPanel.el("span", "inicio-car-chip", { textContent: cap.nombre_camara || cap.camara });
    const spanHace = InicioPanel.el("span", "inicio-car-hace", { textContent: `${formatearHora(cap.ts)} (${InicioPanel.hace(cap.ts)})` });
    
    pie.appendChild(chipCam);
    pie.appendChild(spanHace);

    if (cap.clases && cap.clases.length > 0) {
      const divClases = InicioPanel.el("div", "inicio-car-clases");
      cap.clases.forEach(clase => {
        const cChip = InicioPanel.el("span", "inicio-car-chip", { textContent: clase });
        divClases.appendChild(cChip);
      });
      pie.appendChild(divClases);
    }

    slide.appendChild(img);
    slide.appendChild(pie);
    contenedor.appendChild(slide);

    // Botones de navegación ‹ ›
    if (capturas.length > 1) {
      const btnAnt = InicioPanel.el("button", "inicio-car-btn inicio-car-ant", {
        textContent: "‹",
        ariaLabel: "Anterior"
      });
      btnAnt.addEventListener("click", () => {
        indiceActual = (indiceActual - 1 + capturas.length) % capturas.length;
        renderizar(capturas, todasHoy);
      });

      const btnSig = InicioPanel.el("button", "inicio-car-btn inicio-car-sig", {
        textContent: "›",
        ariaLabel: "Siguiente"
      });
      btnSig.addEventListener("click", () => {
        indiceActual = (indiceActual + 1) % capturas.length;
        renderizar(capturas, todasHoy);
      });

      contenedor.appendChild(btnAnt);
      contenedor.appendChild(btnSig);
    }

    // Tira de miniaturas (hasta 12)
    if (capturas.length > 1) {
      const tira = InicioPanel.el("div", "inicio-car-tira");
      const maxMini = Math.min(capturas.length, 12);
      for (let i = 0; i < maxMini; i++) {
        // miniatura con la foto (antes era solo el número)
        const c = capturas[i];
        const punto = InicioPanel.el("button", "inicio-car-punto", { type: "button" });
        punto.setAttribute("aria-pressed", i === indiceActual ? "true" : "false");
        punto.setAttribute("aria-label", `Captura ${i + 1} de ${capturas.length}`);
        punto.appendChild(InicioPanel.el("img", "inicio-car-mini", {
          src: `/api/foto?ref=${encodeURIComponent(c.ref)}`, alt: "", loading: "lazy", decoding: "async"
        }));
        punto.addEventListener("click", () => {
          indiceActual = i;
          renderizar(capturas, todasHoy);
        });
        tira.appendChild(punto);
      }
      const contador = InicioPanel.el("span", "inicio-car-contador", {
        textContent: `${indiceActual + 1} / ${capturas.length}`
      });
      tira.appendChild(contador);
      contenedor.appendChild(tira);
    }

    // Eventos de teclado (← →)
    contenedor.addEventListener("keydown", e => {
      if (capturas.length <= 1) return;
      if (e.key === "ArrowLeft") {
        indiceActual = (indiceActual - 1 + capturas.length) % capturas.length;
        renderizar(capturas, todasHoy);
      } else if (e.key === "ArrowRight") {
        indiceActual = (indiceActual + 1) % capturas.length;
        renderizar(capturas, todasHoy);
      }
    });

    // Eventos pointer para deslizar (touch / mouse drag)
    let posXInicio = 0;
    contenedor.addEventListener("pointerdown", e => {
      posXInicio = e.clientX;
    });
    contenedor.addEventListener("pointerup", e => {
      const diff = e.clientX - posXInicio;
      if (Math.abs(diff) > 40 && capturas.length > 1) {
        if (diff > 0) {
          indiceActual = (indiceActual - 1 + capturas.length) % capturas.length;
        } else {
          indiceActual = (indiceActual + 1) % capturas.length;
        }
        renderizar(capturas, todasHoy);
      }
    });

    // Pausar autoplay al pasar el mouse o tener el foco
    contenedor.addEventListener("mouseenter", () => { pausado = true; });
    contenedor.addEventListener("mouseleave", () => { pausado = false; });
    contenedor.addEventListener("focusin", () => { pausado = true; });
    contenedor.addEventListener("focusout", () => { pausado = false; });

    cuerpo.appendChild(contenedor);
    iniciarAutoplay(capturas, todasHoy);
  }

  function renderizarError(mensaje) {
    const cuerpo = document.getElementById("inicio-capturas-cuerpo");
    const sub = document.getElementById("inicio-capturas-sub");
    if (!cuerpo) return;
    cuerpo.innerHTML = "";
    if (sub) sub.textContent = "error";
    const divError = InicioPanel.el("div", "inicio-car-error", { textContent: mensaje });
    cuerpo.appendChild(divError);
    detenerAutoplay();
  }

  function iniciarAutoplay(capturas, todasHoy) {
    detenerAutoplay();
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reducedMotion || capturas.length <= 1) return;

    autoplayTimer = setInterval(() => {
      const pestanaActiva = document.hidden === false; // Simplificado, controlado por evento pestana
      if (!pausado) {
        indiceActual = (indiceActual + 1) % capturas.length;
        renderizar(capturas, todasHoy);
      }
    }, 5000);
  }

  function detenerAutoplay() {
    if (autoplayTimer) {
      clearInterval(autoplayTimer);
      autoplayTimer = null;
    }
  }

  function detenerRecarga() {
    if (timer) {
      clearInterval(timer);
      timer = null;
    }
    detenerAutoplay();
  }

  document.addEventListener("pestana", e => {
    detenerRecarga();
    if (e.detail !== "inicio") return;
    cargarCapturas();
    timer = setInterval(cargarCapturas, CADA_CAPTURA);
  });

})();
