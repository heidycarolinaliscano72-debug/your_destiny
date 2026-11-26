# 🚌 ESPECIFICACIÓN MAESTRA — "Your Destiny" v2 (Python + MySQL)

**Tipo de documento:** orden de trabajo autocontenida para agente de código.
**Meta:** migrar el sitio estático a un sistema full-stack **en una sola iteración**, sin reabrir decisiones.
**Lectura obligatoria:** leer completo antes de escribir código y ejecutar el plan de §9 en orden.

> Convención: **[DEBE]** = obligatorio · **[DEBERÍA]** = recomendado · texto normal = informativo.

---

## 0. Reglas generales

1. ⛔ **NO usar Firebase.** Todo backend es Python (Flask) + MySQL.
2. [DEBE] Conservar nombres de las 5 páginas originales, estética, colores y animaciones existentes.
3. [DEBE] Separación de responsabilidades en frontend (ver §7).
4. [DEBE] Auto-verificar con el checklist de §10 **antes** de entregar. Nada se entrega en rojo.
5. Si la carpeta de trabajo **no** contiene el proyecto estático original, generar las páginas siguiendo §7.2.

---

## 1. Estado actual (verificado sobre el código fuente)

Sitio estático HTML/CSS/JS puro (sin build) de una agencia ficticia de buses de Colombia ("Your Destiny", autor: Angel Milan Trejos).

| Página | Función |
|---|---|
| `principal.html` | Landing con modal de login (mockup) y navegación |
| `sobrenoso.html` | "Sobre nosotros" institucional estático |
| `cuendesti.html` | Formulario de cotización de viaje |
| `destacados.html` | Galería de 6 destinos con animación de aparición secuencial |
| `comysug.html` | 3 combos/promos → guarda en `localStorage` y redirige al formulario |

### 1.1 Bugs confirmados y su corrección exigida

| # | Bug | Origen | Corrección [DEBE] |
|---|---|---|---|
| 1 | `ReferenceError`: valida con `fecha` nunca declarada (el valor está en `fechaRaw`) | `cuendesti.js` | Leer el valor del `<input type="date">` directamente; el servidor re-valida |
| 2 | Imágenes rotas: archivos con doble extensión (`Bogota.jpg.jpeg`…) referenciados sin `.jpeg` | `destacados.html` + `img/` | Renombrar archivos (§7.6) y galería renderizada desde BD |
| 3 | Credenciales en texto plano en el cliente (`admin/1234`, `a/a`) | `principal.js` | Eliminar; autenticación real con hash en servidor |
| 4 | Sin responsive (cero `@media queries`) | CSS | Añadir breakpoints (§7.5) |
| 5 | Formulario no persiste (`procesarViaje()` solo simula) | `cuendesti.js` | `POST /api/cotizaciones` → tabla `cotizaciones` |

---

## 2. Alcance

**Dentro:** backend Flask + MySQL · auth real con sesión · persistencia de cotizaciones · destinos y combos servidos desde BD · panel admin con gestión de estados · responsive · README final.

**Fuera:** registro público de usuarios · envío de emails · pasarelas de pago · despliegue/producción · cualquier framework distinto a Flask.

---

## 3. Decisiones cerradas (no discutir)

| Decisión | Detalle |
|---|---|
| Backend | Python + Flask |
| BD | MySQL, base `your_destiny`, charset `utf8mb4` |
| Auth | Sesión Flask + `werkzeug.security` (hash en servidor) |
| Datos dinámicos | Destinos, combos y cotizaciones viven **solo** en BD |
| Flujo combo | Se mantiene `localStorage` → formulario |
| Credenciales iniciales | `admin / 1234` **hasheada** en BD (cambiable después) |

---

## 4. Estructura final

