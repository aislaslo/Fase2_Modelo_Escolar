# Actividad 9 — Escalabilidad, Optimización de Costos y Gobernanza Responsable

> Construida sobre la Fase 2 ([`../README.md`](../README.md)) y la Actividad 8
> ([`../actividad8/`](../actividad8/)): reutiliza el mismo modelo, dataset y
> API ya desplegada en **https://fase2-abandono-escolar.onrender.com**, y la
> infraestructura de monitoreo/MLflow ya construida. Esta carpeta contiene
> únicamente lo nuevo de la Actividad 9: análisis de escalabilidad, costos
> proyectados, auditoría de fairness y plan de escalamiento responsable.

## Mapa de entregables

| Entregable | Lugar |
|---|---|
| **Reporte técnico** — análisis de arquitectura actual, propuesta de rediseño, evaluación de métricas, auditoría ética/técnica/legal, plan de escalamiento responsable | [`reporte_tecnico.md`](reporte_tecnico.md) |
| **Anexo técnico** — tablas comparativas de costos, métricas de desempeño (latencia, throughput, recursos), evaluación de fairness y sesgos | [`anexo_tecnico.md`](anexo_tecnico.md) |
| **Diagrama de arquitectura** — sistema actual y sistema propuesto | Embebidos en [`reporte_tecnico.md`](reporte_tecnico.md), secciones 1 y 2 |
| **Código / configuración** — scripts de prueba de carga y auditoría de fairness | [`scripts/`](scripts/) |

## Contenido de `scripts/`

| Archivo | Qué hace |
|---|---|
| `prueba_carga.py` | Prueba de carga moderada (concurrencia configurable) contra un despliegue real; mide throughput, latencia (p50/p95/p99) y tasa de error; registra en MLflow |
| `auditoria_fairness.py` | Evalúa el modelo entrenado por grupo de `condicion_beca` (proxy socioeconómico): selection rate, TPR, FPR, demographic parity, equal opportunity, equalized odds y regla de las 4/5 (EEOC) |
| `graficar_carga.py` | Genera las gráficas de throughput/latencia vs. concurrencia a partir de `evidencia/resultados_prueba_carga.json` (no ejecuta peticiones nuevas) |

## Uso rápido

```bash
# Desde la raíz del repo, con el venv de la Fase 2 activado
source .venv/bin/activate

# Prueba de carga contra la API en producción (moderada, no agresiva)
python -m actividad9.scripts.prueba_carga --concurrencia 10 --total 30 --run-name mi_prueba

# Prueba de carga contra un contenedor local, para comparar
docker run -d -p 8000:8000 --name abandono-escolar-test abandono-escolar-api
python -m actividad9.scripts.prueba_carga --base-url http://localhost:8000 --concurrencia 10 --total 30 --run-name mi_prueba_local

# Auditoria de fairness sobre el modelo ya entrenado
python -m actividad9.scripts.auditoria_fairness
```
