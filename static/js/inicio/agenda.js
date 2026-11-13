/* Clases CSS usadas:
   - inicio-agenda-izq
   - inicio-agenda-der
   - inicio-agenda-titulo
   - inicio-agenda-dia
   - inicio-agenda-etiqueta
   - inicio-agenda-lista
   - inicio-agenda-evento
   - inicio-agenda-barra
   - inicio-agenda-texto
   - inicio-agenda-nombre
   - inicio-agenda-hora
   - inicio-agenda-detalle
   - inicio-agenda-vacio
   - inicio-agenda-aviso
   - inicio-agenda-cal
   - inicio-agenda-cab
   - inicio-agenda-nav
   - inicio-agenda-mes
   - inicio-agenda-dow
   - inicio-agenda-celda
   - inicio-agenda-hoy
   - inicio-agenda-con-capturas
   - inicio-agenda-punto
*/
(function () {
  "use strict";

  const DIAS = ["domingo", "lunes", "martes", "miércoles", "jueves", "viernes", "sábado"];
  const MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"];
  const DOW_CORTOS = ["LU", "MA", "MI", "JU", "VI", "SA", "DO"];

  let visible = false;
  let timer = null;
  let mesActual = new Date();
  mesActual.setDate(1);
  mesActual.setHours(0, 0, 0, 0);
  let diasCapturas = new Set();

  let izqEl = null;
  let derEl = null;

  function formatearFechaTitulo(d) {
    const dNombre = DIAS[d.getDay()];
    const dNum = d.getDate();
    const mNombre = MESES[d.getMonth()];
    const dCapitalizado = dNombre.charAt(0).toUpperCase() + dNombre.slice(1);
    return `${dCapitalizado} ${dNum} de ${mNombre}`;
  }

  function formatearHora(ts) {
    const d = new Date(ts * 1000);
    let h = d.getHours();
    const m = d.getMinutes();
    const sufijo = h < 12 ? "a. m." : "p. m.";
    h = h % 12 || 12;
    const mStr = m < 10 ? "0" + m : m;
    return `${h}:${mStr} ${sufijo}`;
  }

  function obtenerMedianoches() {
    const ahora = new Date();
    const hoy = new Date(ahora.getFullYear(), ahora.getMonth(), ahora.getDate());
    const ayer = new Date(hoy);
    ayer.setDate(ayer.getDate() - 1);
    return {
      hoyTs: Math.floor(hoy.getTime() / 1000),
      ayerTs: Math.floor(ayer.getTime() / 1000),
      hoyDate: hoy
    };
  }

  function construirEstructura() {
    const contenedor = document.getElementById("inicio-agenda");
    if (!contenedor) return false;

    contenedor.textContent = "";

    izqEl = InicioPanel.el("div", "inicio-agenda-izq");
    derEl = InicioPanel.el("div", "inicio-agenda-der");

    contenedor.append(izqEl, derEl);
    return true;
  }

  function agruparEventos(eventos) {
    const resultado = [];
    for (let i = 0; i < eventos.length; i++) {
      const ev = eventos[i];
      if (ev.tipo === "movimiento") {
        let cuenta = 1;
        let ultimoEv = ev;
        let j = i + 1;
        while (j < eventos.length && eventos[j].tipo === "movimiento" && eventos[j].titulo === ev.titulo) {
          cuenta++;
          ultimoEv = eventos[j];
          j++;
        }
        if (cuenta > 1) {
          resultado.push({
            nivel: ev.nivel || "info",
            titulo: `${ev.titulo} ×${cuenta}`,
            hora: ultimoEv.ts,
            detalle: ultimoEv.detalle
          });
          i = j - 1;
          continue;
        }
      }
      resultado.push({
        nivel: ev.nivel || "info",
        titulo: ev.titulo,
        hora: ev.ts,
        detalle: ev.detalle
      });
    }
    return resultado.slice(0, 12);
  }

  function pintarSeccionEventos(contenedorPadre, tituloSeccion, listaEvs) {
    const seccion = InicioPanel.el("section", "inicio-agenda-dia");
    const etq = InicioPanel.el("h3", "inicio-agenda-etiqueta", { textContent: tituloSeccion });
    seccion.appendChild(etq);

    if (listaEvs.length === 0) {
      const vacio = InicioPanel.el("p", "inicio-agenda-vacio", { textContent: "Sin eventos" });
      seccion.appendChild(vacio);
    } else {
      const ul = InicioPanel.el("ul", "inicio-agenda-lista");
      listaEvs.forEach(ev => {
        const li = InicioPanel.el("li", "inicio-agenda-evento");
        li.setAttribute("data-nivel", ev.nivel);

        const barra = InicioPanel.el("span", "inicio-agenda-barra");
        barra.setAttribute("aria-hidden", "true");

        const textoDiv = InicioPanel.el("div", "inicio-agenda-texto");

        const nombreSpan = InicioPanel.el("span", "inicio-agenda-nombre", { textContent: ev.titulo });
        const horaSpan = InicioPanel.el("span", "inicio-agenda-hora", { textContent: formatearHora(ev.hora) });

        textoDiv.append(nombreSpan, horaSpan);

        if (ev.detalle) {
          const detalleSpan = InicioPanel.el("span", "inicio-agenda-detalle", { textContent: ev.detalle });
          textoDiv.appendChild(detalleSpan);
        }

        li.append(barra, textoDiv);
        ul.appendChild(li);
      });
      seccion.appendChild(ul);
    }

    contenedorPadre.appendChild(seccion);
  }

  function pintarIzquierda(eventos) {
    if (!izqEl) return;
    izqEl.textContent = "";

    const { hoyTs, ayerTs, hoyDate } = obtenerMedianoches();

    const h2 = InicioPanel.el("h2", "inicio-agenda-titulo", { textContent: formatearFechaTitulo(hoyDate) });
    izqEl.appendChild(h2);

    const eventosHoyBrutos = [];
    const eventosAyerBrutos = [];

    eventos.forEach(ev => {
      if (ev.ts >= hoyTs) {
        eventosHoyBrutos.push(ev);
      } else if (ev.ts >= ayerTs) {
        eventosAyerBrutos.push(ev);
      }
    });

    const hoyAgrupados = agruparEventos(eventosHoyBrutos);
    const ayerAgrupados = agruparEventos(eventosAyerBrutos);

    pintarSeccionEventos(izqEl, "HOY", hoyAgrupados);
    pintarSeccionEventos(izqEl, "AYER", ayerAgrupados);
  }

  function pintarErrorIzquierda() {
    if (!izqEl) return;
    izqEl.textContent = "";
    const { hoyDate } = obtenerMedianoches();
    const h2 = InicioPanel.el("h2", "inicio-agenda-titulo", { textContent: formatearFechaTitulo(hoyDate) });
    izqEl.appendChild(h2);

    ["HOY", "AYER"].forEach(nombreSec => {
      const seccion = InicioPanel.el("section", "inicio-agenda-dia");
      const etq = InicioPanel.el("h3", "inicio-agenda-etiqueta", { textContent: nombreSec });
      const aviso = InicioPanel.el("p", "inicio-agenda-aviso", { textContent: "No pude cargar los eventos" });
      seccion.append(etq, aviso);
      izqEl.appendChild(seccion);
    });
  }

  function formatearFechaIso(d) {
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, "0");
    const day = String(d.getDate()).padStart(2, "0");
    return `${y}-${m}-${day}`;
  }

  function pintarDerecha() {
    if (!derEl) return;
    derEl.textContent = "";

    const cal = InicioPanel.el("div", "inicio-agenda-cal");

    const cab = InicioPanel.el("div", "inicio-agenda-cab");
    const btnAnt = InicioPanel.el("button", "inicio-agenda-nav", { type: "button", textContent: "‹" });
    btnAnt.setAttribute("aria-label", "Mes anterior");
    btnAnt.addEventListener("click", () => {
      mesActual.setMonth(mesActual.getMonth() - 1);
      pintarDerecha();
    });

    const mNombre = MESES[mesActual.getMonth()];
    const mCap = mNombre.charAt(0).toUpperCase() + mNombre.slice(1);
    const spanMes = InicioPanel.el("span", "inicio-agenda-mes", { textContent: `${mCap} ${mesActual.getFullYear()}` });

    const btnSig = InicioPanel.el("button", "inicio-agenda-nav", { type: "button", textContent: "›" });
    btnSig.setAttribute("aria-label", "Mes siguiente");
    btnSig.addEventListener("click", () => {
      mesActual.setMonth(mesActual.getMonth() + 1);
      pintarDerecha();
    });

    cab.append(btnAnt, spanMes, btnSig);
    cal.appendChild(cab);

    DOW_CORTOS.forEach(dow => {
      const spanDow = InicioPanel.el("span", "inicio-agenda-dow", { textContent: dow });
      cal.appendChild(spanDow);
    });

    const anio = mesActual.getFullYear();
    const mesIdx = mesActual.getMonth();
    const primerDiaSemana = (new Date(anio, mesIdx, 1).getDay() + 6) % 7; // Lunes = 0
    const totalDiasMes = new Date(anio, mesIdx + 1, 0).getDate();

    for (let i = 0; i < primerDiaSemana; i++) {
      cal.appendChild(InicioPanel.el("span"));
    }

    const hoyStr = formatearFechaIso(new Date());

    for (let d = 1; d <= totalDiasMes; d++) {
      const fechaObj = new Date(anio, mesIdx, d);
      const fechaStr = formatearFechaIso(fechaObj);

      const btnCelda = InicioPanel.el("button", "inicio-agenda-celda", { type: "button", textContent: String(d) });
      btnCelda.setAttribute("type", "button");

      if (fechaStr === hoyStr) {
        btnCelda.classList.add("inicio-agenda-hoy");
      }

      if (diasCapturas.has(fechaStr)) {
        btnCelda.classList.add("inicio-agenda-con-capturas");
        const punto = InicioPanel.el("span", "inicio-agenda-punto");
        punto.setAttribute("aria-hidden", "true");
        btnCelda.appendChild(punto);
        btnCelda.addEventListener("click", () => {
          try {
            sessionStorage.setItem("capturas-fecha", fechaStr);
          } catch (_) {}
          location.hash = "#capturas";
        });
      } else {
        btnCelda.disabled = true;
      }

      cal.appendChild(btnCelda);
    }

    derEl.appendChild(cal);
  }

  async function cargarDatos() {
    const { ayerTs } = obtenerMedianoches();
    const hoyStr = formatearFechaIso(new Date());

    let eventosOk = false;
    let eventosLista = [];

    try {
      const resEv = await InicioPanel.api(`/api/eventos?desde=${ayerTs}&limite=200`);
      eventosLista = (resEv && resEv.eventos) || [];
      eventosOk = true;
    } catch (_) {
      eventosOk = false;
    }

    try {
      const resCap = await InicioPanel.api(`/api/capturas?fecha=${hoyStr}`);
      if (resCap && Array.isArray(resCap.dias)) {
        diasCapturas = new Set(resCap.dias);
      }
    } catch (_) {}

    if (eventosOk) {
      pintarIzquierda(eventosLista);
    } else {
      pintarErrorIzquierda();
    }
    pintarDerecha();
  }

  function detener() {
    if (timer) {
      clearInterval(timer);
      timer = null;
    }
  }

  document.addEventListener("pestana", async e => {
    detener();
    if (e.detail !== "inicio") {
      visible = false;
      return;
    }
    visible = true;
    if (!construirEstructura()) return;
    await cargarDatos();

    timer = setInterval(() => {
      if (!visible) return;
      cargarDatos();
    }, 60000);
  });
})();
