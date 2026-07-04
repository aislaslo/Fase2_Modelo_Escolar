# API de Predicción de Abandono Escolar

Servicio de inferencia del modelo de Regresión Logística desarrollado en la
Actividad 6 del curso **Gestión de Proyectos de Inteligencia Artificial**
(Universidad Tecmilenio). Esta Fase 2 contieneriza el modelo, lo expone como API
REST, valida su funcionamiento local y documenta la estrategia de despliegue en la
nube.

> Alumno: Alejandro Islas López (matrícula T07136481).

## Contenido del repositorio

```
├── src/                    # Codigo fuente (generacion de datos, entrenamiento, API)
├── models/                 # Artefacto serializado del modelo (.joblib)
├── data/                   # Dataset sintetico de entrenamiento
├── tests/                  # Pruebas automatizadas (pytest)
├── docs/                   # Documentacion tecnica, manual de despliegue y validacion
├── Dockerfile
├── .dockerignore
└── requirements.txt
```

## Requisitos

- Python 3.11 o superior
- Docker (para contenerización y ejecución local del contenedor)

## Instalación local

```bash
python3.11 -m venv .venv
source .venv/bin/activate      # En Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Generación de datos y entrenamiento del modelo

> No se dispuso del dataset original de la Actividad 6; se genera un dataset
> sintético equivalente y reproducible. Ver `docs/documentacion_tecnica.md` (sección 2)
> para el detalle y la justificación.

```bash
python -m src.generate_data
python -m src.train
```

Genera el artefacto en `models/modelo_abandono.joblib` y registra la corrida en
MLflow bajo el experimento `abandono_escolar_actividad6`.

## Ejecución del servicio

```bash
uvicorn src.api:app --reload
```

La documentación interactiva queda disponible en `http://localhost:8000/docs`.

## Consumo de la API

```bash
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"promedio_academico": 7.8, "materias_reprobadas": 2, "asistencia": 0.82,
       "condicion_beca": 1, "distancia_campus": 12.5, "horas_trabajo_semanales": 20,
       "semestre_actual": 4, "modalidad": 0}'
```

Respuesta esperada:

```json
{
  "probabilidad_abandono": 0.63,
  "clase_predicha": 1,
  "umbral_aplicado": 0.40,
  "nivel_riesgo": "alto"
}
```

## Contenerización

```bash
docker build -t abandono-escolar-api .
docker run -d -p 8000:8000 --name abandono-escolar-api abandono-escolar-api
```

## Pruebas

```bash
pytest tests/ -v
```

## Documentación adicional

- [`docs/documentacion_tecnica.md`](docs/documentacion_tecnica.md) — documentación
  alineada con ISO/IEC 23053: propósito, diseño, datos, verificación, operación y fin
  de vida útil del sistema.
- [`docs/manual_despliegue.md`](docs/manual_despliegue.md) — manual paso a paso de
  ejecución local, contenerización y estrategia de despliegue en PaaS (Render).
- [`docs/validacion_pruebas.md`](docs/validacion_pruebas.md) — pruebas funcionales,
  casos extremos evaluados, resultados y conclusiones.
