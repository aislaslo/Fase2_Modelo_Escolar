"""Gate de fairness para el pipeline de CI/CD (Fase 3).

Reutiliza la auditoria real de la Actividad 9 (actividad9/scripts/
auditoria_fairness.py) en lugar de reimplementarla. No exige que la regla de
las 4/5 (EEOC) sea >= 0.80 de forma absoluta -- ya se determino en la
Actividad 9 que el valor actual (~0.73) es consecuencia directa y esperada
del peso de `condicion_beca` como variable predictiva legitima, no un sesgo
espurio (ver actividad9/anexo_tecnico.md, seccion 3.3).

En su lugar, este gate es una prueba de REGRESION: compara el resultado
actual contra la linea base documentada
(fase3/scripts/fairness_baseline.json) y falla solo si un cambio de modelo
(por ejemplo, un reentrenamiento con datos nuevos) empeora la disparidad mas
alla de una tolerancia -- exactamente el tipo de cambio silencioso que un
pipeline de gobernanza responsable debe atrapar.

Uso:
    python -m fase3.scripts.gate_fairness
Codigo de salida 0 si no hay regresion, 1 si la hay.
"""

import json
import sys
from pathlib import Path

from actividad9.scripts.auditoria_fairness import auditar

BASELINE_PATH = Path("fase3/scripts/fairness_baseline.json")


def evaluar_gate() -> bool:
    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    tolerancia = baseline["tolerancia"]

    resultado = auditar()

    cociente_actual = resultado["cociente_4_5_reglas"]
    cociente_base = baseline["cociente_4_5_reglas"]
    dpd_actual = resultado["demographic_parity_diff"]
    dpd_base = baseline["demographic_parity_diff"]

    regresion_cociente = cociente_actual < (cociente_base - tolerancia)
    regresion_dpd = dpd_actual > (dpd_base + tolerancia)

    print(f"Cociente regla 4/5:          actual={cociente_actual:.4f}  "
          f"baseline={cociente_base:.4f}  tolerancia={tolerancia}")
    print(f"Demographic parity diff:     actual={dpd_actual:.4f}  "
          f"baseline={dpd_base:.4f}  tolerancia={tolerancia}")

    if regresion_cociente or regresion_dpd:
        print("\nFAIL: el modelo evaluado muestra una regresion de fairness "
              "respecto a la linea base documentada en la Actividad 9.")
        print("Revisar actividad9/docs/runbook equivalente antes de desplegar; "
              "no se recomienda continuar el pipeline sin justificar el cambio.")
        return False

    print("\nPASS: sin regresion de fairness respecto a la linea base.")
    return True


if __name__ == "__main__":
    ok = evaluar_gate()
    sys.exit(0 if ok else 1)