```
your_destiny/
├── app.py                  # Backend completo (sirve páginas + API + init BD)
├── requirements.txt        # flask, mysql-connector-python
├── README.md               # [DEBE] instrucciones de instalación y uso
└── static/
    ├── principal.html  sobrenoso.html  cuendesti.html
    ├── destacados.html comysug.html    admin.html
    ├── css/styles.css
    ├── img/                            # 6 imágenes renombradas
    └── js/
        ├── api.js      # única capa de contacto con el backend
        ├── ui.js       # solo DOM (toast, resumen)
        ├── principal.js  cuendesti.js  destacados.js
        └── comysug.js    admin.js
```

---

## 5. Base de datos

Crear solo la BD; **tablas y seed las crea `app.py` al arrancar** (idempotente, `CREATE TABLE IF NOT EXISTS` + seed si vacío).

```bash
mysql -u root -p -e "CREATE DATABASE IF NOT EXISTS your_destiny CHARACTER SET utf8mb4 COLLATE utf8mb4_spanish_ci;"
```

| Tabla | Columnas |
|---|---|
| `usuarios` | `id PK`, `usuario UNIQUE`, `password_hash`, `rol` (`admin`/`cliente`), `creado_en` |
| `destinos` | `id PK`, `nombre`, `imagen`, `descripcion` |
| `combos` | `id PK`, `nombre`, `detalle`, `precio DECIMAL(10,2)` |
| `cotizaciones` | `id PK`, `origen`, `destino`, `fecha_viaje DATE`, `nombre`, `contacto`, `combo_id FK→combos (NULL, ON DELETE SET NULL)`, `preferencias`, `estado` (`pendiente/confirmada/cancelada`, default `pendiente`), `creado_en` |

**Seed automático:** usuario `admin` (hash de `1234`, rol `admin`) · 6 destinos (Cartagena, Medellín, Salento, Bogotá, Santa Marta, Pereira con imágenes en minúscula y extensión única) · 3 combos (Combo Caribe 250000, Combo Café 180000, Combo Urbano 200000).

---

## 6. Backend

### 6.1 Endpoints [DEBE]

| Método | Ruta | Auth | Descripción |
|---|---|---|---|
| GET | `/` · `/<pagina>.html` | — | Sirve páginas |
| POST | `/api/login` | — | Valida contra BD, abre sesión |
| POST | `/api/logout` | — | Cierra sesión |
| GET | `/api/me` | — | Usuario en sesión (o `null`) |
| GET | `/api/destinos` | — | Lista destinos |
| GET | `/api/combos` | — | Lista combos (`precio` como número) |
| POST | `/api/cotizaciones` | — | Inserta; valida servidor; responde `201` con `id` y `resumen` |
| GET | `/api/admin/cotizaciones` | `admin` | Listado con join de combo; **403** sin rol |
| PATCH | `/api/admin/cotizaciones/<id>` | `admin` | Cambia `estado`; **404** si no existe |

### 6.2 Seguridad [DEBE]

- Consultas **siempre parametrizadas** (nunca concatenar SQL).
- Hash de contraseñas con `generate_password_hash` / `check_password_hash`.
- `secret_key` y credenciales de BD vía variables de entorno con fallback local.
- Validación servidor: campos obligatorios, longitudes máximas, fecha `AAAA-MM-DD` válida y **hoy o posterior**.
- Errores con JSON `{"ok": false, "error": ...}` y código HTTP correcto (400/401/403/404).

### 6.3 Código de referencia — `app.py`

