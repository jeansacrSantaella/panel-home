(function () {
  "use strict";

  // Formatea los segundos transcurridos de uptime a un texto descriptivo
  function formatoUptime(seg) {
    const d = Math.floor(seg / 86400);
    const h = Math.floor((seg % 86400) / 3600);
    const m = Math.floor((seg % 3600) / 60);
    if (d > 0) return `${d} d ${h} h`;
    if (h > 0) return `${h} h ${m} min`;
    return `${m} min`;
  }

  // Devuelve la variable CSS del color según el porcentaje o valor
  function obtenerColor(val) {
    if (val >= 90) return "var(--mal)";
    if (val >= 75) return "var(--alerta)";
    return "var(--acento)";
  }

  // Escucha el evento global emitido por la aplicación principal
  document.addEventListener("panel", function (e) {
    const s = e.detail ? e.detail.sistema : null;
    const subEl = document.getElementById("sistema-sub");
    const avisoEl = document.getElementById("sistema-aviso");
    const barrasEl = document.getElementById("sistema-barras");
    const contUl = document.getElementById("sistema-contenedores");

    if (!subEl || !avisoEl || !barrasEl || !contUl) return;

    // Validar si el servidor no envió información utilizable
    const sinDatos = !s || (s.cpu == null && !s.ram && s.contenedores == null);
    if (sinDatos) {
      avisoEl.textContent = "Sin datos del servidor: corre panel-home en Docker en el mismo equipo para verlos.";
      avisoEl.hidden = false;
      subEl.textContent = "";
      barrasEl.textContent = "";
      contUl.textContent = "";
      return;
    }

    avisoEl.hidden = true;

    // Renderizar subtítulo con uptime, temperatura y núcleos
    const partes = [];
    if (s.uptime != null) partes.push("encendido " + formatoUptime(s.uptime));
    if (s.temperatura != null) partes.push(`${s.temperatura} °C`);
    if (s.nucleos != null) partes.push(`${s.nucleos} núcleos`);
    subEl.textContent = partes.join(" · ");

    // Construir la lista de barras de métricas (CPU, RAM, Temperatura)
    const items = [];
    if (s.cpu != null) {
      items.push({
        etiqueta: "CPU",
        valor: s.cpu,
        texto: `${s.cpu} %`,
        color: obtenerColor(s.cpu)
      });
    }
    if (s.ram && s.ram.total) {
      const pct = (s.ram.usado / s.ram.total) * 100;
      items.push({
        etiqueta: "Memoria",
        valor: pct,
        texto: `${HChart.formatoBytes(s.ram.usado)} de ${HChart.formatoBytes(s.ram.total)}`,
        color: obtenerColor(pct)
      });
    }
    if (s.temperatura != null) {
      items.push({
        etiqueta: "Temperatura",
        valor: s.temperatura,
        texto: `${s.temperatura} °C`,
        color: obtenerColor(s.temperatura)
      });
    }
    HChart.barras(barrasEl, items, { max: 100, etiqueta: "Uso del servidor" });

    // Renderizar contenedores Docker
    contUl.textContent = "";
    if (s.contenedores == null) {
      const li = document.createElement("li");
      li.className = "tenue";
      li.textContent = "Monta /var/run/docker.sock para ver los contenedores (ver README)";
      contUl.appendChild(li);
    } else if (Array.isArray(s.contenedores)) {
      s.contenedores.forEach(function (c) {
        const li = document.createElement("li");
        const punto = document.createElement("span");
        let estadoClase = "mal";
        if (c.estado === "running" && c.salud !== "unhealthy") {
          estadoClase = "ok";
        } else if (c.estado === "restarting" || c.salud === "starting") {
          estadoClase = "alerta";
        }
        punto.className = `punto ${estadoClase}`;
        li.appendChild(punto);

        const b = document.createElement("b");
        b.textContent = c.nombre || "";
        li.appendChild(document.createTextNode(" "));
        li.appendChild(b);

        if (c.detalle) {
          const det = document.createElement("span");
          det.className = "tenue";
          det.textContent = c.detalle;
          li.appendChild(document.createTextNode(" "));
          li.appendChild(det);
        }
        contUl.appendChild(li);
      });
    }
  });
})();
