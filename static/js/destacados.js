// static/js/destacados.js — galería dinámica con modal de detalle y tarifa base
window.addEventListener("DOMContentLoaded", async () => {
  const cont = document.getElementById("galeria");
  const modal = document.getElementById("modalDestino");
  configurarModal(modal);

  function abrirModalDestino(d) {
    const img = document.getElementById("modalDestinoImg");
    img.src = `/static/img/${d.imagen}`;
    img.alt = d.nombre;
    document.getElementById("modalDestinoTitulo").textContent = d.nombre;
    document.getElementById("modalDestinoSubtitulo").textContent = d.subtitulo || "";
    document.getElementById("modalDestinoDescripcion").textContent =
      d.descripcion || "Descubre este increíble destino colombiano con Your Destiny.";
    document.getElementById("modalDestinoIncluye").textContent =
      d.incluye || "Bus confortable, aire acondicionado, Wi-Fi a bordo y seguro de pasajeros.";
    document.getElementById("modalDestinoPrecio").textContent =
      `${formatearCOP(d.precio_base)} COP`;

    const btn = document.getElementById("btnReservarDestino");
    btn.href = `/cuendesti.html?destino=${encodeURIComponent(d.nombre)}`;
    btn.textContent = `Reservar viaje a ${d.nombre}`;
    modal.hidden = false;
  }

  try {
    const lista = await apiGet("/api/destinos");
    cont.innerHTML = "";
    lista.forEach((d, i) => {
      const card = document.createElement("article");
      card.className = "card card-interactiva";
      card.tabIndex = 0;
      card.setAttribute("role", "button");
      card.setAttribute("aria-label", `Ver detalles y tarifa de ${d.nombre}`);
      card.style.animationDelay = i * 0.1 + "s";

      const resumenCorto = d.subtitulo || d.descripcion || "";
      card.innerHTML = `
        <div class="card-img-wrap">
          <img src="/static/img/${escapeHtml(d.imagen)}" alt="${escapeHtml(d.nombre)}">
          <span class="precio-pill">Desde ${formatearCOP(d.precio_base)}</span>
        </div>
        <div class="card-body">
          <h3>${escapeHtml(d.nombre)}</h3>
          <p>${escapeHtml(resumenCorto)}</p>
          <span class="card-cta">Ver detalles y tarifa →</span>
        </div>
      `;

      card.addEventListener("click", () => abrirModalDestino(d));
      card.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          abrirModalDestino(d);
        }
      });
      cont.appendChild(card);
    });
  } catch {
    mostrarToast("No se pudo cargar la galería de destinos");
  }
});
