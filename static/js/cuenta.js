(function () {
  "use strict";

  // Redirigir a login si cualquier petición a /api/ retorna 401
  const originalFetch = window.fetch;
  window.fetch = async function (...args) {
    const res = await originalFetch.apply(this, args);
    const url = typeof args[0] === "string" ? args[0] : (args[0] && args[0].url ? args[0].url : String(args[0] || ""));
    if (res.status === 401 && (url.startsWith("/api/") || url.startsWith(location.origin + "/api/"))) {
      location.replace("/login");
    }
    return res;
  };

  let temporizadorAviso = null;

  // Muestra mensaje temporal en el aviso flotante por 3 segundos
  function mostrarAviso(texto) {
    const el = document.getElementById("aviso-flotante");
    if (!el) return;
    el.textContent = texto;
    el.hidden = false;
    if (temporizadorAviso) clearTimeout(temporizadorAviso);
    temporizadorAviso = setTimeout(() => {
      el.hidden = true;
    }, 3000);
  }

  // Consulta el estado de la sesión activa y actualiza la UI
  async function consultarSesion() {
    try {
      const res = await fetch("/api/sesion", { credentials: "same-origin" });
      if (!res.ok) return;
      const data = await res.json();
      const nombreEl = document.getElementById("cuenta-nombre");
      if (nombreEl) nombreEl.textContent = data.usuario || "";
      const avisoEl = document.getElementById("aviso-contrasena");
      if (avisoEl) avisoEl.hidden = !data.debe_cambiar;
    } catch (_) {}
  }

  document.addEventListener("DOMContentLoaded", () => {
    consultarSesion();
    setInterval(consultarSesion, 60000);

    const btnCuenta = document.getElementById("btn-cuenta");
    const menuCuenta = document.getElementById("menu-cuenta");
    const accionSalir = document.getElementById("accion-salir");
    const accionCambiar = document.getElementById("accion-cambiar");
    const avisoCambiar = document.getElementById("aviso-cambiar");
    const dlgContrasena = document.getElementById("dlg-contrasena");
    const formClave = document.getElementById("form-clave");
    const claveCancelar = document.getElementById("clave-cancelar");

    function cerrarMenu() {
      if (menuCuenta) menuCuenta.hidden = true;
      if (btnCuenta) btnCuenta.setAttribute("aria-expanded", "false");
    }

    // Dentro de la app Android (puente PleyadesApp): elegir o editar la dirección del panel
    const accionServidor = document.getElementById("accion-servidor");
    if (accionServidor && window.PleyadesApp) {
      accionServidor.hidden = false;
      accionServidor.addEventListener("click", () => { cerrarMenu(); window.PleyadesApp.servidores(); });
    }

    if (btnCuenta && menuCuenta) {
      btnCuenta.addEventListener("click", () => {
        const estaOculto = menuCuenta.hidden;
        menuCuenta.hidden = !estaOculto;
        btnCuenta.setAttribute("aria-expanded", estaOculto ? "true" : "false");
        if (estaOculto) {
          const primerBoton = menuCuenta.querySelector("button");
          if (primerBoton) primerBoton.focus();
        }
      });

      menuCuenta.addEventListener("keydown", (e) => {
        const botones = Array.from(menuCuenta.querySelectorAll("button"));
        const idx = botones.indexOf(document.activeElement);
        if (e.key === "ArrowDown") {
          e.preventDefault();
          const sig = (idx + 1) % botones.length;
          botones[sig]?.focus();
        } else if (e.key === "ArrowUp") {
          e.preventDefault();
          const prev = (idx - 1 + botones.length) % botones.length;
          botones[prev]?.focus();
        }
      });

      document.addEventListener("keydown", (e) => {
        if (e.key === "Escape" && !menuCuenta.hidden) {
          cerrarMenu();
          btnCuenta.focus();
        }
      });

      document.addEventListener("click", (e) => {
        if (!e.target.closest(".cuenta")) {
          cerrarMenu();
        }
      });
    }

    if (accionSalir) {
      accionSalir.addEventListener("click", async () => {
        cerrarMenu();
        try {
          // el servidor solo acepta POST con JSON (protección contra peticiones forjadas)
          await fetch("/api/logout", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            credentials: "same-origin",
            body: "{}",
          });
        } catch (_) {}
        location.replace("/login");
      });
    }

    function abrirModalClave() {
      cerrarMenu();
      if (!dlgContrasena) return;
      const actualInput = document.getElementById("clave-actual");
      const nuevaInput = document.getElementById("clave-nueva");
      const confirmInput = document.getElementById("clave-confirmar");
      const errorEl = document.getElementById("clave-error");

      if (actualInput) actualInput.value = "";
      if (nuevaInput) nuevaInput.value = "";
      if (confirmInput) confirmInput.value = "";
      if (errorEl) {
        errorEl.textContent = "";
        errorEl.hidden = true;
      }
      dlgContrasena.showModal();
      if (actualInput) actualInput.focus();
    }

    if (accionCambiar) accionCambiar.addEventListener("click", abrirModalClave);
    if (avisoCambiar) avisoCambiar.addEventListener("click", abrirModalClave);

    if (claveCancelar && dlgContrasena) {
      claveCancelar.addEventListener("click", () => dlgContrasena.close());
    }

    if (formClave) {
      formClave.addEventListener("submit", async (e) => {
        e.preventDefault();
        const actualInput = document.getElementById("clave-actual");
        const nuevaInput = document.getElementById("clave-nueva");
        const confirmInput = document.getElementById("clave-confirmar");
        const errorEl = document.getElementById("clave-error");
        const submitBtn = formClave.querySelector('button[type="submit"]');

        const actual = actualInput ? actualInput.value : "";
        const nueva = nuevaInput ? nuevaInput.value : "";
        const confirmar = confirmInput ? confirmInput.value : "";

        const mostrarErrorForm = (msg) => {
          if (errorEl) {
            errorEl.textContent = msg;
            errorEl.hidden = false;
          }
        };

        if (!actual) {
          mostrarErrorForm("Escribe tu contraseña actual");
          return;
        }
        if (nueva.length < 8) {
          mostrarErrorForm("La nueva contraseña debe tener al menos 8 caracteres");
          return;
        }
        if (nueva !== confirmar) {
          mostrarErrorForm("Las contraseñas no coinciden");
          return;
        }

        if (errorEl) errorEl.hidden = true;
        if (submitBtn) submitBtn.disabled = true;

        try {
          const res = await fetch("/api/contrasena", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            credentials: "same-origin",
            body: JSON.stringify({ actual, nueva }),
          });
          const data = await res.json().catch(() => ({}));

          if (res.ok) {
            if (dlgContrasena) dlgContrasena.close();
            const avisoEl = document.getElementById("aviso-contrasena");
            if (avisoEl) avisoEl.hidden = true;
            mostrarAviso("Contraseña actualizada");
          } else {
            mostrarErrorForm(data.error || "Error al actualizar la contraseña");
          }
        } catch (_) {
          mostrarErrorForm("Error de conexión");
        } finally {
          if (submitBtn) submitBtn.disabled = false;
        }
      });
    }
  });
})();
