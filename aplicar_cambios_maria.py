# =====================================================================
# Aplica draft_content_MARIA_NUEVO.json al draft REAL de CapCut
# "mariaaa baic", con backup automatico del original antes de tocar nada.
# =====================================================================
# USO:
#   1. Cerra CapCut por completo.
#   2. Corre primero procesar_maria.py (con maria_actual.json en la
#      misma carpeta) - genera draft_content_MARIA_NUEVO.json.
#   3. Corre ESTE script.
#   4. Abri CapCut y revisa el resultado.
# =====================================================================

import os
import shutil
from datetime import datetime

CARPETA_DRAFT_REAL = r"C:\Users\user2\AppData\Local\CapCut\User Data\Projects\com.lveditor.draft\mariaaa baic"
RUTA_JSON_NUEVO = "draft_content_MARIA_REORDENADO.json"


def main():
    ruta_real = os.path.join(CARPETA_DRAFT_REAL, "draft_content.json")

    if not os.path.exists(ruta_real):
        raise SystemExit(
            f"No se encontro el draft real en: {ruta_real}\n"
            "Revisa que CARPETA_DRAFT_REAL sea la ruta correcta."
        )

    if not os.path.exists(RUTA_JSON_NUEVO):
        raise SystemExit(
            f"No se encontro {RUTA_JSON_NUEVO} en esta carpeta.\n"
            "Corre primero procesar_maria.py."
        )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    ruta_backup = os.path.join(CARPETA_DRAFT_REAL, f"draft_content_BACKUP_{timestamp}.json")

    print(f"Haciendo backup del draft real en:\n  {ruta_backup}")
    shutil.copy2(ruta_real, ruta_backup)

    print(f"Copiando el draft nuevo sobre:\n  {ruta_real}")
    shutil.copy2(RUTA_JSON_NUEVO, ruta_real)

    print()
    print("Listo. El draft real fue actualizado.")
    print(f"Si algo sale mal, el original esta a salvo en: {ruta_backup}")
    print("Abri CapCut y revisa el resultado.")


if __name__ == "__main__":
    main()
