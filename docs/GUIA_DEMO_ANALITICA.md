# Guía: qué se ve en la app web (demo)

Para quien **prueba y explica la página**.  
No es la explicación del modelo ni de la API: es **lo que hay en pantalla** y **qué significa cada número**.

---

## Antes

- Abrir **http://localhost:5173**
- Archivo de prueba: `samples/reviews_sample.xlsx`
- Optimización: **activada**

---

## 1. Flujo visual de la página

```text
1. Subir Excel (+ dominio y opciones)
2. Procesar
3. RESULTADO NÚCLEO (número grande + tarjetas + descargar)
4. ANALÍTICA (más abajo: supuestos, ahorro, gráficas, tabla)
5. Clasificación de reseñas (preview)
6. (Opcional) Footer: reportar un problema
```

---

## 2. Zona de carga (arriba)

| Qué se ve | Qué es | Qué puedes decir |
|-----------|--------|------------------|
| Zona de soltar archivos | Subes uno o varios `.xlsx` | “Aquí entra el Excel con el texto a analizar.” |
| **Dominio** | Tipo de clasificación (reseñas, contratos, incidencias) | “Cambia cómo se etiquetan las filas, no el conteo de tokens.” |
| **USD / millón de tokens** | Precio de referencia del “mercado” de IA | Ver sección 4.1 |
| **Volumen diario** | Cuántas piezas imaginas procesar **al día** | Ver sección 4.2 |
| **Optimización ON/OFF** | Si se traduce ES→EN o no | “ON = medimos ahorro real con traducción.” |
| Botón **Procesar** | Lanza el análisis | — |

---

## 3. Resultado núcleo (lo primero que aparece)

### 3.1 El número grande
- **Qué es:** tokens **ahorrados** en **este** lote (si optimización está ON).  
- **Cómo se entiende:** tokens en español **menos** tokens en la versión optimizada (inglés).  
- **Frase:** *“Este número es el ahorro de tokens de este archivo.”*

### 3.2 Tarjetas

| Tarjeta | Qué muestra | Cómo explicarlo |
|---------|-------------|-----------------|
| **Tokens originales** | Conteo del texto en **español** | “Así de ‘caro’ era el lote sin optimizar.” |
| **Tokens optimizados** | Conteo después de pasar a **inglés** | “Así queda el mismo contenido optimizado.” |
| **Tiempo de proceso** | Segundos o milisegundos del pipeline | “Cuánto tardó de punta a punta.” |
| **Costo ref. ahorrado** | Ese ahorro de tokens pasado a **dólares** | Usa el precio de “USD / millón” (abajo). |

**Fórmula mental del $ de este lote:**

> Ahorro en $ ≈ (tokens ahorrados ÷ 1 000 000) × (USD por millón)

Ejemplo: si ahorras 1 000 tokens y el millón vale **$2.50**:  
`1000 / 1_000_000 × 2.50 = $0.0025` en este lote (parece poco; por eso después se proyecta a volumen diario/mensual).

### 3.3 Botón Descargar Excel
- Archivo de **salida** con filas ya trabajadas (texto, tokens, clasificación…).  
- *“No solo miramos números: entregamos un Excel usable.”*

### 3.4 Línea de detalle
Suele decir filas, filas únicas, dominio, si entró en el tiempo objetivo, método (reglas / optimización ON).  
Solo menciónalo si te preguntan.

---

## 4. Analítica (la parte de “¿y si hiciera esto todos los días?”)

Baja en la misma página. Aquí entran el **precio del millón** y el **volumen diario**.

### 4.1 USD / millón de tokens (precio de referencia)

| | |
|--|--|
| **Qué es** | Cuánto costaría **1 millón de tokens** en un modelo de IA de referencia (ej. **$2.50**). |
| **Para qué** | Convertir “tokens ahorrados” en **dinero**. |
| **Se puede cambiar** | Sí: si pones otro precio y recalculas, cambian los $ de ahorro y las proyecciones. |
| **Frase** | *“Asumimos que el millón de tokens cuesta X dólares; con eso pasamos el ahorro a plata.”* |

