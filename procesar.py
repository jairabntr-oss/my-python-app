#!/usr/bin/env python3
"""
procesar.py - CLI generico para procesar drafts de CapCut.

Reemplaza a todos los scripts por-proyecto (generar_arrizzo8.py,
procesar_maria.py, agregar_clicks_clip1_serge.py, etc.) con un solo
punto de entrada que usa el core/ del repo.

Uso:
    python procesar.py listar
    python procesar.py inspeccionar --draft "entrv senores"
    python procesar.py subtitulos   --draft "entrv senores" [--dry-run]
    python procesar.py clicks       --draft "entrv senores" [--dry-run] [--modo 2|3]
    python procesar.py limpiar      --draft "entrv senores" [--dry-run]
    python procesar.py full         --draft "entrv senores" [--dry-run]

Reglas que este script hace cumplir SIEMPRE (lecciones del handoff):
  - Backup automatico del draft_content.json antes de cualquier escritura
    (Error #2: el auto-caption original se perdio sin backup).
  - Limpieza de tracks AUTO_ antes de regenerar (Error #3: texto duplicado).
  - Aviso explicito de cerrar CapCut antes de escribir.
  - --dry-run para simular sin tocar el draft.
"""

import argparse
import sys
from pathlib import Path

from config import PATHS
from core.capcut_engine import CapcutEngine
from core.cleaner import Cleaner
from core.click_engine import ClickEngine
from core.draft_manager import DraftManager
from core.logger import logger


SONIDO_CLICK_DEFAULT = PATHS["assets"] / "click_sonido.mp3"


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _ruta_draft_json(engine: CapcutEngine, nombre: str) -> Path:
    """Ruta al draft_content.json real del proyecto en CapCut."""
    return engine.get_drafts_folder() / nombre / "draft_content.json"


def _verificar_draft_existe(engine: CapcutEngine, nombre: str) -> Path:
    ruta = _ruta_draft_json(engine, nombre)
    if not ruta.is_file():
        disponibles = engine.list_projects()
        print(f"[X] No existe el draft '{nombre}' en {engine.get_drafts_folder()}")
        if disponibles:
            print("    Drafts disponibles:")
            for d in disponibles:
                print(f"      - {d}")
        sys.exit(1)
    return ruta


def _backup(ruta_json: Path) -> Path:
    """Backup obligatorio antes de escribir. Aborta si falla."""
    manager = DraftManager(ruta_json)
    backup = manager.create_backup()
    print(f"[OK] Backup creado: {backup}")
    return backup


def _aviso_capcut():
    print("[!] Asegurate de que CapCut este COMPLETAMENTE CERRADO antes de continuar.")
    print("    (Si esta abierto, va a pisar los cambios al cerrarse.)")


# ─── Acciones ────────────────────────────────────────────────────────────────

def accion_listar(_args) -> int:
    engine = CapcutEngine()
    proyectos = engine.list_projects()
    if not proyectos:
        print("No se encontraron drafts (o pycapcut no esta instalado).")
        return 1
    print(f"Drafts en {engine.get_drafts_folder()}:")
    for p in proyectos:
        print(f"  - {p}")
    return 0


def accion_inspeccionar(args) -> int:
    engine = CapcutEngine()
    ruta = _verificar_draft_existe(engine, args.draft)

    manager = DraftManager(ruta)
    manager.load()
    info = manager.analyze()

    print()
    print("=" * 62)
    print(f"INSPECCION: {args.draft}")
    print("=" * 62)
    print(f"Duracion:                  {info['duracion_video_seg']:.1f}s")
    print(f"Segmentos de texto:        {info['total_segmentos_texto']}")
    print(f"Segmentos de audio:        {info['total_segmentos_audio']}")
    print(f"Oraciones procesables:     {info['cantidad_oraciones_procesables']} "
          f"({info['cantidad_palabras_procesables']} palabras)")
    print(f"Oraciones ya estiladas:    {info['cantidad_oraciones_ya_estiladas']}")
    print(f"Textos manuales:           {info['cantidad_textos_manuales']}")
    print(f"Tracks residuales (texto): {info['tracks_residuales_texto']}")
    print(f"Tracks residuales (audio): {info['tracks_residuales_audio']}")

    oraciones = info["oraciones_auto_sin_editar"]
    if oraciones:
        primera = " ".join(w["word"] for w in oraciones[0][:8])
        ultima = " ".join(w["word"] for w in oraciones[-1][:8])
        print(f"Primera oracion:           \"{primera}...\"")
        print(f"Ultima oracion:            \"{ultima}...\"")
    else:
        print()
        print("[!] No hay auto-caption sin editar para procesar en este draft.")
        print("    Posibles causas: ya lo procesaste, o el auto-caption se")
        print("    edito/borro. Si lo procesaste antes, restaura un backup.")
    print("=" * 62)
    return 0


