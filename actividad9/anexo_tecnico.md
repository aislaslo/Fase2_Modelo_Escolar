# Anexo Técnico — Actividad 9

> Tablas de soporte del [`reporte_tecnico.md`](reporte_tecnico.md): costos,
> desempeño y fairness. Los datos de desempeño y fairness provienen de
> ejecuciones reales contra el sistema (Render en producción + Docker local);
> los datos de costo son **proyecciones basadas en precios públicos de cada
> plataforma** (no facturación real, ya que el despliegue actual usa el plan
> gratuito de Render — costo real = $0).

---

## 1. Tablas comparativas de costos (proyectadas)

### 1.1 Opciones de infraestructura por escenario de tráfico

| Escenario | Infraestructura | Costo mensual estimado | CPU / RAM | Notas |
|---|---|---|---|---|
| **Actual (Fase 2)** | Render Free, 1 instancia | **$0** | 0.1 CPU / 512MB | Duerme tras inactividad (cold start 30-50s); sin SLA garantizado; single point of failure |
| Escalamiento vertical (básico) | Render Starter, 1 instancia | ~$7/mes | 0.5 CPU / 512MB | 5× más CPU, elimina cold start (no duerme); sigue siendo instancia única |
| Escalamiento vertical (medio) | Render Standard, 1 instancia | ~$25/mes | 1 CPU / 2GB | Soporta más concurrencia simultánea antes de degradar |
| Escalamiento horizontal | Render Standard × 2-3 (autoscaling) | ~$50-75/mes | 2-3 × (1 CPU/2GB) | Tolerante a fallos, reparte carga; mejora p95/p99 bajo tráfico variable |
| Serverless equivalente (GCP) | Cloud Run, pago por uso | ~$0-15/mes* | Escala 0→N | Escala a cero en inactividad (sin cold start tan largo como Render Free); ideal para tráfico bajo/variable |
| Serverless equivalente (AWS) | App Runner, pago por uso | ~$5-20/mes* | Escala 1→25 instancias | Similar a Cloud Run; sin escalar a cero |

*Estimado para tráfico bajo (algunos miles de peticiones/mes), basado en las
calculadoras públicas de precios de cada proveedor (Google Cloud, s.f.-b;
Amazon Web Services, 2024) — cifras de referencia, no una cotización real.

### 1.2 Desglose por componente (patrón "antes vs. después", ver Tema 21)

| Componente | Antes (actual) | Después (propuesto) | Ahorro / mejora estimada |
|---|---|---|---|
| Cómputo | 1 instancia fija (0.1 CPU) | Autoescalado horizontal (N instancias bajo demanda) | Evita sobreaprovisionar en horas valle; evita saturación en horas pico |
| Inferencia | Regresión Logística sin optimizar | Sin cambio recomendado (ver nota) | 0% — el modelo ya es liviano, no es el cuello de botella (sección 2) |
| Arquitectura | Monolítica (1 servicio) | Monolítica + capa de observabilidad (Actividad 8) ya integrada | Sin costo adicional; ya implementado |
| Almacenamiento | N/A (sin base de datos) | N/A | No aplica a este proyecto |
| Disponibilidad | Sin SLA (Free tier duerme) | 99% con Starter/Standard + autoscaling | Elimina cold start; tolera caída de 1 instancia |

**Nota sobre optimización de inferencia:** a diferencia de un modelo de deep
learning, la Regresión Logística de este proyecto ya es computacionalmente
trivial (microsegundos de CPU por predicción). La sección 2 confirma con
datos reales que el cuello de botella actual es la **asignación de CPU de la
instancia y la red**, no el modelo — por lo que técnicas como *quantization*
o *pruning* (relevantes para redes neuronales grandes) no aplican con
beneficio real aquí. Se documenta como decisión consciente, no como omisión.

---

## 2. Métricas de desempeño (latencia, throughput, uso de recursos)

### 2.1 Prueba de carga real contra producción (Render, plan Free)

Ejecutada con [`scripts/prueba_carga.py`](scripts/prueba_carga.py), 30
peticiones por corrida, con concurrencia creciente (5 → 10 → 15, moderada a
propósito para no arriesgar el servicio compartido):

| Concurrencia | Throughput (req/s) | Latencia p50 | Latencia p95 | Latencia p99 | Errores |
|---|---|---|---|---|---|
| 5 | 8.43 | 454 ms | 1,168 ms | 1,573 ms | 0/30 |
| 10 | 16.72 | 304 ms | 1,344 ms | 1,587 ms | 0/30 |
| 15 | 13.94 | 738 ms | 1,271 ms | 1,332 ms | 0/30 |

