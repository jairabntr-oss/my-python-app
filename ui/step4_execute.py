"""
Paso 4: Ejecución del pipeline completo.
"""

import json
import threading
from pathlib import Path
import customtkinter as ctk
from config import COLORS, settings as app_settings


class Step4Frame(ctk.CTkFrame):
    """Pantalla de ejecución del pipeline."""

    def __init__(self, parent, main_window):
        super().__init__(parent, corner_radius=10)
        self.main_window = main_window
        self.grid_columnconfigure(0, weight=1)

        # ── Título ─────────────────────────────────────────────────────────────
        ctk.CTkLabel(
            self,
            text="Paso 4: Generar",
            font=ctk.CTkFont(size=18, weight="bold"),
        ).grid(row=0, column=0, padx=20, pady=(20, 10), sticky="w")

        # ── Aviso de seguridad ────────────────────────────────────────────────
        aviso = ctk.CTkFrame(self, fg_color=("#FFF3E0", "#3E2000"), corner_radius=8)
        aviso.grid(row=1, column=0, padx=20, pady=(0, 10), sticky="ew")
        ctk.CTkLabel(
            aviso,
            text="⚠️  Asegurate de que CapCut esté CERRADO antes de generar.\n"
                 "   El sistema modificará el archivo draft_content.json directamente.",
            justify="left", anchor="w",
        ).grid(row=0, column=0, padx=10, pady=8, sticky="w")

        # ── Resumen de configuración ──────────────────────────────────────────
        self.resumen_label = ctk.CTkLabel(
            self, text="Cargando configuración…", justify="left", anchor="w"
        )
        self.resumen_label.grid(row=2, column=0, padx=20, pady=5, sticky="w")

        # ── Barra de progreso ─────────────────────────────────────────────────
        self.progress = ctk.CTkProgressBar(self)
        self.progress.grid(row=3, column=0, padx=20, pady=5, sticky="ew")
        self.progress.set(0)

        # ── Log de salida ─────────────────────────────────────────────────────
        self.log_box = ctk.CTkTextbox(self, height=180, state="disabled")
        self.log_box.grid(row=4, column=0, padx=20, pady=10, sticky="ew")

        # ── Botones ───────────────────────────────────────────────────────────
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=5, column=0, padx=20, pady=20, sticky="ew")
        btn_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkButton(
            btn_frame, text="← Atrás", fg_color="transparent",
            command=lambda: self.main_window.show_frame("step3"),
        ).grid(row=0, column=0, sticky="w")

        self.run_btn = ctk.CTkButton(
            btn_frame, text="▶ Generar",
            fg_color=COLORS["success"],
            command=self._ejecutar,
        )
        self.run_btn.grid(row=0, column=2, sticky="e")

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def tkraise(self, aboveThis=None):
        """Al mostrar el frame, actualizar el resumen con la config actual."""
        super().tkraise(aboveThis)
        self._actualizar_resumen()

    # ── Acciones ──────────────────────────────────────────────────────────────

    def _actualizar_resumen(self):
        result = getattr(self.main_window, "analysis_result", None)
        if not result:
            self.resumen_label.configure(text="ℹ️ Volvé al Paso 1 para analizar un proyecto.")
            return

        ruta_sonido = getattr(self.main_window, "ruta_sonido", None)
        modo_clicks = getattr(self.main_window, "modo_clicks", "2_por_oracion")

        texto  = f"📋 Proyecto: {Path(self.main_window.draft_path.get()).parent.name}\n"
        texto += f"   Oraciones a procesar: {result.get('cantidad_oraciones_procesables', 0)}\n"
        texto += f"   Palabras a procesar: {result.get('cantidad_palabras_procesables', 0)}\n"
        texto += f"   Clicks: {'SÍ - ' + modo_clicks if ruta_sonido else 'NO'}\n"
        if ruta_sonido:
            texto += f"   Archivo de click: {Path(ruta_sonido).name}\n"

        self.resumen_label.configure(text=texto)

    def _log(self, mensaje: str):
        """Agrega un mensaje al cuadro de log (thread-safe)."""
        self.log_box.configure(state="normal")
        self.log_box.insert("end", mensaje + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _ejecutar(self):
        """Ejecuta el pipeline en un thread separado para no bloquear la UI."""
        result = getattr(self.main_window, "analysis_result", None)
        if not result:
            self._log("❌ No hay análisis disponible. Volvé al Paso 1.")
            return

        oraciones = result.get("oraciones_auto_sin_editar", [])
        if not oraciones:
            self._log("❌ No hay oraciones procesables.")
            return

        self.run_btn.configure(state="disabled", text="Procesando…")
        self.progress.set(0.1)

        thread = threading.Thread(target=self._pipeline, args=(oraciones,), daemon=True)
        thread.start()

    def _pipeline(self, oraciones):
        """Pipeline real (corre en thread separado)."""
        try:
            from services.draft_service import DraftService

            draft_path = Path(self.main_window.draft_path.get())
            draft_name = draft_path.parent.name
            draft_folder = str(draft_path.parent.parent)

            # Cargar perfil
            profile = getattr(self.main_window, "style_profile", None)
            if not profile:
                profile = app_settings.get("subtitle_style", {})

            ruta_sonido = getattr(self.main_window, "ruta_sonido", None)
            modo = getattr(self.main_window, "modo_clicks", "2_por_oracion")

            self.after(0, self._log, f"🚀 Iniciando generación para: {draft_name}")
            self.after(0, lambda: self.progress.set(0.3))

            service = DraftService(draft_folder, profile)
            es_valido, msg = service.validar_datos_entrada(oraciones)
            if not es_valido:
                self.after(0, self._log, f"❌ Datos inválidos: {msg}")
                self.after(0, self._finalizar, False)
                return

            self.after(0, self._log, f"   Oraciones: {len(oraciones)}")
            self.after(0, lambda: self.progress.set(0.5))

            resultado = service.generar_completo(draft_name, oraciones, ruta_sonido, modo_clicks=modo)

            self.after(0, lambda: self.progress.set(1.0))

            if resultado.get("success"):
                summary = resultado.get("summary", {})
                self.after(0, self._log, resultado.get("status", ""))
                self.after(0, self._log,
                    f"   Palabras generadas: {summary.get('total_palabras_generadas', 0)}\n"
                    f"   Bloques: {summary.get('total_bloques', 0)}\n"
                    f"   Tracks texto limpiados: {summary.get('tracks_limpiados_texto', 0)}\n"
                    f"   Tracks audio limpiados: {summary.get('tracks_limpiados_audio', 0)}"
                )
                if resultado.get("clicks"):
                    cl = resultado["clicks"]
                    if cl.get("success"):
                        self.after(0, self._log, f"   Clicks insertados: {cl.get('total_clicks', 0)}")
                    else:
                        self.after(0, self._log, f"⚠️  Clicks: {cl.get('error', '')}")
                self.after(0, self._log, "💡 Abrí CapCut para ver los subtítulos.")
                self.after(0, self._finalizar, True)
            else:
                self.after(0, self._log, resultado.get("status", "❌ Error desconocido"))
                self.after(0, self._finalizar, False)

        except Exception as e:
            self.after(0, self._log, f"❌ Error fatal: {e}")
            self.after(0, self._finalizar, False)

    def _finalizar(self, exitoso: bool):
        self.run_btn.configure(state="normal", text="▶ Generar")
        if not exitoso:
            self.progress.set(0)