def accion_limpiar(args) -> int:
    engine = CapcutEngine()
    ruta = _verificar_draft_existe(engine, args.draft)

    if args.dry_run:
        manager = DraftManager(ruta)
        manager.load()
        info = manager.analyze()
        print(f"[DRY RUN] Se eliminarian {info['tracks_residuales_texto']} tracks "
              f"AUTO_ de texto y {info['tracks_residuales_audio']} de audio.")
        return 0

    _aviso_capcut()
    _backup(ruta)

    script = engine.load_project(args.draft)
    if script is None:
        return 1

    cleaner = Cleaner(script)
    resultado = cleaner.limpiar_todos()
    script.save()

    print(f"[OK] Limpieza: {resultado['texto']} tracks de texto y "
          f"{resultado['audio']} de audio eliminados.")
    return 0


def accion_subtitulos(args, ya_backupeado: bool = False) -> int:
    engine = CapcutEngine()
    ruta = _verificar_draft_existe(engine, args.draft)

    if not args.dry_run and not ya_backupeado:
        _aviso_capcut()
        _backup(ruta)

    resultado = engine.generate_subtitles_for_project(
        args.draft, dry_run=args.dry_run
    )

    if "error" in resultado:
        print(f"[X] Error generando subtitulos: {resultado['error']}")
        return 1

    prefijo = "[DRY RUN] Se generarian" if args.dry_run else "[OK] Subtitulos generados:"
    print(f"{prefijo} {resultado['total_words']} palabras en "
          f"{resultado['total_blocks']} bloques "
          f"({resultado['simultaneous_dialogs']} dialogos simultaneos) "
          f"-> track '{resultado['track_created']}'")
    return 0


def accion_clicks(args, ya_backupeado: bool = False) -> int:
    engine = CapcutEngine()
    ruta = _verificar_draft_existe(engine, args.draft)

    sonido = Path(args.sonido) if args.sonido else SONIDO_CLICK_DEFAULT
    if not sonido.is_file():
        print(f"[X] No se encontro el sonido de click: {sonido}")
        return 1

    oraciones = engine.extract_captions_from_draft(args.draft)
    if not oraciones:
        print("[X] No hay oraciones de auto-caption para sincronizar clicks.")
        return 1

    modo = "2_por_oracion" if args.modo == "2" else "3_por_oracion"

    if args.dry_run:
        n = len(oraciones)
        clicks_estimados = n * (2 if args.modo == "2" else 3)
        print(f"[DRY RUN] Se insertarian ~{clicks_estimados} clicks "
              f"({modo}) sobre {n} oraciones, sonido: {sonido.name}")
        return 0

    if not ya_backupeado:
        _aviso_capcut()
        _backup(ruta)

    script = engine.load_project(args.draft)
    if script is None:
        return 1

    # Evitar duplicados si ya existe el track (mismo criterio que el
    # script original agregar_clicks_baic.py)
    for track in script.imported_tracks:
        if getattr(track, "name", "") == ClickEngine.TRACK_NAME:
            print(f"[X] Ya existe un track '{ClickEngine.TRACK_NAME}' en este draft.")
            print("    Corre primero: python procesar.py limpiar --draft "
                  f"\"{args.draft}\"")
            return 1

    click_engine = ClickEngine(script, str(sonido))
    resultado = click_engine.generate(oraciones, modo=modo)

    print(f"[OK] {resultado['total_clicks']} clicks insertados "
          f"({resultado['modo']}) -> track '{resultado['track_name']}'")
    return 0


def accion_cortes(args) -> int:
    """Sugiere puntos de corte: silencios largos + cambios de escena,
    cruzados con las oraciones del auto-caption para no cortar frases."""
    from utils.analisis_video import (
        ffmpeg_disponible, video_desde_draft,
        detectar_silencios, detectar_cambios_escena, clasificar_silencios,
    )

    if not ffmpeg_disponible():
        print("[X] ffmpeg no esta instalado o no esta en el PATH.")
        print("    Instalalo con:  winget install Gyan.FFmpeg")
        print("    y despues CERRA y reabri esta consola.")
        return 1

    engine = CapcutEngine()
    ruta = _verificar_draft_existe(engine, args.draft)

    video = Path(args.video) if args.video else video_desde_draft(ruta)
    if video is None or not video.is_file():
        print("[X] No pude encontrar el archivo de video del draft.")
        print("    Pasalo a mano con:  --video \"C:\\ruta\\al\\video.mp4\"")
        return 1
    print(f"Video: {video}")

    print("Analizando audio (silencios)...")
    silencios = detectar_silencios(
        video, umbral_db=args.umbral_db, min_duracion_seg=args.min_silencio
    )
    print("Analizando video (cambios de escena)...")
    escenas = detectar_cambios_escena(video)

    # Cruzar con oraciones del auto-caption para clasificar seguridad
    oraciones = engine.extract_captions_from_draft(args.draft) or []
    silencios = clasificar_silencios(silencios, oraciones)

    def fmt(seg: float) -> str:
        m, s = divmod(seg, 60)
        return f"{int(m):02d}:{s:05.2f}"

    print()
    print("=" * 62)
    print(f"SUGERENCIAS DE CORTE: {args.draft}")
    print("=" * 62)

    seguros = [s for s in silencios if s["seguro"]]
    riesgosos = [s for s in silencios if not s["seguro"]]

    print(f"\nSILENCIOS SEGUROS para cortar ({len(seguros)}) - caen entre frases:")
    for s in seguros:
        print(f"  {fmt(s['inicio'])} -> {fmt(s['fin'])}  ({s['duracion']:.1f}s de aire)")
    if not seguros:
        print("  (ninguno)")

    print(f"\nSILENCIOS RIESGOSOS ({len(riesgosos)}) - pisan una frase, revisar a oido:")
    for s in riesgosos:
        print(f"  {fmt(s['inicio'])} -> {fmt(s['fin'])}  ({s['duracion']:.1f}s)")
    if not riesgosos:
        print("  (ninguno)")

    print(f"\nCAMBIOS DE ESCENA ({len(escenas)}) - puntos de corte visualmente naturales:")
    for t in escenas[:30]:
        print(f"  {fmt(t)}")
    if len(escenas) > 30:
        print(f"  ... y {len(escenas) - 30} mas")
    if not escenas:
        print("  (ninguno)")

    total_aire = sum(s["duracion"] for s in seguros)
    print(f"\nSi cortas todos los silencios seguros, el video se acorta ~{total_aire:.1f}s.")
    print("=" * 62)
    return 0


