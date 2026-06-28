# Receta: Limpiar tracks de subtítulos de una corrida anterior

## Cuándo usar esta receta

Antes de volver a generar subtítulos karaoke sobre un draft que **ya**
tiene tracks `AUTO_sub_*` de una corrida anterior (por ejemplo: se
corrigió algo en `subtitle_engine.py` y se quiere regenerar con el fix
aplicado, o el resultado anterior quedó mal posicionado).

**Si no se limpia primero**, el script de generación no borra nada por su
cuenta — los tracks viejos quedan mezclados visualmente con los nuevos en
CapCut, dando la sensación de un bug de posicionamiento que en realidad es
solo texto duplicado superpuesto.

## Comando

```powershell
python limpiar_tracks_subtitulos.py "nombre del draft"
```

El nombre va exactamente como aparece la carpeta en CapCut (con espacios,
mayúsculas, etc., entre comillas). Sin argumento, el script lista los
drafts disponibles para copiar el nombre exacto.

## Qué hace

1. Busca, dentro de TODOS los tracks de texto del draft, los que tengan
   `name` empezando con `AUTO_sub_` (el prefijo real, distinto del
   `AUTO_pos_N` que usaba el sistema viejo de "entrv fede baic" — por eso
   hizo falta este script nuevo, `core/cleaner.py` no conocía este
   prefijo).
2. Antes de borrar, hace un **backup** del draft completo con timestamp,
   en la misma carpeta del proyecto
   (`draft_content_BACKUP_AAAAMMDD_HHMMSS.json`).
3. Borra esos tracks Y los materiales de texto que referenciaban (para no
   dejar basura huérfana en `materials.texts`).
4. **No toca** el auto-caption original (el track de texto SIN ese
   prefijo) — ese sigue siendo necesario como fuente de datos para volver
   a generar.

## Verificación

El script imprime cuántos tracks/segmentos/materiales borró. Para
confirmar manualmente:

```powershell
copy "C:\Users\<usuario>\AppData\Local\CapCut\User Data\Projects\<nombre_draft>\draft_content.json" "$env:USERPROFILE\Desktop\verificar_limpio.json"
```

Y chequear que solo queden: el track de video, y el track de texto del
auto-caption original (sin prefijo `AUTO_sub_`).

## Ejemplo real (clip1_serge, sesión de referencia)

```
Se van a borrar 5 tracks:
  - 'AUTO_sub_0' (49 segmentos)
  - 'AUTO_sub_1' (44 segmentos)
  - 'AUTO_sub_2' (38 segmentos)
  - 'AUTO_sub_3' (36 segmentos)
  - 'AUTO_sub_4' (21 segmentos)
Total de segmentos de texto a eliminar: 188

Backup guardado en: .../draft_content_BACKUP_20260625_150735.json

Listo. Se borraron 5 tracks, 188 segmentos y 188 materiales de texto huerfanos.
```

## Nota para quien quiera fusionar esto en `core/cleaner.py`

Esta funcionalidad hoy vive como script suelto en la raíz del repo,
duplicando responsabilidad con `core/cleaner.py` (que limpia el prefijo
viejo `AUTO_pos_N`). Lo ideal a futuro es agregar un método
`limpiar_tracks_subtitulos_karaoke()` dentro de `Cleaner` y que este script
quede como wrapper de 2-3 líneas. Ver `docs/cookbook/notas_y_gotchas.md`,
sección "Deuda técnica conocida".
