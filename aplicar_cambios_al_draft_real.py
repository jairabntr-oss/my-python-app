# =====================================================================
# Script auxiliar: aplica draft_content_NUEVO.json al draft REAL de
# CapCut, haciendo backup del original antes de tocar nada.
# =====================================================================
# COMO USARLO:
#   1. Cerra CapCut por completo.
#   2. Corre primero recortar_entrv_fede_baic.py (con
#      RUTA_JSON_ORIGINAL apuntando a una copia fresca de tu
#      draft_content.json real) - eso genera draft_content_NUEVO.json
#      en la misma carpeta donde corras el script.
#   3. Revisa el resultado (podes abrir draft_content_NUEVO.json en un
#      editor de texto, o simplemente confiar en las verificaciones que
#      ya se hicieron).
#   4. Corre ESTE script. Va a:
#        a) Hacer una copia de seguridad del draft_content.json REAL,
#           con fecha y hora en el nombre, en la misma carpeta del
#           proyecto (asi nunca se pierde el original).
#        b) Copiar draft_content_NUEVO.json reemplazando al real.
#   5. Recien ahi, abri CapCut y revisa el resultado.
#
# Si algo se ve mal en CapCut, podes restaurar el backup manualmente
# (renombrar el archivo de backup de vuelta a "draft_content.json").
# =====================================================================

import os
import shutil
from datetime import datetime

# =====================================================================
# CONFIGURACION - AJUSTAR ESTAS DOS RUTAS ANTES DE CORRER
# =====================================================================

CARPETA_DRAFT_REAL = r"C:\Users\user2\AppData\Local\CapCut\User Data\Projects\com.lveditor.draft\entrv fede baic"
RUTA_JSON_NUEVO = "draft_content_V3_NUEVO.json"  # el que genero corregir_v3.py


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
            "Corre primero recortar_entrv_fede_baic.py."
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
