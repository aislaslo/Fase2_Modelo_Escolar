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

## Glosario rápido

Todo el documento responde a una pregunta: **¿cómo sabemos que la API sigue
funcionando bien, y qué hacemos si deja de funcionar bien?** Es la misma lógica que
seguir la salud de un paciente: métricas = signos vitales, logs = bitácora, alertas =
cuándo llamar al doctor, dashboard = el monitor junto a la cama, runbook = protocolo
de emergencia, drift = el paciente cambió y ya no responde igual.

| Término | En palabras simples |
|---|---|
| Métrica | Un número que medimos repetidamente en el tiempo (latencia, disponibilidad) |
| SLO | Una promesa medible de qué tan bien debe funcionar el servicio (ej. "99% disponible") |
| Error budget | El margen de falla que nos permitimos antes de romper la promesa (99% ≈ 7.2h/mes) |
| p95 | "El 95% de las peticiones son más rápidas que este número" — más estricto que un promedio |
| P1 / P2 / P3 | Urgencia tipo triage de hospital: P1 = atender ya, P2 = revisar pronto, P3 = informativo |
| Canary check | Enviar un caso con respuesta ya conocida para detectar fallas antes de que afecten a un usuario real (como el canario que alertaba de gases tóxicos en minas) |
| Dashboard | Pantalla donde se ve la tendencia de las métricas en el tiempo |
| Runbook | Instructivo paso a paso de qué hacer ante cada tipo de problema |
| Data drift / PSI | Los datos nuevos ya no se parecen a los de entrenamiento; PSI es el número que mide qué tan distintos son |
| Rollback | Deshacer el último cambio (como Ctrl+Z) volviendo a la versión anterior que sí funcionaba |
| Reentrenamiento | Enseñarle de nuevo al modelo con datos actualizados, validando que aprendió bien antes de usarlo |
| Cold start | Arranque lento porque el servicio estaba "dormido" por inactividad (normal en el plan gratuito de Render, no es una falla) |

---

## 1. Definición de indicadores (métricas, logs, trazas)

### Métricas

Capturadas por [`scripts/monitor.py`](scripts/monitor.py) en cada ciclo y registradas
como serie de tiempo en MLflow (experimento `actividad8_monitoreo_produccion`):

| Métrica | Descripción |
|---|---|
| `health_latency_ms` | Latencia de `GET /health` |
| `predict_latency_ms` | Latencia promedio de dos llamadas a `POST /predict` |
| `disponible` | 1 si `/health` y ambos `/predict` responden 200 |
| `canary_correcto` | 1 si ambos canary checks clasifican correctamente |
| `cold_start` | 1 si el primer ciclo tardó >5s tras inactividad |
| `alertas_disparadas` | Número de alertas disparadas en el ciclo |

Estas cubren 2 de los 4 "Golden Signals" de SRE (latencia y errores). No se miden
*tráfico* ni *saturación* porque el servicio no expone métricas de CPU/memoria
propias fuera del dashboard de Render, y no hay usuarios concurrentes externos en
esta entrega (limitación conocida, ver sección 6).

### Logs

- **Aplicación:** `src/api.py` usa el logger `uvicorn.error` (advertencias de
  arranque) y Uvicorn registra cada petición HTTP con su código de respuesta.
  Visibles en Render → *Logs*.
- **Alertas (Actividad 8):** [`evidencia/alertas_log.jsonl`](evidencia/alertas_log.jsonl)
  — una línea JSON por alerta disparada (timestamp, alerta, severidad, runbook),
  independiente de que MLflow siga disponible.

### Trazas

No se implementa tracing distribuido (ej. OpenTelemetry) porque el servicio es un
único proceso sin llamadas a otros servicios propios. Cada ciclo de monitoreo actúa
como "traza sintética" de la transacción completa (`health` → `predict` canario bajo
→ `predict` canario alto), con hora y latencia por paso. Sería la primera mejora
recomendada si el servicio creciera a varios componentes.

---

## 2. Diseño de alertas inteligentes

Configuración completa en
[`scripts/alertas_config.yaml`](scripts/alertas_config.yaml).

### SLOs y error budgets

| SLO | Objetivo | Error budget |
|---|---|---|
| Disponibilidad | 99% (30 días) | ~7.2 horas/mes |
| Latencia `/predict` (p95) | < 2000ms | — (excluye cold start) |
| Calidad del modelo | 100% canary checks correctos | 0 — cualquier falla es P1 |
| Estabilidad de datos | PSI < 0.10 en todas las variables | — |

### Reglas de alerta

| ID | Nombre | Severidad | Condición |
|---|---|---|---|
| `ALERT-QUALITY-01` | Modelo degradado | **P1** | Canary check falla en ≥1 ciclo |
| `ALERT-AVAIL-01` | Servicio no disponible | **P1** | `/health` o `/predict` ≠ 200 |
| `ALERT-LAT-01` | Latencia elevada | P2 | >2000ms en 3 ciclos consecutivos |
| `ALERT-DRIFT-01` | Data drift | P2 | PSI ≥ 0.10 en alguna variable |
| `ALERT-LAT-02` | Cold start (informativo) | P3 | >5000ms en el primer ciclo tras inactividad |

**Por qué modelo degradado y caída son P1, y latencia es P2:** un servicio caído o
un modelo con predicciones incorrectas afecta directamente la decisión de un
coordinador sobre un estudiante real. El modelo degradado es el caso más peligroso
porque la API sigue respondiendo `200 OK` — es un error silencioso. La latencia alta
es solo mala experiencia, no una decisión equivocada.

### Reducción de ruido

