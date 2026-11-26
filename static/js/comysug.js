// static/js/comysug.js — compra directa de combos con checkout en modal + WhatsApp
window.addEventListener("DOMContentLoaded", async () => {
  const cont = document.getElementById("combos");
  const modal = document.getElementById("modalCompraCombo");
  const vistaForm = document.getElementById("vistaFormCombo");
  const vistaComprobante = document.getElementById("vistaComprobanteCombo");
  const form = document.getElementById("formCompraCombo");
  const fechaInput = document.getElementById("comboFechaViaje");
  const btnConfirmar = document.getElementById("btnConfirmarCombo");

  fechaInput.min = fechaHoyISO();
  let comboActual = null;

  const cerrarModal = configurarModal(modal, () => {
    form.reset();
    vistaForm.hidden = false;
    vistaComprobante.hidden = true;
    vistaComprobante.innerHTML = "";
    comboActual = null;
  });

  function abrirCheckoutCombo(combo) {
    comboActual = combo;
    document.getElementById("modalComboTitulo").textContent = "Comprar combo";
    document.getElementById("checkoutComboId").value = combo.id;
    document.getElementById("checkoutComboNombre").textContent = combo.nombre;
    document.getElementById("checkoutComboDetalle").textContent = `Incluye: ${combo.detalle}`;
    document.getElementById("checkoutComboPrecio").textContent = `${formatearCOP(combo.precio)} COP (Precio fijo)`;

    form.reset();
    fechaInput.min = fechaHoyISO();
    vistaForm.hidden = false;
    vistaComprobante.hidden = true;
    vistaComprobante.innerHTML = "";
    modal.hidden = false;
    document.getElementById("comboClienteNombre").focus();
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!comboActual) return;

    const payload = {
      tipo: "combo",
      combo_id: comboActual.id,
      cliente_nombre: document.getElementById("comboClienteNombre").value.trim(),
      cliente_contacto: document.getElementById("comboClienteContacto").value.trim(),
      fecha_viaje: fechaInput.value,
    };

    if (!payload.fecha_viaje) {
      mostrarToast("Selecciona una fecha válida para tu viaje");
      return;
    }

    btnConfirmar.disabled = true;
    btnConfirmar.textContent = "Registrando compra...";
    try {
      const r = await apiPost("/api/compras", payload);
      if (r.ok && r.compra) {
        document.getElementById("modalComboTitulo").textContent = "Comprobante de compra";
        const waUrl = r.wa_url || construirUrlWhatsApp(null, r.compra);
        vistaForm.hidden = true;
        vistaComprobante.innerHTML =
          renderComprobanteHTML(r.compra, waUrl) +
          `<div class="acciones-stack">
             <button type="button" class="btn btn-outline" id="btnCerrarComprobanteCombo">Volver a combos</button>
           </div>`;
        vistaComprobante.hidden = false;
        document.getElementById("btnCerrarComprobanteCombo").onclick = cerrarModal;
        mostrarToast("¡Compra registrada! Reserva " + r.compra.codigo_reserva);
      } else {
        mostrarToast(r.error || "No se pudo completar la compra");
      }
    } catch {
      mostrarToast("Servidor no disponible");
    } finally {
      btnConfirmar.disabled = false;
      btnConfirmar.textContent = "Confirmar compra";
    }
  });

  try {
    const cs = await apiGet("/api/combos");
    cont.innerHTML = "";
    cs.forEach((c) => {
      const el = document.createElement("article");
      el.className = "combo";
      el.innerHTML = `
        <div>
          <span class="combo-badge">Precio fijo</span>
          <h3>${escapeHtml(c.nombre)}</h3>
          <p>${escapeHtml(c.detalle)}</p>
        </div>
        <div>
          <strong>${formatearCOP(c.precio)} COP</strong>
          <button type="button">Comprar combo</button>
        </div>
      `;
      el.querySelector("button").addEventListener("click", () => abrirCheckoutCombo(c));
      cont.appendChild(el);
    });
  } catch {
    mostrarToast("No se pudieron cargar los combos");
  }
});
