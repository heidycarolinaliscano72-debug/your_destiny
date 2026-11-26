# app.py — Backend "Your Destiny" (Flask + SQLite / PostgreSQL / MySQL)
import json
import os
import re
import secrets
import sqlite3
import threading
import time
import unicodedata
from datetime import date, datetime
from urllib.parse import quote

from flask import Flask, jsonify, request, send_from_directory, session
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__, static_folder=os.path.join(BASE_DIR, "static"))
app.secret_key = os.environ.get("SECRET_KEY", "cambia-esta-clave-en-produccion")
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

# Número de WhatsApp destino (solo dígitos con código de país, ej. 573227618659)
WHATSAPP_NUMBER = re.sub(
    r"\D", "", os.environ.get("WHATSAPP_NUMBER", "573227618659")
) or "573227618659"

# ---------- Selección automática de motor de base de datos ----------
# 1) DATABASE_URL (PostgreSQL en Render / Neon / Supabase)
# 2) DB_HOST (MySQL en Docker Compose o local)
# 3) SQLite local por defecto (cero configuración para desarrollo o Render gratis)
DATABASE_URL = (os.environ.get("DATABASE_URL") or "").strip()
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = "postgresql://" + DATABASE_URL[len("postgres://") :]

if DATABASE_URL.startswith("postgresql://"):
    DB_BACKEND = "postgres"
elif os.environ.get("DB_HOST"):
    DB_BACKEND = "mysql"
else:
    DB_BACKEND = "sqlite"

SQLITE_PATH = os.environ.get("SQLITE_PATH", os.path.join(BASE_DIR, "your_destiny.db"))
MYSQL_CFG = {
    "host": os.environ.get("DB_HOST", "localhost"),
    "user": os.environ.get("DB_USER", "root"),
    "password": os.environ.get("DB_PASSWORD", ""),
    "database": os.environ.get("DB_NAME", "your_destiny"),
}

_init_lock = threading.Lock()
_db_initialized = False


class DBConnection:
    """Envoltorio ligero que unifica SQLite, PostgreSQL y MySQL."""

    def __init__(self, raw, backend):
        self.raw = raw
        self.backend = backend

    def _sql(self, sql):
        if self.backend == "sqlite":
            return sql.replace("%s", "?")
        return sql

    def _cursor(self, dictionary=False):
        if self.backend == "sqlite":
            return self.raw.cursor()
        if self.backend == "postgres":
            from psycopg.rows import dict_row

            return self.raw.cursor(row_factory=dict_row if dictionary else None)
        return self.raw.cursor(dictionary=dictionary)

    def fetchall(self, sql, params=()):
        cur = self._cursor(dictionary=True)
        try:
            cur.execute(self._sql(sql), params)
            rows = cur.fetchall()
            if self.backend == "sqlite":
                return [dict(r) for r in rows]
            return list(rows)
        finally:
            cur.close()

    def fetchone(self, sql, params=(), dictionary=True):
        cur = self._cursor(dictionary=dictionary)
        try:
            cur.execute(self._sql(sql), params)
            row = cur.fetchone()
            if row is not None and self.backend == "sqlite" and dictionary:
                return dict(row)
            return row
        finally:
            cur.close()

    def execute(self, sql, params=()):
        cur = self._cursor(dictionary=False)
        try:
            cur.execute(self._sql(sql), params)
            return cur.rowcount
        finally:
            cur.close()

    def insert(self, sql, params=()):
        cur = self._cursor(dictionary=False)
        try:
            if self.backend == "postgres":
                cur.execute(self._sql(sql) + " RETURNING id", params)
                return cur.fetchone()[0]
            cur.execute(self._sql(sql), params)
            return cur.lastrowid
        finally:
            cur.close()

    def executemany(self, sql, seq):
        cur = self._cursor(dictionary=False)
        try:
            cur.executemany(self._sql(sql), seq)
        finally:
            cur.close()

    def commit(self):
        self.raw.commit()

    def close(self):
        self.raw.close()


def db():
    if DB_BACKEND == "postgres":
        import psycopg

        raw = psycopg.connect(DATABASE_URL)
        return DBConnection(raw, "postgres")
    if DB_BACKEND == "mysql":
        import mysql.connector

        raw = mysql.connector.connect(**MYSQL_CFG)
        return DBConnection(raw, "mysql")
    raw = sqlite3.connect(SQLITE_PATH, timeout=30)
    raw.row_factory = sqlite3.Row
    raw.execute("PRAGMA foreign_keys = ON")
    raw.execute("PRAGMA busy_timeout = 30000")
    return DBConnection(raw, "sqlite")


# ---------- Utilidades de texto, precios y WhatsApp ----------
def limpiar(texto, max_len):
    return (texto or "").strip()[:max_len]


def normalizar_texto(texto):
    s = unicodedata.normalize("NFKD", (texto or "").strip().lower())
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", s)


def slugify(texto):
    s = normalizar_texto(texto)
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "destino"


def iso(val):
    if val is None:
        return None
    if isinstance(val, (date, datetime)):
        return val.isoformat()
    return str(val)


def formatear_cop(valor):
    return f"{int(round(float(valor))):,}".replace(",", ".")


# Diccionario centralizado de tarifas base en COP (rutas bidireccionales)
TARIFA_ESTANDAR_DEFAULT = 110000

