# Registro de Incidentes Simulados — Actividad 8

> Ambos incidentes se ejecutaron realmente contra la API en producción
> (`https://fase2-abandono-escolar.onrender.com`), con autorización expresa del
> propietario del servicio (uso exclusivo, sin otros usuarios activos durante la
> ventana de la prueba). No son incidentes hipotéticos: cada paso —degradación,
> detección, rollback y verificación— se ejecutó y se registró con timestamps reales.

---

## Incidente 1 — Latencia degradada en `/predict`

| Campo | Valor |
|---|---|
| Fecha | 2026-07-18 |
| Alerta disparada | `ALERT-LAT-01` (P2) |
| Runbook aplicado | [`actividad8/docs/runbook_latencia.md`](../docs/runbook_latencia.md) |
| Causa simulada | `time.sleep(3.5)` agregado deliberadamente en `POST /predict` (`src/api.py`) para reproducir una dependencia lenta |

### Línea de tiempo

| Hora (UTC) | Evento |
|---|---|
| 02:14:47 – 02:15:44 | Línea base capturada: latencia 258-564ms, 6/6 ciclos disponibles, canary OK. Run MLflow: `baseline_produccion`. |
| — | Commit `92ee18e`: se introduce `time.sleep(3.5)` en `/predict`. Push a `origin/main`. |
| ~02:21 | Render completa el redeploy con el código degradado (confirmado por polling: latencia salta de ~0.3s a 3.87s). |
| 02:21:16 – 02:22:29 | Monitoreo del incidente (run MLflow `incidente_01_latencia_degradada`, 5 ciclos): latencia 3810-3999ms sostenida. |
| 02:21:48 | **`ALERT-LAT-01` disparada** (3er ciclo, 3 consecutivos >2000ms). |
| 02:22:04, 02:22:20 | `ALERT-LAT-01` se repite (ciclos 4 y 5), confirmando persistencia del incidente. |
| — | Respuesta: `git revert --no-edit 92ee18e` → commit `62efe93`. Push a `origin/main`. |
| ~02:23 | Render completa el redeploy del rollback (confirmado por polling: latencia vuelve a <2s). |
| 02:23:47 – 02:24:16 | Verificación post-rollback (run MLflow `incidente_01_post_rollback`, 4 ciclos): latencia 260-593ms, 0 alertas. |

### Resultado

**Recuperado.** Latencia volvió al rango normal (260-593ms, consistente con la línea
base) en el primer ciclo de verificación tras el rollback. Tiempo total del
incidente (desde el deploy degradado hasta la confirmación de recuperación):
**~9 minutos**, la mayor parte correspondiente al tiempo de build+deploy de Render
(~2 min por redeploy), no al tiempo de detección o decisión.

### Evidencia

- Capturas: [`actividad8/evidencia/capturas/02_incidente01_overview.png`](../evidencia/capturas/02_incidente01_overview.png),
  [`03_incidente01_dashboard_metricas.png`](../evidencia/capturas/03_incidente01_dashboard_metricas.png)
