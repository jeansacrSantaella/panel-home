(function () {
  "use strict";

  // Elementos DOM principales
  const dlg = document.getElementById("dlg-acerca");
  const btnCerrar = document.getElementById("acerca-cerrar");
  const btnAccion = document.getElementById("accion-acerca");
  const btnPie = document.getElementById("pie-acerca");
  const tabs = Array.from(document.querySelectorAll('.acerca-pestanas [role="tab"]'));
  let ultimoFoco = null;

  // Formato de tiempo de encendido (uptime)
  function formatearUptime(inicio, ahora) {
    if (!inicio || !ahora || ahora <= inicio) return "—";
    const sec = Math.floor(ahora - inicio);
    if (sec < 60) return "menos de 1 min";
    const min = Math.floor(sec / 60);
    const hrs = Math.floor(min / 60);
    const dias = Math.floor(hrs / 24);
    const hRest = hrs % 24;
    const mRest = min % 60;
    if (dias > 0) return hRest > 0 ? `${dias} d ${hRest} h` : `${dias} d`;
    if (hrs > 0) return mRest > 0 ? `${hrs} h ${mRest} min` : `${hrs} h`;
    return `${min} min`;
  }

  // Formato legible de tamaño de base de datos
  function formatearBytes(bytes) {
    if (bytes === null || bytes === undefined || isNaN(bytes)) return "—";
    if (bytes === 0) return "0 B";
    const k = 1024;
    const unidades = ["B", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    if (i === 0) return bytes + " B";
    return (bytes / Math.pow(k, i)).toFixed(1) + " " + unidades[i];
  }

  // Gestión de estado visual de pestañas y paneles
  function activarPestana(tabActiva) {
    tabs.forEach((tab) => {
      const esActiva = tab === tabActiva;
      tab.setAttribute("aria-selected", esActiva ? "true" : "false");
      tab.tabIndex = esActiva ? 0 : -1;
      const panel = document.getElementById(tab.getAttribute("aria-controls"));
      if (panel) {
        panel.hidden = !esActiva;
        if (esActiva) panel.scrollTop = 0;
      }
    });
  }

  // Renderizado en caso de error de conexión
  function renderizarError() {
    const ulServicios = document.getElementById("acerca-servicios");
    if (ulServicios) {
      ulServicios.replaceChildren();
      const li = document.createElement("li");
      li.className = "tenue";
      li.textContent = "No pude leer el estado del panel";
      ulServicios.appendChild(li);
    }
  }

  // Llenado de información del sistema en los elementos
  function renderizarDatos(data) {
    if (!data) return renderizarError();

    const setTexto = (id, val) => {
      const el = document.getElementById(id);
      if (el) el.textContent = val || "—";
    };

    setTexto("acerca-version", data.version);
    setTexto("acerca-python", data.python);
    setTexto("acerca-sqlite", data.sqlite);
    setTexto("acerca-sistema", data.sistema);

    const elEncendido = document.getElementById("acerca-encendido");
    if (elEncendido) elEncendido.textContent = formatearUptime(data.inicio, data.ahora);

    const elEventos = document.getElementById("acerca-eventos");
    if (elEventos) {
      if (data.eventos !== undefined && data.eventos !== null) {
        let txt = Number(data.eventos).toLocaleString("es-MX");
        if (data.eventos_desde) {
          const fecha = new Date(data.eventos_desde * 1000);
          txt += " desde el " + fecha.toLocaleDateString("es-MX", { day: "numeric", month: "short", year: "numeric" });
        }
        elEventos.textContent = txt;
      } else {
        elEventos.textContent = "—";
      }
    }

    const elDb = document.getElementById("acerca-db");
    if (elDb) elDb.textContent = formatearBytes(data.db_bytes);

    const ulServicios = document.getElementById("acerca-servicios");
    if (ulServicios) {
      ulServicios.replaceChildren();
      if (Array.isArray(data.servicios)) {
        data.servicios.forEach((s) => {
          const li = document.createElement("li");

          const punto = document.createElement("span");
          punto.className = "punto " + (s.ok === true ? "ok" : s.ok === false ? "mal" : "apagado");
          li.appendChild(punto);

          const b = document.createElement("b");
          b.textContent = s.nombre || "";
          li.appendChild(b);

          if (s.detalle) {
            const det = document.createElement("span");
            det.className = "tenue";
            det.textContent = " " + s.detalle;
            li.appendChild(det);
          }

          const estado = document.createElement("span");
          estado.className = "acerca-estado";
          estado.textContent = s.ok === true ? "Conectado" : s.ok === false ? "Sin respuesta" : "No configurado";
          li.appendChild(estado);

          ulServicios.appendChild(li);
        });
      }
    }
  }

  // Petición a la API
  function cargarDatos() {
    fetch("/api/acerca", { credentials: "same-origin" })
      .then((res) => {
        if (!res.ok) throw new Error("Status " + res.status);
        return res.json();
      })
      .then(renderizarDatos)
      .catch(renderizarError);
  }

  // Apertura del modal de información
  function abrirDialogo(e) {
    ultimoFoco = e ? e.currentTarget : null;

    const menuCuenta = document.getElementById("menu-cuenta");
    const btnCuenta = document.getElementById("btn-cuenta");
    if (menuCuenta) menuCuenta.hidden = true;
    if (btnCuenta) btnCuenta.setAttribute("aria-expanded", "false");

    if (tabs.length > 0) activarPestana(tabs[0]);

    if (dlg && typeof dlg.showModal === "function") {
      dlg.showModal();
      if (tabs[0]) tabs[0].focus();
      cargarDatos();
    }
  }

  // Suscripción de eventos de apertura y cierre
  if (btnAccion) btnAccion.addEventListener("click", abrirDialogo);
  if (btnPie) btnPie.addEventListener("click", abrirDialogo);
  if (btnCerrar) btnCerrar.addEventListener("click", () => dlg && dlg.close());

  if (dlg) {
    dlg.addEventListener("close", () => {
      if (ultimoFoco) {
        ultimoFoco.focus();
        ultimoFoco = null;
      }
    });

    dlg.addEventListener("click", (e) => {
      if (e.target === dlg) dlg.close();
    });
  }

  // Control teclado y clics para las pestañas
  tabs.forEach((tab, idx) => {
    tab.addEventListener("click", () => {
      activarPestana(tab);
      tab.focus();
    });

    tab.addEventListener("keydown", (e) => {
      let nuevoIdx = idx;
      if (e.key === "ArrowRight") nuevoIdx = (idx + 1) % tabs.length;
      else if (e.key === "ArrowLeft") nuevoIdx = (idx - 1 + tabs.length) % tabs.length;
      else if (e.key === "Home") nuevoIdx = 0;
      else if (e.key === "End") nuevoIdx = tabs.length - 1;
      else return;

      e.preventDefault();
      activarPestana(tabs[nuevoIdx]);
      tabs[nuevoIdx].focus();
    });
  });
})();
