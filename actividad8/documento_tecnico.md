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

## Cómo leer este documento (resumen en palabras simples)

Todo este documento responde a una sola pregunta práctica: **¿cómo sabemos que la
API sigue funcionando bien, y qué hacemos si deja de funcionar bien?**

Es la misma lógica que seguir la salud de un paciente:

| Concepto técnico | Analogía | Qué es en este proyecto |
|---|---|---|
| Métricas | Signos vitales (temperatura, pulso) | Números que medimos repetidamente: qué tan rápido responde la API, si está disponible, si acierta |
| Logs | Bitácora del hospital | Registro con fecha/hora de cada evento relevante que pasó |
| Alertas + SLO | Cuándo llamar al doctor | Reglas de "si esto pasa, es un problema" y qué tan grave es cada una |
| Dashboard | El monitor de signos vitales al lado de la cama | Pantalla donde se ve la tendencia de las métricas en el tiempo |
| Runbook | Protocolo de emergencia del hospital | Instrucciones paso a paso de qué hacer ante cada tipo de problema |
| Data drift | El paciente cambió de hábitos y ya no responde igual a los mismos medicamentos | Los datos nuevos ya no se parecen a los datos con los que se entrenó el modelo |
| Respuesta automatizada | Un desfibrilador automático | Un script que corrige el problema solo, sin esperar a que un humano lo haga manualmente |

Cada una de las 6 secciones que siguen desarrolla uno de estos puntos con el detalle
técnico y la evidencia real que pide la actividad. Se agregó una nota en **letra
cursiva marcada como "En palabras simples"** al inicio de cada sección para quien
quiera la idea general antes de entrar al detalle.

---

## 1. Definición de indicadores (métricas, logs, trazas)

*En palabras simples: aquí se explica qué números medimos, dónde queda el registro
de lo que pasó, y por qué no implementamos "trazas" tradicionales.*

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

> **¿Qué son los "Golden Signals"?** Es un término de la disciplina de SRE (Site
> Reliability Engineering, la práctica de mantener sistemas confiables) para las 4
> señales que casi siempre importan en cualquier servicio: **latencia** (¿qué tan
> rápido responde?), **errores** (¿falla?), **tráfico** (¿cuántas peticiones recibe?)
> y **saturación** (¿qué tan cerca está de su límite de capacidad?). Es como decir
> "estos son los 4 signos vitales que siempre debes revisar", sea cual sea el
> paciente.

**Por qué solo medimos 2 de los 4 Golden Signals:** no medimos *tráfico* ni
*saturación* porque el servicio no expone métricas de infraestructura propias
(CPU/memoria) fuera del dashboard de Render, y en esta entrega no hay usuarios
concurrentes externos generando tráfico real que valga la pena medir. Se documenta
como limitación conocida en la sección 6.

### 1.2 Logs

- **Logs de aplicación:** el servicio (`src/api.py`) usa el logger `uvicorn.error`
  para registrar advertencias de arranque (ej. modelo no encontrado) y Uvicorn
  registra cada petición HTTP con su código de respuesta. Visibles en Render →
  pestaña *Logs*.
- **Log de alertas (Actividad 8):**
  [`actividad8/evidencia/alertas_log.jsonl`](evidencia/alertas_log.jsonl) — un
  registro con cada alerta disparada: timestamp, qué alerta fue, qué tan grave era,
  y qué runbook aplicar. Formato JSONL = un archivo de texto donde cada línea es un
  registro independiente en formato JSON; se eligió porque es fácil de leer línea por
  línea y no depende de que MLflow siga disponible para consultarlo.

### 1.3 Trazas

*En palabras simples: una "traza" normalmente sirve para seguir el camino de una
petición cuando pasa por varios servicios distintos (por ejemplo, API → base de
datos → servicio de pagos → ...). Aquí no aplica del todo porque solo tenemos un
servicio.*

Este proyecto no implementa tracing distribuido (herramientas como OpenTelemetry)
porque el servicio es un único proceso sin llamadas a otros servicios propios — no
hay una cadena de pasos distintos que trazar. En su lugar, cada ciclo de monitoreo
actúa como una "traza sintética" de la transacción completa (`health` → `predict`
canario bajo → `predict` canario alto), registrada con su hora exacta y la latencia
de cada paso. Si el servicio creciera a varios componentes (por ejemplo, separar el
preprocesamiento de datos en su propio servicio), esta sería la primera mejora
recomendada.

---

## 2. Diseño de alertas inteligentes

*En palabras simples: aquí se define qué prometemos que la API va a cumplir (SLO),
cuánto margen de error nos damos antes de que sea grave (error budget), y qué reglas
disparan una alerta — clasificadas por qué tan urgente es cada una.*

Configuración completa en
[`actividad8/scripts/alertas_config.yaml`](scripts/alertas_config.yaml).

