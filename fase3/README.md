# Fase 3 — Solución de IA Lista para la Industria

> Construida sobre la Fase 2 ([`../README.md`](../README.md)), la Actividad 8
> ([`../actividad8/`](../actividad8/)) y la Actividad 9
> ([`../actividad9/`](../actividad9/)): reutiliza el mismo modelo, dataset,
> API en producción, monitoreo y auditorías ya construidos. Esta carpeta
> agrega la capa de automatización (MLOps/GitOps) y la documentación que
> integra todo el proyecto en una narrativa profesional.

## Mapa de entregables

| Entregable | Dónde verificarlo |
|---|---|
| **1. Pipeline automatizado (MLOps/GitOps)** — CI, pruebas de código y datos, versionado de modelo, gate de fairness, despliegue continuo | [`.github/workflows/pipeline.yml`](../.github/workflows/pipeline.yml) (repo raíz — requisito de GitHub Actions) + [`scripts/`](scripts/) + [evidencia de un run real exitoso](evidencia/capturas/) |
| **2. Documento técnico de operación** — arquitectura, monitoreo, auditoría, métricas, optimización | [`documento_operacion.md`](documento_operacion.md) |
| **3. Portfolio técnico-estratégico** — problema, valor de negocio, stack, resultados, evidencia visual | [`portfolio.md`](portfolio.md) |
| **4. Simulación de entrevista y presentación profesional** | [`entrevista/README.md`](entrevista/README.md) — **pendiente**, placeholder a petición explícita |

## Contenido de `scripts/`

| Archivo | Qué hace |
|---|---|
| `gate_fairness.py` | Gate de CI: reutiliza `actividad9/scripts/auditoria_fairness.py` como prueba de regresión (falla solo si un cambio de modelo empeora la disparidad ya documentada) |
| `fairness_baseline.json` | Línea base de fairness (Actividad 9) contra la que se compara el gate |
| `registrar_version_modelo.py` | Registra cada versión del modelo (commit, F1, hash de artefactos) — registro basado en git, sin infraestructura dedicada |

Las **pruebas de datos** nuevas (`tests/test_data.py`) viven en `tests/`
junto a las de código de la Fase 2, no aquí — es una extensión natural de
esa suite, no un componente aislado de la Fase 3.

## Qué es genuinamente nuevo en la Fase 3 (vs. reutilizado)

- **Nuevo:** el pipeline de CI/CD en sí (antes no existía ninguna
  automatización — "CI/CD" era solo el auto-deploy de Render sin validación
  previa), las pruebas de datos, el gate de fairness como control continuo,
  y el registro de versiones de modelo.
- **Reutilizado sin cambios:** el modelo, la API, el monitoreo (Actividad 8),
  y la auditoría de fairness (Actividad 9) — el pipeline los orquesta, no
  los reemplaza.

## Resumen de lo ejecutado (no solo documentado)

El pipeline se ejecutó realmente contra GitHub Actions (no es una
simulación local): **run \#1, ambos jobs exitosos, 4m 26s**, incluyendo un
smoke test real contra la API en producción después del redeploy de Render.
Ver evidencia completa en
[`evidencia/capturas/`](evidencia/capturas/) y el detalle en
[`documento_operacion.md`](documento_operacion.md).