_RUTAS_RAW = {
    ("bogota", "cartagena"): 145000,
    ("bogota", "medellin"): 95000,
    ("bogota", "salento"): 85000,
    ("bogota", "santa marta"): 155000,
    ("bogota", "pereira"): 80000,
    ("bogota", "cali"): 105000,
    ("bogota", "barranquilla"): 140000,
    ("bogota", "bucaramanga"): 92000,
    ("bogota", "manizales"): 82000,
    ("bogota", "armenia"): 78000,
    ("bogota", "ibague"): 52000,
    ("bogota", "villavicencio"): 45000,
    ("bogota", "tunja"): 42000,
    ("bogota", "neiva"): 72000,
    ("medellin", "cartagena"): 125000,
    ("medellin", "santa marta"): 135000,
    ("medellin", "salento"): 68000,
    ("medellin", "pereira"): 62000,
    ("medellin", "cali"): 92000,
    ("medellin", "barranquilla"): 130000,
    ("medellin", "bucaramanga"): 98000,
    ("medellin", "manizales"): 58000,
    ("medellin", "armenia"): 66000,
    ("cartagena", "santa marta"): 58000,
    ("cartagena", "barranquilla"): 38000,
    ("cartagena", "salento"): 165000,
    ("cartagena", "pereira"): 155000,
    ("cartagena", "cali"): 175000,
    ("cartagena", "bucaramanga"): 132000,
    ("santa marta", "barranquilla"): 34000,
    ("santa marta", "salento"): 170000,
    ("santa marta", "pereira"): 165000,
    ("santa marta", "cali"): 185000,
    ("santa marta", "bucaramanga"): 128000,
    ("salento", "pereira"): 35000,
    ("salento", "armenia"): 28000,
    ("salento", "manizales"): 48000,
    ("salento", "cali"): 65000,
    ("pereira", "manizales"): 32000,
    ("pereira", "armenia"): 26000,
    ("pereira", "cali"): 58000,
    ("cali", "popayan"): 42000,
    ("cali", "pasto"): 88000,
    ("cali", "armenia"): 54000,
    ("cali", "manizales"): 68000,
}

TARIFAS_RUTAS = {
    tuple(sorted((normalizar_texto(a), normalizar_texto(b)))): precio
    for (a, b), precio in _RUTAS_RAW.items()
}

# Recargos opcionales detectados en preferencias del pasajero
RECARGOS_PREFERENCIAS = [
    {
        "id": "ventana",
        "concepto": "Asiento ventana",
        "valor": 15000,
        "keywords": ("ventana", "ventanilla"),
    },
    {
        "id": "nocturno",
        "concepto": "Horario nocturno",
        "valor": 10000,
        "keywords": ("nocturn", "noche", "madrugada"),
    },
    {
        "id": "vip",
        "concepto": "Servicio VIP / Ejecutivo",
        "valor": 25000,
        "keywords": ("vip", "ejecutiv", "premium", "reclinable", "bus cama"),
    },
    {
        "id": "equipaje",
        "concepto": "Equipaje adicional",
        "valor": 18000,
        "keywords": ("equipaje", "maleta"),
    },
    {
        "id": "mascota",
        "concepto": "Transporte de mascota",
        "valor": 20000,
        "keywords": ("mascota", "perro", "gato"),
    },
]

CIUDADES_SUGERIDAS = [
    "Bogotá",
    "Medellín",
    "Cartagena",
    "Santa Marta",
    "Salento",
    "Pereira",
    "Cali",
    "Barranquilla",
    "Bucaramanga",
    "Manizales",
    "Armenia",
    "Ibagué",
    "Villavicencio",
    "Neiva",
]

DESTINOS_SEED = [
    (
        "cartagena",
        "Cartagena",
        "Murallas coloniales y mar Caribe",
        (
            "Recorre la histórica Ciudad Amurallada, el Castillo de San Felipe y las plazas "
            "llenas de color frente al mar Caribe. Cartagena combina arquitectura colonial, "
            "gastronomía costeña de primer nivel y atardeceres inolvidables."
        ),
        "Bus ejecutivo climatizado, Wi-Fi a bordo, puerto USB, seguro de viaje y parada en Terminal de Transporte de Cartagena.",
        145000,
        "cartagena.jpg",
    ),
    (
        "medellin",
        "Medellín",
        "La ciudad de la eterna primavera",
        (
            "Descubre el Valle de Aburrá, sus miradores en las montañas, la Comuna 13, "
            "el Parque Arví y su moderna red de Metrocable. Un destino vibrante con clima "
            "agradable todo el año y hospitalidad paisa."
        ),
        "Bus doble piso panorámico, sillas reclinables, Wi-Fi, aire acondicionado y seguro de pasajeros.",
        95000,
        "medellin.jpg",
    ),
    (
        "salento",
        "Salento",
        "Valle de Cocora y tradición cafetera",
        (
            "Explora las palmas de cera más altas del mundo en el Valle de Cocora, camina "
            "por la colorida Calle Real y visita fincas cafeteras tradicionales rodeadas de "
            "bosque de niebla en el corazón del Quindío."
        ),
        "Transporte turístico confortable, equipaje de bodega incluido, seguro de viaje y recomendaciones de fincas cafeteras.",
        85000,
        "salento.jpg",
    ),
    (
        "bogota",
        "Bogotá",
        "Capital cultural de Colombia",
        (
            "Sube al Cerro de Monserrate, camina por las calles empedradas de La Candelaria "
            "y visita el Museo del Oro. Bogotá ofrece una mezcla única de historia, arte "
            "contemporáneo, gastronomía andina y vida nocturna."
        ),
        "Bus interdepartamental moderno, calefacción/clima regulado, conectores USB, Wi-Fi y seguro obligatorio.",
        75000,
        "bogota.jpg",
    ),
    (
        "santa-marta",
        "Santa Marta",
        "Playas del Tayrona y Sierra Nevada",
        (
            "Vive el contraste entre las playas cristalinas del Parque Nacional Tayrona, "
            "la bahía más linda de América y los senderos de la Sierra Nevada. Ideal para "
            "amantes del mar, el ecoturismo y el descanso tropical."
        ),
        "Bus ejecutivo con aire acondicionado, paradas programadas, Wi-Fi a bordo, seguro de viaje y asistencia 24/7.",
        155000,
        "santamarta.jpg",
    ),
    (
        "pereira",
        "Pereira",
        "Puerta del Eje Cafetero",
        (
            "Punto estratégico para conocer los termales de Santa Rosa de Cabal, el Bioparque "
            "Ukumarí y los paisajes verdes del Paisaje Cultural Cafetero. Una ciudad dinámica, "
            "acogedora y rodeada de montañas."
        ),
        "Bus confortable con sillas ergonómicas, equipaje incluido, Wi-Fi, aire acondicionado y seguro de viaje.",
        80000,
        "pereira.jpg",
    ),
]