### 2.1 SLOs y error budgets

> **SLO (Service Level Objective / Objetivo de Nivel de Servicio):** es una promesa
> concreta y medible sobre qué tan bien debe funcionar el servicio. Por ejemplo,
> "99% de disponibilidad" es una promesa; no dice "siempre" (poco realista), dice
> "casi siempre, con un margen conocido".
>
> **Error budget (presupuesto de error):** es ese margen, convertido en algo
> tangible. Si prometemos 99% de disponibilidad al mes, matemáticamente eso significa
> que nos "permitimos" fallar hasta 7.2 horas al mes sin romper la promesa. Mientras
> no gastemos ese presupuesto, no hay un problema real — es la diferencia entre "algo
> tembló" y "se cayó el edificio".

| SLO | Objetivo | Error budget |
|---|---|---|
| Disponibilidad | 99% (30 días) | ~7.2 horas/mes de indisponibilidad tolerada |
| Latencia `/predict` (p95) | < 2000ms | — (excluye cold start, ver nota) |
| Calidad del modelo | 100% canary checks correctos | 0 — cualquier falla es P1 |
| Estabilidad de datos | PSI < 0.10 en todas las variables | — |

*Nota sobre "p95": significa "el 95% de las peticiones deben ser más rápidas que
este número". No usamos el promedio porque un promedio puede esconder que, por
ejemplo, 1 de cada 10 peticiones tarda muchísimo — p95 obliga a que casi todas las
peticiones cumplan el objetivo, no solo "en promedio".*

### 2.2 Reglas de alerta (priorizadas por severidad/impacto operativo)

> **¿Por qué P1, P2, P3?** Es una prioridad de urgencia, igual que el triage en una
> sala de urgencias: no todos los pacientes se atienden en el orden en que llegaron,
> se atiende primero al que está en mayor riesgo. P1 = atender ya. P2 = revisar
> pronto, no es una emergencia. P3 = informativo, ni siquiera requiere que alguien
> actúe.

| ID | Nombre | Severidad | Condición |
|---|---|---|---|
| `ALERT-QUALITY-01` | Modelo degradado | **P1** | Canary check falla en ≥1 ciclo |
| `ALERT-AVAIL-01` | Servicio no disponible | **P1** | `/health` o `/predict` ≠ 200 |
| `ALERT-LAT-01` | Latencia elevada | P2 | >2000ms en 3 ciclos consecutivos |
| `ALERT-DRIFT-01` | Data drift | P2 | PSI ≥ 0.10 en alguna variable |
| `ALERT-LAT-02` | Cold start (informativo) | P3 | >5000ms en el primer ciclo tras inactividad |

> **¿Qué es un "canary check"?** El nombre viene de una práctica minera antigua: los
> mineros bajaban con un canario enjaulado porque el canario es más sensible a los
> gases tóxicos que un humano — si el canario se desmayaba, era la señal de salir
> antes de que el gas afectara a las personas. Aquí, un "canary check" es lo mismo en
> software: le mandamos a la API dos casos de prueba de los que **ya sabemos la
> respuesta correcta** (uno que debería salir "riesgo bajo", otro "riesgo alto"). Si
> la API responde distinto a lo esperado, es la señal de alerta temprana de que algo
> se rompió, sin tener que esperar a que un estudiante real reciba una predicción
> incorrecta.

**Por qué el modelo degradado y la caída del servicio son P1 y la latencia es
"solo" P2:** un servicio caído o un modelo dando resultados incorrectos afecta
directamente la decisión que toma un coordinador sobre un estudiante real — y en el
caso del modelo degradado, la API sigue respondiendo `200 OK` (parece que todo está
bien) aunque la predicción esté mal, lo cual es más peligroso porque es un error
silencioso. La latencia alta es solo una mala experiencia, no una decisión
equivocada.

### 2.3 Reducción de ruido

*En palabras simples: una alerta que se dispara por cualquier cosita mínima deja de
ser útil, porque la gente empieza a ignorarlas ("fatiga de alertas"). Aquí se explica
cómo se evita eso.*

- `ALERT-LAT-01` requiere **3 ciclos consecutivos**, no un solo pico, para evitar
  alertar por variabilidad normal de red (una petición lenta aislada no significa que
  algo esté roto).
- `ALERT-LAT-02` (cold start) se evalúa y excluye **antes** de `ALERT-LAT-01`, para
  que el comportamiento esperado del plan gratuito de Render (que "duerme" el
  servicio tras inactividad) nunca se confunda con una alerta de latencia real.
- Las alertas se ordenan por severidad al registrarse, de forma que un operador
  revisando el log siempre ve primero lo más crítico.

---

## 3. Descripción de dashboards

