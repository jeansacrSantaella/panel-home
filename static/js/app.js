/**
 * static/js/app.js — Lógica de tarjetas y panel principal.
 */
(function () {
  "use strict";

  let equipoSeleccionadoMac = null;

  // milisegundos legibles; null/undefined (sin respuesta) -> "–"
  const ms = v => (v == null ? "–" : Math.round(v) + " ms");

  /**
   * Carga el estado general del panel desde la API.
   */
  async function cargarPanel() {
    const elActualizado = document.getElementById("actualizado");
    const elIpPublica = document.getElementById("ip-publica");

    try {
      const res = await fetch("/api/panel");
      if (!res.ok) throw new Error("HTTP error " + res.status);
      const d = await res.json();

      if (elActualizado && d.actualizado) {
        const fecha = new Date(d.actualizado * 1000);
        const horaStr = fecha.toLocaleTimeString("es-MX", {
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit"
        });
        elActualizado.textContent = "Actualizado " + horaStr;
      }

      if (elIpPublica) {
        elIpPublica.textContent = (d.red && d.red.public_ip) ? "IP pública " + d.red.public_ip : "";
      }

      pintarChips(d);
      pintarCamaras(d);
      pintarMapa(d);
      pintarCaidas(d);
      pintarConsumo(d);
      document.dispatchEvent(new CustomEvent("panel", { detail: d }));  // otras tarjetas (espacio.js)
    } catch (err) {
      if (elActualizado) {
        elActualizado.textContent = "Sin conexión con el panel";
      }
    }
  }

  /**
   * Helper para crear elementos chip.
   */
  function crearChip(texto, estado) {
    const span = document.createElement("span");
    span.className = "chip " + (estado || "");
    span.textContent = texto;
    return span;
  }

  /**
   * Pinta los chips de estado superior.
   */
  function pintarChips(d) {
    const cont = document.getElementById("chips");
    if (!cont) return;
    cont.textContent = "";

    if (!d.red) {
      cont.appendChild(crearChip("NetWatch sin datos", "alerta"));
    } else {
      const checks = d.red.checks || {};
      if (checks.wan) {
        cont.appendChild(crearChip(checks.wan.label || "Internet", checks.wan.down_since ? "mal" : "ok"));
      }
      if (checks.lan) {
        cont.appendChild(crearChip(checks.lan.label || "Red local", checks.lan.down_since ? "mal" : "ok"));
      }
      if (checks.dns) {
        cont.appendChild(crearChip(checks.dns.label || "DNS", checks.dns.down_since ? "mal" : "ok"));
      }
    }

    const cams = d.camaras || [];
    const totalCams = cams.length;
    const okCams = cams.filter(c => c.estado === "ok").length;
    const haySinRed = cams.some(c => c.estado === "sin_red");
    const haySinVideo = cams.some(c => c.estado === "sin_video");
    const estCam = haySinRed ? "mal" : (haySinVideo ? "alerta" : "ok");
    cont.appendChild(crearChip(`Cámaras ${okCams}/${totalCams} ok`, estCam));

    const estGo = d.go2rtc_ok === true ? "ok" : (d.go2rtc_ok === false ? "mal" : "alerta");
    cont.appendChild(crearChip("go2rtc", estGo));
  }

  /**
   * Pinta la tarjeta de cámaras y mantiene los iframes activos.
   */
  function pintarCamaras(d) {
    const cont = document.getElementById("camaras");
    if (!cont) return;

    const cams = d.camaras || [];
    if (cams.length === 0) {
      cont.textContent = "No se encontraron cámaras (¿gestorCamaras encendido?)";
      return;
    }

    if (cont.children.length === 0 && cont.textContent) {
      cont.textContent = "";
    }

    const base = d.go2rtc_url || `${location.protocol}//${location.hostname}:1984`;
    const idsActuales = new Set(cams.map(c => String(c.id)));

    // Quitar cámaras que ya no existen
    Array.from(cont.querySelectorAll(".camara")).forEach(div => {
      const id = div.getAttribute("data-id");
      if (!idsActuales.has(id)) {
        div.remove();
      }
    });

    // Crear o actualizar cámaras
    cams.forEach(cam => {
      const camId = String(cam.id);
      let div = Array.from(cont.querySelectorAll(".camara")).find(el => el.getAttribute("data-id") === camId);

      if (!div) {
        div = document.createElement("div");
        div.className = "camara";
        div.setAttribute("data-id", camId);

        const iframe = document.createElement("iframe");
        iframe.src = `${base}/stream.html?src=${encodeURIComponent(cam.id)}&mode=mse`;
        iframe.title = `Video de ${cam.nombre || cam.id}`;
        iframe.loading = "lazy";
        iframe.setAttribute("allow", "autoplay");

        const pie = document.createElement("div");
        pie.className = "camara-pie";

        div.appendChild(iframe);
        div.appendChild(pie);
        cont.appendChild(div);
      }

      // Actualizar pie
      const pie = div.querySelector(".camara-pie");
      if (pie) {
        pie.textContent = "";

        let clsState = "alerta";
        let lblState = "Desconocido";
        if (cam.estado === "ok") {
          clsState = "ok";
          lblState = "En vivo";
        } else if (cam.estado === "sin_video") {
          clsState = "alerta";
          lblState = "Sin video";
        } else if (cam.estado === "sin_red") {
          clsState = "mal";
          lblState = "Sin red";
        }

        pie.appendChild(crearChip(lblState, clsState));

        const nomSpan = document.createElement("span");
        nomSpan.className = "camara-nombre";
        nomSpan.textContent = cam.nombre || cam.id;
        pie.appendChild(nomSpan);

        if (cam.latencia_ms != null) {
          const latSpan = document.createElement("span");
          latSpan.className = "tenue";
          latSpan.textContent = cam.latencia_ms + " ms";
          pie.appendChild(latSpan);
        }

        if (cam.cortes_24h != null) {
          const corSpan = document.createElement("span");
          corSpan.className = "tenue";
          corSpan.textContent = cam.cortes_24h + " cortes 24 h";
          pie.appendChild(corSpan);
        }

        if (d.ultimo_movimiento && d.ultimo_movimiento[cam.id]) {
          const mov = d.ultimo_movimiento[cam.id];
          const fecha = new Date(mov.ts * 1000);
          const horaStr = fecha.toLocaleTimeString("es-MX", { hour: "2-digit", minute: "2-digit" });
          const det = mov.detalle || mov.titulo || "";

          const btn = document.createElement("button");
          btn.className = "mov";
          btn.textContent = `Movimiento ${horaStr}${det ? " · " + det : ""}`;
          btn.onclick = () => window.abrirFoto(mov.ref, `Movimiento ${horaStr} · ${det || cam.nombre}`);
          pie.appendChild(btn);
        }
      }
    });
  }

  /**
   * Pinta el mapa radial de la red y el detalle del equipo seleccionado.
   */
  function pintarMapa(d) {
    const cont = document.getElementById("mapa");
    const redCuenta = document.getElementById("red-cuenta");
    if (!cont) return;

    const equipos = d.equipos || [];
    const conectados = equipos.filter(e => e.online).length;
    if (redCuenta) {
      redCuenta.textContent = `· ${conectados} de ${equipos.length} conectados`;
    }

    let maxConsumo = 0;
    equipos.forEach(e => {
      if (e.consumo) {
        const tot = (e.consumo.rx || 0) + (e.consumo.tx || 0);
        if (tot > maxConsumo) maxConsumo = tot;
      }
    });

    const nodos = equipos.map(eq => {
      let estado = "ok";
      if (!eq.online) {
        estado = "apagado";
      } else if (eq.q && eq.q.loss >= 20) {
        estado = "mal";
      } else if (eq.q && (eq.q.loss > 0 || eq.q.avg > 100)) {
        estado = "alerta";
      }

      const totConsumo = eq.consumo ? ((eq.consumo.rx || 0) + (eq.consumo.tx || 0)) : 0;
      const peso = maxConsumo > 0 ? totConsumo / maxConsumo : 0;

      const latStr = ms(eq.q && eq.q.avg);
      const titulo = `${eq.nombre}\nIP: ${eq.ip}\nMAC: ${eq.mac}\nFabricante: ${eq.vendor || "–"}\nLatencia: ${latStr}`;

      return {
        id: eq.mac,
        etiqueta: eq.nombre,
        estado,
        peso,
        titulo,
        equipo: eq
      };
    });

    const lanLabel = (d.red && d.red.checks && d.red.checks.lan && d.red.checks.lan.label) || "LAN";
    HChart.radial(cont, {
      centro: { etiqueta: "Router", titulo: "Router · " + lanLabel },
      nodos
    }, {
      onClick: (nodo) => mostrarEquipo(nodo.equipo)
    });

    if (equipoSeleccionadoMac) {
      const sel = equipos.find(e => e.mac === equipoSeleccionadoMac);
      if (sel) {
        mostrarEquipo(sel);
      } else {
        const detCont = document.getElementById("detalle-equipo");
        if (detCont) {
          detCont.setAttribute("hidden", "");
          detCont.textContent = "";
        }
      }
    }
  }

  /**
   * Muestra la información detallada de un equipo.
   */
  function mostrarEquipo(eq) {
    if (!eq) return;
    equipoSeleccionadoMac = eq.mac;

    const detCont = document.getElementById("detalle-equipo");
    if (!detCont) return;

    detCont.removeAttribute("hidden");
    detCont.textContent = "";

    const dl = document.createElement("dl");

    const consumoTxt = eq.consumo
      ? `${HChart.formatoBytes(eq.consumo.rx || 0)} bajada / ${HChart.formatoBytes(eq.consumo.tx || 0)} subida`
      : "Sin datos";

    const datos = [
      ["Nombre", eq.nombre],
      ["IP", eq.ip],
      ["MAC", eq.mac],
      ["Fabricante", eq.vendor || "–"],
      ["Estado", eq.online ? "Conectado" : "Desconectado"],
      ["Latencia", ms(eq.q && eq.q.avg)],
      ["Jitter", ms(eq.q && eq.q.jitter)],
      ["Pérdida", eq.q ? `${eq.q.loss}%` : "–"],
      ["Desconexiones 24 h", eq.drops != null ? String(eq.drops) : "–"],
      ["Consumo 24 h", consumoTxt]
    ];

    datos.forEach(([k, v]) => {
      const dt = document.createElement("dt");
      dt.textContent = k;
      const dd = document.createElement("dd");
      dd.textContent = v;
      dl.appendChild(dt);
      dl.appendChild(dd);
    });

    detCont.appendChild(dl);

    if (eq.consumo && eq.consumo.serie && eq.consumo.serie.length) {
      const chispaDiv = document.createElement("div");
      chispaDiv.className = "detalle-chispa";
      detCont.appendChild(chispaDiv);
      HChart.chispa(chispaDiv, eq.consumo.serie, { alto: 24, ancho: 120 });
    }
  }

  /**
   * Pinta la sección de caídas, cintas de disponibilidad y latencia.
   */
  function pintarCaidas(d) {
    const contUptime = document.getElementById("uptime");
    const contCintas = document.getElementById("cintas");
    const contCaidas = document.getElementById("caidas-hora");
    const contLat = document.getElementById("latencia");

    if (!d.red) {
      if (contUptime) contUptime.textContent = "Sin datos de NetWatch";
      if (contCintas) contCintas.textContent = "";
      if (contCaidas) contCaidas.textContent = "";
      if (contLat) contLat.textContent = "";
      return;
    }

    if (contUptime) {
      contUptime.textContent = "";
      const servicios = [
        { key: "wan", label: "Internet" },
        { key: "lan", label: "Red local" },
        { key: "dns", label: "DNS" }
      ];
      servicios.forEach(s => {
        const val = d.red.uptime ? d.red.uptime[s.key] : null;
        const valTxt = val != null ? `${val.toFixed(2)}%` : "–";

        const div = document.createElement("div");
        div.className = "kpi";
        const b = document.createElement("b");
        b.textContent = valTxt;
        const span = document.createElement("span");
        span.textContent = s.label;
        div.appendChild(b);
        div.appendChild(span);
        contUptime.appendChild(div);
      });
    }

    if (contCintas) {
      contCintas.textContent = "";
      const servicios = [
        { key: "wan", label: "Internet" },
        { key: "lan", label: "Red local" },
        { key: "dns", label: "DNS" }
      ];
      servicios.forEach(s => {
        // etiqueta y cinta van directo a la rejilla de 2 columnas de #cintas
        const etiq = document.createElement("div");
        etiq.className = "cinta-etiqueta";
        etiq.textContent = s.label;

        const divGrafico = document.createElement("div");
        contCintas.appendChild(etiq);
        contCintas.appendChild(divGrafico);

        const ribbonData = (d.red.ribbon && d.red.ribbon[s.key]) || [];
        HChart.cinta(divGrafico, ribbonData, {
          inicio: d.red.ribbon_start || 0,
          paso: 600
        });
      });
    }

    if (contCaidas) {
      const hours = d.red.hours || [];
      const etiquetas = Array.from({ length: 24 }, (_, i) => String(i));
      const horaActual = new Date((d.ahora || (Date.now() / 1000)) * 1000).getHours();
      HChart.columnas(contCaidas, hours, {
        alto: 60,
        etiquetas,
        marcar: horaActual,
        formato: v => v + " caídas"
      });
    }

    if (contLat) {
      const series = d.red.series || {};
      let claveSerie = "1.1.1.1";
      if (!series[claveSerie]) {
        claveSerie = Object.keys(series).find(k => k !== "gateway") || Object.keys(series)[0];
      }

      const serie = series[claveSerie] || [];
      const valores = serie.map(p => (p && p[2] ? p[1] : null));

      HChart.columnas(contLat, valores, {
        alto: 60,
        formato: v => (v == null ? "sin respuesta" : Math.round(v) + " ms"),
        color: v => (v == null ? "var(--mal)" : (v > 100 ? "var(--alerta)" : "var(--acento)"))
      });
    }
  }

  /**
   * Pinta la tarjeta de consumo o calidad de red según consumo_activo.
   */
  function pintarConsumo(d) {
    const aviso = document.getElementById("consumo-aviso");
    const contDona = document.getElementById("consumo-dona");
    const contBarras = document.getElementById("consumo-barras");
    const titulo = document.getElementById("consumo-titulo");
    // Sin CONSUMO_CMD (el módem de Telmex no da bytes por equipo) la tarjeta muestra la calidad de conexión
    if (titulo) titulo.textContent = d.consumo_activo ? "Consumo por dispositivo · 24 h" : "Calidad por dispositivo · última hora";

    if (!d.consumo_activo) {
      if (aviso) {
        aviso.removeAttribute("hidden");
        aviso.textContent = "Latencia promedio y pérdida de paquetes de cada equipo conectado (de NetWatch). Rojo: pierde 20 % o más; ámbar: pierde algo.";
      }
      if (contDona) contDona.textContent = "";

      if (contBarras) {
        const equiposCon = (d.equipos || [])
          .filter(e => e.online && e.q && e.q.avg != null)
          .sort((a, b) => (b.q ? b.q.avg : 0) - (a.q ? a.q.avg : 0));

        const items = equiposCon.map(e => ({
          etiqueta: e.nombre,
          valor: e.q.avg,
          texto: `${Math.round(e.q.avg)} ms · ${e.q.loss}% pérdida`,
          color: e.q.loss >= 20 ? "var(--mal)" : (e.q.loss > 0 ? "var(--alerta)" : "var(--acento)")
        }));

        HChart.barras(contBarras, items);
      }
    } else {
      if (aviso) aviso.setAttribute("hidden", "");

      const conConsumo = (d.equipos || [])
        .filter(e => e.consumo && ((e.consumo.rx || 0) + (e.consumo.tx || 0)) > 0)
        .sort((a, b) => ((b.consumo.rx || 0) + (b.consumo.tx || 0)) - ((a.consumo.rx || 0) + (a.consumo.tx || 0)));

      const top8 = conConsumo.slice(0, 8);
      const top5 = conConsumo.slice(0, 5);
      const resto = conConsumo.slice(5);

      const partesDona = top5.map(e => ({
        etiqueta: e.nombre,
        valor: (e.consumo.rx || 0) + (e.consumo.tx || 0)
      }));

      const sumaOtros = resto.reduce((acc, e) => acc + (e.consumo.rx || 0) + (e.consumo.tx || 0), 0);
      if (sumaOtros > 0) {
        partesDona.push({ etiqueta: "Otros", valor: sumaOtros });
      }

      const totalGeneral = conConsumo.reduce((acc, e) => acc + (e.consumo.rx || 0) + (e.consumo.tx || 0), 0);

      if (contDona) {
        HChart.dona(contDona, partesDona, { centro: HChart.formatoBytes(totalGeneral) });
      }

      if (contBarras) {
        const itemsBarras = top8.map(e => {
          const rx = e.consumo.rx || 0;
          const tx = e.consumo.tx || 0;
          const tot = rx + tx;
          return {
            etiqueta: e.nombre,
            valor: tot,
            texto: HChart.formatoBytes(tot) + " ↓" + HChart.formatoBytes(rx)
          };
        });

        HChart.barras(contBarras, itemsBarras);
      }
    }
  }


  document.addEventListener("DOMContentLoaded", () => {
    cargarPanel();
    setInterval(cargarPanel, 15000);
  });
})();
