# FeedbackIQ × n8n — Reportes de problemas (guía paso a paso)

Esta guía asume que el **código de FeedbackIQ ya está listo** (formulario del footer + `POST /api/report`).  
Aquí solo armamos **n8n en tu laptop** y lo conectamos.

```
Usuario (footer) → FeedbackIQ backend (:4004) → Webhook n8n (:5678)
                                                      ↓
                                    reglas (Code) → Switch severidad
                                      ↓ crítica          ↓ media/baja
                                   Telegram            (sigue)
                                      └────────┬────────┘
                                               ↓
                                        Google Sheets
                                               ↓
                                             Email
```

---

## 0. Qué necesitas

| Herramienta | ¿Para qué? | ¿Obligatorio? |
|-------------|------------|---------------|
| Docker | Correr n8n local | Recomendado |
| n8n (Community) | Workflow | Sí |
| Cuenta Gmail / SMTP | Correo del reporte | Sí para el correo |
| Bot de Telegram + chat id | Alertas críticas | Opcional pero útil |
| Google Sheets | Bug tracker | Recomendado |
| Ollama | Clasificación con IA | **No** (opcional, sección 10) |

---

## 1. Instalar n8n (Docker)

En una terminal:

```bash
docker run -d \
  --name n8n \
  -p 5678:5678 \
  -v ~/.n8n:/home/node/.n8n \
  --restart unless-stopped \
  n8nio/n8n
```

Abre: **http://localhost:5678**

La primera vez crea un usuario admin (solo local).

Comprobar que corre:

```bash
docker ps | grep n8n
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:5678
```

Detener / arrancar:

```bash
docker stop n8n
docker start n8n
```

---

## 2. Configurar FeedbackIQ (backend)

### 2.1 Dependencia Python

Si aún no está `httpx` en el venv:

```bash
/home/canela/FeedBackIQ/backend/.venv/bin/pip install "httpx>=0.27.0"
```

### 2.2 Archivo `backend/.env`

Copia el ejemplo y edita:

```bash
cd /home/canela/FeedBackIQ/backend
cp -n .env.example .env
```

Mientras pruebas **solo el formulario** (sin n8n):

```env
N8N_DRY_RUN=true
N8N_WEBHOOK_URL=
N8N_WEBHOOK_SECRET=
```

Cuando el Webhook de n8n esté listo (paso 3):

```env
N8N_DRY_RUN=false
N8N_WEBHOOK_URL=http://localhost:5678/webhook/feedbackiq-report
N8N_WEBHOOK_SECRET=pon-un-secreto-largo-aqui
N8N_WEBHOOK_HEADER_NAME=X-FeedbackIQ-Secret
```

> **Importante:** reinicia el backend después de cambiar `.env`.

---

## 3. Crear el workflow en n8n (orden de nodos)

Crea un workflow vacío: **New workflow** → nómbralo `FeedbackIQ Reportes`.

### 3.1 Nodo Webhook

1. Clic **+** → busca **Webhook**.
2. Configura:
   - **HTTP Method:** `POST`
   - **Path:** `feedbackiq-report`  
     (la URL quedará tipo `http://localhost:5678/webhook/feedbackiq-report`)
   - **Authentication:** `Header Auth` (recomendado)
     - Crea credencial Header Auth:
       - **Name:** `X-FeedbackIQ-Secret` (mismo nombre que en `.env`)
       - **Value:** el mismo secreto que `N8N_WEBHOOK_SECRET`
3. **Respond:** `Immediately` (o “When Last Node Finishes” si prefieres).
4. Pulsa **Listen for test event** si quieres capturar un POST de prueba.

Guarda la **Production URL** del webhook (botón del nodo → Production URL).  
Esa es la que va en `N8N_WEBHOOK_URL`.

> En n8n hay URL de *test* y de *production*. Con el workflow **activo** (toggle arriba a la derecha) usa la de production.

### 3.2 Nodo Set (interruptor opcional de IA)

1. Añade **Set** (o “Edit Fields”).
2. Campo booleano:
   - Name: `usar_ia_local`
   - Value: `false`  ← **déjalo en false** para empezar (solo reglas).

### 3.3 Nodo IF

1. Condición: `usar_ia_local` **is equal to** `true`.
2. Rama **false** → va al Code de reglas (3.4).  
3. Rama **true** → solo si más adelante activas Ollama (sección 10).

