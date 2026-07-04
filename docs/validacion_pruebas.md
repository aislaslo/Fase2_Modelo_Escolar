# Documento de Validación y Pruebas

> Evidencia de las pruebas funcionales, casos extremos y resultados obtenidos durante
> la implementación de la Fase 2 (contenerización y despliegue del modelo de
> predicción de abandono escolar).

---

## 1. Validación del modelo

Ejecución de `python -m src.train` sobre el dataset sintético generado por
`src/generate_data.py` (semilla fija, 1000 registros):

| Métrica | Resultado |
|---------|-----------|
| F1 (conjunto de prueba, 20%) | 0.8493 |
| AUC-ROC | 0.9464 |
| F1 media (5-fold cross-validation) | 0.8155 |
| Desviación estándar (5-fold CV) | 0.0422 |

**Conclusión:** el objetivo SMART (F1 ≥ 0.80 en 5-fold CV) se cumple. Las métricas son
cercanas a las reportadas en la Actividad 6 (F1 = 0.8456, AUC-ROC = 0.8660, F1 CV =
0.8376 ± 0.0226), con la salvedad de que provienen de un dataset sintético equivalente
y no del dataset original (ver `docs/documentacion_tecnica.md`, sección 2).

## 2. Pruebas funcionales automatizadas (pytest)

Suite: `tests/test_api.py`, ejecutada con `python -m pytest tests/ -v`.

```
collected 11 items

tests/test_api.py::test_health                            PASSED
tests/test_api.py::test_predict_riesgo_alto                PASSED
tests/test_api.py::test_predict_riesgo_bajo                PASSED
tests/test_api.py::test_predict_entrada_incompleta         PASSED
tests/test_api.py::test_predict_promedio_fuera_de_rango    PASSED
tests/test_api.py::test_predict_asistencia_negativa        PASSED
tests/test_api.py::test_predict_materias_reprobadas_negativas PASSED
tests/test_api.py::test_predict_modalidad_invalida         PASSED
tests/test_api.py::test_predict_boundary_asistencia_extremos PASSED
tests/test_api.py::test_predict_horas_trabajo_fuera_de_rango PASSED
tests/test_api.py::test_predict_modelo_no_disponible        PASSED

11 passed in 1.52s
```

### 2.1 Casos funcionales cubiertos

| Caso | Verificación |
|------|--------------|
| `GET /health` | Responde `200` con `{"estado": "operativo"}` |
| `POST /predict` con perfil de riesgo alto | `200`, `clase_predicha = 1`, `nivel_riesgo = "alto"` |
| `POST /predict` con perfil de riesgo bajo | `200`, `clase_predicha = 0`, `nivel_riesgo = "bajo"` |

### 2.2 Casos extremos (edge cases) evaluados

| Caso extremo | Entrada | Resultado esperado | Resultado obtenido |
|--------------|---------|---------------------|---------------------|
| Entrada incompleta | Solo 1 de 8 campos | `422` | `422` ✅ |
| Valor fuera de rango superior | `promedio_academico = 15.0` (> 10) | `422` | `422` ✅ |
| Valor fuera de rango inferior | `asistencia = -0.1` (< 0) | `422` | `422` ✅ |
| Valor negativo en campo `ge=0` | `materias_reprobadas = -1` | `422` | `422` ✅ |
| Valor fuera de enum | `modalidad = 9` (no es 0 ni 1) | `422` | `422` ✅ |
| Límite exacto inferior | `asistencia = 0.0` | `200` (valor límite valido) | `200` ✅ |
| Límite exacto superior | `asistencia = 1.0` | `200` (valor límite valido) | `200` ✅ |
| Valor fuera de rango superior | `horas_trabajo_semanales = 200` (> 168) | `422` | `422` ✅ |
| Modelo no disponible | Artefacto `.joblib` ausente (`MODEL_PATH` simulado inexistente) | `503`, sin caída del proceso | `503` ✅ |

