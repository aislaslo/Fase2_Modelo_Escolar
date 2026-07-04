# Manual de Despliegue — API de Predicción de Abandono Escolar

> Cubre: ejecución local, contenerización con Docker y estrategia de despliegue en la
> nube bajo el modelo PaaS, conforme al Tema 16 (Módulo 2, Semana 8) del curso.
> El despliegue en la nube descrito aquí es **demostrativo**: se documenta el
> procedimiento completo, pero no se ejecutó un despliegue real en esta entrega,
> conforme a la advertencia del propio material del curso (las actividades de nube no
> son obligatorias para la evaluación final).

---

## 1. Requerimientos técnicos

| Componente | Requisito |
|------------|-----------|
| Lenguaje | Python 3.11 o superior |
| Gestor de paquetes | pip (ver `requirements.txt`) |
| Contenedores | Docker Engine / Docker Desktop |
| Control de versiones | Git, repositorio en GitHub |
| Cuenta en plataforma PaaS | Render (o equivalente: Railway, Fly.io) |
| Puerto expuesto por el servicio | 8000 (HTTP) |

## 2. Ejecución local sin Docker

```bash
python3.11 -m venv .venv
source .venv/bin/activate          # En Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 1. Generar el dataset (no se dispuso del CSV original de la Actividad 6;
#    ver docs/documentacion_tecnica.md, seccion 2, para la justificacion).
python -m src.generate_data

# 2. Entrenar y serializar el modelo
python -m src.train

# 3. Levantar la API
uvicorn src.api:app --reload
```

La documentación interactiva queda disponible en `http://localhost:8000/docs`
(Swagger UI, generada automáticamente por FastAPI).

## 3. Contenerización con Docker

### 3.1 Construcción de la imagen

```bash
docker build -t abandono-escolar-api .
```

El `Dockerfile` usa `python:3.11-slim` como base, instala dependencias en una capa
separada (aprovecha la caché de Docker) y copia únicamente `src/` y `models/`: el
artefacto del modelo se incluye en la imagen de forma intencional para que el
contenedor sea autosuficiente y no dependa de generar/entrenar el modelo en tiempo de
arranque.

### 3.2 Ejecución del contenedor

```bash
docker run -d -p 8000:8000 --name abandono-escolar-api abandono-escolar-api
```

### 3.3 Verificación

```bash
curl http://localhost:8000/health
# {"estado":"operativo"}

curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"promedio_academico": 7.8, "materias_reprobadas": 2, "asistencia": 0.82,
       "condicion_beca": 1, "distancia_campus": 12.5, "horas_trabajo_semanales": 20,
       "semestre_actual": 4, "modalidad": 0}'
```

Evidencia real de esta verificación (build, ejecución y respuesta de endpoints) se
documenta en [`docs/validacion_pruebas.md`](./validacion_pruebas.md).

## 4. Estrategia de despliegue en la nube (PaaS)

Se elige **Render** como plataforma de referencia: modelo de servicio **PaaS**
(coherente con el enfoque del Tema 16), soporta despliegue directo desde un
`Dockerfile` en un repositorio de GitHub, ofrece un plan gratuito suficiente para fines
demostrativos y no requiere gestión manual de infraestructura subyacente.

### 4.1 Pasos de despliegue (procedimiento documentado)

1. Publicar el repositorio (código fuente, `Dockerfile`, `models/modelo_abandono.joblib`)
   en GitHub — ver sección 5.
2. En Render, crear un nuevo **Web Service** y conectarlo al repositorio de GitHub.
3. Seleccionar **Docker** como entorno de ejecución (Render detecta el `Dockerfile`
   automáticamente).
4. Configurar variables de entorno si aplica (no se requieren para esta API; el modelo
   se carga desde el sistema de archivos de la imagen).
5. Definir el puerto expuesto: 8000 (Render inyecta la variable `PORT`; si se despliega
   realmente, ajustar el `CMD` del contenedor para usar `--port $PORT` en lugar de un
   puerto fijo, o configurar el servicio para mapear el puerto 8000 expuesto).
6. Disparar el despliegue (Render construye la imagen a partir del `Dockerfile` y la
   ejecuta).
7. Verificar disponibilidad accediendo a `https://<nombre-del-servicio>.onrender.com/health`.
8. Repetir las pruebas funcionales de la sección 3.3 contra la URL pública.

### 4.2 Consideraciones de escalabilidad y seguridad (Tema 16)

- **Modelo de servicio:** PaaS — Render gestiona la infraestructura subyacente
  (cómputo, red, balanceo); el equipo del proyecto solo gestiona la imagen y el código.
- **Modelo de infraestructura:** nube pública. Adecuado aquí porque el dataset es
  sintético y no contiene información real de estudiantes; si se usara el dataset real
  de la Actividad 6 con datos institucionales sensibles, correspondería evaluar una
  nube privada o híbrida para el almacenamiento de datos, aun si la API de inferencia
  se mantiene en PaaS público.
- **Escalabilidad:** Render permite escalar horizontalmente el servicio (más
  instancias) sin cambios en el código, dado que la API es *stateless*.
- **Seguridad mínima recomendada antes de un despliegue real:** restringir CORS a los
  orígenes del frontend institucional, y añadir autenticación (API key o JWT) en
  `/predict`, ya que la versión actual no implementa control de acceso.

### 4.3 Alternativas consideradas

- **Railway:** mismo modelo de despliegue por `Dockerfile`, interfaz similar a Render;
  válida como alternativa si Render no estuviera disponible.
- **AWS:** explícitamente no es un requisito según el material del curso; se descarta
  para mantener el despliegue de bajo costo y sin necesidad de gestionar IAM, VPC, etc.

## 5. Publicación del repositorio en GitHub

```bash
git init                                   # si el repo no esta inicializado
git remote add origin <URL-del-repositorio>
git add .
git commit -m "Fase 2: API contenerizada de prediccion de abandono escolar"
git push -u origin main
```

El repositorio debe incluir: código fuente (`src/`), `Dockerfile`, `.dockerignore`,
`requirements.txt`, pruebas (`tests/`), documentación (`docs/`) y `README.md`. Se
excluyen del control de versiones el entorno virtual, el caché de pytest y los datos de
seguimiento local de MLflow (ver `.gitignore`).

## 6. Uso de herramientas de documentación (IA generativa)

Este manual, la documentación técnica ISO/IEC 23053 y el documento de validación se
redactaron con apoyo de **Claude Code** (Anthropic) como asistente de código en VS Code,
siguiendo el enfoque sugerido en el Tema 16 de usar IA generativa para estructurar la
documentación técnica del despliegue. Cada fase (dataset, entrenamiento, API,
contenerización, pruebas) fue ejecutada y verificada localmente antes de documentarse.
