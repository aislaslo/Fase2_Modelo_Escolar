"""Automatizacion de respuesta a incidentes: rollback o reentrenamiento del
modelo (Actividad 8).

Dos modos de respuesta automatizada:

  --modo rollback      Restaura el artefacto de modelo (`models/modelo_abandono.joblib`)
                        desde un commit anterior conocido como bueno, usando
                        `git checkout <commit> -- models/modelo_abandono.joblib`.
                        Es la respuesta mas rapida ante un incidente de
                        "modelo degradado": revierte el archivo sin tener que
                        reentrenar.

  --modo reentrenar     Vuelve a generar el dataset y reentrenar el modelo
                        desde cero (src/generate_data.py + src/train.py), y
                        SOLO acepta el nuevo artefacto como reemplazo si el
                        F1 de prueba supera el umbral minimo (0.80, el mismo
                        objetivo SMART de la Fase 2). Si no lo supera, aborta
                        sin tocar el modelo en produccion.

Por seguridad, el script nunca hace `git push` automaticamente salvo que se
pase --push explicitamente; sin ese flag deja el cambio listo en el working
tree para revision manual antes de subir (y disparar el redeploy en Render).

Uso:
    python -m actividad8.scripts.rollback --modo rollback --commit-bueno <hash> --push
    python -m actividad8.scripts.rollback --modo reentrenar --push
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

MODEL_PATH = Path("models/modelo_abandono.joblib")
F1_MINIMO = 0.80


def sh(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    print(f"$ {' '.join(cmd)}")
    resultado = subprocess.run(cmd, capture_output=True, text=True)
    if resultado.stdout:
        print(resultado.stdout)
    if resultado.returncode != 0:
        if resultado.stderr:
            print(resultado.stderr, file=sys.stderr)
        if check:
            raise SystemExit(resultado.returncode)
    return resultado


def commitear_y_pushear(mensaje: str) -> None:
    sh(["git", "add", str(MODEL_PATH)])
    sh(["git", "commit", "-m", mensaje])
    sh(["git", "push", "origin", "main"])
    print("\nCambio pusheado a origin/main. Render redesplegara automaticamente "
          "(auto-deploy activado en el servicio).")


def modo_rollback(commit_bueno: str, push: bool) -> None:
    print(f"\n=== Rollback: restaurando {MODEL_PATH} desde el commit {commit_bueno} ===\n")
    sh(["git", "checkout", commit_bueno, "--", str(MODEL_PATH)])
    sh(["git", "status", "--short"])

    if push:
        commitear_y_pushear(
            f"Rollback: restaurar modelo desde {commit_bueno} (respuesta automatizada, Actividad 8)"
        )
    else:
        print(f"\nModelo restaurado en el working tree desde {commit_bueno}. "
              "Revisa `git diff --stat` y vuelve a ejecutar con --push para "
              "confirmar el rollback y disparar el redeploy.")


def modo_reentrenar(push: bool) -> None:
    print("\n=== Reentrenamiento: regenerando dataset y modelo ===\n")
    sh(["python", "-m", "src.generate_data"])
    resultado_train = sh(["python", "-m", "src.train"])

    match = re.search(r"F1 prueba:\s*([\d.]+)", resultado_train.stdout)
    if not match:
        print("No se pudo leer el F1 de prueba de la salida de src.train. Abortando.",
              file=sys.stderr)
        raise SystemExit(1)

    f1 = float(match.group(1))
    print(f"F1 de prueba del modelo reentrenado: {f1:.4f} (minimo aceptado: {F1_MINIMO})")

    if f1 < F1_MINIMO:
        sh(["git", "checkout", "--", str(MODEL_PATH)])  # descarta el modelo reentrenado
        print(f"\nF1 {f1:.4f} por debajo del minimo {F1_MINIMO}. Modelo reentrenado "
              "RECHAZADO y descartado; el modelo en produccion no se modifica.")
        raise SystemExit(1)

    print(f"\nF1 {f1:.4f} cumple el minimo. Modelo reentrenado ACEPTADO.")
    if push:
        commitear_y_pushear(
            f"Reentrenamiento automatizado: nuevo modelo con F1={f1:.4f} (Actividad 8)"
        )
    else:
        print("Modelo reentrenado listo en el working tree. Vuelve a ejecutar con "
              "--push para confirmar y disparar el redeploy.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--modo", choices=["rollback", "reentrenar"], required=True)
    parser.add_argument("--commit-bueno", help="Hash del commit con el modelo bueno (solo --modo rollback)")
    parser.add_argument("--push", action="store_true", help="Hace commit y push del resultado")
    args = parser.parse_args()

    if args.modo == "rollback":
        if not args.commit_bueno:
            parser.error("--modo rollback requiere --commit-bueno <hash>")
        modo_rollback(args.commit_bueno, args.push)
    else:
        modo_reentrenar(args.push)