**Hallazgo corregido durante la validación:** en la primera versión de `src/api.py`, la
carga del modelo en el evento de arranque (`lifespan`) no capturaba `FileNotFoundError`.
Esto provocaba que, si el artefacto no existía, **todo el proceso de la API fallaba al
iniciar** (el contenedor no llegaba a estar disponible), en lugar de permitir que
`/health` respondiera y `/predict` devolviera `503` de forma controlada, que era el
comportamiento ya previsto en el manejo de errores del endpoint. Se corrigió
capturando la excepción en `lifespan` (con registro en el log) y se agregó la prueba
automatizada `test_predict_modelo_no_disponible` para evitar una regresión futura.
Evidencia manual de la corrección (ejecución local, con el artefacto renombrado
temporalmente):

```
GET  /health   -> 200 {"estado":"operativo"}
POST /predict  -> 503 {"detail":"No se encontro el modelo en models/modelo_abandono.joblib..."}
```

## 3. Pruebas de integración manual (curl)

Ejecutadas contra la API corriendo localmente vía `uvicorn` (entorno virtual, sin
Docker):

```
POST /predict  (riesgo alto: promedio 5.5, 4 reprobadas, asistencia 0.60, trabaja 35h)
-> {"probabilidad_abandono":0.9999,"clase_predicha":1,"umbral_aplicado":0.4,"nivel_riesgo":"alto"}

POST /predict  (riesgo bajo: promedio 9.2, 0 reprobadas, asistencia 0.98, con beca)
-> {"probabilidad_abandono":0.0002,"clase_predicha":0,"umbral_aplicado":0.4,"nivel_riesgo":"bajo"}
```

Se confirma que el umbral de decisión aplicado es 0.40 (no 0.5), tal como exige el
alcance de la Fase 2.

## 4. Pruebas de contenerización (Docker)

### 4.1 Construcción de la imagen

```
docker build -t abandono-escolar-api .
```

Resultado: construcción exitosa. Imagen `abandono-escolar-api:latest`, tamaño de
contenido ≈ 289 MB (imagen base `python:3.11-slim` + dependencias de
`requirements.txt`).

### 4.2 Ejecución del contenedor

```
docker run -d -p 8000:8000 --name abandono-escolar-test abandono-escolar-api
docker ps
```

Resultado: contenedor en estado `Up`, puerto `8000` mapeado correctamente
(`0.0.0.0:8000->8000/tcp`).

### 4.3 Verificación de endpoints dentro del contenedor

```
GET  /health   -> 200 {"estado":"operativo"}
POST /predict  (riesgo alto) -> 200 {"probabilidad_abandono":0.9999,"clase_predicha":1,...}
POST /predict  (entrada invalida: solo promedio_academico=15.0) -> 422
```

Logs del contenedor confirman el registro correcto de cada petición:

```
INFO: Application startup complete.
INFO: Uvicorn running on http://0.0.0.0:8000
INFO: 192.168.65.1 - "GET /health HTTP/1.1" 200 OK
INFO: 192.168.65.1 - "POST /predict HTTP/1.1" 200 OK
INFO: 192.168.65.1 - "POST /predict HTTP/1.1" 422 Unprocessable Entity
```

El contenedor se detuvo y eliminó tras la prueba (`docker stop` / `docker rm`); la
imagen se conserva para su publicación.

## 5. Resultados y conclusiones

- El modelo cumple el objetivo SMART (F1 ≥ 0.80) sobre el dataset sintético
  reproducible generado para esta fase.
- La API expone correctamente `/health` y `/predict`, valida la entrada con Pydantic,
  y aplica el umbral de decisión de 0.40 en todas las predicciones.
- Se evaluaron 9 casos extremos (rangos inválidos, valores límite, entrada incompleta,
  enum inválido, modelo no disponible) además de los 2 casos funcionales base; los 11
  casos están cubiertos por pruebas automatizadas que pasan de forma reproducible.
- La contenerización con Docker es funcional: la imagen construye sin errores y el
  contenedor sirve la API de forma idéntica al entorno local sin Docker.
- Durante la validación se identificó y corrigió un defecto real (fallo de arranque
  ante modelo ausente), lo que confirma el valor de ejecutar las pruebas de casos
  extremos antes de considerar el sistema listo para documentar su despliegue.
- **Limitación abierta:** no se ejecutó un despliegue real en un PaaS (ver
  `docs/manual_despliegue.md`); la estrategia de nube está documentada pero no
  verificada end-to-end contra una URL pública.