```python
# app.py — Backend "Your Destiny" (Flask + MySQL)
import os
from datetime import date, datetime
from flask import Flask, request, jsonify, session, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
import mysql.connector

app = Flask(__name__, static_folder="static")
app.secret_key = os.environ.get("SECRET_KEY", "cambia-esta-clave-en-produccion")

DB = {
    "host": os.environ.get("DB_HOST", "localhost"),
    "user": os.environ.get("DB_USER", "root"),
    "password": os.environ.get("DB_PASSWORD", ""),
    "database": os.environ.get("DB_NAME", "your_destiny"),
}

def db():
    return mysql.connector.connect(**DB)

def limpiar(texto, max_len):
    return (texto or "").strip()[:max_len]

# ---------- Páginas ----------
PAGINAS = ["principal.html", "sobrenoso.html", "cuendesti.html",
           "destacados.html", "comysug.html", "admin.html"]

@app.route("/")
def inicio():
    return send_from_directory(app.static_folder, "principal.html")

@app.route("/<pagina>")
def pagina(pagina):
    if pagina in PAGINAS:
        return send_from_directory(app.static_folder, pagina)
    return "404", 404

# ---------- Autenticación ----------
@app.route("/api/login", methods=["POST"])
def login():
    d = request.get_json() or {}
    conn = db(); cur = conn.cursor(dictionary=True)
    cur.execute("SELECT id, usuario, password_hash, rol FROM usuarios WHERE usuario=%s",
                (d.get("usuario"),))
    u = cur.fetchone(); cur.close(); conn.close()
    if u and check_password_hash(u["password_hash"], d.get("password", "")):
        session["user"] = {"id": u["id"], "usuario": u["usuario"], "rol": u["rol"]}
        return jsonify({"ok": True, "usuario": u["usuario"], "rol": u["rol"]})
    return jsonify({"ok": False, "error": "Usuario o contraseña incorrectos"}), 401

@app.route("/api/logout", methods=["POST"])
def logout():
    session.clear(); return jsonify({"ok": True})

@app.route("/api/me")
def me():
    return jsonify({"ok": True, "user": session.get("user")})

# ---------- Datos públicos ----------
@app.route("/api/destinos")
def destinos():
    conn = db(); cur = conn.cursor(dictionary=True)
    cur.execute("SELECT id, nombre, imagen, descripcion FROM destinos")
    data = cur.fetchall(); cur.close(); conn.close()
    return jsonify(data)

@app.route("/api/combos")
def combos():
    conn = db(); cur = conn.cursor(dictionary=True)
    cur.execute("SELECT id, nombre, detalle, precio FROM combos")
    data = cur.fetchall(); cur.close(); conn.close()
    for row in data:
        row["precio"] = float(row["precio"])
    return jsonify(data)

# ---------- Cotizaciones ----------
@app.route("/api/cotizaciones", methods=["POST"])
def crear_cotizacion():
    d = request.get_json() or {}
    origen    = limpiar(d.get("origen"), 100)
    destino   = limpiar(d.get("destino"), 100)
    nombre    = limpiar(d.get("nombre"), 100)
    contacto  = limpiar(d.get("contacto"), 150)
    prefer    = limpiar(d.get("preferencias"), 500)
    faltan = [k for k, v in {"origen": origen, "destino": destino,
                             "nombre": nombre, "contacto": contacto}.items() if not v]
    if faltan:
        return jsonify({"ok": False, "error": "Faltan campos: " + ", ".join(faltan)}), 400
    try:
        fecha = datetime.strptime(d.get("fecha", ""), "%Y-%m-%d").date()
    except ValueError:
        return jsonify({"ok": False, "error": "Fecha inválida (use AAAA-MM-DD)"}), 400
    if fecha < date.today():
        return jsonify({"ok": False, "error": "La fecha debe ser hoy o posterior"}), 400
    try:
        combo_id = int(d["comboId"]) if d.get("comboId") is not None else None
    except (TypeError, ValueError):
        combo_id = None

    conn = db(); cur = conn.cursor()
    cur.execute("""INSERT INTO cotizaciones
                   (origen, destino, fecha_viaje, nombre, contacto, combo_id, preferencias)
                   VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                (origen, destino, fecha, nombre, contacto, combo_id, prefer))
    conn.commit(); nuevo_id = cur.lastrowid; cur.close(); conn.close()
    return jsonify({"ok": True, "id": nuevo_id, "resumen": {
        "id": nuevo_id, "origen": origen, "destino": destino,
        "fecha": fecha.isoformat(), "nombre": nombre, "estado": "pendiente"}}), 201

# ---------- Admin ----------
def requiere_admin():
    u = session.get("user")
    return u if u and u["rol"] == "admin" else None

@app.route("/api/admin/cotizaciones")
def admin_cotizaciones():
    if not requiere_admin():
        return jsonify({"ok": False, "error": "No autorizado"}), 403
    conn = db(); cur = conn.cursor(dictionary=True)
    cur.execute("""SELECT c.*, b.nombre AS combo FROM cotizaciones c
                   LEFT JOIN combos b ON b.id = c.combo_id
                   ORDER BY c.creado_en DESC""")
    data = cur.fetchall(); cur.close(); conn.close()
    for r in data:
        r["fecha_viaje"] = r["fecha_viaje"].isoformat()
        r["creado_en"] = r["creado_en"].isoformat()
    return jsonify(data)

@app.route("/api/admin/cotizaciones/<int:cid>", methods=["PATCH"])
def actualizar_cotizacion(cid):
    if not requiere_admin():
        return jsonify({"ok": False, "error": "No autorizado"}), 403
    estado = (request.get_json() or {}).get("estado")
    if estado not in ("pendiente", "confirmada", "cancelada"):
        return jsonify({"ok": False, "error": "Estado inválido"}), 400
    conn = db(); cur = conn.cursor()
    cur.execute("UPDATE cotizaciones SET estado=%s WHERE id=%s", (estado, cid))
    conn.commit(); n = cur.rowcount; cur.close(); conn.close()
    if n == 0:
        return jsonify({"ok": False, "error": "No existe"}), 404
    return jsonify({"ok": True})

# ---------- Init + seed ----------
def init_db():
    conn = db(); cur = conn.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS usuarios (
        id INT AUTO_INCREMENT PRIMARY KEY, usuario VARCHAR(50) NOT NULL UNIQUE,
        password_hash VARCHAR(255) NOT NULL, rol VARCHAR(20) NOT NULL DEFAULT 'cliente',
        creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS destinos (
        id INT AUTO_INCREMENT PRIMARY KEY, nombre VARCHAR(100) NOT NULL,
        imagen VARCHAR(255) NOT NULL, descripcion TEXT)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS combos (
        id INT AUTO_INCREMENT PRIMARY KEY, nombre VARCHAR(100) NOT NULL,
        detalle VARCHAR(255) NOT NULL, precio DECIMAL(10,2) NOT NULL)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS cotizaciones (
        id INT AUTO_INCREMENT PRIMARY KEY, origen VARCHAR(100) NOT NULL,
        destino VARCHAR(100) NOT NULL, fecha_viaje DATE NOT NULL,
        nombre VARCHAR(100) NOT NULL, contacto VARCHAR(150) NOT NULL,
        combo_id INT NULL, preferencias TEXT,
        estado VARCHAR(20) NOT NULL DEFAULT 'pendiente',
        creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        CONSTRAINT fk_cot_combo FOREIGN KEY (combo_id)
            REFERENCES combos(id) ON DELETE SET NULL)""")
    cur.execute("SELECT COUNT(*) FROM usuarios")
    if cur.fetchone()[0] == 0:
        cur.execute("INSERT INTO usuarios (usuario, password_hash, rol) VALUES (%s,%s,%s)",
                    ("admin", generate_password_hash("1234"), "admin"))
    cur.execute("SELECT COUNT(*) FROM destinos")
    if cur.fetchone()[0] == 0:
        cur.executemany("INSERT INTO destinos (nombre, imagen, descripcion) VALUES (%s,%s,%s)", [
            ("Cartagena", "cartagena.jpg", "Murallas y mar Caribe"),
            ("Medellín", "medellin.jpg", "Eterna primavera"),
            ("Salento", "salento.jpg", "Valle de Cocora y café"),
            ("Bogotá", "bogota.jpg", "Capital de Colombia"),
            ("Santa Marta", "santamarta.jpg", "Playas y Sierra Nevada"),
            ("Pereira", "pereira.jpg", "Puerta del eje cafetero")])
    cur.execute("SELECT COUNT(*) FROM combos")
    if cur.fetchone()[0] == 0:
        cur.executemany("INSERT INTO combos (nombre, detalle, precio) VALUES (%s,%s,%s)", [
            ("Combo Caribe", "Cartagena + Santa Marta", 250000),
            ("Combo Café", "Salento + Pereira", 180000),
            ("Combo Urbano", "Bogotá + Medellín", 200000)])
    conn.commit(); cur.close(); conn.close()

if __name__ == "__main__":
    init_db()
    app.run(debug=True)
```