### 3.4 Nodo Code — clasificación por reglas

1. Añade **Code**.
2. Abre el archivo del repo:

   `docs/n8n/code-clasificacion.js`

3. Copia **todo** el contenido y pégalo en el nodo.
4. Conecta: `IF (false)` → `Code (reglas)`.

Este nodo produce:

| Campo | Ejemplo |
|-------|---------|
| `severidad` | `critica` \| `media` \| `baja` |
| `modulo_probable` | `Carga/exportación de Excel` |
| `resumen` | primeros 120 caracteres |
| `texto_original` | mensaje completo |

### 3.5 Nodo Switch (severidad)

1. Añade **Switch**.
2. Mode: Rules / value = `{{ $json.severidad }}`
3. Salidas:
   - Output 0: `critica`
   - Output 1: `media` (o “fallback” para media y baja)
   - Output 2: `baja` (opcional; puedes unir media y baja)

### 3.6 Nodo Telegram (solo crítica)

1. Habla con **@BotFather** en Telegram → `/newbot` → copia el **token**.
2. Escribe a tu bot, luego obtén tu chat id (p. ej. con `@userinfobot` o la API `getUpdates`).
3. En n8n: nodo **Telegram** → credencial con el token.
4. **Chat ID:** el tuyo.
5. **Text** ejemplo:

```text
🚨 FeedbackIQ CRÍTICO
Módulo: {{ $json.modulo_probable }}
Resumen: {{ $json.resumen }}

{{ $json.texto_original }}
```

6. Conecta: `Switch (critica)` → `Telegram` → (sigue a Sheets).

Las ramas media/baja van **directo** a Sheets (sin Telegram).

### 3.7 Nodo Google Sheets

1. Crea una hoja en Google Drive, por ejemplo `FeedbackIQ_Bugs`.
2. Encabezados en la fila 1:

```text
fecha | severidad | modulo | resumen | texto_original | source
```

3. En n8n: **Google Sheets** → Append row.
4. Mapea columnas a `{{ $json.timestamp }}`, `severidad`, `modulo_probable`, etc.
5. Conecta Telegram **y** media/baja → **Sheets**.

### 3.8 Nodo Email / Gmail

1. Añade **Gmail** o **Email Send (SMTP)**.
2. Asunto:

```text
[FeedbackIQ][{{ $json.severidad }}] {{ $json.modulo_probable }}
```

3. Cuerpo (HTML o texto) con resumen + texto original.
4. Conecta **después** de Sheets.

### 3.9 Activar el workflow

Toggle **Active** (arriba a la derecha) = ON.

---

## 4. Conectar FeedbackIQ

1. Copia la Production URL del Webhook.
2. En `backend/.env`:

```env
N8N_DRY_RUN=false
N8N_WEBHOOK_URL=http://localhost:5678/webhook/feedbackiq-report
N8N_WEBHOOK_SECRET=el-mismo-secreto-del-header-auth
N8N_WEBHOOK_HEADER_NAME=X-FeedbackIQ-Secret
```

3. Reinicia backend:

```bash
cd /home/canela/FeedBackIQ
# detén el proceso anterior si está corriendo
fuser -k 4004/tcp 2>/dev/null
cd backend && .venv/bin/python run.py
```

4. Frontend:

```bash
cd /home/canela/FeedBackIQ/frontend && npm run dev
```

5. Abre http://localhost:5173 → baja al footer → envía un mensaje de prueba:

```text
El excel no carga y la app se cierra al exportar
```

Debería marcar severidad **critica** y módulo de Excel.

---

## 5. Probar solo el webhook (sin UI)

```bash
curl -s -X POST http://localhost:5678/webhook/feedbackiq-report \
  -H "Content-Type: application/json" \
  -H "X-FeedbackIQ-Secret: el-mismo-secreto" \
  -d '{"mensaje":"El excel no carga y se cierra","source":"curl-test"}'
```

Y vía backend:

```bash
curl -s -X POST http://127.0.0.1:4004/api/report \
  -H "Content-Type: application/json" \
  -d '{"mensaje":"El excel no carga y se cierra","page":"#/"}'
```

Estado del canal:

```bash
curl -s http://127.0.0.1:4004/api/report/status
```

---

## 6. Diagrama de nodos (checklist)

