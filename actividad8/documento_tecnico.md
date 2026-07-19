# Documento Técnico — Monitorización, Mantenimiento y Gobernanza Operativa

> Actividad 8 — Gestión de Proyectos de Inteligencia Artificial (Universidad
> Tecmilenio). Construida sobre la Fase 2 (API de predicción de abandono escolar,
> desplegada en `https://fase2-abandono-escolar.onrender.com`).
> Alumno: Alejandro Islas López (matrícula T07136481).

## Objetivo

Implementar la monitorización, mantenimiento y gobernanza operativa del servicio de
predicción de abandono escolar, asegurando su continuidad y confiabilidad, con
evidencia documentada de cada fase del proceso, incluyendo el uso de herramientas de
tracking y la simulación de incidentes críticos reales contra el despliegue en
producción.

---

## 1. Definición de indicadores (métricas, logs, trazas)

### 1.1 Métricas

Capturadas por [`actividad8/scripts/monitor.py`](scripts/monitor.py) en cada ciclo de
monitoreo y registradas como serie de tiempo en MLflow (experimento
`actividad8_monitoreo_produccion`):

| Métrica | Descripción | Tipo |
|---|---|---|
| `health_latency_ms` | Latencia de `GET /health` | Golden signal: latencia |
| `predict_latency_ms` | Latencia promedio de dos llamadas a `POST /predict` | Golden signal: latencia |
| `disponible` | 1 si `/health` y ambos `/predict` responden 200, 0 si no | Golden signal: errores |
| `canary_correcto` | 1 si ambos canary checks clasifican correctamente, 0 si no | Calidad del modelo |
| `cold_start` | 1 si el primer ciclo tardó >5s (esperado tras inactividad) | Contexto operativo |
| `alertas_disparadas` | Número de alertas disparadas en el ciclo | Resumen de salud |

No se mide *tráfico* ni *saturación* (2 de los 4 Golden Signals de SRE) porque el
servicio no expone métricas de infraestructura propias (CPU/memoria) fuera del
dashboard de Render, y el volumen de tráfico real es controlado por el propio
monitoreo (no hay usuarios concurrentes externos en esta entrega). Se documenta como
limitación conocida en la sección 6.

### 1.2 Logs

- **Logs de aplicación:** el servicio (`src/api.py`) usa el logger `uvicorn.error`
  para registrar advertencias de arranque (ej. modelo no encontrado) y Uvicorn
  registra cada petición HTTP con su código de respuesta. Visibles en Render →
  pestaña *Logs*.
- **Log de alertas (Actividad 8):**
  [`actividad8/evidencia/alertas_log.jsonl`](evidencia/alertas_log.jsonl) — un
  registro JSONL append-only con cada alerta disparada: timestamp, id de alerta,
  severidad, runbook asociado, y el ciclo de monitoreo completo que la originó
  (útil para *post-mortems* sin depender de que MLflow siga disponible).

### 1.3 Trazas

Este proyecto no implementa tracing distribuido (ej. OpenTelemetry) porque el
servicio es un único proceso sin llamadas downstream a otros servicios propios —no
hay una cadena de spans que trazar. En su lugar, cada ciclo de monitoreo actúa como
una "traza sintética" de la transacción completa (`health` → `predict` canary bajo →
`predict` canary alto), registrada con su `timestamp` y latencia por etapa en el log
de alertas y en MLflow. Si el servicio creciera a múltiples componentes (ej. un
servicio de preprocesamiento separado), esta sería la primera adición recomendada
(ver sección 6 del documento de validación).

---

## 2. Diseño de alertas inteligentes

Configuración completa en
[`actividad8/scripts/alertas_config.yaml`](scripts/alertas_config.yaml).

### 2.1 SLOs y error budgets

| SLO | Objetivo | Error budget |
|---|---|---|
| Disponibilidad | 99% (30 días) | ~7.2 horas/mes de indisponibilidad tolerada |
| Latencia `/predict` (p95) | < 2000ms | — (excluye cold start, ver nota) |
| Calidad del modelo | 100% canary checks correctos | 0 — cualquier falla es P1 |
| Estabilidad de datos | PSI < 0.10 en todas las variables | — |

### 2.2 Reglas de alerta (priorizadas por severidad/impacto operativo)

