# Reporte de Auditoría de Fairness — Actividad 9

Atributo protegido (proxy socioeconómico): **`condicion_beca`** (0 = sin beca, 1 = con beca). Evaluado sobre el conjunto de prueba (20%, `random_state=42`), no sobre datos de entrenamiento.

## Métricas por grupo

| Grupo | n | Selection rate | TPR (recall) | FPR | Precision | Accuracy |
|---|---|---|---|---|---|---|
| Sin beca | 140 | 0.4786 | 0.9107 | 0.1905 | 0.7612 | 0.85 |
| Con beca | 60 | 0.35 | 0.875 | 0.1591 | 0.6667 | 0.85 |

## Métricas de disparidad

| Métrica | Valor | Interpretación |
|---|---|---|
| Demographic parity difference | 0.1286 | Diferencia en tasa de predicción de riesgo entre grupos (0 = paridad perfecta) |
| Equal opportunity difference | 0.0357 | Diferencia en TPR (recall) entre grupos |
| Equalized odds difference | 0.0357 | Máximo entre diferencia de TPR y de FPR |
| Cociente regla de las 4/5 (EEOC) | 0.7313 | NO cumple (umbral ≥ 0.80) |