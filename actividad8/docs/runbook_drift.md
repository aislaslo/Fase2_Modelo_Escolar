# Runbook: Data drift detectado (ALERT-DRIFT-01)

**Severidad:** P2 — revisión en el corto plazo (no degrada el servicio de forma
inmediata, pero incrementa el riesgo de predicciones sesgadas si no se atiende).

---

## 1. Disparador

`actividad8/scripts/detectar_drift.py` calcula el Population Stability Index (PSI)
entre `data/dataset_abandono.csv` (entrenamiento) y un dataset que representa datos
recientes de producción, para cada una de las 8 variables predictoras.

| PSI | Clasificación |
|---|---|
| < 0.10 | Sin drift relevante |
| 0.10 – 0.25 | Moderado (revisar) |
| ≥ 0.25 | Significativo (acción requerida) |

`ALERT-DRIFT-01` se dispara si al menos una variable tiene PSI ≥ 0.10.

## 2. Diagnóstico

1. Ejecutar la detección y revisar el reporte:
   ```bash
   python -m actividad8.scripts.detectar_drift
   cat actividad8/evidencia/reporte_drift.md
   ```
2. Para cada variable marcada como `MODERADO` o `SIGNIFICATIVO`, comparar
   `media_referencia` vs `media_produccion` para entender la dirección del cambio
   (ej. ¿subió o bajó el promedio académico?).
3. Determinar si el drift es:
   - **Esperado / estacional** (ej. inicio de semestre, periodo de exámenes) → de
     bajo riesgo, documentar y monitorear.
   - **Estructural** (ej. cambio permanente en la población estudiantil, un nuevo
     programa que atrae un perfil distinto) → requiere reentrenamiento.

## 3. Respuesta

**Si el drift es significativo y estructural:**

```bash
# 1. Incorporar los datos recientes representativos al dataset de entrenamiento
#    (fuera del alcance de este script: requiere una fuente de datos reales
#    etiquetados; en este proyecto se ilustra con datos sinteticos).
# 2. Reentrenar y validar contra el umbral minimo de F1:
python -m actividad8.scripts.rollback --modo reentrenar --push
```

El modo `reentrenar` de `rollback.py` reentrena y **solo** despliega el nuevo modelo
si el F1 de prueba es ≥ 0.80; de lo contrario aborta sin tocar producción.

**Si el drift es moderado o estacional:**

- No reentrenar de inmediato. Registrar el hallazgo y aumentar la frecuencia de
  monitoreo de esa variable en los siguientes ciclos.

## 4. Verificación

Tras un reentrenamiento, volver a ejecutar `detectar_drift.py` con un dataset de
producción actualizado y confirmar que el PSI de las variables afectadas baja de
0.10, o que el nuevo modelo (entrenado con datos que incluyen el drift) sigue
cumpliendo el F1 mínimo en `docs/validacion_pruebas.md`.

## 5. Escalamiento

Si el drift es significativo en 3 o más variables simultáneamente, o si el F1 del
modelo reentrenado no logra superar el umbral mínimo tras el ajuste, escalar para
una revisión completa del proceso de recolección de datos — puede indicar un
problema en la fuente de datos, no solo en el modelo.

## 6. Evidencia de ejecución real (Actividad 8)

Ejecutado el 2026-07-18 comparando `data/dataset_abandono.csv` contra
`actividad8/evidencia/dataset_produccion_con_drift.csv` (dataset sintético generado
deliberadamente con distribuciones desplazadas). Resultado: drift significativo en
`asistencia` (PSI=0.264) y `promedio_academico` (PSI=0.2558); drift moderado en
`horas_trabajo_semanales` (PSI=0.196) y `modalidad` (PSI=0.1602). Ver
[`actividad8/evidencia/reporte_drift.md`](../evidencia/reporte_drift.md) y
[`actividad8/incidentes/registro_incidentes.md`](../incidentes/registro_incidentes.md).