*En palabras simples: el "dashboard" es la pantalla donde se ve, de un vistazo, cómo
se ha comportado la API en el tiempo — igual que el monitor de signos vitales al
lado de una cama de hospital.*

El dashboard operativo se implementa sobre la interfaz visual (UI) de MLflow, la
herramienta que ya usa este proyecto desde la Fase 2 para llevar registro de
entrenamientos. Aquí se reutiliza para llevar registro de **monitoreo**: cada vez que
`monitor.py` hace un ciclo de revisión, guarda un punto de datos con un número de
paso (`step`) — esto hace que MLflow dibuje automáticamente una gráfica de línea por
cada métrica a lo largo del tiempo, sin tener que instalar ni configurar una
herramienta de visualización adicional.

**Estructura (ver capturas en [`actividad8/evidencia/capturas/`](evidencia/capturas/)):**

1. **Lista de runs** (`01_mlflow_lista_runs.png`): una fila por cada sesión de
   monitoreo que se ejecutó (línea base, cada incidente, cada verificación
   post-rollback), con nombre, duración y fecha — permite ver de un vistazo el
   historial completo.
2. **Overview de un run** (`02_incidente01_overview.png`): qué URL se monitoreó,
   cuántos ciclos, y el commit exacto del código (`monitor.py`) que generó esa
   corrida — así queda trazado qué versión del código produjo qué resultado.
3. **Panel de métricas por ciclo** (`03_.../04_...png`): 6 gráficas, una por
   métrica, con el número de ciclo en el eje horizontal — es la parte más útil para
   decidir rápido: de un vistazo se ve en qué ciclo exacto empezó a subir la latencia
   o a fallar el canary check.

**Por qué esta estructura y no un dashboard externo (como Grafana):** para el
alcance de esta actividad, MLflow ya estaba integrado en el proyecto y ofrece
gráficas de línea por métrica sin infraestructura adicional que instalar o pagar. La
limitación conocida es que no es un dashboard "en vivo todo el tiempo" — hay que
ejecutar `monitor.py` para que aparezcan nuevos puntos; no se actualiza solo. Si este
proyecto pasara a producción real con usuarios de verdad, lo siguiente sería
automatizar `monitor.py` con una tarea programada (cron) y considerar una
herramienta como Grafana para verlo en tiempo real sin tener que correr nada
manualmente.

---

## 4. Runbooks de respuesta a incidentes

*En palabras simples: un "runbook" es un instructivo de "qué hacer si pasa X",
escrito con anticipación para no tener que improvisar en el momento del problema —
como el instructivo de qué hacer si se va la luz en una casa.*

Se escribió un runbook por cada tipo de alerta, y todos siguen la misma estructura en
4 pasos: **diagnóstico** (confirmar que el problema es real, no un falso positivo) →
**respuesta** (qué comando ejecutar para arreglarlo) → **verificación** (cómo
confirmar que ya se arregló) → **escalamiento** (qué hacer si lo anterior no
funcionó).

- [`docs/runbook_modelo_degradado.md`](docs/runbook_modelo_degradado.md) — `ALERT-QUALITY-01` (P1)
- [`docs/runbook_disponibilidad.md`](docs/runbook_disponibilidad.md) — `ALERT-AVAIL-01` (P1)
- [`docs/runbook_latencia.md`](docs/runbook_latencia.md) — `ALERT-LAT-01` (P2)
- [`docs/runbook_drift.md`](docs/runbook_drift.md) — `ALERT-DRIFT-01` (P2)

Los runbooks de modelo degradado y latencia se **ejecutaron realmente** durante esta
actividad, no se quedaron solo en el papel: se provocó el problema a propósito, se
siguió el runbook paso a paso, y se confirmó que la API volvió a la normalidad. Ver
[`incidentes/registro_incidentes.md`](incidentes/registro_incidentes.md) para la
evidencia completa con horas exactas, comandos y resultados.

---

## 5. Estrategias de detección de data drift

*En palabras simples: "drift" (deriva, en español) significa que los datos nuevos
ya no se parecen a los datos con los que entrenamos el modelo — como si un doctor
aprendió a diagnosticar con pacientes de una ciudad, y de repente empieza a atender
pacientes de otra ciudad con hábitos y condiciones distintas. El modelo sigue
funcionando técnicamente, pero sus predicciones pueden volverse menos confiables
porque el mundo real ya cambió respecto a cuando se entrenó.*

### 5.1 Método

Se usa el **Population Stability Index (PSI)**, la forma más común de medir drift en
la industria (se usa mucho en modelos de riesgo crediticio, y aplica igual aquí para
riesgo de abandono escolar), implementado en
[`actividad8/scripts/detectar_drift.py`](scripts/detectar_drift.py). La idea en
palabras simples:

