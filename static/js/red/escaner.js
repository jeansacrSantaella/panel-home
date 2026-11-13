(function () {
  "use strict";

  const form = document.getElementById("red-escaner-form");
  const hostInput = document.getElementById("red-escaner-host");
  const portsInput = document.getElementById("red-escaner-puertos");
  const resultado = document.getElementById("red-escaner-resultado");
  const btn = form?.querySelector('button[type="submit"]');

  // Crea una fila de tabla de dos columnas
  function agregarFila(tabla, clave, valor) {
    const tr = RedPanel.el("tr");
    tr.append(
      RedPanel.el("th", "", { textContent: clave }),
      RedPanel.el("td", "", { textContent: valor || "—" })
    );
    tabla.append(tr);
  }

  // Pinta el resultado del escaneo
  function renderizar(r) {
    resultado.replaceChildren();

    // 1. Resumen de identidad
    const resumen = RedPanel.el("table", "tabla");
    const cuerpoResumen = RedPanel.el("tbody");
    resumen.append(cuerpoResumen);

    const ipTexto = r.ip + (r.host !== r.ip ? ` (${r.host})` : "");
    const nombreTexto = r.known?.alias || r.hostname || "—";
    const macTexto = r.mac ? r.mac + (r.random_mac ? " · privada" : "") : "Fuera de la red local";
    const soTexto = r.os_hint ? `${r.os_hint} (TTL ${r.ttl})` : "—";
    const dnsTexto = r.dns.ok ? `Sí, ${r.dns.ms} ms` : "No";
    const invTexto = r.known ? `Sí, desde ${RedPanel.fecha(r.known.first_seen)}${r.known.network ? " · " + r.known.network : ""}` : "No";

    agregarFila(cuerpoResumen, "IP", ipTexto);
    agregarFila(cuerpoResumen, "Nombre", nombreTexto);
    agregarFila(cuerpoResumen, "MAC", macTexto);
    agregarFila(cuerpoResumen, "Fabricante", r.vendor);
    agregarFila(cuerpoResumen, "Sistema probable", soTexto);
    agregarFila(cuerpoResumen, "Servidor DNS", dnsTexto);
    agregarFila(cuerpoResumen, "En inventario", invTexto);

    // 2. Calidad de red (Ping)
    const pingSeccion = RedPanel.el("div", "kpi", { style: "margin: 1.5rem 0" });
    const p = r.ping || {};
    const latencia = RedPanel.el("div", "cifra", {
      textContent: p.loss < 100 && p.avg !== null ? `${p.avg} ms` : "—"
    });
    const pingDetalle = RedPanel.el("div", "tenue", {
      textContent: p.loss >= 100 ? "Sin respuesta (100% pérdida)" : `Pérdida: ${p.loss}% · Jitter: ${p.jitter ?? "—"} ms`
    });
    pingSeccion.append(RedPanel.el("div", "kpi-titulo", { textContent: "CALIDAD DE RESPUESTA" }), latencia, pingDetalle);

    // 3. Tabla de puertos
    const tituloPuertos = RedPanel.el("h3", "", {
      textContent: `Puertos abiertos (${r.open.length} de ${r.ports_scanned})`,
      style: "margin-top: 2rem"
    });
    
    let tablaPuertos;
    if (r.open.length === 0) {
      tablaPuertos = RedPanel.el("p", "tenue", { textContent: "No se detectaron puertos TCP abiertos en el rango probado." });
    } else {
      tablaPuertos = RedPanel.el("table", "tabla");
      const thead = RedPanel.el("thead");
      const trh = RedPanel.el("tr");
      trh.append(
        RedPanel.el("th", "", { textContent: "PUERTO" }),
        RedPanel.el("th", "", { textContent: "SERVICIO" }),
        RedPanel.el("th", "", { textContent: "RESPUESTA (BANNER)" })
      );
      thead.append(trh);
      
      const tbody = RedPanel.el("tbody");
      r.open.forEach(o => {
        const tr = RedPanel.el("tr");
        const bannerCorto = o.banner ? (o.banner.length > 80 ? o.banner.substring(0, 80) + "…" : o.banner) : "—";
        tr.append(
          RedPanel.el("td", "mono", { textContent: o.port }),
          RedPanel.el("td", "", { textContent: o.service || "—" }),
          RedPanel.el("td", "mono", { textContent: bannerCorto, title: o.banner || "" })
        );
        tbody.append(tr);
      });
      tablaPuertos.append(thead, tbody);
    }

    // 4. Pasos del análisis
    const detalles = RedPanel.el("details", "", { style: "margin-top: 2rem" });
    detalles.append(RedPanel.el("summary", "tenue", { textContent: `Pasos del análisis · ${r.elapsed} s` }));
    const listaPasos = RedPanel.el("ul", "actividad");
    r.steps.forEach(s => {
      const li = RedPanel.el("li");
      li.dataset.nivel = "info";
      li.append(RedPanel.el("span", "", { textContent: s }));
      listaPasos.append(li);
    });
    detalles.append(listaPasos);

    resultado.append(resumen, pingSeccion, tituloPuertos, tablaPuertos, detalles);
  }

  // Manejador del formulario
  if (form) {
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const host = hostInput.value.trim();
      if (!host) return;

      const puertos = portsInput.value.trim() || null;
      const textoOriginal = btn.textContent;

      btn.disabled = true;
      btn.textContent = "Escaneando…";
      resultado.setAttribute("aria-busy", "true");
      resultado.replaceChildren(RedPanel.el("p", "tenue", { textContent: "Escaneando… puede tardar decenas de segundos." }));

      try {
        const datos = await RedPanel.api("/api/red/escanear", {
          method: "POST",
          body: { host, ports: puertos }
        });
        renderizar(datos);
      } catch (err) {
        resultado.replaceChildren(RedPanel.el("p", "aviso", { textContent: "Error: " + err.message }));
      } finally {
        btn.disabled = false;
        btn.textContent = textoOriginal;
        resultado.removeAttribute("aria-busy");
      }
    });
  }

  // API pública para otros módulos (ej. equipos.js)
  window.RedEscaner = {
    escanear(host) {
      if (!hostInput || !form) return;
      hostInput.value = host;
      // Desplaza hasta el formulario para que el usuario vea que ocurre algo
      form.scrollIntoView({ behavior: "smooth" });
      form.requestSubmit();
    }
  };

})();
