// static/js/ui.js — utilidades compartidas de DOM, formato, modales y WhatsApp
function escapeHtml(texto) {
  return String(texto ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function formatearCOP(valor) {
  const num = Math.round(Number(valor) || 0);
  return "$" + num.toLocaleString("es-CO");
}

function fechaHoyISO() {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function mostrarToast(msg) {
  let t = document.getElementById("toast");
  if (!t) {
    t = document.createElement("div");
    t.id = "toast";
    document.body.appendChild(t);
  }
  t.textContent = msg;
  t.classList.add("visible");
  clearTimeout(t._timer);
  t._timer = setTimeout(() => t.classList.remove("visible"), 3200);
}

function construirUrlWhatsApp(numero, compra) {
  const limpio = String(numero || "573227618659").replace(/\D/g, "");
  const totalFormateado = Math.round(Number(compra.total) || 0).toLocaleString("es-CO");
  const texto =
    `Hola, acabo de comprar en Your Destiny:\n` +
    `Reserva: ${compra.codigo_reserva}\n` +
    `Pasajero: ${compra.cliente_nombre}\n` +
    `Plan/Ruta: ${compra.detalle}\n` +
    `Fecha: ${compra.fecha_viaje}\n` +
    `Total: $${totalFormateado} COP`;
  return `https://wa.me/${limpio}?text=${encodeURIComponent(texto)}`;
}

function renderComprobanteHTML(compra, waUrl) {
  const tipoTexto = compra.tipo === "combo" ? "Combo promocional" : "Tiquete de viaje";
  const prefHtml = compra.preferencias
    ? `<div><span>Preferencias</span><strong>${escapeHtml(compra.preferencias)}</strong></div>`
    : "";
  return `
    <div class="comprobante">
      <div class="tarjeta-header">
        <h3>¡Compra confirmada!</h3>
        <span class="codigo-badge">${escapeHtml(compra.codigo_reserva)}</span>
      </div>
      <p>Tu reserva quedó registrada a nombre de <strong>${escapeHtml(compra.cliente_nombre)}</strong>.</p>
      <div class="comprobante-datos">
        <div><span>Tipo</span><strong>${tipoTexto}</strong></div>
        <div><span>Fecha de viaje</span><strong>${escapeHtml(compra.fecha_viaje)}</strong></div>
        <div><span>Plan / Ruta</span><strong>${escapeHtml(compra.detalle)}</strong></div>
        <div><span>Contacto</span><strong>${escapeHtml(compra.cliente_contacto)}</strong></div>
        ${prefHtml}
        <div><span>Estado</span><strong>${escapeHtml(compra.estado || "confirmada")}</strong></div>
      </div>
      <div class="comprobante-total">
        <span>Total pagado</span>
        <strong>${formatearCOP(compra.total)} COP</strong>
      </div>
      <div class="acciones-stack">
        <a class="btn btn-whatsapp" href="${escapeHtml(waUrl)}" target="_blank" rel="noopener noreferrer">
          Notificar compra por WhatsApp
        </a>
      </div>
      <p class="nota-pequena">Pulsa el botón para abrir WhatsApp con el resumen de tu reserva listo para enviar.</p>
    </div>
  `;
}

function configurarModal(modalEl, onClose) {
  if (!modalEl) return;
  const cerrar = () => {
    modalEl.hidden = true;
    if (typeof onClose === "function") onClose();
  };
  modalEl.addEventListener("click", (e) => {
    if (e.target === modalEl) cerrar();
  });
  const btnClose = modalEl.querySelector(".modal-close");
  if (btnClose) btnClose.addEventListener("click", cerrar);
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !modalEl.hidden) cerrar();
  });
  return cerrar;
}

// Mostrar enlace a Panel Admin y Cerrar sesión en el nav cuando el usuario está autenticado
window.addEventListener("DOMContentLoaded", async () => {
  const navUl = document.querySelector("nav ul");
  if (!navUl || typeof apiGet !== "function") return;
  try {
    const me = await apiGet("/api/me");
    if (me && me.user) {
      if (me.user.rol === "admin" && !navUl.querySelector('a[href="/admin.html"]')) {
        const liAdmin = document.createElement("li");
        liAdmin.innerHTML = `<a href="/admin.html">Panel Admin</a>`;
        navUl.appendChild(liAdmin);
      }
      if (!navUl.querySelector(".nav-logout")) {
        const liOut = document.createElement("li");
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "nav-logout";
        btn.textContent = `Salir (${me.user.usuario})`;
        btn.onclick = async () => {
          await apiPost("/api/logout", {});
          location.href = "/";
        };
        liOut.appendChild(btn);
        navUl.appendChild(liOut);
      }
    }
  } catch {
    /* silencioso */
  }
});