1. Agarramos los datos con los que se entrenó el modelo y los dividimos en 10 grupos
   (por ejemplo, por rango de promedio académico: el 10% con promedio más bajo, el
   siguiente 10%, etc.).
2. Agarramos los datos nuevos y vemos qué porcentaje cae en cada uno de esos mismos
   10 grupos.
3. Si la distribución es parecida (más o menos el mismo porcentaje en cada grupo),
   el PSI sale bajo. Si es muy distinta (por ejemplo, ahora el 40% cae en el grupo de
   promedio más bajo cuando antes era el 10%), el PSI sale alto.

La fórmula exacta (para quien quiera el detalle matemático):

```
PSI = Σ (pct_nuevo - pct_referencia) × ln(pct_nuevo / pct_referencia)
```

Umbrales estándar de la industria: PSI < 0.10 = sin drift relevante, 0.10-0.25 =
drift moderado (vale la pena revisar), ≥ 0.25 = drift significativo (requiere
acción). Se aplica a las 6 variables numéricas y, con el mismo cálculo, a las 2
variables categóricas (`condicion_beca`, `modalidad`).

### 5.2 Generación de datos de prueba

Al no contar con un flujo real de datos de producción (nadie está usando la API con
datos reales de estudiantes todavía), se generó
[`scripts/generar_dataset_drift.py`](scripts/generar_dataset_drift.py): 300 registros
sintéticos donde se cambió a propósito la distribución de 4 de las 8 variables
(menor promedio académico, menor asistencia, más horas de trabajo, más modalidad en
línea — un escenario plausible de dificultad económica creciente entre estudiantes),
para poder probar que el sistema de detección realmente funciona.

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

El sistema detectó correctamente las 4 variables donde se provocó el cambio (2 salen
como significativas, 2 como moderadas) y no marcó ninguna alerta falsa en las 4
variables que se dejaron sin cambios — es decir, el detector distingue bien entre
"esto cambió de verdad" y "esto sigue igual". Reporte completo:
[`evidencia/reporte_drift.md`](evidencia/reporte_drift.md). Registrado también en
MLflow (run `deteccion_drift`,
[`evidencia/capturas/05_deteccion_drift.png`](evidencia/capturas/05_deteccion_drift.png)).

---

## 6. Documentación de respuesta automatizada

*En palabras simples: hasta ahora todo lo anterior sirve para **detectar** que algo
salió mal. Esta sección es sobre **corregirlo sin que un humano tenga que hacerlo a
mano paso a paso** — con dos estrategias distintas según el caso.*

[`actividad8/scripts/rollback.py`](scripts/rollback.py) implementa dos modos:

### 6.1 Rollback ("deshacer el último cambio")

*Es el equivalente de Ctrl+Z: si el modelo nuevo está roto, simplemente volvemos a
poner el modelo anterior que sí funcionaba, sin perder tiempo averiguando qué salió
mal primero.*

```bash
python -m actividad8.scripts.rollback --modo rollback --commit-bueno <hash> --push
```

Restaura `models/modelo_abandono.joblib` desde una versión anterior conocida como
buena, hace commit y push, lo que dispara automáticamente un nuevo despliegue en
Render. Es la respuesta más rápida ante un modelo degradado porque no requiere
volver a entrenar nada.

### 6.2 Reentrenamiento con validación ("enseñarle de nuevo, pero verificando que aprendió bien")

```bash
python -m actividad8.scripts.rollback --modo reentrenar --push
```

Vuelve a generar el dataset y a entrenar el modelo desde cero, y — este es el punto
importante — **solo** acepta el modelo nuevo si su F1 de prueba es al menos 0.80 (el
mismo objetivo mínimo de calidad definido desde la Fase 2). Si el modelo reentrenado
sale peor que ese mínimo, el script lo descarta automáticamente y dice que no,
dejando el modelo anterior funcionando en producción sin tocarlo. Esto evita que una
"solución automática" termine empeorando las cosas.

### 6.3 Salvaguarda de diseño

Ninguno de los dos modos hace `git push` a menos que se le pase la opción `--push`
explícitamente — sin ese flag, el script deja el cambio listo para que un humano lo
revise antes de confirmarlo. Así el mismo script sirve tanto para respuesta 100%
automática (como se usó en el incidente 2, más abajo) como para preparar un cambio
que alguien aprueba manualmente antes de subirlo.

### 6.4 Evidencia de ejecución real

El modo `rollback` se ejecutó realmente durante el incidente 2 (modelo degradado),
con la salida completa de la consola capturada en
[`incidentes/registro_incidentes.md`](incidentes/registro_incidentes.md). El modo
`reentrenar` no se necesitó en ningún incidente real de esta entrega (ambos se
resolvieron con el rollback simple, que es más rápido), pero se probó exitosamente
en el entorno local antes de documentarse aquí, para confirmar que también funciona.
