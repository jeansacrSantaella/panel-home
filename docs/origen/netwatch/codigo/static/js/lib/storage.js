// Tolera el bloqueo de localStorage en modo privado o por la configuración del navegador.
export const storage = {
  get(key) {
    try { return localStorage.getItem(key); } catch { return null; }
  },
  set(key, value) {
    try { localStorage.setItem(key, value); } catch { /* No guardes la preferencia. */ }
  },
  remove(key) {
    try { localStorage.removeItem(key); } catch { /* No hay nada que borrar. */ }
  },
};
