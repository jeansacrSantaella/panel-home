(function() {
    "use strict";

    // Elementos del DOM
    const inputFecha = document.getElementById("capturas-fecha");
    const selCamara = document.getElementById("capturas-camara");
    const txtCuenta = document.getElementById("capturas-cuenta");
    const divGrid = document.getElementById("capturas-grid");
    const btnRecargar = document.getElementById("capturas-recargar");

    // Estado local
    let capturas = [];
    let inicializado = false;

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

    // Obtiene la fecha de hoy en hora local (AAAA-MM-DD)
    function hoyLocal() {
        const d = new Date();
        const aaaa = d.getFullYear();
        const mm = String(d.getMonth() + 1).padStart(2, "0");
        const dd = String(d.getDate()).padStart(2, "0");
        return `${aaaa}-${mm}-${dd}`;
    }

    // Actualiza las opciones del selector de cámaras conservando la selección previa
    function actualizarCamaras(lista) {
        if (!selCamara) return;

        const selVal = selCamara.value;
        const camarasMap = new Map();

        lista.forEach(c => {
            if (c.camara && !camarasMap.has(c.camara)) {
                camarasMap.set(c.camara, c.nombre_camara || c.camara);
            }
        });

        while (selCamara.options.length > 1) {
            selCamara.remove(1);
        }

        camarasMap.forEach((nombre, id) => {
            const opt = document.createElement("option");
            opt.value = id;
            opt.textContent = nombre;
            selCamara.appendChild(opt);
        });

        if (selVal && camarasMap.has(selVal)) {
            selCamara.value = selVal;
        } else {
            selCamara.value = "";
        }
    }

    // Pinta las capturas filtradas en el grid agrupadas por hora
    function pintar() {
        if (!divGrid) return;
        divGrid.textContent = "";

        const camSel = selCamara ? selCamara.value : "";
        const filtradas = camSel ? capturas.filter(c => c.camara === camSel) : capturas;

        if (txtCuenta) {
            txtCuenta.textContent = filtradas.length + " capturas";
        }

        if (filtradas.length === 0) {
            const p = document.createElement("p");
            p.className = "aviso";
            p.textContent = "Sin capturas este día";
            divGrid.appendChild(p);
            return;
        }

        let ultimaHora = null;
        // Lista para el carrusel del visor: mismas fotos y orden que el grid
        const carrusel = filtradas.map(c => ({
            ref: c.ref,
            texto: [c.hora, c.nombre_camara || c.camara, Array.isArray(c.clases) ? c.clases.join(", ") : ""].filter(Boolean).join(" · ")
        }));

        filtradas.forEach(c => {
            const horaGrupo = c.hora ? c.hora.substring(0, 2) + ":00" : "";
            if (horaGrupo && horaGrupo !== ultimaHora) {
                ultimaHora = horaGrupo;
                const h3 = document.createElement("h3");
                h3.className = "captura-hora";
                h3.textContent = horaGrupo;
                divGrid.appendChild(h3);
            }

            const clasesStr = Array.isArray(c.clases) ? c.clases.join(", ") : "";
            const partesPie = [c.hora, c.nombre_camara || c.camara, clasesStr].filter(Boolean);
            const pieTexto = partesPie.join(" · ");

            const btn = document.createElement("button");
            btn.className = "captura";
            btn.type = "button";

            const img = document.createElement("img");
            img.loading = "lazy";
            img.alt = `${c.nombre_camara || c.camara} ${c.hora}`;
            img.src = "/api/foto?ref=" + encodeURIComponent(c.ref);

            const pie = document.createElement("span");
            pie.className = "captura-pie";
            pie.textContent = pieTexto;

            btn.appendChild(img);
            btn.appendChild(pie);

            btn.addEventListener("click", function() {
                if (typeof window.abrirFoto === "function") {
                    window.abrirFoto(c.ref, pieTexto, carrusel);
                }
            });

            divGrid.appendChild(btn);
        });
    }

    // Carga los datos de capturas desde la API
    function cargar() {
        let fecha = inputFecha ? inputFecha.value : "";
        if (!fecha) {
            fecha = hoyLocal();
            if (inputFecha) {
                inputFecha.value = fecha;
            }
        }

        // constelación de carga mientras llegan (solo si la galería está vacía, para no parpadear en la recarga de cada minuto)
        if (divGrid && window.OrionCarga && !divGrid.querySelector(".captura")) {
            window.OrionCarga.en(divGrid, "Buscando capturas…");
        }

        fetch("/api/capturas?fecha=" + encodeURIComponent(fecha))
            .then(res => res.json())
            .then(data => {
                if (data.error) {
                    capturas = [];
                    if (divGrid) {
                        divGrid.textContent = "";
                        const p = document.createElement("p");
                        p.className = "aviso";
                        p.textContent = data.error;
                        divGrid.appendChild(p);
                    }
                    if (txtCuenta) txtCuenta.textContent = "0 capturas";
                    return;
                }

                capturas = data.capturas || [];

                if (Array.isArray(data.dias) && data.dias.length > 0 && inputFecha) {
                    inputFecha.min = data.dias[data.dias.length - 1];
                    inputFecha.max = data.dias[0];
                }

                actualizarCamaras(capturas);
                pintar();
            })
            .catch(err => {
                capturas = [];
                if (divGrid) {
                    divGrid.textContent = "";
                    const p = document.createElement("p");
                    p.className = "aviso";
                    p.textContent = "Error al cargar capturas: " + err.message;
                    divGrid.appendChild(p);
                }
                if (txtCuenta) txtCuenta.textContent = "0 capturas";
            });
    }

    // Eventos
    if (inputFecha) {
        inputFecha.addEventListener("change", cargar);
    }
    if (selCamara) {
        selCamara.addEventListener("change", pintar);
    }
    if (btnRecargar) {
        btnRecargar.addEventListener("click", cargar);
    }

    // Carga inicial al mostrar la pestaña
    document.addEventListener("pestana", function(e) {
        if (e.detail === "capturas") {
            const pedida = consumirFechaPedida();
            if (!inicializado) {
                inicializado = true;
                cargar();
            } else if (pedida) {
                cargar();
            }
        }
    });

    // Recarga periódica si la pestaña está visible y la fecha es hoy
    setInterval(function() {
        const pestana = document.getElementById("pestana-capturas");
        const fechaVal = inputFecha ? inputFecha.value : "";
        if (pestana && !pestana.hidden && fechaVal === hoyLocal()) {
            cargar();
        }
    }, 60000);
})();