No es que FeedbackIQ te cobre eso: es un **supuesto** para simular costo de usar un LLM.

### 4.2 Volumen diario

| | |
|--|--|
| **Qué es** | Cuántas reseñas/textos crees procesar **por día** (ej. **10 000**). |
| **Para qué** | El lote del Excel puede ser chico (15, 500 filas). El volumen diario **escala** el ahorro a la vida real. |
| **Se puede cambiar** | Sí: más volumen diario → más ahorro diario y mensual estimado. |
| **Frase** | *“Este archivo es una muestra; el volumen diario imagina cuánto haríamos cada día en producción.”* |

### 4.3 Ahorro diario estimado

- Toma el ahorro del lote, lo **proporciona** al volumen diario.  
- *“Si cada día procesáramos tantas piezas como dice el volumen diario, ahorraríamos unos $ al día.”*

### 4.4 Ahorro mensual estimado

- Suele ser **ahorro diario × 30**.  
- *“Eso al mes se ve en este número (más grande y más ‘vendible’).”*

### 4.5 Punto de equilibrio / break-even

- Responde: *“¿Desde cuánto volumen o tamaño de texto ‘vale la pena’ optimizar?”*  
- En nuestra app el optimizador local es barato; igual se muestra como **indicador de negocio**.  
- No te enredes: *“Es la frontera a partir de la cual el ahorro compensa el costo de optimizar.”*

### 4.6 Tabla comparativa a / b / c (si aparece)

| Letra | Qué es en simple |
|-------|------------------|
| **(a) Diccionario** | Forma vieja / referencia (no es la profesional). |
| **(b) Neuronal ★** | La optimización **real** (la que importa). |
| **(c) Dedup** | Textos repetidos: menos trabajo duplicado. |

### 4.7 Gráfica “costo por modelo”

- Mismo lote de tokens.  
- Barras: **sin optimización** vs **con optimización** para varios modelos (Gemini, GPT, etc.).  
- *“El ahorro de tokens se nota más cuando el modelo es caro.”*

### 4.8 Proyección 30 días

- Línea que **acumula** el ahorro día a día.  
- *“Si el ritmo se mantiene un mes, el ahorro se ve así.”*

### 4.9 Latencia por etapa

- Dónde se fue el tiempo (leer Excel, traducir, exportar…).  
- *“Para ver si el cuello de botella es la traducción u otra cosa.”*

### 4.10 Distribución de tipos

- Cómo se clasificaron las reseñas (crash, login, pago…).  
- *“Además del ahorro, la app entiende de qué tratan los textos.”*

### 4.11 Tabla multi-modelo

| Columna | Significado |
|--------|-------------|
| **$/MTok** | Precio del millón en ese modelo |
| **Sin opt.** | Costo del lote **sin** optimizar |
| **Con opt.** | Costo del lote **con** menos tokens |
| **Ahorro** | Diferencia en $ |

---

## 5. Preview de clasificación

Lista de filas: texto, tipo (crash, etc.), tokens antes → después.  
*“Cada fila del Excel queda etiquetada y con su conteo.”*

---

## 6. Footer (opcional)

**¿Encontraste un problema?** → envía un reporte (n8n → Sheets + mail).  
Solo si n8n está activo. No es la parte de tokens.

---

## 7. Guion de 1 minuto (quien prueba la web)

1. “Subo el Excel y proceso con optimización activada.”  
2. “El número grande son los **tokens ahorrados** de este lote.”  
3. “Aquí tokens en español, aquí en la versión optimizada, el tiempo y el $ de este archivo.”  
4. “El precio por millón y el volumen diario son **supuestos**: sirven para proyectar ahorro **diario y mensual** si esto se hiciera todos los días.”  
5. “Abajo comparamos modelos y la proyección a 30 días.”  
6. “Y puedo descargar el Excel de resultados.”

---

## 8. Números por defecto (si no los cambian)

| Campo | Valor típico en la app |
|--------|-------------------------|
| USD / millón de tokens | **2.50** |
| Volumen diario | **10 000** |
| Días del mes (proyección) | **30** |

Si en la demo los cambian en pantalla, explica con **los valores que se vean en ese momento**.