- `ALERT-LAT-01` exige **3 ciclos consecutivos**, no un pico aislado.
- `ALERT-LAT-02` (cold start) se evalúa y excluye **antes** que `ALERT-LAT-01`, para
  no confundir el comportamiento esperado de Render con una falla real.
- Las alertas se ordenan por severidad al registrarse, para que lo más crítico se
  vea primero.

---

## 3. Descripción de dashboards

El dashboard reutiliza la UI de MLflow (ya integrada desde la Fase 2): cada ciclo de
`monitor.py` se guarda con un número de paso (`step`), lo que genera automáticamente
una gráfica de línea por métrica, sin instalar nada adicional.

**Estructura** (capturas en [`evidencia/capturas/`](evidencia/capturas/)):

1. **Lista de runs** (`01_...png`) — una fila por sesión de monitoreo (línea base,
   cada incidente, cada verificación post-rollback).
2. **Overview de un run** (`02_...png`) — URL monitoreada, métricas finales, y el
   commit exacto del código que generó esa corrida.
3. **Panel de métricas por ciclo** (`03_.../04_...png`) — 6 gráficas con el ciclo en
   el eje X; permite ver en qué ciclo exacto empezó a subir la latencia o a fallar
   el canary check.

**Por qué MLflow y no un dashboard externo (Grafana):** ya estaba integrado desde la
Fase 2, sin infraestructura adicional. Limitación conocida: no se actualiza solo, hay
que ejecutar `monitor.py`. Si el proyecto pasara a producción real, lo siguiente
sería automatizar `monitor.py` con un cron y considerar Grafana para verlo en vivo.

---

## 4. Runbooks de respuesta a incidentes

Un runbook por tipo de alerta, mismos 4 pasos siempre: **diagnóstico** (descartar
falso positivo) → **respuesta** (comando a ejecutar) → **verificación** (confirmar
que se arregló) → **escalamiento** (qué hacer si no funcionó).

- [`docs/runbook_modelo_degradado.md`](docs/runbook_modelo_degradado.md) — `ALERT-QUALITY-01` (P1)
- [`docs/runbook_disponibilidad.md`](docs/runbook_disponibilidad.md) — `ALERT-AVAIL-01` (P1)
- [`docs/runbook_latencia.md`](docs/runbook_latencia.md) — `ALERT-LAT-01` (P2)
- [`docs/runbook_drift.md`](docs/runbook_drift.md) — `ALERT-DRIFT-01` (P2)

Los runbooks de modelo degradado y latencia **se ejecutaron realmente**, no quedaron
solo en el papel: se provocó el problema a propósito, se siguió el runbook, y se
confirmó la recuperación. Evidencia completa con horas y comandos en
[`incidentes/registro_incidentes.md`](incidentes/registro_incidentes.md).

---

## 5. Estrategias de detección de data drift

### Método

Se usa **Population Stability Index (PSI)**, el estándar más común en monitoreo de
modelos de riesgo, en [`scripts/detectar_drift.py`](scripts/detectar_drift.py):

1. Se divide el dataset de entrenamiento en 10 grupos por cuantiles (ej. por rango de
   promedio académico).
2. Se calcula qué porcentaje del dataset nuevo cae en cada uno de esos mismos grupos.
3. Si la distribución es parecida, PSI sale bajo; si es muy distinta, PSI sale alto.

```
PSI = Σ (pct_nuevo - pct_referencia) × ln(pct_nuevo / pct_referencia)
```

Umbrales: PSI < 0.10 sin drift, 0.10–0.25 moderado, ≥ 0.25 significativo. Se aplica a
las 6 variables numéricas y, igual, a las 2 categóricas.

### Datos de prueba y resultado real

Sin un flujo real de producción, [`scripts/generar_dataset_drift.py`](scripts/generar_dataset_drift.py)
genera 300 registros sintéticos con drift deliberado en 4 de las 8 variables (menor
promedio y asistencia, más horas de trabajo y modalidad en línea):

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

El sistema detectó correctamente las 4 variables modificadas (2 significativas, 2
moderadas) sin falsos positivos en las 4 sin cambios. Reporte completo:
[`evidencia/reporte_drift.md`](evidencia/reporte_drift.md); registrado en MLflow
(run `deteccion_drift`, [`evidencia/capturas/05_deteccion_drift.png`](evidencia/capturas/05_deteccion_drift.png)).

---

## 6. Documentación de respuesta automatizada

[`scripts/rollback.py`](scripts/rollback.py) implementa dos modos:

### Rollback

```bash
python -m actividad8.scripts.rollback --modo rollback --commit-bueno <hash> --push
```

Restaura `models/modelo_abandono.joblib` desde una versión anterior conocida como
buena, hace commit y push, y dispara el redeploy automático en Render. Es la
respuesta más rápida: no requiere reentrenar.

### Reentrenamiento con validación

```bash
python -m actividad8.scripts.rollback --modo reentrenar --push
```

Reentrena desde cero y **solo** acepta el modelo nuevo si su F1 de prueba es ≥ 0.80
(el mismo mínimo de la Fase 2); si no lo supera, lo descarta automáticamente y deja
el modelo anterior sin tocar. Evita que una "solución automática" empeore las cosas.

### Salvaguarda y evidencia

Ninguno de los dos modos hace `git push` salvo que se pase `--push` explícitamente —
sin ese flag, el cambio queda listo para revisión manual. El modo `rollback` se
ejecutó realmente en el incidente 2 (modelo degradado); ver
[`incidentes/registro_incidentes.md`](incidentes/registro_incidentes.md). El modo
`reentrenar` no se necesitó en ningún incidente real (ambos se resolvieron con
rollback simple), pero se probó exitosamente en local antes de documentarse aquí.
