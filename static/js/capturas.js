(function() {
    "use strict";

    // Elementos del DOM
    const $ = id => document.getElementById(id);
    const inputFecha = $("capturas-fecha");
    const listaDias = $("capturas-dias");
    const selCamara = $("capturas-camara");
    const selTipo = $("capturas-tipo");
    const txtCuenta = $("capturas-cuenta");
    const divGrid = $("capturas-grid");
    const btnRecargar = $("capturas-recargar");
    const btnSel = $("capturas-seleccionar");
    const btnTodo = $("capturas-todo");
    const txtSel = $("capturas-sel-cuenta");
    const btnDescSel = $("capturas-desc-sel");
    const btnDescDia = $("capturas-desc-dia");
    const btnBorrarSel = $("capturas-borrar-sel");
    const btnBorrarDia = $("capturas-borrar-dia");
    const pNota = $("capturas-nota");
    const pEstado = $("capturas-estado");
    const dlg = $("capturas-dlg");

    // Estado local
    let items = [];            // {tipo, id, camara, nombre_camara, hora, clases, url, ref}
    let remoto = false;        // true: fotos en gestorCamaras (solo lectura, sin clips)
    let modoListo = false;
    let seleccionando = false;
    const marcados = new Set();  // claves "tipo:fecha/archivo"
    let nombresCam = {};
    let inicializado = false;
    let visibles = [];

    // Fecha pedida desde la agenda de Inicio (sessionStorage); se consume una sola vez
    function consumirFechaPedida() {
        let fecha = null;
        try {
            fecha = sessionStorage.getItem("capturas-fecha");
            sessionStorage.removeItem("capturas-fecha");
        } catch (_) {
            return false;
        }
        if (!fecha || !/^\d{4}-\d{2}-\d{2}$/.test(fecha) || !inputFecha) return false;
        inputFecha.value = fecha;
        return true;
    }

    consumirFechaPedida();

    // Fecha de hoy en hora local (AAAA-MM-DD)
    function hoyLocal() {
        const d = new Date();
        return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
    }

    function fechaActual() {
        if (inputFecha && !inputFecha.value) inputFecha.value = hoyLocal();
        return inputFecha ? inputFecha.value : hoyLocal();
    }

    function el(tag, clase, texto) {
        const e = document.createElement(tag);
        if (clase) e.className = clase;
        if (texto != null) e.textContent = texto;
        return e;
    }

    function aviso(texto) {
        divGrid.textContent = "";
        divGrid.appendChild(el("p", "aviso", texto));
    }

    function estado(texto) {
        if (pEstado) pEstado.textContent = texto || "";
    }

    // Convierte un nombre "cam_HH-MM-SS_clase-clase.ext" en sus partes
    function analizar(nombre) {
        const m = /^([^_/]+)_(\d\d)-(\d\d)-(\d\d)(?:_([\w-]+))?\.\w+$/.exec(nombre);
        if (!m) return { camara: "", hora: "", clases: [] };
        return { camara: m[1], hora: `${m[2]}:${m[3]}:${m[4]}`, clases: m[5] ? m[5].split("-") : [] };
    }

    function nombreCam(id) {
        return nombresCam[id] || id;
    }

    // Aplica el modo remoto: oculta lo que requiere el servidor local
    function aplicarModo() {
        const local = !remoto;
        [btnSel, btnDescDia, btnBorrarDia].forEach(b => { if (b) b.hidden = !local; });
        if (selTipo) selTipo.parentElement.hidden = !local;
        if (pNota) {
            pNota.hidden = local;
            pNota.textContent = local ? "" :
                "Las grabaciones están en gestorCamaras: aquí solo se ven las fotos; para borrar o ver clips usa su propio panel.";
        }
        if (!local) salirSeleccion();
    }

    // Actualiza las opciones del selector de cámaras conservando la selección previa
    function actualizarCamaras() {
        if (!selCamara) return;
        const previa = selCamara.value;
        const mapa = new Map();
        items.forEach(c => { if (c.camara && !mapa.has(c.camara)) mapa.set(c.camara, c.nombre_camara); });
        while (selCamara.options.length > 1) selCamara.remove(1);
        mapa.forEach((nombre, id) => {
            const opt = el("option", null, nombre);
            opt.value = id;
            selCamara.appendChild(opt);
        });
        selCamara.value = mapa.has(previa) ? previa : "";
    }

    function marcarDias(dias) {
        if (!Array.isArray(dias) || !dias.length) return;
        if (inputFecha) {
            inputFecha.min = dias[dias.length - 1];
            inputFecha.max = dias[0];
        }
        if (listaDias) {
            listaDias.textContent = "";
            dias.forEach(d => { const o = document.createElement("option"); o.value = d; listaDias.appendChild(o); });
        }
    }

    // --- selección ---
    function clave(it) { return it.tipo + ":" + it.id; }

    function actualizarBarra() {
        const n = marcados.size;
        [btnTodo, txtSel, btnDescSel, btnBorrarSel].forEach(b => { if (b) b.hidden = !seleccionando; });
        if (btnSel) {
            btnSel.textContent = seleccionando ? "Cancelar selección" : "Seleccionar";
            btnSel.setAttribute("aria-pressed", seleccionando ? "true" : "false");
        }
        if (txtSel) txtSel.textContent = n + (n === 1 ? " seleccionada" : " seleccionadas");
        if (btnDescSel) btnDescSel.disabled = n === 0;
        if (btnBorrarSel) btnBorrarSel.disabled = n === 0;
        if (btnTodo) {
            const todas = visibles.length > 0 && visibles.every(it => marcados.has(clave(it)));
            btnTodo.textContent = todas ? "Quitar todo" : "Seleccionar todo";
        }
        divGrid.classList.toggle("seleccionando", seleccionando);
    }

    function salirSeleccion() {
        seleccionando = false;
        marcados.clear();
        if (divGrid) pintar();
        actualizarBarra();
    }

    // --- miniaturas ---
    function formatoDuracion(s) {
        if (!isFinite(s)) return "";
        const t = Math.round(s);
        return Math.floor(t / 60) + ":" + String(t % 60).padStart(2, "0");
    }

    function chips(clases) {
        const cont = el("span", "captura-clases");
        clases.forEach(c => cont.appendChild(el("span", "chip-clase", c)));
        return cont;
    }

    function crearCelda(it, carrusel, indice) {
        const celda = el("div", "captura-celda");
        const btn = el("button", "captura");
        btn.type = "button";
        const etiqueta = (it.tipo === "clip" ? "Clip " : "Foto ") + it.nombre_camara + " " + it.hora;

        const marco = el("span", "captura-marco");
        if (it.tipo === "clip") {
            const v = document.createElement("video");
            v.preload = "metadata";
            v.muted = true;
            v.playsInline = true;
            v.src = it.url + "#t=0.1";
            const dur = el("span", "captura-dur");
            v.addEventListener("loadedmetadata", () => { dur.textContent = formatoDuracion(v.duration); });
            marco.appendChild(v);
            marco.appendChild(el("span", "captura-play", "▶"));
            marco.appendChild(dur);
        } else {
            const img = document.createElement("img");
            img.loading = "lazy";
            img.alt = etiqueta;
            img.src = it.url;
            marco.appendChild(img);
        }
        btn.appendChild(marco);

        const pie = el("span", "captura-pie");
        pie.appendChild(el("span", "captura-pie-texto", [it.hora, it.nombre_camara].filter(Boolean).join(" · ")));
        if (it.clases.length) pie.appendChild(chips(it.clases));
        btn.appendChild(pie);
        btn.setAttribute("aria-label", etiqueta + (it.clases.length ? ", " + it.clases.join(", ") : ""));

        const casilla = document.createElement("input");
        casilla.type = "checkbox";
        casilla.className = "captura-casilla";
        casilla.setAttribute("aria-label", "Seleccionar " + etiqueta);
        casilla.checked = marcados.has(clave(it));
        casilla.hidden = !seleccionando;
        casilla.addEventListener("change", () => alternar(it, casilla.checked, celda));

        btn.addEventListener("click", () => {
            if (seleccionando) {
                casilla.checked = !casilla.checked;
                alternar(it, casilla.checked, celda);
            } else if (typeof window.abrirFoto === "function") {
                window.abrirFoto(it.ref, carrusel[indice].texto, carrusel);
            }
        });

        celda.classList.toggle("marcada", casilla.checked);
        celda.appendChild(btn);
        celda.appendChild(casilla);
        return celda;
    }

    function alternar(it, activo, celda) {
        if (activo) marcados.add(clave(it)); else marcados.delete(clave(it));
        celda.classList.toggle("marcada", activo);
        actualizarBarra();
    }

    // Pinta lo filtrado agrupado por hora
    function pintar() {
        if (!divGrid) return;
        divGrid.textContent = "";
        const cam = selCamara ? selCamara.value : "";
        const tipo = selTipo && !remoto ? selTipo.value : "todo";
        visibles = items.filter(it => (!cam || it.camara === cam) &&
            (tipo === "todo" || (tipo === "fotos" ? it.tipo === "foto" : it.tipo === "clip")));

        const nf = visibles.filter(i => i.tipo === "foto").length;
        const nc = visibles.length - nf;
        if (txtCuenta) {
            txtCuenta.textContent = remoto ? nf + " capturas" : `${nf} fotos · ${nc} clips`;
        }

        if (!visibles.length) {
            const p = el("div", "capturas-vacio");
            p.appendChild(el("strong", null, "Sin capturas este día"));
            p.appendChild(el("span", "tenue", items.length ? "Ninguna coincide con el filtro." :
                "Elige otro día: los que tienen grabaciones aparecen al abrir el calendario."));
            divGrid.appendChild(p);
            actualizarBarra();
            return;
        }

        const carrusel = visibles.map(it => {
            const base = [it.hora, it.nombre_camara, it.clases.join(", ")].filter(Boolean).join(" · ");
            return { ref: it.ref, texto: (it.tipo === "clip" ? "Clip · " : "") + base, video: it.tipo === "clip" ? it.url : null };
        });

        let ultima = null;
        visibles.forEach((it, i) => {
            const h = it.hora ? it.hora.substring(0, 2) + ":00" : "";
            if (h && h !== ultima) {
                ultima = h;
                divGrid.appendChild(el("h3", "captura-hora", h));
            }
            divGrid.appendChild(crearCelda(it, carrusel, i));
        });
        actualizarBarra();
    }

    // --- carga ---
    function cargarNombres() {
        return fetch("/api/camaras").then(r => r.ok ? r.json() : []).then(lista => {
            const arr = Array.isArray(lista) ? lista : (lista && lista.camaras) || [];
            arr.forEach(c => { if (c && c.id) nombresCam[c.id] = c.nombre || c.id; });
        }).catch(() => {});
    }

    function construirLocal(fecha, data) {
        const arr = [];
        (data.fotos || []).forEach(n => {
            const p = analizar(n);
            arr.push({ tipo: "foto", id: fecha + "/" + n, ref: fecha + "/" + n,
                url: `/api/grabaciones/fotos/${fecha}/${encodeURIComponent(n)}`, ...p });
        });
        (data.clips || []).forEach(n => {
            const p = analizar(n);
            arr.push({ tipo: "clip", id: fecha + "/" + n, ref: fecha + "/" + n,
                url: `/api/grabaciones/clips/${fecha}/${encodeURIComponent(n)}`, ...p });
        });
        arr.forEach(it => { it.nombre_camara = nombreCam(it.camara); });
        arr.sort((a, b) => (b.hora || "").localeCompare(a.hora || ""));
        return arr;
    }

    function cargarRemoto(fecha) {
        return fetch("/api/capturas?fecha=" + encodeURIComponent(fecha)).then(r => r.json()).then(data => {
            if (data.error) { items = []; aviso(data.error); return; }
            marcarDias(data.dias);
            items = (data.capturas || []).map(c => ({
                tipo: "foto", id: c.ref, ref: c.ref, camara: c.camara, hora: c.hora,
                nombre_camara: c.nombre_camara || c.camara, clases: Array.isArray(c.clases) ? c.clases : [],
                url: "/api/foto?ref=" + encodeURIComponent(c.ref)
            }));
        });
    }

    function cargarLocal(fecha) {
        return fetch("/api/grabaciones?fecha=" + encodeURIComponent(fecha)).then(r => r.json().then(d => ({ r, d })))
            .then(({ r, d }) => {
                if (!r.ok) throw new Error(d.error || "error " + r.status);
                items = construirLocal(fecha, d);
            });
    }

    function cargar() {
        const fecha = fechaActual();
        if (divGrid && window.OrionCarga && !divGrid.querySelector(".captura")) {
            window.OrionCarga.en(divGrid, "Buscando capturas…");
        }
        const detectar = modoListo ? Promise.resolve() :
            fetch("/api/grabaciones/dias").then(r => {
                if (r.status === 409) { remoto = true; return null; }
                return r.ok ? r.json() : null;
            }).then(d => {
                modoListo = true;
                if (d && d.dias) marcarDias(d.dias);
                aplicarModo();
            }).catch(() => { modoListo = true; aplicarModo(); });

        detectar.then(() => Promise.all([cargarNombres(), null])).then(() =>
            remoto ? cargarRemoto(fecha) : cargarLocal(fecha)
        ).then(() => {
            // descarta marcas de archivos que ya no existen
            const claves = new Set(items.map(clave));
            marcados.forEach(k => { if (!claves.has(k)) marcados.delete(k); });
            actualizarCamaras();
            pintar();
        }).catch(err => {
            items = [];
            aviso("Error al cargar capturas: " + err.message);
            if (txtCuenta) txtCuenta.textContent = "0 capturas";
        });
    }

    // --- diálogo de confirmación / PIN ---
    // Devuelve una promesa con el PIN (o "") si aceptan, o null si cancelan
    function preguntar(titulo, texto, pedirPin, error) {
        return new Promise(resolve => {
            $("capturas-dlg-titulo").textContent = titulo;
            $("capturas-dlg-texto").textContent = texto;
            $("capturas-dlg-pin").hidden = !pedirPin;
            const pin = $("capturas-pin");
            pin.value = "";
            const pe = $("capturas-dlg-error");
            pe.hidden = !error;
            pe.textContent = error || "";
            let resultado = null;
            const ok = e => { e.preventDefault(); resultado = pedirPin ? pin.value : ""; dlg.close(); };
            const cancelar = () => dlg.close();
            const form = $("capturas-form");
            form.addEventListener("submit", ok);
            $("capturas-dlg-cancelar").addEventListener("click", cancelar);
            dlg.addEventListener("close", function fin() {
                form.removeEventListener("submit", ok);
                $("capturas-dlg-cancelar").removeEventListener("click", cancelar);
                dlg.removeEventListener("close", fin);
                resolve(resultado);
            });
            dlg.showModal();
            (pedirPin ? pin : $("capturas-dlg-ok")).focus();
        });
    }

    // POST con reintento pidiendo el PIN si el servidor responde 401
    async function conPin(ruta, cuerpo) {
        let pin = null;
        let error = "";
        for (;;) {
            const cab = { "Content-Type": "application/json" };
            if (pin) cab["X-Admin"] = pin;
            const r = await fetch(ruta, { method: "POST", headers: cab, body: JSON.stringify(cuerpo) });
            const d = await r.json().catch(() => ({}));
            if (r.status !== 401) {
                if (!r.ok) throw new Error(d.error || "error " + r.status);
                return d;
            }
            pin = await preguntar("PIN de administrador", "Para borrar hace falta el PIN.", true, error);
            if (pin === null) return null;
            error = "PIN incorrecto";
        }
    }

    async function borrar(ruta, cuerpo, titulo, texto) {
        const ok = await preguntar(titulo, texto, false);
        if (ok === null) return;
        estado("Borrando…");
        try {
            const d = await conPin(ruta, cuerpo);
            if (d === null) { estado("Borrado cancelado."); return; }
            estado((d.borrados || 0) + " archivos borrados.");
            marcados.clear();
            cargar();
            modoListo = false;  // refresca también la lista de días
        } catch (err) {
            estado("No se pudo borrar: " + err.message);
        }
    }

    function listasSeleccion() {
        const fotos = [], clips = [];
        items.forEach(it => {
            if (!marcados.has(clave(it))) return;
            (it.tipo === "clip" ? clips : fotos).push(it.id);
        });
        return { fotos, clips };
    }

    // Descarga la respuesta como archivo, con el nombre de Content-Disposition
    async function descargar(respuesta) {
        if (!respuesta.ok) {
            const d = await respuesta.json().catch(() => ({}));
            throw new Error(d.error || "error " + respuesta.status);
        }
        const cd = respuesta.headers.get("Content-Disposition") || "";
        const m = /filename="?([^";]+)"?/.exec(cd);
        const blob = await respuesta.blob();
        const a = document.createElement("a");
        a.href = URL.createObjectURL(blob);
        a.download = m ? m[1] : "grabaciones.zip";
        document.body.appendChild(a);
        a.click();
        a.remove();
        setTimeout(() => URL.revokeObjectURL(a.href), 10000);
    }

    async function exportar(promesa) {
        estado("Preparando el .zip…");
        try {
            await descargar(await promesa);
            estado("Descarga lista.");
        } catch (err) {
            estado("No se pudo descargar: " + err.message);
        }
    }

    // --- eventos ---
    if (inputFecha) inputFecha.addEventListener("change", () => { marcados.clear(); cargar(); });
    if (selCamara) selCamara.addEventListener("change", pintar);
    if (selTipo) selTipo.addEventListener("change", pintar);
    if (btnRecargar) btnRecargar.addEventListener("click", () => { modoListo = false; cargar(); });

    if (btnSel) btnSel.addEventListener("click", () => {
        if (seleccionando) { salirSeleccion(); return; }
        seleccionando = true;
        pintar();
    });
    if (btnTodo) btnTodo.addEventListener("click", () => {
        const todas = visibles.length > 0 && visibles.every(it => marcados.has(clave(it)));
        visibles.forEach(it => { if (todas) marcados.delete(clave(it)); else marcados.add(clave(it)); });
        pintar();
    });
    if (btnDescSel) btnDescSel.addEventListener("click", () => {
        exportar(fetch("/api/grabaciones/exportar", {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify(listasSeleccion())
        }));
    });
    if (btnDescDia) btnDescDia.addEventListener("click", () => {
        exportar(fetch("/api/grabaciones/exportar/" + encodeURIComponent(fechaActual())));
    });
    if (btnBorrarSel) btnBorrarSel.addEventListener("click", () => {
        const n = marcados.size;
        if (!n) return;
        borrar("/api/grabaciones/borrar", listasSeleccion(), "Borrar selección",
            `Se borrarán ${n} archivos de forma permanente.`);
    });
    if (btnBorrarDia) btnBorrarDia.addEventListener("click", () => {
        const f = fechaActual();
        borrar("/api/grabaciones/borrar-dia", { fecha: f }, "Borrar el día",
            `Se borrarán todas las fotos y clips del ${f} de forma permanente.`);
    });

    // Carga inicial al mostrar la pestaña
    document.addEventListener("pestana", function(e) {
        if (e.detail === "capturas") {
            const pedida = consumirFechaPedida();
            if (!inicializado) {
                inicializado = true;
                cargar();
            } else if (pedida) {
                marcados.clear();
                cargar();
            }
        }
    });

    // Recarga periódica si la pestaña está visible, es hoy y no se está seleccionando
    setInterval(function() {
        const pestana = $("pestana-capturas");
        if (pestana && !pestana.hidden && !seleccionando && fechaActual() === hoyLocal()) cargar();
    }, 60000);
})();