- Log de alertas: [`actividad8/evidencia/alertas_log.jsonl`](../evidencia/alertas_log.jsonl)
- Commits: [`92ee18e`](https://github.com/aislaslo/Fase2_Modelo_Escolar/commit/92ee18e) (incidente) →
  [`62efe93`](https://github.com/aislaslo/Fase2_Modelo_Escolar/commit/62efe93) (rollback)

---

## Incidente 2 — Modelo degradado (etiquetas invertidas)

| Campo | Valor |
|---|---|
| Fecha | 2026-07-18 |
| Alerta disparada | `ALERT-QUALITY-01` (P1) |
| Runbook aplicado | [`actividad8/docs/runbook_modelo_degradado.md`](../docs/runbook_modelo_degradado.md) |
| Causa simulada | `models/modelo_abandono.joblib` reemplazado por un modelo entrenado con las etiquetas de `abandono` invertidas (simula un bug de pipeline de datos) |

### Línea de tiempo

| Hora (UTC) | Evento |
|---|---|
| — | Se genera localmente un modelo con etiquetas invertidas y se verifica que falla ambos canary checks de forma determinística (riesgo bajo → clase 1, riesgo alto → clase 0). |
| — | Commit `f62d0cb`: se reemplaza `models/modelo_abandono.joblib`. Push a `origin/main`. |
| ~02:26 | Render completa el redeploy con el modelo degradado (confirmado por polling: canary de riesgo bajo pasa de clase 0 a clase 1). |
| 02:26:51 | Monitoreo del incidente (run MLflow `incidente_02_modelo_degradado`, 4 ciclos). **`ALERT-QUALITY-01` disparada en el primer ciclo** (a diferencia del incidente 1, la falla de calidad es inmediata, no requiere ciclos consecutivos). |
| 02:27:00, 02:27:09, 02:27:20 | `ALERT-QUALITY-01` se repite en los 4 ciclos del monitoreo (100% de fallos). |
| — | Respuesta: `python -m actividad8.scripts.rollback --modo rollback --commit-bueno 62efe93 --push` → commit `90811c2`. |
| ~02:28 | Render completa el redeploy del rollback (confirmado por polling: canary de riesgo bajo vuelve a clase 0). |
| 02:28:35 – 02:29:02 | Verificación post-rollback (run MLflow `incidente_02_post_rollback`, 4 ciclos): `canary_correcto=True` en los 4 ciclos, 0 alertas. |

### Resultado

**Recuperado.** El modelo degradado quedó activo en producción durante
aproximadamente 3-4 minutos entre el redeploy del incidente y la confirmación del
rollback — sirviendo predicciones sistemáticamente incorrectas durante esa ventana.
La respuesta automatizada (`rollback.py`) restauró el modelo correcto en un solo
comando, sin intervención manual del código.

**Nota de impacto:** este es el escenario de mayor severidad (P1) porque, a
diferencia del incidente de latencia, el servicio respondía `200 OK` con
predicciones incorrectas — no hay señal de error visible para un consumidor de la
API sin los canary checks. Esto confirma la importancia de monitorear *calidad*, no
solo disponibilidad.

### Evidencia

- Capturas: [`actividad8/evidencia/capturas/04_incidente02_dashboard_metricas.png`](../evidencia/capturas/04_incidente02_dashboard_metricas.png)
- Log de alertas: [`actividad8/evidencia/alertas_log.jsonl`](../evidencia/alertas_log.jsonl)
- Commits: [`f62d0cb`](https://github.com/aislaslo/Fase2_Modelo_Escolar/commit/f62d0cb) (incidente) →
  [`90811c2`](https://github.com/aislaslo/Fase2_Modelo_Escolar/commit/90811c2) (rollback, ejecutado por `rollback.py`)
- Salida real del script de rollback: ver sección "Uso adecuado de herramientas" en
  [`actividad8/documento_tecnico.md`](../documento_tecnico.md)

---

## Resumen comparativo

| | Incidente 1 (latencia) | Incidente 2 (modelo degradado) |
|---|---|---|
| Severidad | P2 | P1 |
| Ciclos hasta disparo de alerta | 3 (requiere confirmar persistencia) | 1 (inmediato) |
| Señal visible sin monitoreo activo | Sí (respuesta lenta, perceptible) | **No** (respuesta `200 OK`, error silencioso) |
| Método de respuesta | `git revert` manual | Script `rollback.py` (automatizado) |
| Tiempo total incidente→recuperación confirmada | ~9 min (dominado por 2 redeploys de Render) | ~7 min (dominado por 2 redeploys de Render) |

**Conclusión general:** en ambos casos, el tiempo de detección y decisión fue de
segundos; el tiempo de recuperación estuvo dominado por la latencia de build+deploy
de Render (~90 segundos por redeploy), no por el proceso de monitoreo o respuesta.
Esto valida el diseño de `monitor.py` + `alertas_config.yaml` + `rollback.py` como un
ciclo de respuesta a incidentes funcional de extremo a extremo.
