# Runbook: Latencia elevada en /predict (ALERT-LAT-01)

**Severidad:** P2 — revisión en el corto plazo.
**Impacto:** los coordinadores esperan mas tiempo del esperado por una respuesta; no
hay pérdida de datos ni respuestas incorrectas, solo degradación de experiencia.

---

## 1. Disparador

`actividad8/scripts/monitor.py` mide `predict_latency_ms` en cada ciclo. Si supera
2000ms durante 3 ciclos consecutivos **y** ninguno de esos ciclos está marcado como
`cold_start` (ver sección 5), se dispara `ALERT-LAT-01`.

## 2. Diagnóstico

1. Descartar cold start del plan gratuito de Render (ver sección 5) — si el servicio
   estuvo inactivo, el primer request puede tardar 30-50s y es esperado, no un
   incidente real.
2. Confirmar la degradación de forma manual:
   ```bash
   curl -s -o /dev/null -w "%{time_total}s\n" -X POST \
     https://fase2-abandono-escolar.onrender.com/predict \
     -H "Content-Type: application/json" \
     -d '{"promedio_academico": 7.8, "materias_reprobadas": 2, "asistencia": 0.82,
          "condicion_beca": 1, "distancia_campus": 12.5, "horas_trabajo_semanales": 20,
          "semestre_actual": 4, "modalidad": 0}'
   ```
3. Revisar los logs del servicio en el dashboard de Render (pestaña *Logs*) buscando
   errores, reintentos, o uso elevado de CPU/memoria en la métrica de la instancia.
4. Revisar si hubo un despliegue reciente que pudo introducir codigo mas lento
   (ej. una dependencia nueva, un cambio en la logica de inferencia).

## 3. Respuesta

**Si el origen es un despliegue reciente con código más lento:**

```bash
git log --oneline -5          # identificar el ultimo commit bueno conocido
git revert --no-edit <hash-del-commit-que-introdujo-la-lentitud>
git push origin main          # dispara el redeploy automatico
```

**Si el origen es infraestructura (instancia sobrecargada, no código):**

- Verificar el plan de Render; el plan Free tiene 0.1 CPU / 512MB — considerar
  escalar temporalmente a un plan pagado (Starter: 0.5 CPU / 512MB) desde el
  dashboard si la carga es sostenida y no puntual.

## 4. Verificación

```bash
python -m actividad8.scripts.monitor --ciclos 3 --intervalo-seg 8
```

Confirmar `predict_latency_ms < 2000` de forma sostenida y que `ALERT-LAT-01` no
vuelva a dispararse.

## 5. Nota sobre cold start (no confundir con este incidente)

El plan gratuito de Render suspende el servicio tras ~15 minutos de inactividad. El
primer request tras ese periodo puede tardar 30-50s — esto es *esperado* y se
clasifica como `ALERT-LAT-02` (P3, informativo), no como `ALERT-LAT-01`. No requiere
intervención; ver `alertas_config.yaml`.

## 6. Escalamiento

Si la latencia elevada persiste tras el rollback y no hay un despliegue reciente que
la explique, escalar para investigar la infraestructura de Render directamente
(posible degradación del proveedor).

## 7. Evidencia de ejecución real (Actividad 8)

Este runbook se ejecutó realmente el 2026-07-18 contra la API de producción,
provocando deliberadamente la latencia (ver
[`actividad8/incidentes/registro_incidentes.md`](../incidentes/registro_incidentes.md),
incidente 1) para validar que la deteccion y el rollback funcionan end-to-end.