**Hallazgo clave:** el throughput deja de crecer (e incluso baja) entre
concurrencia 10 y 15, y la latencia p50 casi se duplica (304ms → 738ms) — el
punto donde la instancia única de 0.1 CPU empieza a saturarse. No hubo
errores en ningún nivel probado (el servicio se degrada, no se cae), lo cual
es consistente con el diseño *stateless* de la API.

### 2.2 Misma prueba contra un contenedor local (recursos no limitados)

Mismo `Dockerfile`, misma imagen, ejecutado localmente (sin restricción de
CPU impuesta por un plan de hosting, y sin latencia de red — cliente y
servidor en la misma máquina):

| Concurrencia | Throughput (req/s) | Latencia p50 | Latencia p95 | Latencia p99 | Errores |
|---|---|---|---|---|---|
| 5 | 322.3 | 12.4 ms | 33.5 ms | 33.8 ms | 0/30 |
| 10 | 367.7 | 26.4 ms | 36.4 ms | 38.0 ms | 0/30 |
| 15 | 347.7 | 36.0 ms | 55.0 ms | 57.7 ms | 0/30 |

### 2.3 Comparación e interpretación

| | Render Free (producción) | Local (sin restricción) | Diferencia |
|---|---|---|---|
| Throughput @ concurrencia 10 | 16.72 req/s | 367.7 req/s | ~22× mayor en local |
| Latencia p50 @ concurrencia 10 | 304 ms | 26.4 ms | ~11× menor en local |

Esta comparación (no es una medición aislada de CPU pura, incluye también la
latencia de red ausente en local) confirma que el **cuello de botella actual
es de infraestructura** (CPU limitada + variabilidad de red hacia Render),
no del modelo ni del código de la API — sustentando la recomendación de
escalar verticalmente y/u horizontalmente (sección 1) en lugar de optimizar
el modelo.

### 2.4 Uso de recursos (CPU / memoria)

Render (plan Free) no expone una API pública de métricas de
infraestructura por instancia sin autenticación adicional fuera de esta
entrega; el uso de CPU/memoria se infiere de forma indirecta a partir del
comportamiento observado (degradación de latencia bajo concurrencia
creciente, sección 2.1) y de los límites documentados del plan (0.1 CPU /
512MB). **Limitación declarada:** no se tienen series de tiempo de
CPU%/memoria% reales; si el proyecto pasara a un plan pagado, el dashboard
de Render expone estas métricas directamente y se recomienda incorporarlas
al monitoreo de `actividad8/scripts/monitor.py`.

---

## 3. Evaluación de fairness y sesgos

> Atributo protegido evaluado: **`condicion_beca`** (con beca / sin beca),
> usado como proxy de nivel socioeconómico — el dataset no incluye atributos
> demográficos explícitos (género, etnia, discapacidad). Metodología y
> definiciones completas en
> [`scripts/auditoria_fairness.py`](scripts/auditoria_fairness.py). Evaluado
> sobre el conjunto de prueba (20%, no usado en entrenamiento).

### 3.1 Métricas por grupo

| Grupo | n | Selection rate (predicción "en riesgo") | Recall (TPR) | FPR | Precision | Accuracy |
|---|---|---|---|---|---|---|
| Sin beca | 140 | 0.4786 | 0.9107 | 0.1905 | 0.7612 | 0.85 |
| Con beca | 60 | 0.3500 | 0.8750 | 0.1591 | 0.6667 | 0.85 |

### 3.2 Métricas de disparidad

| Métrica | Valor | Umbral de referencia | Resultado |
|---|---|---|---|
| Demographic parity difference | 0.1286 | — | El modelo marca "en riesgo" ~13 puntos porcentuales más seguido a estudiantes sin beca |
| Equal opportunity difference (Δ TPR) | 0.0357 | — | Diferencia baja: el modelo detecta casos reales de abandono con similar efectividad en ambos grupos |
| Equalized odds difference | 0.0357 | — | Consistente con lo anterior |
| Regla de las 4/5 (EEOC) | 0.7313 | ≥ 0.80 | **No cumple** |

### 3.3 Interpretación

La *accuracy* es idéntica en ambos grupos (0.85) y la diferencia en *recall*
es baja (0.036) — el modelo no es sistemáticamente peor identificando a
estudiantes en riesgo real dentro de ninguno de los dos grupos. Sin embargo,
la regla de las 4/5 **no se cumple** en la tasa de selección: esto es
**consecuencia directa y esperada** de que `condicion_beca` es una de las
variables predictoras con mayor peso en el modelo (coeficiente -1.6265, ver
`docs/documentacion_tecnica.md` de la Fase 2) — no de un sesgo espurio
introducido por otra variable correlacionada. Esto expone una tensión de
fairness clásica (¿usar directamente un atributo sensible como variable
predictiva, o excluirlo y aceptar una posible pérdida de desempeño?), que se
desarrolla en la sección de auditoría ética del
[`reporte_tecnico.md`](reporte_tecnico.md).
