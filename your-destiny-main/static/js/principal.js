// static/js/principal.js — login real (sin credenciales en cliente)
window.addEventListener("DOMContentLoaded", () => {
  const modal = document.getElementById("modalLogin");
  const cerrarModal = configurarModal(modal);

  document.getElementById("btnAbrirLogin").addEventListener("click", () => {
    modal.hidden = false;
    document.getElementById("usuario").focus();
  });

  document.getElementById("loginForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    try {
      const r = await apiPost("/api/login", {
        usuario: document.getElementById("usuario").value.trim(),
        password: document.getElementById("password").value,
      });
      if (r.ok) {
        cerrarModal();
        mostrarToast("Bienvenido, " + r.usuario);
        if (r.rol === "admin") {
          setTimeout(() => {
            location.href = "/admin.html";
          }, 500);
        } else {
          location.reload();
        }
      } else {
        mostrarToast(r.error || "Credenciales inválidas");
      }
    } catch {
      mostrarToast("Servidor no disponible");
    }
  });
});
