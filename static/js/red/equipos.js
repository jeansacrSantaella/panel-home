/* Pestaña Red: tabla de equipos y edición de alias en línea. */
(function () {
  "use strict";

  let ultimoResumen = null;
  let filtroBusqueda = "";
  let filtroEstado = "todos";
  let filasPorPagina = parseInt((document.getElementById("red-equipos-filas") || {}).value, 10) || 25;
  let paginaActual = 0;
  let editandoMac = null;

  function normalizar(texto) {
    return (texto || "").toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "");
  }

  function render() {
    const contenedorTabla = document.getElementById("red-equipos-tabla");
    const contenedorPaginas = document.getElementById("red-equipos-paginas");
    const subTexto = document.getElementById("red-equipos-sub");
    if (!contenedorTabla || !ultimoResumen || !ultimoResumen.devices) return;

    const devices = ultimoResumen.devices;
    const totalDispositivos = devices.length;
    const enLinea = devices.filter(d => d.online).length;

    if (subTexto) {
      subTexto.textContent = `${enLinea} en línea de ${totalDispositivos}`;
    }

    // Filtrado
    const query = normalizar(filtroBusqueda);
    const filtrados = devices.filter(d => {
      if (filtroEstado === "en_linea" && !d.online) return false;
      if (filtroEstado === "fuera" && d.online) return false;
      if (!query) return true;
      const texto = [d.hostname, d.alias, d.ip, d.mac, d.vendor].filter(Boolean).join(" ");
      return normalizar(texto).includes(query);
    });

    const totalPaginas = Math.ceil(filtrados.length / filasPorPagina) || 1;
    if (paginaActual >= totalPaginas) paginaActual = totalPaginas - 1;
    if (paginaActual < 0) paginaActual = 0;

    const inicio = paginaActual * filasPorPagina;
    const paginaActualItems = filtrados.slice(inicio, inicio + filasPorPagina);

    contenedorTabla.replaceChildren();

    if (filtrados.length === 0) {
      const tabla = RedPanel.el("table", "tabla");
      const tr = RedPanel.el("tr");
      const td = RedPanel.el("td", "tenue", { colSpan: 6, textContent: "No se encontraron equipos." });
      td.style.textAlign = "center";
      tr.append(td);
      tabla.append(tr);
      contenedorTabla.append(tabla);
      if (contenedorPaginas) contenedorPaginas.replaceChildren();
      return;
    }

    const tabla = RedPanel.el("table", "tabla");
    const filaCabeza = RedPanel.el("tr");
    ["Estado", "Nombre", "IP", "MAC", "Calidad", "Caídas 24 h", "Visto"].forEach(cabecera => {
      filaCabeza.append(RedPanel.el("th", "", { textContent: cabecera, scope: "col" }));
    });
    const thead = RedPanel.el("thead");
    thead.append(filaCabeza);
    const tbody = RedPanel.el("tbody");
    tabla.append(thead, tbody);

    paginaActualItems.forEach(d => {
      const tr = RedPanel.el("tr");

      // Columna Estado
      const tdEstado = RedPanel.el("td");
      if (d.online) {
        const punto = RedPanel.el("span", "punto");
        punto.dataset.estado = "ok";
        tdEstado.append(punto);
      }
      tr.append(tdEstado);

      // Columna Nombre y Fabricante
      const tdNombre = RedPanel.el("td");
      const divNombre = RedPanel.el("div", "red-alias");
      
      const principalNombre = d.alias || d.hostname || d.vendor || d.ip;

      if (editandoMac === d.mac) {
        const input = RedPanel.el("input", "red-alias-input", { type: "text", value: d.alias || "", maxLength: 64 });
        input.setAttribute("aria-label", "Alias de " + principalNombre);
        let guardado = false;  // Enter guarda y el repintado dispara blur: que no guarde dos veces

        const guardarAlias = async () => {
          if (guardado || editandoMac !== d.mac) return;
          guardado = true;
          const nuevoAlias = input.value.trim();
          try {
            await RedPanel.api("/api/red/alias", {
              method: "POST",
              body: { mac: d.mac, alias: nuevoAlias }
            });
            editandoMac = null;
            RedPanel.recargar();
          } catch (err) {
            guardado = false;
            input.title = err.message || "Error al guardar";
            input.focus();
          }
        };

        input.addEventListener("keydown", e => {
          if (e.key === "Enter") {
            e.preventDefault();
            guardarAlias();
          } else if (e.key === "Escape") {
            guardado = true;
            editandoMac = null;
            render();
          }
        });
        input.addEventListener("blur", guardarAlias);

        divNombre.append(input);
        setTimeout(() => input.focus(), 0);
      } else {
        const spanTexto = RedPanel.el("b", "", { textContent: principalNombre });
        const botonLapiz = RedPanel.el("button", "red-alias-lapiz", { type: "button", textContent: "✎", title: "Editar alias" });
        botonLapiz.setAttribute("aria-label", "Editar alias de " + principalNombre);
        botonLapiz.addEventListener("click", () => {
          editandoMac = d.mac;
          render();
        });

        divNombre.append(spanTexto, botonLapiz);
      }

      tdNombre.append(divNombre);
      // el fabricante debajo, salvo que ya sea el nombre que se muestra
      if (principalNombre !== d.vendor) {
        tdNombre.append(RedPanel.el("small", "tenue", { textContent: d.vendor || "Fabricante desconocido" }));
      }
      tr.append(tdNombre);

      // Columna IP
      const tdIp = RedPanel.el("td", "mono", { textContent: d.ip });
      tr.append(tdIp);

      // Columna MAC
      const tdMac = RedPanel.el("td");
      const divMac = RedPanel.el("div", "mono", { textContent: d.mac });
      tdMac.append(divMac);
      if (d.random_mac) {
        tdMac.append(RedPanel.el("small", "tenue", { textContent: " privada" }));
      }
      tr.append(tdMac);

      // Columna Calidad
      const tdCalidad = RedPanel.el("td", "mono");
      if (!d.online) {
        tdCalidad.textContent = "—";
      } else if (!d.q) {
        tdCalidad.textContent = "sin respuesta a ping";
      } else if (d.q.loss >= 100) {
        tdCalidad.textContent = "sin respuesta a ping";
      } else {
        tdCalidad.textContent = `${d.q.avg} ms · ${d.q.loss} %`;
      }
      tr.append(tdCalidad);

      // Columna Caídas
      const tdDrops = RedPanel.el("td", "", { textContent: String(d.drops ?? 0) });
      tr.append(tdDrops);

      // Columna Visto
      const tdVisto = RedPanel.el("td", "", { textContent: RedPanel.hace(d.last_seen) });
      tdVisto.title = RedPanel.fecha(d.last_seen);
      tr.append(tdVisto);

      tbody.append(tr);
    });

    contenedorTabla.append(tabla);

    if (contenedorPaginas) {
      RedPanel.paginador(contenedorPaginas, paginaActual, totalPaginas, nuevaPag => {
        paginaActual = nuevaPag;
        render();
      });
    }
  }

  document.addEventListener("red-datos", e => {
    ultimoResumen = e.detail && e.detail.resumen;  // detail = {resumen, sonda, vivo}
    // Si estamos editando un equipo, no repintamos completamente para no romper el input activo
    if (editandoMac) return;
    render();
  });

  document.addEventListener("DOMContentLoaded", () => {
    const inputBuscar = document.getElementById("red-equipos-buscar");
    const selectFiltro = document.getElementById("red-equipos-filtro");
    const selectFilas = document.getElementById("red-equipos-filas");

    if (inputBuscar) {
      inputBuscar.addEventListener("input", e => {
        filtroBusqueda = e.target.value;
        paginaActual = 0;
        render();
      });
    }

    if (selectFiltro) {
      selectFiltro.addEventListener("change", e => {
        filtroEstado = e.target.value;
        paginaActual = 0;
        render();
      });
    }

    if (selectFilas) {
      selectFilas.addEventListener("change", e => {
        filasPorPagina = parseInt(e.target.value, 10) || 10;
        paginaActual = 0;
        render();
      });
    }
  });

  document.addEventListener("buscar-red", e => {
    const texto = e.detail || "";
    filtroBusqueda = texto;
    const inputBuscar = document.getElementById("red-equipos-buscar");
    if (inputBuscar) {
      inputBuscar.value = texto;
    }
    paginaActual = 0;
    render();
  });
})();