def calcular_tarifa(origen, destino, preferencias="", conn=None):
    orig_norm = normalizar_texto(origen)
    dest_norm = normalizar_texto(destino)
    clave = tuple(sorted((orig_norm, dest_norm)))

    ruta_catalogo = clave in TARIFAS_RUTAS
    if ruta_catalogo:
        tarifa_base = TARIFAS_RUTAS[clave]
    else:
        tarifa_base = None
        if conn is not None:
            rows = conn.fetchall("SELECT nombre, precio_base FROM destinos")
            for r in rows:
                if normalizar_texto(r["nombre"]) == dest_norm and r.get("precio_base"):
                    tarifa_base = int(round(float(r["precio_base"])))
                    break
        if tarifa_base is None:
            tarifa_base = TARIFA_ESTANDAR_DEFAULT

    pref_norm = normalizar_texto(preferencias)
    recargos = []
    for item in RECARGOS_PREFERENCIAS:
        if any(kw in pref_norm for kw in item["keywords"]):
            recargos.append({"concepto": item["concepto"], "valor": item["valor"]})

    total = tarifa_base + sum(r["valor"] for r in recargos)
    return {
        "tarifa_base": tarifa_base,
        "recargos": recargos,
        "total": total,
        "ruta_catalogo": ruta_catalogo,
    }


def generar_codigo_reserva():
    sufijo = secrets.token_hex(2).upper()
    return f"YD-{date.today().strftime('%Y%m%d')}-{sufijo}"


def construir_whatsapp(codigo, nombre, detalle, fecha_viaje, total):
    texto = (
        "Hola, acabo de comprar en Your Destiny:\n"
        f"Reserva: {codigo}\n"
        f"Pasajero: {nombre}\n"
        f"Plan/Ruta: {detalle}\n"
        f"Fecha: {fecha_viaje}\n"
        f"Total: ${formatear_cop(total)} COP"
    )
    wa_url = f"https://wa.me/{WHATSAPP_NUMBER}?text={quote(texto)}"
    return wa_url, texto


# ---------- Rutas de páginas estáticas ----------
PAGINAS = [
    "principal.html",
    "sobrenoso.html",
    "cuendesti.html",
    "destacados.html",
    "comysug.html",
    "admin.html",
]


@app.route("/")
def inicio():
    return send_from_directory(app.static_folder, "principal.html")


@app.route("/cotizar")
def alias_cotizar():
    return send_from_directory(app.static_folder, "cuendesti.html")


@app.route("/destinos")
def alias_destinos():
    return send_from_directory(app.static_folder, "destacados.html")


@app.route("/combos")
def alias_combos():
    return send_from_directory(app.static_folder, "comysug.html")


@app.route("/admin")
def alias_admin():
    return send_from_directory(app.static_folder, "admin.html")


@app.route("/<pagina>")
def pagina(pagina):
    if pagina in PAGINAS:
        return send_from_directory(app.static_folder, pagina)
    return "404", 404


# ---------- Salud y configuración pública ----------
@app.route("/api/health")
def health():
    return jsonify({"ok": True, "db": DB_BACKEND})


@app.route("/api/config")
def api_config():
    return jsonify(
        {
            "whatsapp_number": WHATSAPP_NUMBER,
            "ciudades": CIUDADES_SUGERIDAS,
            "recargos_disponibles": [
                {"id": r["id"], "concepto": r["concepto"], "valor": r["valor"]}
                for r in RECARGOS_PREFERENCIAS
            ],
            "tarifa_default": TARIFA_ESTANDAR_DEFAULT,
        }
    )


# ---------- Autenticación ----------
@app.route("/api/login", methods=["POST"])
def login():
    d = request.get_json() or {}
    conn = db()
    try:
        u = conn.fetchone(
            "SELECT id, usuario, password_hash, rol FROM usuarios WHERE usuario=%s",
            (d.get("usuario"),),
        )
    finally:
        conn.close()
    if u and check_password_hash(u["password_hash"], d.get("password", "")):
        session["user"] = {"id": u["id"], "usuario": u["usuario"], "rol": u["rol"]}
        return jsonify({"ok": True, "usuario": u["usuario"], "rol": u["rol"]})
    return jsonify({"ok": False, "error": "Usuario o contraseña incorrectos"}), 401