```
[Webhook POST /feedbackiq-report]
        │
        ▼
[Set: usar_ia_local = false]
        │
        ▼
[IF usar_ia_local?]
   false ──► [Code: reglas] ──► [Switch severidad]
   true  ──► (sección 10 Ollama) ──┘
                                      │
                    critica ──► [Telegram]
                                      │
                    media/baja ───────┤
                                      ▼
                              [Google Sheets]
                                      ▼
                                   [Email]
```

---

## 7. CORS (solo si el navegador llama a n8n directo)

En **esta arquitectura el navegador NO llama a n8n**: llama a FeedbackIQ (`/api/report`) y el backend reenvía.  
Eso evita CORS y oculta el secreto del webhook. **No necesitas CORS especial en n8n** para el flujo normal.

---

## 8. Seguridad mínima

- Header secret en el Webhook (`X-FeedbackIQ-Secret`).
- No expongas http://localhost:5678 a internet sin auth.
- Si demos desde otra red: `ngrok http 5678` y actualiza `N8N_WEBHOOK_URL` a la URL https de ngrok (el backend sigue en tu máquina; si el backend también está local, ngrok solo hace falta si n8n debe ser alcanzado desde fuera).

Para demo en la **misma laptop**: localhost basta.

---

## 9. Payload que envía el backend

```json
{
  "mensaje": "texto del usuario",
  "source": "feedbackiq-web",
  "timestamp": "2026-08-01T12:00:00+00:00",
  "page": "#/",
  "user_agent": "…",
  "severidad": "critica",
  "modulo_probable": "Carga/exportación de Excel",
  "resumen": "…",
  "texto_original": "…"
}
```

El nodo Code de n8n puede **recalcular** severidad/módulo; no importa si el backend ya los mandó.

---

## 10. Opcional: Ollama (IA local)

Solo cuando quieras mejor redacción. Por defecto **no lo uses**.

1. En el Set: `usar_ia_local = true`.
2. Rama true del IF → **HTTP Request**:
   - Method: POST  
   - URL: `http://host.docker.internal:11434/api/generate`  
     (si n8n está en Docker y Ollama en el host; en Linux a veces hace falta `--add-host=host.docker.internal:host-gateway` en el `docker run`)
   - Body JSON:

```json
{
  "model": "llama3.2:3b",
  "prompt": "Eres un clasificador de reportes FeedbackIQ. Responde SOLO JSON: {\"severidad\":\"critica|media|baja\",\"modulo_probable\":\"...\",\"resumen\":\"...\",\"texto_original\":\"...\"}. Reporte: {{ $json.mensaje }}",
  "format": "json",
  "stream": false
}
```

3. Timeout del nodo: **15–20 s**.  
4. On Error → **Continue (error output)** → conecta al Code de reglas.  
5. En éxito → Code `docs/n8n/code-parse-ollama.js` → mismo Switch de severidad.

---

## 11. Problemas frecuentes

| Síntoma | Qué revisar |
|---------|-------------|
| Form dice “canal no configurado” | `N8N_WEBHOOK_URL` vacío y `N8N_DRY_RUN=false` |
| “n8n no respondió” | `docker ps`, puerto 5678, workflow **Active** |
| HTTP 403/401 desde backend | Header secret distinto al de n8n |
| Webhook 404 | Usando URL de test con workflow inactivo, o path mal escrito |
| Telegram no llega | Chat id incorrecto; escribiste antes al bot |
| Sheets vacío | Credencial Google; nombres de columna; Append en la hoja correcta |

---

## 12. Archivos del repo relacionados

| Archivo | Uso |
|---------|-----|
| `frontend/js/report-form.js` | Formulario footer |
| `backend/app/core/report_service.py` | Proxy al webhook |
| `backend/app/core/report_rules.py` | Reglas locales (espejo del Code n8n) |
| `docs/n8n/code-clasificacion.js` | Pegar en nodo Code |
| `docs/n8n/code-parse-ollama.js` | Pegar si usas Ollama |
| `backend/.env.example` | Variables de entorno |

---

Cuando termines el workflow, el flujo completo de sustentación es:

1. Usuario reporta en el footer  
2. Backend clasifica y reenvía a n8n  
3. n8n registra en Sheets + email  
4. Si es crítico → push de Telegram al móvil  
