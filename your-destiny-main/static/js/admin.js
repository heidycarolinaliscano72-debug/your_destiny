// static/js/admin.js — panel protegido: compras, cotizaciones, usuarios, combos y destinos
(async () => {
  // --- Protección: solo administradores ---
  let me;
  try {
    me = await apiGet("/api/me");
  } catch {
    mostrarToast("Servidor no disponible");
    return;
  }
  if (!me.user || me.user.rol !== "admin") {
    document.querySelector("main").innerHTML =
      `<h1>403 — No autorizado</h1><p>Debes iniciar sesión como administrador en la <a href="/">página principal</a>.</p>`;
    return;
  }

  // --- Pestañas ---
  document.querySelectorAll(".tab").forEach((tab) => {
    tab.onclick = () => {
      document.querySelectorAll(".tab").forEach((t) => t.classList.remove("activo"));
      tab.classList.add("activo");
      document.querySelectorAll(".panel-admin").forEach((p) => (p.hidden = true));
      document.getElementById("sec-" + tab.dataset.sec).hidden = false;
    };
  });

  // --- Compras ---
  async function cargarCompras() {
    const filas = await apiGet("/api/admin/compras");
    const tbody = document.querySelector("#tablaCompras tbody");
    if (!filas.length) {
      tbody.innerHTML = `<tr><td colspan="8">Aún no hay compras registradas.</td></tr>`;
      return;
    }
    tbody.innerHTML = filas
      .map(
        (c) => `
      <tr>
        <td><strong>${escapeHtml(c.codigo_reserva)}</strong></td>
        <td><span class="badge-tipo ${escapeHtml(c.tipo)}">${escapeHtml(c.tipo)}</span></td>
        <td>${escapeHtml(c.cliente_nombre)}</td>
        <td>${escapeHtml(c.cliente_contacto)}</td>
        <td>${escapeHtml(c.detalle)}</td>
        <td>${escapeHtml(c.fecha_viaje)}</td>
        <td><strong>${formatearCOP(c.total)}</strong></td>
        <td><select data-id="${c.id}" class="sel-estado-compra">
          ${["confirmada", "pendiente", "cancelada"]
            .map((e) => `<option ${e === c.estado ? "selected" : ""}>${e}</option>`)
            .join("")}
        </select></td>
      </tr>`
      )
      .join("");
    tbody.querySelectorAll(".sel-estado-compra").forEach((sel) => {
      sel.onchange = async () => {
        try {
          const r = await apiPatch(`/api/admin/compras/${sel.dataset.id}`, {
            estado: sel.value,
          });
          mostrarToast(r.ok ? "Estado de compra actualizado" : r.error || "Error");
        } catch {
          mostrarToast("Servidor no disponible");
        }
      };
    });
  }

  // --- Cotizaciones ---
  async function cargarCotizaciones() {
    const filas = await apiGet("/api/admin/cotizaciones");
    const tbody = document.querySelector("#tablaCotizaciones tbody");
    if (!filas.length) {
      tbody.innerHTML = `<tr><td colspan="6">Aún no hay cotizaciones registradas.</td></tr>`;
      return;
    }
    tbody.innerHTML = filas
      .map(
        (c) => `
      <tr>
        <td>${escapeHtml(c.codigo || "#" + c.id)}</td>
        <td>${escapeHtml(c.nombre)}</td>
        <td>${escapeHtml(c.origen)} → ${escapeHtml(c.destino)}</td>
        <td>${escapeHtml(c.fecha_viaje)}</td>
        <td><strong>${formatearCOP(c.total)}</strong></td>
        <td><select data-id="${c.id}" class="sel-estado">
          ${["pendiente", "confirmada", "cancelada"]
            .map((e) => `<option ${e === c.estado ? "selected" : ""}>${e}</option>`)
            .join("")}
        </select></td>
      </tr>`
      )
      .join("");
    tbody.querySelectorAll(".sel-estado").forEach((sel) => {
      sel.onchange = async () => {
        try {
          const r = await apiPatch(`/api/admin/cotizaciones/${sel.dataset.id}`, {
            estado: sel.value,
          });
          mostrarToast(r.ok ? "Estado actualizado" : r.error || "Error");
        } catch {
          mostrarToast("Servidor no disponible");
        }
      };
    });
  }

  // --- Usuarios ---
  async function cargarUsuarios() {
    const filas = await apiGet("/api/admin/usuarios");
    const tbody = document.querySelector("#tablaUsuarios tbody");
    tbody.innerHTML = filas
      .map(
        (u) => `
      <tr>
        <td>${u.id}</td>
        <td>${escapeHtml(u.usuario)}</td>
        <td>${escapeHtml(u.rol)}</td>
        <td>${escapeHtml((u.creado_en || "").slice(0, 10))}</td>
        <td><button class="btn-peligro" data-id="${u.id}">Eliminar</button></td>
      </tr>`
      )
      .join("");
    tbody.querySelectorAll(".btn-peligro").forEach((btn) => {
      btn.onclick = async () => {
        if (!confirm("¿Eliminar este usuario?")) return;
        try {
          const r = await apiDelete(`/api/admin/usuarios/${btn.dataset.id}`);
          mostrarToast(r.ok ? "Usuario eliminado" : r.error || "Error");
          if (r.ok) cargarUsuarios();
        } catch {
          mostrarToast("Servidor no disponible");
        }
      };
    });
  }

  document.getElementById("formUsuario").addEventListener("submit", async (e) => {
    e.preventDefault();
    try {
      const r = await apiPost("/api/admin/usuarios", {
        usuario: document.getElementById("nuevoUsuario").value,
        password: document.getElementById("nuevaClave").value,
        rol: document.getElementById("nuevoRol").value,
      });
      mostrarToast(r.ok ? "Usuario creado" : r.error || "Error");
      if (r.ok) {
        e.target.reset();
        cargarUsuarios();
      }
    } catch {
      mostrarToast("Servidor no disponible");
    }
  });

  // --- Combos ---
  async function cargarCombos() {
    const filas = await apiGet("/api/combos");
    const tbody = document.querySelector("#tablaCombos tbody");
    tbody.innerHTML = filas
      .map(
        (c) => `
      <tr>
        <td>${c.id}</td>
        <td>${escapeHtml(c.nombre)}</td>
        <td>${escapeHtml(c.detalle)}</td>
        <td>${formatearCOP(c.precio)}</td>
        <td>
          <button class="btn-editar" data-id="${c.id}">Editar</button>
          <button class="btn-peligro" data-id="${c.id}">Eliminar</button>
        </td>
      </tr>`
      )
      .join("");
    tbody.querySelectorAll(".btn-editar").forEach((btn) => {
      btn.onclick = () => {
        const c = filas.find((x) => x.id == btn.dataset.id);
        document.getElementById("comboId").value = c.id;
        document.getElementById("comboNombre").value = c.nombre;
        document.getElementById("comboDetalle").value = c.detalle;
        document.getElementById("comboPrecio").value = c.precio;
        document.getElementById("btnGuardarCombo").textContent = "Guardar cambios";
        document.getElementById("btnCancelarCombo").hidden = false;
      };
    });
    tbody.querySelectorAll(".btn-peligro").forEach((btn) => {
      btn.onclick = async () => {
        if (!confirm("¿Eliminar este combo?")) return;
        try {
          const r = await apiDelete(`/api/admin/combos/${btn.dataset.id}`);
          mostrarToast(r.ok ? "Combo eliminado" : r.error || "Error");
          if (r.ok) cargarCombos();
        } catch {
          mostrarToast("Servidor no disponible");
        }
      };
    });
  }

  function limpiarFormCombo() {
    document.getElementById("formCombo").reset();
    document.getElementById("comboId").value = "";
    document.getElementById("btnGuardarCombo").textContent = "Crear combo";
    document.getElementById("btnCancelarCombo").hidden = true;
  }

  document.getElementById("btnCancelarCombo").onclick = limpiarFormCombo;

  document.getElementById("formCombo").addEventListener("submit", async (e) => {
    e.preventDefault();
    const id = document.getElementById("comboId").value;
    const datos = {
      nombre: document.getElementById("comboNombre").value,
      detalle: document.getElementById("comboDetalle").value,
      precio: Number(document.getElementById("comboPrecio").value),
    };
    try {
      const r = id
        ? await apiPatch(`/api/admin/combos/${id}`, datos)
        : await apiPost("/api/admin/combos", datos);
      mostrarToast(r.ok ? "Combo guardado" : r.error || "Error");
      if (r.ok) {
        limpiarFormCombo();
        cargarCombos();
      }
    } catch {
      mostrarToast("Servidor no disponible");
    }
  });

  // --- Destinos ---
  async function cargarDestinos() {
    const filas = await apiGet("/api/destinos");
    const tbody = document.querySelector("#tablaDestinos tbody");
    tbody.innerHTML = filas
      .map(
        (d) => `
      <tr>
        <td>${d.id}</td>
        <td>${escapeHtml(d.nombre)}</td>
        <td>${escapeHtml(d.subtitulo)}</td>
        <td>${formatearCOP(d.precio_base)}</td>
        <td>${escapeHtml(d.imagen)}</td>
        <td>
          <button class="btn-editar" data-id="${d.id}">Editar</button>
          <button class="btn-peligro" data-id="${d.id}">Eliminar</button>
        </td>
      </tr>`
      )
      .join("");
    tbody.querySelectorAll(".btn-editar").forEach((btn) => {
      btn.onclick = () => {
        const d = filas.find((x) => x.id == btn.dataset.id);
        document.getElementById("destinoId").value = d.id;
        document.getElementById("destinoNombre").value = d.nombre;
        document.getElementById("destinoSubtitulo").value = d.subtitulo || "";
        document.getElementById("destinoImagen").value = d.imagen;
        document.getElementById("destinoPrecioBase").value = d.precio_base;
        document.getElementById("destinoIncluye").value = d.incluye || "";
        document.getElementById("destinoDescripcion").value = d.descripcion || "";
        document.getElementById("btnGuardarDestino").textContent = "Guardar cambios";
        document.getElementById("btnCancelarDestino").hidden = false;
      };
    });
    tbody.querySelectorAll(".btn-peligro").forEach((btn) => {
      btn.onclick = async () => {
        if (!confirm("¿Eliminar este destino?")) return;
        try {
          const r = await apiDelete(`/api/admin/destinos/${btn.dataset.id}`);
          mostrarToast(r.ok ? "Destino eliminado" : r.error || "Error");
          if (r.ok) cargarDestinos();
        } catch {
          mostrarToast("Servidor no disponible");
        }
      };
    });
  }

  function limpiarFormDestino() {
    document.getElementById("formDestino").reset();
    document.getElementById("destinoId").value = "";
    document.getElementById("btnGuardarDestino").textContent = "Crear destino";
    document.getElementById("btnCancelarDestino").hidden = true;
  }

  document.getElementById("btnCancelarDestino").onclick = limpiarFormDestino;

  document.getElementById("formDestino").addEventListener("submit", async (e) => {
    e.preventDefault();
    const id = document.getElementById("destinoId").value;
    const datos = {
      nombre: document.getElementById("destinoNombre").value,
      subtitulo: document.getElementById("destinoSubtitulo").value,
      imagen: document.getElementById("destinoImagen").value,
      precio_base: Number(document.getElementById("destinoPrecioBase").value),
      incluye: document.getElementById("destinoIncluye").value,
      descripcion: document.getElementById("destinoDescripcion").value,
    };
    try {
      const r = id
        ? await apiPatch(`/api/admin/destinos/${id}`, datos)
        : await apiPost("/api/admin/destinos", datos);
      mostrarToast(r.ok ? "Destino guardado" : r.error || "Error");
      if (r.ok) {
        limpiarFormDestino();
        cargarDestinos();
      }
    } catch {
      mostrarToast("Servidor no disponible");
    }
  });

  // --- Carga inicial ---
  try {
    await Promise.all([
      cargarCompras(),
      cargarCotizaciones(),
      cargarUsuarios(),
      cargarCombos(),
      cargarDestinos(),
    ]);
  } catch {
    mostrarToast("Servidor no disponible");
  }
})();
