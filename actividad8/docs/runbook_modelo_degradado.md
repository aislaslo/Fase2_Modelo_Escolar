# Runbook: Modelo degradado (ALERT-QUALITY-01)

**Severidad:** P1 — acción inmediata.
**Impacto:** predicciones incorrectas activas en producción; riesgo de decisiones
erroneas sobre estudiantes reales (falsos negativos o falsos positivos de abandono).

---

## 1. Disparador

`actividad8/scripts/monitor.py` ejecuta dos "canary checks" en cada ciclo: payloads
de referencia con clase esperada conocida (uno de riesgo bajo, uno de riesgo alto; ver
`CANARY_RIESGO_BAJO` / `CANARY_RIESGO_ALTO` en el script). Si `clase_predicha` no
coincide con lo esperado en cualquiera de los dos, se dispara `ALERT-QUALITY-01`.

## 2. Diagnóstico (antes de actuar)

1. Confirmar que la alerta no es un falso positivo: ejecutar manualmente los dos
   payloads canary contra el endpoint y revisar la respuesta.
   ```bash
   curl -X POST https://fase2-abandono-escolar.onrender.com/predict \
     -H "Content-Type: application/json" \
     -d '{"promedio_academico": 9.5, "materias_reprobadas": 0, "asistencia": 0.99,
          "condicion_beca": 1, "distancia_campus": 1.0, "horas_trabajo_semanales": 0,
          "semestre_actual": 6, "modalidad": 0}'
   # Se espera clase_predicha = 0
   ```
2. Revisar el historial de commits recientes sobre `models/modelo_abandono.joblib`
   para identificar el ultimo cambio:
   ```bash
   git log --oneline -- models/modelo_abandono.joblib
   ```
3. Revisar si hubo un despliegue reciente (Render → pestaña *Events* del servicio)
   que coincida en tiempo con el inicio de la degradación.

## 3. Respuesta

**Opción A — Rollback (respuesta mas rapida, usar por defecto):**

```bash
python -m actividad8.scripts.rollback --modo rollback \
  --commit-bueno <hash-del-ultimo-commit-bueno> --push
```

Esto restaura el artefacto `models/modelo_abandono.joblib` desde el commit indicado,
hace commit y push, lo que dispara el redeploy automático en Render.

**Opción B — Reentrenamiento (si el rollback no es viable, ej. no hay una version
buena reciente conocida):**

```bash
python -m actividad8.scripts.rollback --modo reentrenar --push
```

El script reentrena con `src/generate_data.py` + `src/train.py` y **solo** acepta el
nuevo modelo si el F1 de prueba es ≥ 0.80 (el mismo objetivo SMART de la Fase 2). Si
no lo supera, aborta automáticamente y no toca el modelo en producción.

## 4. Verificación

Esperar el redeploy (~1-2 min, verificar en Render → Events) y confirmar con:

```bash
python -m actividad8.scripts.monitor --ciclos 3 --intervalo-seg 8
```

Confirmar `canary_correcto=True` en los 3 ciclos y que no se dispare
`ALERT-QUALITY-01` de nuevo.

## 5. Escalamiento

Si tras dos intentos de rollback la alerta persiste, o no existe un commit bueno
conocido en el historial reciente: detener el tráfico (pausar el servicio en Render)
en lugar de seguir sirviendo predicciones incorrectas, y escalar para investigación
manual del pipeline de datos/entrenamiento.

## 6. Evidencia de ejecución real (Actividad 8)

Este runbook se ejecutó realmente el 2026-07-18 contra la API de producción. Ver
[`actividad8/incidentes/registro_incidentes.md`](../incidentes/registro_incidentes.md),
incidente 2, para el registro completo (timestamps, comandos, resultados).
