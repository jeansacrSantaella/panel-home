(function () {
  "use strict";

  // Elementos DOM del paso 1
  const formEntrar = document.getElementById("form-entrar");
  const inputUsuario = document.getElementById("usuario");
  const inputContrasena = document.getElementById("contrasena");
  const errEntrar = document.getElementById("error-entrar");
  const btnEntrar = document.getElementById("btn-entrar");

  // Elementos DOM del paso 2
  const formCambiar = document.getElementById("form-cambiar");
  const campoActual = document.getElementById("campo-actual");
  const inputActual = document.getElementById("actual");
  const inputNueva = document.getElementById("nueva");
  const fuerzaBarra = document.getElementById("fuerza-barra");
  const fuerzaTexto = document.getElementById("fuerza-texto");
  const inputConfirmar = document.getElementById("confirmar");
  const errCambiar = document.getElementById("error-cambiar");

  let claveActual = "";

  function mostrarError(elem, msg) {
    if (!elem) return;
    elem.textContent = msg;
    elem.hidden = false;
  }

  function ocultarError(elem) {
    if (!elem) return;
    elem.textContent = "";
    elem.hidden = true;
  }

  function enfoqueInicial() {
    if (inputUsuario && inputUsuario.value) {
      if (inputContrasena) inputContrasena.focus();
    } else if (inputUsuario) {
      inputUsuario.focus();
    }
  }

  // Verificar sesión existente al iniciar
  async function comprobarSesion() {
    try {
      const res = await fetch("/api/sesion", {
        headers: { "Content-Type": "application/json" },
        credentials: "same-origin"
      });
      if (res.status === 200) {
        const data = await res.json().catch(() => ({}));
        if (data.debe_cambiar) {
          if (formEntrar) formEntrar.hidden = true;
          if (formCambiar) formCambiar.hidden = false;
          if (campoActual) campoActual.hidden = false;
          if (inputActual) inputActual.focus();
        } else {
          location.replace("/");
        }
      } else {
        enfoqueInicial();
      }
    } catch (_) {
      enfoqueInicial();
    }
  }

  // Manejo de tasa límite 429
  function iniciarCuentaRegresiva(segundos, textoOriginal) {
    let seg = parseInt(segundos, 10) || 30;
    if (btnEntrar) btnEntrar.disabled = true;
    mostrarError(errEntrar, `Demasiados intentos. Espera ${seg} s.`);

    const timer = setInterval(() => {
      seg--;
      if (seg <= 0) {
        clearInterval(timer);
        if (btnEntrar) {
          btnEntrar.disabled = false;
          btnEntrar.textContent = textoOriginal;
        }
        ocultarError(errEntrar);
      } else {
        mostrarError(errEntrar, `Demasiados intentos. Espera ${seg} s.`);
      }
    }, 1000);
  }

  // Formulario Paso 1: Login
  if (formEntrar) {
    formEntrar.addEventListener("submit", async (e) => {
      e.preventDefault();
      ocultarError(errEntrar);

      const usr = inputUsuario ? inputUsuario.value.trim() : "";
      const pwd = inputContrasena ? inputContrasena.value : "";

      if (!usr || !pwd) {
        mostrarError(errEntrar, "Escribe tu usuario y contraseña");
        return;
      }

      const textoOriginal = btnEntrar ? btnEntrar.textContent : "";
      if (btnEntrar) {
        btnEntrar.disabled = true;
        btnEntrar.textContent = "Entrando…";
      }

      try {
        const res = await fetch("/api/login", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "same-origin",
          body: JSON.stringify({ usuario: usr, contrasena: pwd })
        });
        const data = await res.json().catch(() => ({}));

        if (res.status === 200) {
          if (data.debe_cambiar) {
            claveActual = pwd;
            formEntrar.hidden = true;
            if (formCambiar) formCambiar.hidden = false;
            if (campoActual) campoActual.hidden = true;
            if (inputNueva) inputNueva.focus();
          } else {
            location.replace("/");
          }
        } else if (res.status === 401) {
          mostrarError(errEntrar, data.error || "Usuario o contraseña incorrectos");
          if (inputContrasena) {
            inputContrasena.value = "";
            inputContrasena.focus();
          }
          if (btnEntrar) {
            btnEntrar.disabled = false;
            btnEntrar.textContent = textoOriginal;
          }
        } else if (res.status === 429) {
          iniciarCuentaRegresiva(data.segundos, textoOriginal);
        } else {
          mostrarError(errEntrar, data.error || "No pude conectar con el panel");
          if (btnEntrar) {
            btnEntrar.disabled = false;
            btnEntrar.textContent = textoOriginal;
          }
        }
      } catch (_) {
        mostrarError(errEntrar, "No pude conectar con el panel");
        if (btnEntrar) {
          btnEntrar.disabled = false;
          btnEntrar.textContent = textoOriginal;
        }
      }
    });
  }

  // Indicador de fuerza de contraseña
  if (inputNueva) {
    inputNueva.addEventListener("input", () => {
      const val = inputNueva.value;
      let puntaje = 0;

      if (val.length >= 8) puntaje++;
      if (val.length >= 12) puntaje++;
      if (/[a-zA-Z]/.test(val) && /[0-9]/.test(val)) puntaje++;
      if (/[^a-zA-Z0-9]/.test(val) || (/[a-z]/.test(val) && /[A-Z]/.test(val))) puntaje++;

      const nivel = puntaje <= 1 ? "debil" : (puntaje === 2 ? "media" : "buena");

      if (fuerzaBarra) {
        fuerzaBarra.style.width = (puntaje * 25) + "%";
        fuerzaBarra.dataset.nivel = nivel;
      }

      if (fuerzaTexto) {
        if (val.length < 8) {
          fuerzaTexto.textContent = "Muy corta: mínimo 8 caracteres";
        } else if (nivel === "debil") {
          fuerzaTexto.textContent = "Débil";
        } else if (nivel === "media") {
          fuerzaTexto.textContent = "Aceptable";
        } else {
          fuerzaTexto.textContent = "Buena";
        }
      }
    });
  }

  // Formulario Paso 2: Cambiar contraseña
  if (formCambiar) {
    formCambiar.addEventListener("submit", async (e) => {
      e.preventDefault();
      ocultarError(errCambiar);

      const nueva = inputNueva ? inputNueva.value : "";
      const confirmar = inputConfirmar ? inputConfirmar.value : "";
      const actual = claveActual || (inputActual ? inputActual.value : "");

      if (!actual) {
        mostrarError(errCambiar, "Escribe tu contraseña actual");
        return;
      }
      if (nueva.length < 8) {
        mostrarError(errCambiar, "La nueva contraseña debe tener al menos 8 caracteres");
        return;
      }
      if (nueva === "1234") {
        mostrarError(errCambiar, "La contraseña no puede ser 1234");
        return;
      }
      if (nueva !== confirmar) {
        mostrarError(errCambiar, "Las contraseñas no coinciden");
        return;
      }

      try {
        const res = await fetch("/api/contrasena", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "same-origin",
          body: JSON.stringify({ actual, nueva })
        });
        const data = await res.json().catch(() => ({}));

        if (res.status === 200) {
          location.replace("/");
        } else {
          mostrarError(errCambiar, data.error || "No se pudo cambiar la contraseña");
        }
      } catch (_) {
        mostrarError(errCambiar, "No pude conectar con el panel");
      }
    });
  }

  // Alternar visibilidad de contraseña
  document.querySelectorAll(".ver-clave").forEach((btn) => {
    btn.addEventListener("click", () => {
      const targetId = btn.getAttribute("data-para");
      const targetInput = document.getElementById(targetId);
      if (!targetInput) return;

      const esPass = targetInput.type === "password";
      targetInput.type = esPass ? "text" : "password";
      btn.setAttribute("aria-pressed", esPass ? "true" : "false");
      btn.setAttribute("aria-label", esPass ? "Ocultar contraseña" : "Mostrar contraseña");
    });
  });

  comprobarSesion();
})();
