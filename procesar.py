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


# --------- Helpers ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

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


# --------- Acciones ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

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
    """Sugiere puntos de corte. Fuente PRINCIPAL: pausas en el habla segun
    los timestamps del auto-caption (inmune al ruido ambiente). Fuentes
    secundarias: silencios de audio y cambios de escena (ffmpeg)."""
    from utils.analisis_video import (
        ffmpeg_disponible, video_desde_draft, detectar_silencios,
        detectar_cambios_escena, clasificar_silencios, detectar_pausas_habla,
    )

    engine = CapcutEngine()
    ruta = _verificar_draft_existe(engine, args.draft)

    def fmt(seg: float) -> str:
        m, s = divmod(seg, 60)
        return f"{int(m):02d}:{s:05.2f}"

    print()
    print("=" * 62)
    print(f"SUGERENCIAS DE CORTE: {args.draft}")
    print("=" * 62)

    # ------ Fuente principal: pausas del habla (transcripcion) ------------------------------------------
    oraciones = engine.extract_captions_from_draft(args.draft) or []
    if oraciones:
        manager = DraftManager(ruta)
        manager.load()
        duracion = manager.analyze()["duracion_video_seg"]

        pausas = detectar_pausas_habla(
            oraciones, min_pausa_seg=args.min_silencio,
            duracion_video_seg=duracion,
        )
        etiquetas = {
            "inicio_video": "aire antes de la 1ra palabra",
            "entre_frases": "nadie habla",
            "fin_video": "aire despues de la ultima palabra",
        }
        print(f"\nPAUSAS EN EL HABLA ({len(pausas)}) - desde la transcripcion,")
        print("inmune al ruido de fondo. Cortes seguros entre frases:")
        for p in pausas:
            print(f"  {fmt(p['inicio'])} -> {fmt(p['fin'])}  "
                  f"({p['duracion']:.1f}s, {etiquetas[p['tipo']]})")
        if not pausas:
            print(f"  (ninguna pausa >= {args.min_silencio}s - habla continua)")
        total = sum(p["duracion"] for p in pausas)
        print(f"  Total recortable: ~{total:.1f}s")
    else:
        print("\n[!] Este draft no tiene auto-caption sin editar, asi que no")
        print("    puedo detectar pausas desde la transcripcion. Corre el")
        print("    auto-caption de CapCut primero (o restaura un backup).")

    # ------ Fuentes secundarias: ffmpeg (opcional) ------------------------------------------------------------------------------
    if args.solo_habla:
        print("=" * 62)
        return 0

    if not ffmpeg_disponible():
        print("\n(ffmpeg no instalado: salteo silencios de audio y escenas.")
        print(" Instalalo con: winget install Gyan.FFmpeg)")
        print("=" * 62)
        return 0

    video = Path(args.video) if args.video else video_desde_draft(ruta)
    if video is None or not video.is_file():
        print("\n(No encontre el video del draft: salteo analisis de audio/")
        print(" escenas. Pasalo con --video si lo queres.)")
        print("=" * 62)
        return 0

    print(f"\nVideo: {video}")
    print("Analizando audio y escenas con ffmpeg...")
    silencios = clasificar_silencios(
        detectar_silencios(video, umbral_db=args.umbral_db,
                           min_duracion_seg=args.min_silencio),
        oraciones,
    )
    escenas = detectar_cambios_escena(video)

    seguros = [s for s in silencios if s["seguro"]]
    print(f"\nSILENCIOS DE AUDIO ({len(silencios)}, {len(seguros)} seguros) - "
          f"puede dar 0 con ruido ambiente:")
    for s in silencios:
        marca = "seguro" if s["seguro"] else "RIESGOSO"
        print(f"  {fmt(s['inicio'])} -> {fmt(s['fin'])}  "
              f"({s['duracion']:.1f}s, {marca})")
    if not silencios:
        print("  (ninguno - normal en ambientes ruidosos; usa las pausas de arriba)")

    print(f"\nCAMBIOS DE ESCENA ({len(escenas)}):")
    for t in escenas[:30]:
        print(f"  {fmt(t)}")
    if not escenas:
        print("  (ninguno - normal si es una sola toma continua)")

    print("=" * 62)
    return 0