---

## 7. Frontend

### 7.1 Reglas generales [DEBE]

- Mover páginas a `static/`; referencias de assets como `/static/css/...`, `/static/js/...`, `/static/img/...`.
- Orden de scripts en cada página: `api.js` → `ui.js` → JS de la página.
- **Eliminar** de todo JS: objeto `usuarios` hardcodeado, `procesarViaje()` simulado y cualquier rastro de Firebase.
- Garantizar estos `id` (crearlos si faltan): `loginForm`, `usuario`, `password`, `modalLogin`, `formViaje`, `origen`, `destino`, `fecha` (`type="date"`), `nombre`, `contacto`, `preferencias`, `resumen`, `galeria`, `combos`.
- En `cuendesti.html`: `<div id="resumen" hidden></div>` si no existe.
- Manejo de errores: todo `apiGet` de carga con `.catch()` que muestre toast.

### 7.2 Contenido mínimo por página (solo si falta el HTML original)

- **principal.html:** nav con enlaces a las 5 secciones; hero con marca "Your Destiny"; botón que abre `#modalLogin` con el formulario de login.
- **sobrenoso.html:** texto institucional estático.
- **cuendesti.html:** formulario `#formViaje` con los ids de §7.1 + `#resumen`.
- **destacados.html:** contenedor vacío `#galeria` (lo pinta JS).
- **comysug.html:** contenedor vacío `#combos` (lo pinta JS).
- [DEBERÍA] Paleta coherente de transporte (azul profundo + amarillo), cards en grid, modal centrado, footer con crédito.

