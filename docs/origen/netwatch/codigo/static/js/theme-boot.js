// Cárgalo en <head> sin defer para aplicar el tema antes del primer pintado.
(function () {
  try {
    var theme = localStorage.getItem("netwatch-dashboard-theme");
    if (theme === "light" || theme === "dark") document.documentElement.dataset.theme = theme;
  } catch (e) { /* Conserva el tema del sistema. */ }
})();
