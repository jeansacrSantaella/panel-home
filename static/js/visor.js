(function () {
    "use strict";

    // Obtener elementos del DOM
    var dlg = document.getElementById("visor-foto");
    var img = document.getElementById("visor-img");
    var txt = document.getElementById("visor-texto");
    var btnAnt = document.getElementById("visor-ant");
    var btnSig = document.getElementById("visor-sig");
    var lblPos = document.getElementById("visor-pos");

    // Si falta alguno de los elementos requeridos, abortar
    if (!dlg || !img || !txt || !btnAnt || !btnSig || !lblPos) {
        return;
    }

    // Marco de la foto: muestra la carga mientras llega la imagen
    var marco = img.parentElement;
    function listo() { marco.classList.remove("cargando"); }
    img.addEventListener("load", listo);
    img.addEventListener("error", listo);

    // Reproductor de clips (se crea al primer uso)
    var video = null;
    function quitarVideo() {
        if (video) {
            video.pause();
            video.removeAttribute("src");
            video.load();
            video.hidden = true;
        }
    }
    dlg.addEventListener("close", quitarVideo);

    // Estado interno del visor
    var fotos = [];
    var indiceActual = 0;

    /**
     * Actualiza la imagen, el texto, la posición y el estado de navegación.
     * @param {number} i - Índice de la foto a mostrar.
     */
    function mostrar(i) {
        indiceActual = i;
        var actual = fotos[i];
        var total = fotos.length;

        quitarVideo();
        if (actual.video) {
            // clip: <video controls> con Range en el servidor
            if (!video) {
                video = document.createElement("video");
                video.controls = true;
                video.preload = "metadata";
                video.className = "visor-video";
                marco.insertBefore(video, img);
            }
            marco.classList.remove("cargando");
            img.hidden = true;
            video.hidden = false;
            video.setAttribute("aria-label", actual.texto || "Clip");
            video.src = actual.video;
        } else {
            img.hidden = false;
            marco.classList.add("cargando");  // anillo de carga hasta que llegue la foto
            img.src = "/api/foto?ref=" + encodeURIComponent(actual.ref);
            img.alt = actual.texto || "";
        }
        txt.textContent = actual.texto || "";
        lblPos.textContent = (i + 1) + " / " + total;

        if (total === 1) {
            btnAnt.hidden = true;
            btnSig.hidden = true;
            lblPos.hidden = true;
        } else {
            btnAnt.hidden = false;
            btnSig.hidden = false;
            lblPos.hidden = false;
        }

        btnAnt.disabled = (i === 0);
        btnSig.disabled = (i === total - 1);

        // Precarga de imagen anterior y siguiente
        if (i > 0 && !fotos[i - 1].video) {
            new Image().src = "/api/foto?ref=" + encodeURIComponent(fotos[i - 1].ref);
        }
        if (i < total - 1 && !fotos[i + 1].video) {
            new Image().src = "/api/foto?ref=" + encodeURIComponent(fotos[i + 1].ref);
        }
    }

    function irAnterior() {
        if (indiceActual > 0) {
            mostrar(indiceActual - 1);
        }
    }

    function irSiguiente() {
        if (indiceActual < fotos.length - 1) {
            mostrar(indiceActual + 1);
        }
    }

    // Listener de clic en botones de flecha
    btnAnt.addEventListener("click", irAnterior);
    btnSig.addEventListener("click", irSiguiente);

    // Navegación con teclado (flechas ← y →)
    dlg.addEventListener("keydown", function (e) {
        if (!dlg.open || e.target === video) {
            return;  // con el foco en el video, las flechas adelantan el clip
        }
        if (e.key === "ArrowLeft") {
            e.preventDefault();
            irAnterior();
        } else if (e.key === "ArrowRight") {
            e.preventDefault();
            irSiguiente();
        }
    });

    // Clic en el fondo (backdrop) cierra el visor
    dlg.addEventListener("click", function (e) {
        if (e.target === dlg) {
            dlg.close();
        }
    });

    // Gestión de gestos táctiles (swipe) sobre la imagen
    var touchStartX = 0;
    var touchStartY = 0;

    img.addEventListener("touchstart", function (e) {
        if (e.touches && e.touches.length > 0) {
            touchStartX = e.touches[0].clientX;
            touchStartY = e.touches[0].clientY;
        }
    }, { passive: true });

    img.addEventListener("touchend", function (e) {
        if (e.changedTouches && e.changedTouches.length > 0) {
            var diffX = e.changedTouches[0].clientX - touchStartX;
            var diffY = e.changedTouches[0].clientY - touchStartY;

            if (Math.abs(diffX) > 40 && Math.abs(diffX) > Math.abs(diffY)) {
                if (diffX < 0) {
                    irSiguiente();
                } else {
                    irAnterior();
                }
            }
        }
    }, { passive: true });

    /**
     * Abre el visor de fotos en el diálogo modal.
     * @param {string} ref - Referencia de la foto inicial.
     * @param {string} texto - Texto / descripción de la foto inicial.
     * @param {Array<{ref: string, texto: string}>} [lista] - Lista de fotos opcional.
     */
    window.abrirFoto = function (ref, texto, lista) {
        if (Array.isArray(lista) && lista.length > 0) {
            fotos = lista;
        } else {
            fotos = [{ ref: ref, texto: texto }];
        }

        var idx = fotos.findIndex(function (item) {
            return item.ref === ref;
        });

        var inicio = idx >= 0 ? idx : 0;
        mostrar(inicio);

        if (!dlg.open) {
            dlg.showModal();
        }
    };
})();