| ID | Nombre | Severidad | Condición |
|---|---|---|---|
| `ALERT-QUALITY-01` | Modelo degradado | **P1** | Canary check falla en ≥1 ciclo |
| `ALERT-AVAIL-01` | Servicio no disponible | **P1** | `/health` o `/predict` ≠ 200 |
| `ALERT-LAT-01` | Latencia elevada | P2 | >2000ms en 3 ciclos consecutivos |
| `ALERT-DRIFT-01` | Data drift | P2 | PSI ≥ 0.10 en alguna variable |
| `ALERT-LAT-02` | Cold start (informativo) | P3 | >5000ms en el primer ciclo tras inactividad |

**Criterio de priorización:** la severidad P1 se reserva para alertas donde el
servicio *parece* funcionar pero produce resultados incorrectos o inaccesibles
(impacto directo e inmediato sobre la decisión que toma el usuario final —
coordinadores evaluando riesgo real de estudiantes). P2 son degradaciones de
experiencia o señales tempranas de riesgo futuro. P3 es puramente informativo, para
evitar que comportamiento esperado (cold start) se confunda con una alerta real y
genere ruido/fatiga de alertas.

### 2.3 Reducción de ruido

- `ALERT-LAT-01` requiere **3 ciclos consecutivos**, no un solo pico, para evitar
  alertar por variabilidad normal de red.
- `ALERT-LAT-02` (cold start) se evalúa y excluye **antes** de `ALERT-LAT-01`, para
  que el comportamiento esperado del plan gratuito de Render nunca dispare la alerta
  de latencia real.
- Las alertas se ordenan por severidad al registrarse (`registrar_alertas()` en
  `monitor.py`), de forma que un operador revisando el log siempre ve primero lo más
  crítico.

---

## 3. Descripción de dashboards

El dashboard operativo se implementa sobre la UI nativa de MLflow (experimento
`actividad8_monitoreo_produccion`), aprovechando que cada ciclo de monitoreo se
registra con `step` incremental dentro de un run — esto genera automáticamente
gráficas de línea por métrica a lo largo del tiempo, sin necesidad de una
herramienta de visualización adicional.

**Estructura (ver capturas en [`actividad8/evidencia/capturas/`](evidencia/capturas/)):**

1. **Lista de runs** (`01_mlflow_lista_runs.png`): un run por sesión de monitoreo
   (línea base, cada incidente, cada verificación post-rollback), con nombre,
   duración y fecha — permite ver de un vistazo el historial de sesiones de
   monitoreo.
2. **Overview de un run** (`02_incidente01_overview.png`): parámetros (URL
   monitoreada, número de ciclos, intervalo), métricas finales, y el commit exacto
   del código fuente (`monitor.py`) que generó esa corrida — trazabilidad completa
   entre código y datos observados.
3. **Panel de métricas por ciclo** (`03_.../04_...png`): 6 gráficas (una por
   métrica) con el step (ciclo) en el eje X — el panel central para *toma de
   decisiones en tiempo real*: un operador ve inmediatamente si `predict_latency_ms`
   o `canary_correcto` se salen de rango, y en qué ciclo exacto empezó.

**Por qué esta estructura y no un dashboard externo (Grafana/Streamlit):** para el
alcance de esta actividad, MLflow ya está integrado en el proyecto (Fase 2) y ofrece
series de tiempo por métrica sin infraestructura adicional. La limitación conocida es
que no es un dashboard "en vivo" (hay que ejecutar `monitor.py` para generar nuevos
puntos) — ver sección 6 del documento de validación para la extensión recomendada
(ej. cron job + Grafana) si el proyecto pasara a producción real.

---

## 4. Runbooks de respuesta a incidentes

Cuatro runbooks, uno por tipo de alerta, con diagnóstico → respuesta → verificación →
escalamiento:

- [`docs/runbook_modelo_degradado.md`](docs/runbook_modelo_degradado.md) — `ALERT-QUALITY-01` (P1)
- [`docs/runbook_disponibilidad.md`](docs/runbook_disponibilidad.md) — `ALERT-AVAIL-01` (P1)
- [`docs/runbook_latencia.md`](docs/runbook_latencia.md) — `ALERT-LAT-01` (P2)
- [`docs/runbook_drift.md`](docs/runbook_drift.md) — `ALERT-DRIFT-01` (P2)

Los runbooks de modelo degradado y latencia se **ejecutaron realmente** durante esta
actividad (no son solo procedimiento documentado); ver
[`incidentes/registro_incidentes.md`](incidentes/registro_incidentes.md) para la
evidencia completa con timestamps, comandos y resultados.