### 7.3 Archivos JS [DEBE]

```js
// static/js/api.js — única capa de contacto con el backend
async function apiGet(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error("Error " + res.status);
  return res.json();
}
async function apiPost(url, data) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "same-origin",
    body: JSON.stringify(data)
  });
  return res.json();
}
```

```js
// static/js/ui.js — solo DOM
function mostrarToast(msg) {
  let t = document.getElementById("toast");
  if (!t) { t = document.createElement("div"); t.id = "toast"; document.body.appendChild(t); }
  t.textContent = msg; t.classList.add("visible");
  setTimeout(() => t.classList.remove("visible"), 3000);
}
function mostrarResumen(r) {
  const caja = document.getElementById("resumen");
  if (!caja) return;
  caja.innerHTML = `<h3>Solicitud #${r.id} recibida</h3>
    <p>${r.origen} → ${r.destino}</p><p>Fecha: ${r.fecha}</p>
    <p>Pasajero: ${r.nombre}</p><p>Estado: ${r.estado}</p>`;
  caja.hidden = false;
}
```

```js
// static/js/principal.js — login real (sin credenciales en cliente)
document.getElementById("loginForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    const r = await apiPost("/api/login", {
      usuario: document.getElementById("usuario").value.trim(),
      password: document.getElementById("password").value
    });
    if (r.ok) {
      document.getElementById("modalLogin").hidden = true;
      mostrarToast("Bienvenido, " + r.usuario);
    } else {
      mostrarToast(r.error || "Credenciales inválidas");
    }
  } catch {
    mostrarToast("Servidor no disponible");
  }
});
```