def accion_full(args) -> int:
    """limpiar -> subtitulos -> clicks, con UN solo backup al inicio."""
    engine = CapcutEngine()
    ruta = _verificar_draft_existe(engine, args.draft)

    if not args.dry_run:
        _aviso_capcut()
        _backup(ruta)

    # 1. Limpiar residuales (sin backup propio: ya lo hicimos)
    if args.dry_run:
        accion_limpiar(args)
    else:
        script = engine.load_project(args.draft)
        if script is None:
            return 1
        resultado = Cleaner(script).limpiar_todos()
        script.save()
        print(f"[OK] Limpieza previa: {resultado['texto']} texto / "
              f"{resultado['audio']} audio")

    # 2. Subtitulos
    rc = accion_subtitulos(args, ya_backupeado=True)
    if rc != 0:
        return rc

    # 3. Clicks
    return accion_clicks(args, ya_backupeado=True)


# ─── Main ────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Procesar drafts de CapCut (subtitulos karaoke + clicks).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Ejemplos:\n"
            "  python procesar.py listar\n"
            "  python procesar.py inspeccionar --draft \"entrv senores\"\n"
            "  python procesar.py full --draft \"entrv senores\" --dry-run\n"
        ),
    )
    sub = parser.add_subparsers(dest="accion", required=True)

    sub.add_parser("listar", help="Lista los drafts disponibles en CapCut")

    def _con_draft(nombre, ayuda, con_dry=True):
        p = sub.add_parser(nombre, help=ayuda)
        p.add_argument("--draft", required=True, help="Nombre exacto del draft")
        if con_dry:
            p.add_argument("--dry-run", action="store_true",
                           help="Simular sin escribir en el draft")
        return p

    _con_draft("inspeccionar", "Muestra que hay en el draft", con_dry=False)
    _con_draft("limpiar", "Elimina tracks AUTO_ residuales")
    _con_draft("subtitulos", "Genera subtitulos karaoke")

    p_clicks = _con_draft("clicks", "Agrega clicks de audio sincronizados")
    p_clicks.add_argument("--modo", choices=["2", "3"], default="2",
                          help="Clicks por oracion (default: 2)")
    p_clicks.add_argument("--sonido", help="Ruta al mp3 del click "
                          f"(default: {SONIDO_CLICK_DEFAULT})")

    p_full = _con_draft("full", "limpiar + subtitulos + clicks")
    p_full.add_argument("--modo", choices=["2", "3"], default="2")
    p_full.add_argument("--sonido", default=None)

    p_cortes = _con_draft("cortes", "Sugiere puntos de corte (ffmpeg, sin IA)",
                          con_dry=False)
    p_cortes.add_argument("--video", help="Ruta al video (default: se busca en el draft)")
    p_cortes.add_argument("--min-silencio", type=float, default=1.0,
                          dest="min_silencio",
                          help="Duracion minima de silencio en seg (default: 1.0)")
    p_cortes.add_argument("--umbral-db", type=int, default=-35, dest="umbral_db",
                          help="Umbral de silencio en dB (default: -35)")

    args = parser.parse_args()

    acciones = {
        "listar": accion_listar,
        "inspeccionar": accion_inspeccionar,
        "limpiar": accion_limpiar,
        "subtitulos": accion_subtitulos,
        "clicks": accion_clicks,
        "full": accion_full,
        "cortes": accion_cortes,
    }

    try:
        return acciones[args.accion](args)
    except KeyboardInterrupt:
        print("\nCancelado.")
        return 130
    except Exception as e:
        logger.error(f"Error en accion '{args.accion}': {e}", exc_info=True)
        print(f"[X] Error inesperado: {e}")
        print("    Detalle completo en logs/app.log")
        return 1


if __name__ == "__main__":
    sys.exit(main())