def accion_acelerar(args) -> int:
    """Corta las pausas del habla y las ACELERA (speed ramp) en vez de
    eliminarlas. Por defecto, la velocidad de cada pausa depende de la
    frase que la precede: frases largas/densas se aceleran MENOS (dan
    tiempo a asimilar), frases cortas/relleno se aceleran MAS.
    EXPERIMENTAL: probar primero en una COPIA del draft y con --dry-run."""
    from utils.analisis_video import detectar_pausas_habla
    from core.velocidad import AceleradorPausas, calcular_velocidad_por_importancia

    engine = CapcutEngine()
    ruta = _verificar_draft_existe(engine, args.draft)

    oraciones = engine.extract_captions_from_draft(args.draft) or []
    if not oraciones:
        print("[X] Este draft no tiene auto-caption sin editar: no puedo")
        print("    ubicar las pausas del habla.")
        return 1

    manager = DraftManager(ruta)
    manager.load()
    duracion = manager.analyze()["duracion_video_seg"]

    pausas = detectar_pausas_habla(
        oraciones, min_pausa_seg=args.min_silencio,
        duracion_video_seg=duracion,
    )
    if not args.extremos:
        pausas = [p for p in pausas if p["tipo"] == "entre_frases"]

    if not pausas:
        print(f"No hay pausas >= {args.min_silencio}s para acelerar.")
        return 0

    if args.uniforme:
        pausas = [{**p, "velocidad": args.velocidad} for p in pausas]
    else:
        pausas = calcular_velocidad_por_importancia(
            pausas, oraciones, args.velocidad_min, args.velocidad_max)

    def fmt(seg: float) -> str:
        m, s = divmod(seg, 60)
        return f"{int(m):02d}:{s:05.2f}"

    ahorro_teorico = sum(p["duracion"] - p["duracion"] / p["velocidad"]
                        for p in pausas)
    modo = f"uniforme {args.velocidad:g}x" if args.uniforme else \
           f"variable {args.velocidad_min:g}x-{args.velocidad_max:g}x segun frase previa"
    print(f"Pausas a acelerar ({modo}): {len(pausas)} "
          f"(ahorro estimado ~{ahorro_teorico:.1f}s)")
    for p in pausas:
        detalle = (f", frase previa: {p['palabras_frase_previa']} palabras"
                  if "palabras_frase_previa" in p else "")
        print(f"  {fmt(p['inicio'])} -> {fmt(p['fin'])}  "
              f"({p['duracion']:.1f}s -> {p['duracion']/p['velocidad']:.1f}s "
              f"@ {p['velocidad']:g}x{detalle})")

    if args.dry_run:
        print("[DRY RUN] No se escribio nada.")
        return 0

    _aviso_capcut()
    _backup(ruta)

    acelerador = AceleradorPausas(ruta)
    resultado = acelerador.acelerar_pausas(pausas, forzar=args.forzar)

    for s in resultado["saltadas"]:
        print(f"  [!] Saltada {fmt(s['inicio'])}-{fmt(s['fin'])}: {s['motivo']}")

    if resultado["aplicadas"] == 0:
        print("[X] No se aplico ninguna pausa. El draft NO se modifico.")
        return 1

    acelerador.guardar()
    print(f"[OK] {resultado['aplicadas']} pausas aceleradas, video "
          f"~{resultado['ahorro_seg']:.1f}s mas corto.")
    print("    Abri CapCut y revisa la timeline ANTES de seguir editando.")
    print("    Si algo se ve mal, restaura el backup de arriba.")
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


# --------- Main ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

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
    p_cortes.add_argument("--solo-habla", action="store_true", dest="solo_habla",
                          help="Solo pausas desde transcripcion (rapido, sin ffmpeg)")

    p_acel = _con_draft("acelerar",
                        "Acelera las pausas del habla (speed ramp) [EXPERIMENTAL]")
    p_acel.add_argument("--velocidad-min", type=float, default=2.0,
                        dest="velocidad_min",
                        help="Velocidad para pausas tras frases densas (default: 2.0)")
    p_acel.add_argument("--velocidad-max", type=float, default=8.0,
                        dest="velocidad_max",
                        help="Velocidad para pausas tras frases cortas (default: 8.0)")
    p_acel.add_argument("--uniforme", action="store_true",
                        help="Usar UNA sola velocidad para todas las pausas "
                             "(ignora la frase previa)")
    p_acel.add_argument("--velocidad", type=float, default=4.0,
                        help="Velocidad fija, solo con --uniforme (default: 4.0)")
    p_acel.add_argument("--min-silencio", type=float, default=1.0,
                        dest="min_silencio",
                        help="Duracion minima de pausa en seg (default: 1.0)")
    p_acel.add_argument("--extremos", action="store_true",
                        help="Incluir tambien el aire inicial/final del video")
    p_acel.add_argument("--forzar", action="store_true",
                        help="No abortar si otro track atraviesa una pausa")

    args = parser.parse_args()

    acciones = {
        "listar": accion_listar,
        "inspeccionar": accion_inspeccionar,
        "limpiar": accion_limpiar,
        "subtitulos": accion_subtitulos,
        "clicks": accion_clicks,
        "full": accion_full,
        "cortes": accion_cortes,
        "acelerar": accion_acelerar,
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