```js
// static/js/cuendesti.js — bug fecha CORREGIDO + persistencia MySQL
window.addEventListener("DOMContentLoaded", async () => {
  const comboId = localStorage.getItem("comboSeleccionado");
  if (comboId) {
    try {
      const c = (await apiGet("/api/combos")).find(x => x.id == comboId);
      if (c) mostrarToast("Combo aplicado: " + c.nombre);
    } catch { /* sin toast de carga */ }
  }
  document.getElementById("formViaje").addEventListener("submit", async (e) => {
    e.preventDefault();
    const datos = {
      origen: document.getElementById("origen").value,
      destino: document.getElementById("destino").value,
      fecha: document.getElementById("fecha").value, // ← corrección del bug fecha/fechaRaw
      nombre: document.getElementById("nombre").value,
      contacto: document.getElementById("contacto").value,
      preferencias: document.getElementById("preferencias").value,
      comboId: comboId ? Number(comboId) : null
    };
    if (!datos.fecha) { mostrarToast("Selecciona una fecha válida"); return; }
    try {
      const r = await apiPost("/api/cotizaciones", datos);
      if (r.ok) { mostrarResumen(r.resumen); localStorage.removeItem("comboSeleccionado"); }
      else mostrarToast(r.error || "Error al enviar");
    } catch {
      mostrarToast("Servidor no disponible");
    }
  });
});
```

```js
// static/js/destacados.js — galería desde BD (corrige imágenes rotas)
apiGet("/api/destinos")
  .then(lista => {
    const cont = document.getElementById("galeria");
    lista.forEach((d, i) => {
      const card = document.createElement("article");
      card.className = "card";
      card.style.animationDelay = i * 0.15 + "s"; // conservar animación secuencial
      card.innerHTML = `<img src="/static/img/${d.imagen}" alt="${d.nombre}">
                        <h3>${d.nombre}</h3><p>${d.descripcion}</p>`;
      cont.appendChild(card);
    });
  })
  .catch(() => mostrarToast("No se pudo cargar la galería"));
```

```js
// static/js/comysug.js — combos desde BD
apiGet("/api/combos")
  .then(cs => {
    const cont = document.getElementById("combos");
    cs.forEach(c => {
      const el = document.createElement("div");
      el.className = "combo";
      el.innerHTML = `<h3>${c.nombre}</h3><p>${c.detalle}</p>
                      <strong>$${c.precio}</strong><button>Seleccionar</button>`;
      el.querySelector("button").onclick = () => {
        localStorage.setItem("comboSeleccionado", c.id);
        location.href = "/cuendesti.html";
      };
      cont.appendChild(el);
    });
  })
  .catch(() => mostrarToast("No se pudieron cargar los combos"));
```

```js
// static/js/admin.js — panel protegido + gestión de estados
(async () => {
  try {
    const me = await apiGet("/api/me");
    if (!me.user || me.user.rol !== "admin") {
      document.body.innerHTML = "<h1>403 — No autorizado</h1>";
      return;
    }
    const filas = await apiGet("/api/admin/cotizaciones");
    const tbody = document.querySelector("#tablaCotizaciones tbody");
    tbody.innerHTML = filas.map(c => `
      <tr>
        <td>${c.id}</td><td>${c.nombre}</td><td>${c.origen} → ${c.destino}</td>
        <td>${c.fecha_viaje}</td><td>${c.combo ?? "—"}</td>
        <td><select data-id="${c.id}" class="sel-estado">
          ${["pendiente", "confirmada", "cancelada"].map(e =>
            `<option ${e === c.estado ? "selected" : ""}>${e}</option>`).join("")}
        </select></td>
      </tr>`).join("");
    tbody.querySelectorAll(".sel-estado").forEach(sel => {
      sel.onchange = async () => {
        const res = await fetch(`/api/admin/cotizaciones/${sel.dataset.id}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ estado: sel.value })
        });
        const r = await res.json();
        mostrarToast(r.ok ? "Estado actualizado" : (r.error || "Error"));
      };
    });
  } catch {
    mostrarToast("Servidor no disponible");
  }
})();
```

### 7.4 `admin.html` (nueva)

```html
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Admin — Your Destiny</title>
  <link rel="stylesheet" href="/static/css/styles.css">
</head>
<body>
  <h1>Cotizaciones recibidas</h1>
  <table id="tablaCotizaciones" border="1" cellpadding="8">
    <thead><tr><th>ID</th><th>Cliente</th><th>Ruta</th><th>Fecha</th><th>Combo</th><th>Estado</th></tr></thead>
    <tbody></tbody>
  </table>
  <script src="/static/js/api.js"></script>
  <script src="/static/js/ui.js"></script>
  <script src="/static/js/admin.js"></script>