---

## 5. Estrategias de detección de data drift

### 5.1 Método

Se usa el **Population Stability Index (PSI)**, el estándar más común en monitoreo
de modelos de riesgo (crediticio, educativo, etc.), implementado en
[`actividad8/scripts/detectar_drift.py`](scripts/detectar_drift.py):

1. El dataset de referencia (`data/dataset_abandono.csv`, entrenamiento) se divide en
   10 bins por cuantiles, por cada variable numérica.
2. Se calcula qué porcentaje de un dataset nuevo ("producción") cae en cada bin.
3. `PSI = Σ (pct_nuevo - pct_referencia) × ln(pct_nuevo / pct_referencia)`
4. Umbrales: PSI < 0.10 sin drift, 0.10-0.25 moderado, ≥ 0.25 significativo.

Se aplica a las 6 variables numéricas y, con el mismo cálculo (2 bins), a las 2
variables categóricas (`condicion_beca`, `modalidad`).

### 5.2 Generación de datos de prueba

Al no contar con un flujo real de datos de producción, se generó
[`scripts/generar_dataset_drift.py`](scripts/generar_dataset_drift.py): 300 registros
sintéticos con drift deliberado en 4 de las 8 variables (menor promedio académico,
menor asistencia, más horas de trabajo, más modalidad en línea — un escenario
plausible de dificultad económica creciente entre estudiantes).

### 5.3 Resultado de la ejecución real

| Variable | PSI | Clasificación |
|---|---|---|
| `asistencia` | 0.2640 | **Significativo** |
| `promedio_academico` | 0.2558 | **Significativo** |
| `horas_trabajo_semanales` | 0.1960 | Moderado |
| `modalidad` | 0.1602 | Moderado |
| `semestre_actual` | 0.0486 | Sin drift |
| `distancia_campus` | 0.0346 | Sin drift |
| `materias_reprobadas` | 0.0273 | Sin drift |
| `condicion_beca` | 0.0019 | Sin drift |

El sistema detectó correctamente las 4 variables con drift deliberado (2
significativas, 2 moderadas) y no generó falsos positivos en las 4 variables sin
cambio de distribución. Reporte completo:
[`evidencia/reporte_drift.md`](evidencia/reporte_drift.md). Registrado también en
MLflow (run `deteccion_drift`,
[`evidencia/capturas/05_deteccion_drift.png`](evidencia/capturas/05_deteccion_drift.png)).

---

## 6. Documentación de respuesta automatizada

[`actividad8/scripts/rollback.py`](scripts/rollback.py) implementa dos modos de
respuesta automatizada a incidentes:

### 6.1 Rollback

```bash
python -m actividad8.scripts.rollback --modo rollback --commit-bueno <hash> --push
```

Restaura `models/modelo_abandono.joblib` desde un commit anterior conocido como
bueno (`git checkout <hash> -- <archivo>`), commitea y hace push, lo que dispara el
redeploy automático en Render (auto-deploy conectado a `main`). Es la respuesta más
rápida ante degradación del modelo: no requiere reentrenar.

### 6.2 Reentrenamiento con validación

```bash
python -m actividad8.scripts.rollback --modo reentrenar --push
```

Reentrena desde cero (`src/generate_data.py` + `src/train.py`) y **solo** acepta el
nuevo modelo como reemplazo si el F1 de prueba ≥ 0.80 (el objetivo SMART de la Fase
2); si no lo supera, aborta automáticamente y descarta el modelo reentrenado sin
tocar producción. Este control evita que una respuesta automatizada empeore un
incidente en lugar de resolverlo.

### 6.3 Salvaguarda de diseño

Ninguno de los dos modos hace `git push` a menos que se pase `--push` explícitamente
— sin ese flag, el script deja el cambio listo en el working tree para revisión
manual. Esto permite usar el script tanto para respuesta automática (con `--push`,
como se hizo en el incidente 2) como para preparar un cambio que un humano revisa
antes de confirmar.

### 6.4 Evidencia de ejecución real

El modo `rollback` se ejecutó realmente durante el incidente 2 (modelo degradado),
con salida de consola capturada íntegramente en
[`incidentes/registro_incidentes.md`](incidentes/registro_incidentes.md). El modo
`reentrenar` no se ejecutó como parte de un incidente real en esta entrega (ambos
incidentes se resolvieron con rollback simple), pero fue probado exitosamente en
desarrollo local antes de documentarse aquí.
