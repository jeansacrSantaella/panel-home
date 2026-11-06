(function () {
  "use strict";

  const GRUPOS = {
    camaras: [
      "movimiento",
      "camara_sin_red",
      "camara_sin_video",
      "camara_ok",
      "go2rtc_caido",
      "go2rtc_ok"
    ],
    internet: [
      "internet_caido",
      "internet_ok",
      "red_local_caida",
      "red_local_ok",
      "dns_caido",
      "dns_ok",
      "cambio_ip",
      "ip_publica"
    ],
    equipos: ["equipo_nuevo", "equipo_conectado", "equipo_desconectado"],
    sistema: ["fuente_caida", "fuente_ok", "pausa_monitor", "contenedor_caido", "contenedor_ok"]
  };

  let maxId = 0;
  let ultimoTs = null;
  let ultimoDia = null;
  let grupoActivo = "todos";

  function obtenerTextoDia(ts) {
    const d = new Date(ts * 1000);
    const hoy = new Date();
    const ayer = new Date();
    ayer.setDate(hoy.getDate() - 1);

    if (d.toDateString() === hoy.toDateString()) return "Hoy";
    if (d.toDateString() === ayer.toDateString()) return "Ayer";

    const str = d.toLocaleDateString("es-MX", {
      weekday: "long",
      day: "numeric",
      month: "long",
      year: "numeric"
    });
    return str.charAt(0).toUpperCase() + str.slice(1);
  }

  function perteneceAFiltro(tipo) {
    if (grupoActivo === "todos") return true;
    const lista = GRUPOS[grupoActivo];
    return lista ? lista.includes(tipo) : false;
  }

  function crearNodoEvento(ev, esNuevo) {
    const li = document.createElement("li");
    li.className = "ev " + (ev.nivel || "info") + (esNuevo ? " nuevo" : "");

    const spanHora = document.createElement("span");
    spanHora.className = "ev-hora";
    const d = new Date(ev.ts * 1000);
    const hh = String(d.getHours()).padStart(2, "0");
    const mm = String(d.getMinutes()).padStart(2, "0");
    spanHora.textContent = hh + ":" + mm;

    const spanPunto = document.createElement("span");
    spanPunto.className = "ev-punto";

    const divContenedor = document.createElement("div");

    const divTitulo = document.createElement("div");
    divTitulo.className = "ev-titulo";
    divTitulo.textContent = ev.titulo || "";

    const divDetalle = document.createElement("div");
    divDetalle.className = "ev-detalle";
    divDetalle.textContent = ev.detalle || "";

    divContenedor.appendChild(divTitulo);
    divContenedor.appendChild(divDetalle);

    if (ev.ref) {
      const btnFoto = document.createElement("button");
      btnFoto.type = "button";
      btnFoto.className = "ev-foto-btn";
      btnFoto.setAttribute("aria-label", "Ver foto: " + (ev.titulo || ""));
      btnFoto.dataset.ref = ev.ref;
      btnFoto.dataset.texto = ev.titulo || ev.detalle || "";
      const img = document.createElement("img");
      img.className = "ev-foto";
      img.loading = "lazy";
      img.src = "/api/foto?ref=" + encodeURIComponent(ev.ref);
      btnFoto.appendChild(img);
      btnFoto.addEventListener("click", function () {
        if (typeof window.abrirFoto === "function") {
          // Carrusel con las fotos visibles de la línea de tiempo (respeta el filtro activo)
          const lista = Array.from(document.querySelectorAll("#linea-tiempo .ev-foto-btn"))
            .filter(b => b.offsetParent !== null)
            .map(b => ({ ref: b.dataset.ref, texto: b.dataset.texto }));
          window.abrirFoto(ev.ref, ev.titulo || ev.detalle || "", lista);
        }
      });
      divContenedor.appendChild(btnFoto);
    }

    li.appendChild(spanHora);
    li.appendChild(spanPunto);
    li.appendChild(divContenedor);

    return li;
  }

  function insertarEventoArriba(ev) {
    const ol = document.getElementById("linea-tiempo");
    if (!ol) return;

    const textoDia = obtenerTextoDia(ev.ts);
    const primerHijo = ol.firstElementChild;

    if (primerHijo && primerHijo.classList.contains("dia") && primerHijo.textContent === textoDia) {
      const nodoEv = crearNodoEvento(ev, true);
      if (primerHijo.nextSibling) {
        ol.insertBefore(nodoEv, primerHijo.nextSibling);
      } else {
        ol.appendChild(nodoEv);
      }
    } else {
      const liDia = document.createElement("li");
      liDia.className = "dia";
      liDia.textContent = textoDia;
      const nodoEv = crearNodoEvento(ev, true);

      if (primerHijo) {
        ol.insertBefore(liDia, primerHijo);
        ol.insertBefore(nodoEv, primerHijo);
      } else {
        ol.appendChild(liDia);
        ol.appendChild(nodoEv);
      }
    }
  }

  function cargarEventos(reiniciar) {
    const ol = document.getElementById("linea-tiempo");
    const btnMas = document.getElementById("mas-eventos");
    if (!ol) return;

    if (reiniciar) {
      ultimoTs = null;
      ultimoDia = null;
      ol.textContent = "";
    }

    let url = "/api/eventos?limite=50";
    if (grupoActivo !== "todos" && GRUPOS[grupoActivo]) {
      url += "&tipos=" + encodeURIComponent(GRUPOS[grupoActivo].join(","));
    }
    if (!reiniciar && ultimoTs !== null) {
      url += "&hasta=" + ultimoTs;
    }

    fetch(url)
      .then(function (res) { return res.json(); })
      .then(function (data) {
        if (!data || !Array.isArray(data.eventos)) return;
        const mevs = data.eventos;

        if (btnMas) {
          btnMas.hidden = mevs.length < 50;
        }

        mevs.forEach(function (ev) {
          if (ev.id > maxId) {
            maxId = ev.id;
          }

          const textoDia = obtenerTextoDia(ev.ts);
          if (textoDia !== ultimoDia) {
            const liDia = document.createElement("li");
            liDia.className = "dia";
            liDia.textContent = textoDia;
            ol.appendChild(liDia);
            ultimoDia = textoDia;
          }

          const nodoEv = crearNodoEvento(ev, false);
          ol.appendChild(nodoEv);
          ultimoTs = ev.ts;
        });
      })
      .catch(function () {});
  }

  function buscarNuevos() {
    fetch("/api/eventos?limite=20")
      .then(function (res) { return res.json(); })
      .then(function (data) {
        if (!data || !Array.isArray(data.eventos)) return;
        const mevs = data.eventos;
        if (mevs.length === 0) return;

        const nuevos = mevs.filter(function (ev) { return ev.id > maxId; });
        if (nuevos.length === 0) return;

        nuevos.sort(function (a, b) { return a.id - b.id; });

        nuevos.forEach(function (ev) {
          if (ev.id > maxId) maxId = ev.id;

          if (
            (ev.nivel === "alto" || ev.nivel === "medio") &&
            "Notification" in window &&
            Notification.permission === "granted"
          ) {
            const opts = { body: ev.detalle || "", tag: "panel-" + ev.id };
            if (ev.ref) {
              opts.icon = "/api/foto?ref=" + encodeURIComponent(ev.ref);
            }
            new Notification(ev.titulo || "Evento", opts);
          }

          if (perteneceAFiltro(ev.tipo)) {
            insertarEventoArriba(ev);
          }
        });
      })
      .catch(function () {});
  }

  function actualizarBotonNotif() {
    const btnNotif = document.getElementById("btn-notif");
    if (!btnNotif) return;

    if (!("Notification" in window)) {
      btnNotif.hidden = true;
      return;
    }

    if (Notification.permission === "granted") {
      btnNotif.textContent = "Notificaciones activas";
      btnNotif.disabled = true;
    } else {
      btnNotif.textContent = "Activar notificaciones";
      btnNotif.disabled = false;
    }
  }

  function init() {
    const contenedorFiltros = document.getElementById("filtros");
    if (contenedorFiltros) {
      contenedorFiltros.addEventListener("click", function (e) {
        const btn = e.target.closest(".filtro");
        if (!btn) return;
        const todos = contenedorFiltros.querySelectorAll(".filtro");
        todos.forEach(function (b) { b.classList.remove("activo"); });
        btn.classList.add("activo");
        grupoActivo = btn.dataset.grupo || "todos";
        cargarEventos(true);
      });
    }

    const btnMas = document.getElementById("mas-eventos");
    if (btnMas) {
      btnMas.addEventListener("click", function () {
        cargarEventos(false);
      });
    }

    const btnNotif = document.getElementById("btn-notif");
    if (btnNotif && "Notification" in window) {
      actualizarBotonNotif();
      btnNotif.addEventListener("click", function () {
        Notification.requestPermission().then(function () {
          actualizarBotonNotif();
        });
      });
    } else if (btnNotif) {
      actualizarBotonNotif();
    }

    cargarEventos(true);
    setInterval(buscarNuevos, 15000);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
