# Your Destiny — Plataforma de Viajes (Flask + Gunicorn)

Agencia de transporte terrestre en Colombia. Incluye cotizador con cálculo real de tarifas y recargos, catálogo interactivo de destinos destacados con reseñas y tarifas base, compra directa de combos con precio fijo, comprobantes con notificación por WhatsApp (`wa.me`) y panel de administración completo.

## Funcionalidades principales

- **Cotizar y comprar viaje (`/cuendesti.html`):** flujo en 2 pasos. Calcula tarifas reales según ruta (`origen → destino`) y suma recargos opcionales (asiento ventana, horario nocturno, servicio VIP, equipaje adicional, mascota), aplicando una tarifa estándar segura para ciudades fuera del catálogo. Permite confirmar la compra al instante y abrir WhatsApp con el resumen prellenado.
- **Destinos destacados (`/destacados.html`):** galería dinámica con modal interactivo que muestra reseña turística completa, qué incluye el viaje, tarifa base y botón directo para reservar con el destino precargado.
- **Combos y sugerencias (`/comysug.html`):** checkout directo en modal con nombre y precio fijo bloqueados. Guarda la compra a nombre del cliente y entrega el comprobante con código de reserva y botón de WhatsApp.
- **Panel de administración (`/admin.html`):** protegido por sesión (`admin` / `1234`). Permite gestionar **Compras**, **Cotizaciones**, **Usuarios**, **Combos** y **Destinos**.

## Ejecución local rápida (sin Docker ni MySQL)

Por defecto utiliza SQLite (`your_destiny.db`), así que arranca en segundos:

```bash
pip install -r requirements.txt
python app.py
```

O con Gunicorn (igual que en producción):

```bash
gunicorn app:app --bind 0.0.0.0:5000
```

## Ejecución con Docker Compose (Flask + MySQL 8)

```bash
docker compose up -d --build
```

## Despliegue gratuito en Render

1. Sube esta carpeta a un repositorio en GitHub.
2. En [Render](https://render.com), crea un **New Web Service** (o importa directamente `render.yaml` con **New Blueprint**):
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn app:app`
   - **Health Check Path:** `/api/health`
3. Configura las variables de entorno en Render:
   - `SECRET_KEY`: cadena aleatoria segura
   - `WHATSAPP_NUMBER`: tu número de WhatsApp en formato internacional sin `+` (ej. `573227618659`)
   - `DATABASE_URL` *(opcional)*: URL de PostgreSQL (por ejemplo en **Neon**, **Supabase** o **Render Postgres**). Si no se configura, la app funciona automáticamente con SQLite local.

> **Nota sobre Render Free:** el servicio se suspende tras 15 minutos sin tráfico (~40s en despertar en la primera carga) y el disco local de SQLite es efímero entre reinicios/deploys. Para persistencia permanente sin costo, conecta una base PostgreSQL gratuita en Neon o Supabase usando `DATABASE_URL`.

## Variables de entorno soportadas

| Variable | Descripción | Valor por defecto |
|---|---|---|
| `PORT` | Puerto HTTP asignado por Render | `5000` |
| `SECRET_KEY` | Clave para firmar cookies de sesión | `cambia-esta-clave-en-produccion` |
| `WHATSAPP_NUMBER` | Número destino para enlaces `wa.me` (sin `+`) | `573227618659` |
| `DATABASE_URL` | URL PostgreSQL (`postgresql://...`) | *(vacío → usa SQLite)* |
| `DB_HOST`, `DB_USER`, `DB_PASSWORD`, `DB_NAME` | Configuración MySQL (Docker Compose) | *(vacío → usa SQLite)* |

## Endpoints principales de la API

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/api/health` | Estado del servicio y motor de BD activo |
| `GET` | `/api/config` | Número de WhatsApp, ciudades sugeridas y recargos |
| `GET` | `/api/destinos` | Catálogo de destinos con reseña, incluye y tarifa base |
| `GET` | `/api/destinos/<slug>` | Detalle de un destino por slug |
| `GET` | `/api/combos` | Listado de combos con precio fijo |
| `POST` | `/api/cotizar` | Calcula tarifa + recargos y guarda la cotización |
| `POST` | `/api/compras` | Registra compra de combo o tiquete y devuelve comprobante + `wa_url` |
| `GET/PATCH` | `/api/admin/compras` | Gestión de compras (solo admin) |
| `GET/PATCH` | `/api/admin/cotizaciones` | Gestión de cotizaciones (solo admin) |
| `GET/POST/DELETE` | `/api/admin/usuarios` | Gestión de usuarios (solo admin) |
| `POST/PATCH/DELETE` | `/api/admin/combos` | CRUD de combos (solo admin) |
| `POST/PATCH/DELETE` | `/api/admin/destinos` | CRUD de destinos (solo admin) |