@app.route("/api/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"ok": True})


@app.route("/api/me")
def me():
    return jsonify({"ok": True, "user": session.get("user")})


# ---------- Destinos ----------
def _serializar_destino(row):
    return {
        "id": row["id"],
        "slug": row.get("slug") or slugify(row["nombre"]),
        "nombre": row["nombre"],
        "subtitulo": row.get("subtitulo") or "",
        "descripcion": row.get("descripcion") or "",
        "incluye": row.get("incluye") or "",
        "precio_base": int(round(float(row.get("precio_base") or TARIFA_ESTANDAR_DEFAULT))),
        "imagen": row["imagen"],
    }


@app.route("/api/destinos")
def destinos():
    conn = db()
    try:
        rows = conn.fetchall(
            "SELECT id, slug, nombre, subtitulo, descripcion, incluye, precio_base, imagen "
            "FROM destinos ORDER BY id"
        )
    finally:
        conn.close()
    return jsonify([_serializar_destino(r) for r in rows])


@app.route("/api/destinos/<slug>")
def destino_detalle(slug):
    conn = db()
    try:
        row = conn.fetchone(
            "SELECT id, slug, nombre, subtitulo, descripcion, incluye, precio_base, imagen "
            "FROM destinos WHERE slug=%s",
            (slugify(slug),),
        )
    finally:
        conn.close()
    if not row:
        return jsonify({"ok": False, "error": "Destino no encontrado"}), 404
    return jsonify(_serializar_destino(row))


# ---------- Combos ----------
@app.route("/api/combos")
def combos():
    conn = db()
    try:
        rows = conn.fetchall("SELECT id, nombre, detalle, precio FROM combos ORDER BY id")
    finally:
        conn.close()
    for row in rows:
        row["precio"] = int(round(float(row["precio"])))
    return jsonify(rows)


# ---------- Cotizador con cálculo real de tarifas ----------
@app.route("/api/cotizar", methods=["POST"])
@app.route("/api/cotizaciones", methods=["POST"])
def crear_cotizacion():
    d = request.get_json() or {}
    origen = limpiar(d.get("origen"), 100)
    destino = limpiar(d.get("destino"), 100)
    nombre = limpiar(d.get("nombre"), 100)
    contacto = limpiar(d.get("contacto"), 150)
    prefer = limpiar(d.get("preferencias"), 500)

    faltan = [
        k
        for k, v in {
            "origen": origen,
            "destino": destino,
            "nombre": nombre,
            "contacto": contacto,
        }.items()
        if not v
    ]
    if faltan:
        return jsonify({"ok": False, "error": "Faltan campos: " + ", ".join(faltan)}), 400

    if normalizar_texto(origen) == normalizar_texto(destino):
        return (
            jsonify(
                {
                    "ok": False,
                    "error": "El origen y el destino no pueden ser la misma ciudad",
                }
            ),
            400,
        )

    try:
        fecha = datetime.strptime(d.get("fecha", ""), "%Y-%m-%d").date()
    except ValueError:
        return jsonify({"ok": False, "error": "Fecha inválida (use AAAA-MM-DD)"}), 400
    if fecha < date.today():
        return jsonify({"ok": False, "error": "La fecha debe ser hoy o posterior"}), 400

    conn = db()
    try:
        calculo = calcular_tarifa(origen, destino, prefer, conn=conn)
        recargos_json = json.dumps(calculo["recargos"], ensure_ascii=False)
        nuevo_id = conn.insert(
            """INSERT INTO cotizaciones
               (origen, destino, fecha_viaje, nombre, contacto, combo_id,
                preferencias, tarifa_base, recargos_json, total, estado)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (
                origen,
                destino,
                fecha.isoformat(),
                nombre,
                contacto,
                None,
                prefer,
                calculo["tarifa_base"],
                recargos_json,
                calculo["total"],
                "pendiente",
            ),
        )
        codigo = f"COT-{nuevo_id:04d}"
        conn.execute("UPDATE cotizaciones SET codigo=%s WHERE id=%s", (codigo, nuevo_id))
        conn.commit()
    finally:
        conn.close()

    resumen = {
        "id": nuevo_id,
        "codigo": codigo,
        "origen": origen,
        "destino": destino,
        "fecha": fecha.isoformat(),
        "nombre": nombre,
        "contacto": contacto,
        "preferencias": prefer,
        "tarifa_base": calculo["tarifa_base"],
        "recargos": calculo["recargos"],
        "total": calculo["total"],
        "ruta_catalogo": calculo["ruta_catalogo"],
        "estado": "pendiente",
    }
    return jsonify({"ok": True, "id": nuevo_id, "resumen": resumen}), 201


# ---------- Compras directas (Combos y Tiquetes cotizados) ----------
@app.route("/api/compras", methods=["POST"])
def crear_compra():
    d = request.get_json() or {}
    tipo = (d.get("tipo") or "").strip().lower()
    if tipo not in ("combo", "tiquete"):
        return jsonify({"ok": False, "error": "Tipo de compra inválido (combo o tiquete)"}), 400

    conn = db()
    try:
        if tipo == "combo":
            try:
                combo_id = int(d.get("combo_id"))
            except (TypeError, ValueError):
                return jsonify({"ok": False, "error": "Debes seleccionar un combo válido"}), 400

            combo = conn.fetchone(
                "SELECT id, nombre, detalle, precio FROM combos WHERE id=%s", (combo_id,)
            )
            if not combo:
                return jsonify({"ok": False, "error": "El combo seleccionado no existe"}), 404

            cliente_nombre = limpiar(d.get("cliente_nombre") or d.get("nombre"), 100)
            cliente_contacto = limpiar(d.get("cliente_contacto") or d.get("contacto"), 150)
            if not cliente_nombre or not cliente_contacto:
                return (
                    jsonify(
                        {
                            "ok": False,
                            "error": "Nombre completo y teléfono/email son obligatorios",
                        }
                    ),
                    400,
                )

            try:
                fecha = datetime.strptime(
                    d.get("fecha_viaje") or d.get("fecha") or "", "%Y-%m-%d"
                ).date()
            except ValueError:
                return jsonify({"ok": False, "error": "Fecha inválida (use AAAA-MM-DD)"}), 400
            if fecha < date.today():
                return (
                    jsonify({"ok": False, "error": "La fecha de viaje debe ser hoy o posterior"}),
                    400,
                )

            origen = limpiar(d.get("origen"), 100) or "Terminal principal"
            destino = combo["detalle"]
            detalle = f"{combo['nombre']} ({combo['detalle']})"
            preferencias = limpiar(d.get("preferencias"), 500)
            total = int(round(float(combo["precio"])))
            cotizacion_id = None

        else:
            # Compra de tiquete a partir de una cotización existente o datos de ruta
            cotizacion_id = d.get("cotizacion_id")
            cot = None
            if cotizacion_id is not None:
                try:
                    cotizacion_id = int(cotizacion_id)
                except (TypeError, ValueError):
                    return jsonify({"ok": False, "error": "ID de cotización inválido"}), 400
                cot = conn.fetchone(
                    "SELECT * FROM cotizaciones WHERE id=%s", (cotizacion_id,)
                )
                if not cot:
                    return jsonify({"ok": False, "error": "La cotización no existe"}), 404

            if cot:
                origen = cot["origen"]
                destino = cot["destino"]
                fecha_str = iso(cot["fecha_viaje"])[:10]
                cliente_nombre = (
                    limpiar(d.get("cliente_nombre"), 100) or cot["nombre"]
                )
                cliente_contacto = (
                    limpiar(d.get("cliente_contacto"), 150) or cot["contacto"]
                )
                preferencias = cot.get("preferencias") or ""
                total = int(round(float(cot["total"])))
            else:
                origen = limpiar(d.get("origen"), 100)
                destino = limpiar(d.get("destino"), 100)
                cliente_nombre = limpiar(d.get("cliente_nombre") or d.get("nombre"), 100)
                cliente_contacto = limpiar(d.get("cliente_contacto") or d.get("contacto"), 150)
                preferencias = limpiar(d.get("preferencias"), 500)
                if not (origen and destino and cliente_nombre and cliente_contacto):
                    return (
                        jsonify(
                            {
                                "ok": False,
                                "error": "Origen, destino, nombre y contacto son obligatorios",
                            }
                        ),
                        400,
                    )
                if normalizar_texto(origen) == normalizar_texto(destino):
                    return (
                        jsonify(
                            {
                                "ok": False,
                                "error": "El origen y el destino no pueden ser la misma ciudad",
                            }
                        ),
                        400,
                    )
                try:
                    fecha = datetime.strptime(
                        d.get("fecha_viaje") or d.get("fecha") or "", "%Y-%m-%d"
                    ).date()
                except ValueError:
                    return jsonify({"ok": False, "error": "Fecha inválida (use AAAA-MM-DD)"}), 400
                if fecha < date.today():
                    return (
                        jsonify(
                            {"ok": False, "error": "La fecha de viaje debe ser hoy o posterior"}
                        ),
                        400,
                    )
                fecha_str = fecha.isoformat()
                calculo = calcular_tarifa(origen, destino, preferencias, conn=conn)
                total = calculo["total"]

            detalle = f"Tiquete {origen} → {destino}"
            combo_id = None
            fecha = datetime.strptime(fecha_str, "%Y-%m-%d").date()

        codigo_reserva = generar_codigo_reserva()
        # Garantizar unicidad en el improbable caso de colisión
        while conn.fetchone(
            "SELECT id FROM compras WHERE codigo_reserva=%s", (codigo_reserva,)
        ):
            codigo_reserva = generar_codigo_reserva()

        compra_id = conn.insert(
            """INSERT INTO compras
               (codigo_reserva, tipo, detalle, origen, destino, fecha_viaje,
                cliente_nombre, cliente_contacto, preferencias, cotizacion_id,
                combo_id, total, estado)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (
                codigo_reserva,
                tipo,
                detalle,
                origen,
                destino,
                fecha.isoformat(),
                cliente_nombre,
                cliente_contacto,
                preferencias,
                cotizacion_id,
                combo_id,
                total,
                "confirmada",
            ),
        )
        if cotizacion_id is not None:
            conn.execute(
                "UPDATE cotizaciones SET estado=%s WHERE id=%s",
                ("confirmada", cotizacion_id),
            )
        conn.commit()
    finally:
        conn.close()

    wa_url, wa_mensaje = construir_whatsapp(
        codigo_reserva, cliente_nombre, detalle, fecha.isoformat(), total
    )
    compra = {
        "id": compra_id,
        "codigo_reserva": codigo_reserva,
        "tipo": tipo,
        "detalle": detalle,
        "origen": origen,
        "destino": destino,
        "fecha_viaje": fecha.isoformat(),
        "cliente_nombre": cliente_nombre,
        "cliente_contacto": cliente_contacto,
        "preferencias": preferencias,
        "total": total,
        "estado": "confirmada",
    }
    return (
        jsonify(
            {
                "ok": True,
                "compra": compra,
                "wa_url": wa_url,
                "wa_mensaje": wa_mensaje,
            }
        ),
        201,
    )


# ---------- Panel de administración ----------
def requiere_admin():
    u = session.get("user")
    return u if u and u["rol"] == "admin" else None


@app.route("/api/admin/compras")
def admin_compras():
    if not requiere_admin():
        return jsonify({"ok": False, "error": "No autorizado"}), 403
    conn = db()
    try:
        rows = conn.fetchall("SELECT * FROM compras ORDER BY created_at DESC, id DESC")
    finally:
        conn.close()
    for r in rows:
        r["fecha_viaje"] = iso(r["fecha_viaje"])
        r["created_at"] = iso(r["created_at"])
        r["total"] = int(round(float(r["total"])))
    return jsonify(rows)


@app.route("/api/admin/compras/<int:cid>", methods=["PATCH"])
def admin_actualizar_compra(cid):
    if not requiere_admin():
        return jsonify({"ok": False, "error": "No autorizado"}), 403
    estado = (request.get_json() or {}).get("estado")
    if estado not in ("confirmada", "pendiente", "cancelada"):
        return jsonify({"ok": False, "error": "Estado inválido"}), 400
    conn = db()
    try:
        n = conn.execute("UPDATE compras SET estado=%s WHERE id=%s", (estado, cid))
        conn.commit()
    finally:
        conn.close()
    if n == 0:
        return jsonify({"ok": False, "error": "No existe"}), 404
    return jsonify({"ok": True})


@app.route("/api/admin/cotizaciones")
def admin_cotizaciones():
    if not requiere_admin():
        return jsonify({"ok": False, "error": "No autorizado"}), 403
    conn = db()
    try:
        rows = conn.fetchall(
            """SELECT c.*, b.nombre AS combo FROM cotizaciones c
               LEFT JOIN combos b ON b.id = c.combo_id
               ORDER BY c.creado_en DESC, c.id DESC"""
        )
    finally:
        conn.close()
    for r in rows:
        r["fecha_viaje"] = iso(r["fecha_viaje"])
        r["creado_en"] = iso(r["creado_en"])
        r["total"] = int(round(float(r.get("total") or 0)))
        r["tarifa_base"] = int(round(float(r.get("tarifa_base") or 0)))
    return jsonify(rows)


@app.route("/api/admin/cotizaciones/<int:cid>", methods=["PATCH"])
def actualizar_cotizacion(cid):
    if not requiere_admin():
        return jsonify({"ok": False, "error": "No autorizado"}), 403
    estado = (request.get_json() or {}).get("estado")
    if estado not in ("pendiente", "confirmada", "cancelada"):
        return jsonify({"ok": False, "error": "Estado inválido"}), 400
    conn = db()
    try:
        n = conn.execute("UPDATE cotizaciones SET estado=%s WHERE id=%s", (estado, cid))
        conn.commit()
    finally:
        conn.close()
    if n == 0:
        return jsonify({"ok": False, "error": "No existe"}), 404
    return jsonify({"ok": True})


# ---------- Admin: usuarios ----------
@app.route("/api/admin/usuarios")
def admin_usuarios():
    if not requiere_admin():
        return jsonify({"ok": False, "error": "No autorizado"}), 403
    conn = db()
    try:
        rows = conn.fetchall("SELECT id, usuario, rol, creado_en FROM usuarios ORDER BY id")
    finally:
        conn.close()
    for r in rows:
        r["creado_en"] = iso(r["creado_en"])
    return jsonify(rows)


@app.route("/api/admin/usuarios", methods=["POST"])
def admin_crear_usuario():
    if not requiere_admin():
        return jsonify({"ok": False, "error": "No autorizado"}), 403
    d = request.get_json() or {}
    usuario = limpiar(d.get("usuario"), 50)
    password = d.get("password", "")
    rol = d.get("rol") if d.get("rol") in ("admin", "cliente") else "cliente"
    if not usuario or len(password) < 4:
        return (
            jsonify(
                {
                    "ok": False,
                    "error": "Usuario requerido y contraseña de mínimo 4 caracteres",
                }
            ),
            400,
        )
    conn = db()
    try:
        if conn.fetchone("SELECT id FROM usuarios WHERE usuario=%s", (usuario,)):
            return jsonify({"ok": False, "error": "El usuario ya existe"}), 400
        nuevo_id = conn.insert(
            "INSERT INTO usuarios (usuario, password_hash, rol) VALUES (%s,%s,%s)",
            (usuario, generate_password_hash(password), rol),
        )
        conn.commit()
    finally:
        conn.close()
    return jsonify({"ok": True, "id": nuevo_id}), 201


@app.route("/api/admin/usuarios/<int:uid>", methods=["DELETE"])
def admin_borrar_usuario(uid):
    u = requiere_admin()
    if not u:
        return jsonify({"ok": False, "error": "No autorizado"}), 403
    if u["id"] == uid:
        return (
            jsonify({"ok": False, "error": "No puedes eliminar tu propio usuario"}),
            400,
        )
    conn = db()
    try:
        n = conn.execute("DELETE FROM usuarios WHERE id=%s", (uid,))
        conn.commit()
    finally:
        conn.close()
    if n == 0:
        return jsonify({"ok": False, "error": "No existe"}), 404
    return jsonify({"ok": True})


# ---------- Admin: combos ----------
def validar_combo(d):
    nombre = limpiar(d.get("nombre"), 100)
    detalle = limpiar(d.get("detalle"), 255)
    try:
        precio = float(d.get("precio"))
        if precio < 0:
            raise ValueError
    except (TypeError, ValueError):
        return None
    if not nombre or not detalle:
        return None
    return nombre, detalle, precio


@app.route("/api/admin/combos", methods=["POST"])
def admin_crear_combo():
    if not requiere_admin():
        return jsonify({"ok": False, "error": "No autorizado"}), 403
    v = validar_combo(request.get_json() or {})
    if not v:
        return (
            jsonify(
                {"ok": False, "error": "Nombre, detalle y precio válido son obligatorios"}
            ),
            400,
        )
    conn = db()
    try:
        nuevo_id = conn.insert(
            "INSERT INTO combos (nombre, detalle, precio) VALUES (%s,%s,%s)", v
        )
        conn.commit()
    finally:
        conn.close()
    return jsonify({"ok": True, "id": nuevo_id}), 201


@app.route("/api/admin/combos/<int:cid>", methods=["PATCH"])
def admin_actualizar_combo(cid):
    if not requiere_admin():
        return jsonify({"ok": False, "error": "No autorizado"}), 403
    v = validar_combo(request.get_json() or {})
    if not v:
        return (
            jsonify(
                {"ok": False, "error": "Nombre, detalle y precio válido son obligatorios"}
            ),
            400,
        )
    conn = db()
    try:
        n = conn.execute(
            "UPDATE combos SET nombre=%s, detalle=%s, precio=%s WHERE id=%s", (*v, cid)
        )
        conn.commit()
    finally:
        conn.close()
    if n == 0:
        return jsonify({"ok": False, "error": "No existe"}), 404
    return jsonify({"ok": True})


@app.route("/api/admin/combos/<int:cid>", methods=["DELETE"])
def admin_borrar_combo(cid):
    if not requiere_admin():
        return jsonify({"ok": False, "error": "No autorizado"}), 403
    conn = db()
    try:
        n = conn.execute("DELETE FROM combos WHERE id=%s", (cid,))
        conn.commit()
    finally:
        conn.close()
    if n == 0:
        return jsonify({"ok": False, "error": "No existe"}), 404
    return jsonify({"ok": True})


# ---------- Admin: destinos ----------
def validar_destino(d):
    nombre = limpiar(d.get("nombre"), 100)
    imagen = limpiar(d.get("imagen"), 255)
    subtitulo = limpiar(d.get("subtitulo"), 200)
    descripcion = limpiar(d.get("descripcion"), 1000)
    incluye = limpiar(d.get("incluye"), 500)
    slug = slugify(d.get("slug") or nombre)
    try:
        precio_base = float(d.get("precio_base", TARIFA_ESTANDAR_DEFAULT))
        if precio_base < 0:
            raise ValueError
    except (TypeError, ValueError):
        return None
    if not nombre or not imagen:
        return None
    return slug, nombre, subtitulo, descripcion, incluye, precio_base, imagen


@app.route("/api/admin/destinos", methods=["POST"])
def admin_crear_destino():
    if not requiere_admin():
        return jsonify({"ok": False, "error": "No autorizado"}), 403
    v = validar_destino(request.get_json() or {})
    if not v:
        return (
            jsonify(
                {"ok": False, "error": "Nombre, imagen y precio base válido son obligatorios"}
            ),
            400,
        )
    conn = db()
    try:
        slug = v[0]
        if conn.fetchone("SELECT id FROM destinos WHERE slug=%s", (slug,)):
            slug = f"{slug}-{secrets.token_hex(2)}"
            v = (slug, *v[1:])
        nuevo_id = conn.insert(
            """INSERT INTO destinos
               (slug, nombre, subtitulo, descripcion, incluye, precio_base, imagen)
               VALUES (%s,%s,%s,%s,%s,%s,%s)""",
            v,
        )
        conn.commit()
    finally:
        conn.close()
    return jsonify({"ok": True, "id": nuevo_id}), 201


@app.route("/api/admin/destinos/<int:did>", methods=["PATCH"])
def admin_actualizar_destino(did):
    if not requiere_admin():
        return jsonify({"ok": False, "error": "No autorizado"}), 403
    v = validar_destino(request.get_json() or {})
    if not v:
        return (
            jsonify(
                {"ok": False, "error": "Nombre, imagen y precio base válido son obligatorios"}
            ),
            400,
        )
    conn = db()
    try:
        n = conn.execute(
            """UPDATE destinos
               SET slug=%s, nombre=%s, subtitulo=%s, descripcion=%s,
                   incluye=%s, precio_base=%s, imagen=%s
               WHERE id=%s""",
            (*v, did),
        )
        conn.commit()
    finally:
        conn.close()
    if n == 0:
        return jsonify({"ok": False, "error": "No existe"}), 404
    return jsonify({"ok": True})


@app.route("/api/admin/destinos/<int:did>", methods=["DELETE"])
def admin_borrar_destino(did):
    if not requiere_admin():
        return jsonify({"ok": False, "error": "No autorizado"}), 403
    conn = db()
    try:
        n = conn.execute("DELETE FROM destinos WHERE id=%s", (did,))
        conn.commit()
    finally:
        conn.close()
    if n == 0:
        return jsonify({"ok": False, "error": "No existe"}), 404
    return jsonify({"ok": True})


# ---------- Inicialización y migración segura de BD ----------
def _pk_col():
    if DB_BACKEND == "postgres":
        return "SERIAL PRIMARY KEY"
    if DB_BACKEND == "mysql":
        return "INT AUTO_INCREMENT PRIMARY KEY"
    return "INTEGER PRIMARY KEY AUTOINCREMENT"


def _columnas_tabla(conn, tabla):
    if DB_BACKEND == "sqlite":
        rows = conn.fetchall(f"PRAGMA table_info({tabla})")
        return {r["name"] for r in rows}
    if DB_BACKEND == "postgres":
        rows = conn.fetchall(
            "SELECT column_name FROM information_schema.columns WHERE table_name=%s",
            (tabla,),
        )
        return {r["column_name"] for r in rows}
    rows = conn.fetchall(f"SHOW COLUMNS FROM {tabla}")
    return {r["Field"] for r in rows}


def _asegurar_columnas(conn, tabla, columnas_ddl):
    existentes = _columnas_tabla(conn, tabla)
    for col, ddl in columnas_ddl:
        if col not in existentes:
            conn.execute(f"ALTER TABLE {tabla} ADD COLUMN {col} {ddl}")


def _acquire_process_lock():
    try:
        import fcntl

        lock_path = (
            f"{SQLITE_PATH}.init.lock"
            if DB_BACKEND == "sqlite"
            else os.path.join("/tmp", "your_destiny_init.lock")
        )
        fp = open(lock_path, "w")
        fcntl.flock(fp, fcntl.LOCK_EX)
        return fp
    except Exception:
        return None


def _release_process_lock(fp):
    if fp is None:
        return
    try:
        import fcntl

        fcntl.flock(fp, fcntl.LOCK_UN)
    except Exception:
        pass
    try:
        fp.close()
    except Exception:
        pass


def init_db():
    global _db_initialized
    with _init_lock:
        if _db_initialized:
            return

        lock_fp = _acquire_process_lock()
        try:
            conn = None
            reintentos = 30 if DB_BACKEND in ("mysql", "postgres") else 1
            ultimo_error = None
            for _ in range(reintentos):
                try:
                    conn = db()
                    break
                except Exception as exc:
                    ultimo_error = exc
                    time.sleep(2)
            if conn is None:
                raise RuntimeError(f"No se pudo conectar a la base de datos: {ultimo_error}")

            try:
                if DB_BACKEND == "sqlite":
                    conn.execute("PRAGMA journal_mode = WAL")

                pk = _pk_col()
                conn.execute(
                    f"""CREATE TABLE IF NOT EXISTS usuarios (
                        id {pk},
                        usuario VARCHAR(50) NOT NULL UNIQUE,
                        password_hash VARCHAR(255) NOT NULL,
                        rol VARCHAR(20) NOT NULL DEFAULT 'cliente',
                        creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )"""
                )
                conn.execute(
                    f"""CREATE TABLE IF NOT EXISTS destinos (
                        id {pk},
                        slug VARCHAR(120) UNIQUE,
                        nombre VARCHAR(100) NOT NULL,
                        subtitulo VARCHAR(200) DEFAULT '',
                        descripcion TEXT,
                        incluye TEXT,
                        precio_base NUMERIC(10,2) NOT NULL DEFAULT 110000,
                        imagen VARCHAR(255) NOT NULL
                    )"""
                )
                conn.execute(
                    f"""CREATE TABLE IF NOT EXISTS combos (
                        id {pk},
                        nombre VARCHAR(100) NOT NULL,
                        detalle VARCHAR(255) NOT NULL,
                        precio NUMERIC(10,2) NOT NULL
                    )"""
                )
                conn.execute(
                    f"""CREATE TABLE IF NOT EXISTS cotizaciones (
                        id {pk},
                        codigo VARCHAR(30),
                        origen VARCHAR(100) NOT NULL,
                        destino VARCHAR(100) NOT NULL,
                        fecha_viaje DATE NOT NULL,
                        nombre VARCHAR(100) NOT NULL,
                        contacto VARCHAR(150) NOT NULL,
                        combo_id INT NULL,
                        preferencias TEXT,
                        tarifa_base NUMERIC(10,2) NOT NULL DEFAULT 0,
                        recargos_json TEXT,
                        total NUMERIC(10,2) NOT NULL DEFAULT 0,
                        estado VARCHAR(20) NOT NULL DEFAULT 'pendiente',
                        creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        CONSTRAINT fk_cot_combo FOREIGN KEY (combo_id)
                            REFERENCES combos(id) ON DELETE SET NULL
                    )"""
                )
                conn.execute(
                    f"""CREATE TABLE IF NOT EXISTS compras (
                        id {pk},
                        codigo_reserva VARCHAR(40) NOT NULL UNIQUE,
                        tipo VARCHAR(20) NOT NULL,
                        detalle VARCHAR(255) NOT NULL,
                        origen VARCHAR(100) NOT NULL,
                        destino VARCHAR(150) NOT NULL,
                        fecha_viaje DATE NOT NULL,
                        cliente_nombre VARCHAR(100) NOT NULL,
                        cliente_contacto VARCHAR(150) NOT NULL,
                        preferencias TEXT,
                        cotizacion_id INT NULL,
                        combo_id INT NULL,
                        total NUMERIC(10,2) NOT NULL,
                        estado VARCHAR(20) NOT NULL DEFAULT 'confirmada',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )"""
                )

                # Migración segura si existía una BD previa v2 sin las columnas nuevas
                _asegurar_columnas(
                    conn,
                    "destinos",
                    [
                        ("slug", "VARCHAR(120)"),
                        ("subtitulo", "VARCHAR(200) DEFAULT ''"),
                        ("incluye", "TEXT"),
                        ("precio_base", "NUMERIC(10,2) NOT NULL DEFAULT 110000"),
                    ],
                )
                _asegurar_columnas(
                    conn,
                    "cotizaciones",
                    [
                        ("codigo", "VARCHAR(30)"),
                        ("tarifa_base", "NUMERIC(10,2) NOT NULL DEFAULT 0"),
                        ("recargos_json", "TEXT"),
                        ("total", "NUMERIC(10,2) NOT NULL DEFAULT 0"),
                    ],
                )

                # Seed idempotente de usuario admin
                if not conn.fetchone("SELECT id FROM usuarios WHERE usuario=%s", ("admin",)):
                    try:
                        conn.insert(
                            "INSERT INTO usuarios (usuario, password_hash, rol) VALUES (%s,%s,%s)",
                            ("admin", generate_password_hash("1234"), "admin"),
                        )
                    except Exception:
                        pass

                # Seed o actualización de catálogo de destinos
                if conn.fetchone("SELECT COUNT(*) AS n FROM destinos")["n"] == 0:
                    conn.executemany(
                        """INSERT INTO destinos
                           (slug, nombre, subtitulo, descripcion, incluye, precio_base, imagen)
                           VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                        DESTINOS_SEED,
                    )
                else:
                    # Si venían de v2 (sin slug/incluye), enriquecerlos automáticamente
                    seed_por_nombre = {normalizar_texto(d[1]): d for d in DESTINOS_SEED}
                    actuales = conn.fetchall("SELECT id, nombre, slug, incluye FROM destinos")
                    for row in actuales:
                        if not row.get("slug") or not row.get("incluye"):
                            seed = seed_por_nombre.get(normalizar_texto(row["nombre"]))
                            if seed:
                                conn.execute(
                                    """UPDATE destinos
                                       SET slug=%s, subtitulo=%s, descripcion=%s,
                                           incluye=%s, precio_base=%s
                                       WHERE id=%s""",
                                    (seed[0], seed[2], seed[3], seed[4], seed[5], row["id"]),
                                )
                            else:
                                conn.execute(
                                    "UPDATE destinos SET slug=%s WHERE id=%s",
                                    (slugify(row["nombre"]), row["id"]),
                                )

                # Seed de combos
                if conn.fetchone("SELECT COUNT(*) AS n FROM combos")["n"] == 0:
                    conn.executemany(
                        "INSERT INTO combos (nombre, detalle, precio) VALUES (%s,%s,%s)",
                        [
                            ("Combo Caribe", "Cartagena + Santa Marta", 250000),
                            ("Combo Café", "Salento + Pereira", 180000),
                            ("Combo Urbano", "Bogotá + Medellín", 200000),
                        ],
                    )

                conn.commit()
                _db_initialized = True
            finally:
                conn.close()
        finally:
            _release_process_lock(lock_fp)


# Inicializar automáticamente al cargar el módulo (necesario para gunicorn app:app en Render)
init_db()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)
