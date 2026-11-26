// static/js/cuendesti.js — flujo en 2 pasos: Cotizar con tarifa real + Comprar con WhatsApp
window.addEventListener("DOMContentLoaded", () => {
  // Limpiar cualquier remanente viejo de la versión anterior
  localStorage.removeItem("comboSeleccionado");

  const form = document.getElementById("formViaje");
  const resumenBox = document.getElementById("resumen");
  const origenInput = document.getElementById("origen");
  const destinoInput = document.getElementById("destino");
  const fechaInput = document.getElementById("fecha");
  const btnCotizar = document.getElementById("btnCotizar");

  fechaInput.min = fechaHoyISO();

  // Precargar destino si el usuario llegó desde "Destinos destacados"
  const params = new URLSearchParams(window.location.search);
  const destinoParam = params.get("destino");
  if (destinoParam) {
    destinoInput.value = destinoParam;
    mostrarToast(`Destino precargado: ${destinoParam}`);
    origenInput.focus();
  }

  let cotizacionActual = null;

  function recopilarPreferencias() {
    const seleccionadas = Array.from(
      document.querySelectorAll('#prefsRapidas input[type="checkbox"]:checked')
    ).map((cb) => cb.value);
    const textoLibre = document.getElementById("preferencias").value.trim();
    if (textoLibre) seleccionadas.push(textoLibre);
    return seleccionadas.join(", ");
  }

  function renderTarjetaCotizacion(r) {
    const filasRecargos = (r.recargos || [])
      .map(
        (rec) => `
          <li>
            <span>Recargo: ${escapeHtml(rec.concepto)}</span>
            <span>+${formatearCOP(rec.valor)}</span>
          </li>`
      )
      .join("");

    const notaRuta = r.ruta_catalogo
      ? ""
      : `<p class="nota-pequena">Se aplicó nuestra tarifa estándar para rutas fuera del catálogo principal.</p>`;

    resumenBox.innerHTML = `
      <div class="tarjeta-cotizacion">
        <div class="tarjeta-header">
          <h3>Cotización lista</h3>
          <span class="codigo-badge">${escapeHtml(r.codigo || "#" + r.id)}</span>
        </div>
        <p>
          <strong>${escapeHtml(r.origen)} → ${escapeHtml(r.destino)}</strong><br>
          Fecha: ${escapeHtml(r.fecha)} · Pasajero: ${escapeHtml(r.nombre)}
        </p>
        <ul class="desglose-lista">
          <li>
            <span>Tarifa base (${escapeHtml(r.origen)} → ${escapeHtml(r.destino)})</span>
            <span>${formatearCOP(r.tarifa_base)}</span>
          </li>
          ${filasRecargos}
          <li class="desglose-total">
            <span>Total estimado</span>
            <span>${formatearCOP(r.total)} COP</span>
          </li>
        </ul>
        ${notaRuta}
        <div class="acciones-row">
          <button type="button" class="btn btn-primary" id="btnComprarTiquete">Comprar tiquete ahora</button>
          <button type="button" class="btn btn-outline" id="btnModificarCotizacion">Modificar datos</button>
        </div>
      </div>
    `;
    resumenBox.hidden = false;
    resumenBox.scrollIntoView({ behavior: "smooth", block: "nearest" });

    document
      .getElementById("btnComprarTiquete")
      .addEventListener("click", confirmarCompraTiquete);
    document.getElementById("btnModificarCotizacion").addEventListener("click", () => {
      origenInput.focus();
      form.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  }

  async function confirmarCompraTiquete() {
    if (!cotizacionActual) return;
    const btn = document.getElementById("btnComprarTiquete");
    btn.disabled = true;
    btn.textContent = "Confirmando compra...";

    try {
      const r = await apiPost("/api/compras", {
        tipo: "tiquete",
        cotizacion_id: cotizacionActual.id,
      });
      if (r.ok && r.compra) {
        const waUrl = r.wa_url || construirUrlWhatsApp(null, r.compra);
        resumenBox.innerHTML =
          renderComprobanteHTML(r.compra, waUrl) +
          `<div class="acciones-stack">
             <button type="button" class="btn btn-outline" id="btnNuevaCotizacion">Hacer otra cotización</button>
           </div>`;
        document.getElementById("btnNuevaCotizacion").addEventListener("click", () => {
          form.reset();
          fechaInput.min = fechaHoyISO();
          cotizacionActual = null;
          resumenBox.hidden = true;
          resumenBox.innerHTML = "";
          origenInput.focus();
        });
        mostrarToast("¡Tiquete comprado! Reserva " + r.compra.codigo_reserva);
      } else {
        mostrarToast(r.error || "No se pudo confirmar la compra");
        btn.disabled = false;
        btn.textContent = "Comprar tiquete ahora";
      }
    } catch {
      mostrarToast("Servidor no disponible");
      btn.disabled = false;
      btn.textContent = "Comprar tiquete ahora";
    }
  }

  // Paso 1: calcular cotización
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const datos = {
      origen: origenInput.value.trim(),
      destino: destinoInput.value.trim(),
      fecha: fechaInput.value,
      nombre: document.getElementById("nombre").value.trim(),
      contacto: document.getElementById("contacto").value.trim(),
      preferencias: recopilarPreferencias(),
    };

    if (!datos.fecha) {
      mostrarToast("Selecciona una fecha válida");
      return;
    }

    btnCotizar.disabled = true;
    btnCotizar.textContent = "Calculando tarifa...";
    try {
      const r = await apiPost("/api/cotizar", datos);
      if (r.ok && r.resumen) {
        cotizacionActual = r.resumen;
        renderTarjetaCotizacion(r.resumen);
        mostrarToast(`Tarifa calculada: ${formatearCOP(r.resumen.total)} COP`);
      } else {
        mostrarToast(r.error || "Error al cotizar el viaje");
      }
    } catch {
      mostrarToast("Servidor no disponible");
    } finally {
      btnCotizar.disabled = false;
      btnCotizar.textContent = "Calcular tarifa y cotizar";
    }
  });
});