</body>
</html>
```

### 7.5 CSS — añadir a `styles.css` [DEBE]

```css
/* Toast */
#toast { position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%);
  background: #222; color: #fff; padding: 10px 18px; border-radius: 6px;
  opacity: 0; transition: opacity .3s; z-index: 999; }
#toast.visible { opacity: 1; }

/* Responsive (obligatorio) */
@media (max-width: 768px) {
  .galeria, .combos { grid-template-columns: 1fr; }
  nav ul { flex-direction: column; }
  form { padding: 1rem; }
}
```

### 7.6 Imágenes [DEBE]

Renombrar a minúsculas y extensión única, coincidiendo con el seed:
`Bogota.jpg.jpeg → bogota.jpg`, `cartagena.jpg.jpeg → cartagena.jpg`, y análogo para `medellin.jpg`, `salento.jpg`, `santamarta.jpg`, `pereira.jpg`. Ubicarlas en `static/img/`.

---

## 8. Plan de trabajo (ejecutar en este orden)

1. Crear estructura (§4) y `requirements.txt` (`flask`, `mysql-connector-python`).
2. Crear BD (§5) y verificar `python app.py` arranca y siembra.
3. Probar API con curl: login correcto/incorrecto, POST cotización, GET admin con y sin sesión.
4. Migrar/ajustar HTML y CSS (§7.1, §7.5, §7.6).
5. Reemplazar JS de páginas (§7.3) y crear `admin.html`/`admin.js` (§7.4).
6. QA completa en navegador según §10, incluyendo viewport 375 px.
7. Escribir `README.md` (requisitos, instalación, ejecución, credenciales iniciales, estructura).

```bash
# Pruebas rápidas de API
curl -X POST http://localhost:5000/api/login -H "Content-Type: application/json" -d '{"usuario":"admin","password":"1234"}'
curl -X POST http://localhost:5000/api/cotizaciones -H "Content-Type: application/json" -d '{"origen":"Bogotá","destino":"Cartagena","fecha":"2025-12-01","nombre":"Test","contacto":"t@t.com"}'
```

---

## 9. Criterios de aceptación (checklist de entrega)

- [ ] `python app.py` arranca sin errores; tablas y seed creados automáticamente.
- [ ] `GET /` sirve `principal.html`; rutas inexistentes → 404.
- [ ] Login `admin/1234` → `ok:true`; credenciales malas → 401; ningún JS del cliente contiene contraseñas ni el objeto `usuarios`.
- [ ] Galería: 6 tarjetas, **todas las imágenes cargan**, animación secuencial visible.
- [ ] Formulario: inserta fila en `cotizaciones` (verificar con `SELECT * FROM cotizaciones;`), pinta `#resumen` con el `id` y limpia el `localStorage`.
- [ ] Fecha vacía → toast sin `ReferenceError` en consola; fecha pasada o mal formada → 400 del servidor.
- [ ] Combo elegido en `comysug.html` se anuncia en `cuendesti.html` y su `combo_id` queda en BD.
- [ ] `/api/admin/cotizaciones` sin sesión → 403; con sesión admin → datos; `admin.html` pinta tabla y el `<select>` de estado persiste cambios (PATCH).
- [ ] Sitio correcto a 375 px y 768 px.
- [ ] Caída de servidor manejada: toasts "Servidor no disponible", sin errores crudos en UI.
- [ ] Cero referencias a Firebase en todo el proyecto.
- [ ] `README.md` presente y suficiente para instalar y correr sin ayuda externa.

---

## 10. Estilo

- Comentarios y textos de UI en **español**.
- Únicas dependencias: `flask`, `mysql-connector-python`.
- Código legible, funciones cortas, sin variables muertas.
- No modificar nombres de páginas ni estética base; solo añadir/mejorar.