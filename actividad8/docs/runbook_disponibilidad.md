# Runbook: Servicio no disponible (ALERT-AVAIL-01)

**Severidad:** P1 — acción inmediata.
**Impacto:** el servicio no responde; bloquea por completo el flujo de detección de
riesgo de abandono para coordinadores y directivos.

---

## 1. Disparador

`actividad8/scripts/monitor.py` marca `disponible=False` si `GET /health` o
`POST /predict` (con cualquiera de los dos canary checks) no devuelve `200`, o si la
petición falla por completo (timeout, conexión rechazada). Dispara `ALERT-AVAIL-01`
en el mismo ciclo (no requiere ciclos consecutivos, a diferencia de latencia).

## 2. Diagnóstico

1. Confirmar manualmente:
   ```bash
   curl -i https://fase2-abandono-escolar.onrender.com/health
   ```
2. Revisar el dashboard de Render:
   - Pestaña **Events**: ¿el servicio está en estado `Deploy failed`, `Suspended` o
     reiniciando en loop?
   - Pestaña **Logs**: buscar tracebacks de Python, errores de arranque
     (`Application startup failed`), o el mensaje conocido
     `Modelo no disponible al iniciar` (ver `src/api.py`, función `lifespan`) que
     indica que `models/modelo_abandono.joblib` no se encontró al arrancar.
3. Distinguir entre:
   - **Cold start** (el servicio estaba dormido, tarda en responder pero SI
     responde eventualmente con 200) → no es este incidente, ver
     `runbook_latencia.md` sección 5.
   - **Caída real** (el servicio no llega a `Live` en Render, o responde con error) →
     continuar con este runbook.

## 3. Respuesta

**Si el build/deploy falló (ver Events en Render):**

```bash
git log --oneline -5
git revert --no-edit <hash-del-ultimo-commit-pusheado>
git push origin main
```

**Si el modelo no se encontró al arrancar** (`models/modelo_abandono.joblib` faltante
o corrupto):

```bash
git checkout <ultimo-commit-bueno> -- models/modelo_abandono.joblib
git add models/modelo_abandono.joblib
git commit -m "Restaurar artefacto de modelo faltante"
git push origin main
```

Nota: gracias al diseño de `src/api.py` (`lifespan`), la ausencia del modelo no tumba
el proceso — `/health` sigue respondiendo 200 y `/predict` responde 503 de forma
controlada. Si `ALERT-AVAIL-01` se dispara, es indicio de un problema mas severo que
solo el modelo faltante (ver logs).

## 4. Verificación

```bash
python -m actividad8.scripts.monitor --ciclos 3 --intervalo-seg 8
```

Confirmar `disponible=True` en los 3 ciclos.

## 5. Escalamiento

Si el servicio no vuelve a `Live` en Render tras 15 minutos de intentos de rollback,
escalar como incidente de infraestructura del proveedor (Render) y evaluar activar
manualmente el manual de despliegue (`docs/manual_despliegue.md`) sobre una
plataforma alternativa (Railway, ver sección 4.3 del manual).
