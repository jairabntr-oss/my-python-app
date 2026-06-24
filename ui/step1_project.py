import os
from tkinter import filedialog

import customtkinter as ctk

from core.draft_manager import DraftManager
from ui.components.buttons import AnalyzeButton, StyledButton
from config import COLORS, settings as app_settings
from utils.capcut_projects import listar_proyectos
from utils.mensajes import interpretar_analisis, interpretar_error
from utils.diagnostico import diagnosticar_draft


class Step1Frame(ctk.CTkFrame):
    def __init__(self, parent, main_window):
        super().__init__(parent, corner_radius=10)
        self.main_window = main_window
        self.grid_columnconfigure(0, weight=1)

        self._proyectos = []  # lista de CapcutProject del ultimo refresh

        ctk.CTkLabel(
            self, text="Paso 1: Elegí tu proyecto de CapCut",
            font=ctk.CTkFont(size=18, weight="bold"),
        ).grid(row=0, column=0, padx=20, pady=(20, 10), sticky="w")

        # Selector de proyecto (dropdown)
        selector_frame = ctk.CTkFrame(self, fg_color="transparent")
        selector_frame.grid(row=1, column=0, padx=20, pady=5, sticky="ew")
        selector_frame.grid_columnconfigure(0, weight=1)

        self.project_menu = ctk.CTkOptionMenu(
            selector_frame,
            values=["(presiona Actualizar para listar)"],
            command=self._on_project_selected,
        )
        self.project_menu.grid(row=0, column=0, padx=(0, 10), sticky="ew")

        StyledButton(
            selector_frame, text="🔄 Actualizar", width=120,
            command=self.refrescar_proyectos, style="secondary",
        ).grid(row=0, column=1)

        StyledButton(
            selector_frame, text="Examinar…", width=100,
            command=self.browse_file, style="secondary",
        ).grid(row=0, column=2, padx=(10, 0))

        self.ruta_label = ctk.CTkLabel(
            self, text="", justify="left", anchor="w",
            font=ctk.CTkFont(size=11), text_color=("gray40", "gray60"),
        )
        self.ruta_label.grid(row=2, column=0, padx=20, pady=(0, 5), sticky="w")

        self.progress = ctk.CTkProgressBar(self)
        self.progress.grid(row=3, column=0, padx=20, sticky="ew")
        self.progress.set(0)

        # Panel de resultado / instrucciones
        info_frame = ctk.CTkFrame(self, fg_color=("#F0F0F0", "#2A2A2A"), corner_radius=8)
        info_frame.grid(row=4, column=0, padx=20, pady=15, sticky="ew")
        info_frame.grid_columnconfigure(0, weight=1)

        self.analysis_label = ctk.CTkLabel(
            info_frame,
            text="Elegí un proyecto de la lista y presioná 'Analizar'.",
            justify="left", anchor="w",
        )
        self.analysis_label.grid(row=0, column=0, sticky="w", padx=12, pady=12)

        # Botones de accion
        actions_frame = ctk.CTkFrame(self, fg_color="transparent")
        actions_frame.grid(row=5, column=0, padx=20, pady=10, sticky="ew")
        actions_frame.grid_columnconfigure(1, weight=1)

        self.analyze_btn = AnalyzeButton(actions_frame, command=self.analyze_draft)
        self.analyze_btn.grid(row=0, column=1, sticky="e", padx=(0, 10))
        StyledButton(
            actions_frame, text="🔍 Diagnosticar", style="secondary",
            command=self.diagnosticar,
        ).grid(row=0, column=2, sticky="e", padx=(0, 10))
        self.next_btn = StyledButton(
            actions_frame, text="Siguiente →",
            command=lambda: self.main_window.show_frame("step2"),
            style="success", state="disabled",
        )
        self.next_btn.grid(row=0, column=3, sticky="e")

        self.after(200, self.refrescar_proyectos)

    # Listado de proyectos

    def refrescar_proyectos(self):
        ruta_manual = (
            app_settings.get("capcut", {})
            .get("default_projects_path", "")
            .replace("{USER}", os.environ.get("USERNAME", os.path.expanduser("~")))
        )
        proyectos = listar_proyectos(ruta_manual=ruta_manual or None)
        self._proyectos = proyectos

        if not proyectos:
            self.project_menu.configure(values=["(no se encontraron proyectos de CapCut)"])
            self.project_menu.set("(no se encontraron proyectos de CapCut)")
            self.ruta_label.configure(
                text="No se detecto la carpeta de CapCut automaticamente.\n"
                     "Usa 'Examinar…' para elegir el draft_content.json a mano."
            )
            return

        etiquetas = [f"{p.name}   ({p.modified_human})" for p in proyectos]
        self.project_menu.configure(values=etiquetas)
        self.project_menu.set(etiquetas[0])
        self._on_project_selected(etiquetas[0])

    def _on_project_selected(self, etiqueta):
        idx = None
        for i, p in enumerate(self._proyectos):
            if etiqueta.startswith(p.name + "   ("):
                idx = i
                break
        if idx is None:
            return
        proyecto = self._proyectos[idx]
        self.main_window.draft_path.set(str(proyecto.draft_json))
        self.ruta_label.configure(text=f"📁 {proyecto.draft_json}")
        self.next_btn.configure(state="disabled")
        self.analysis_label.configure(text="Proyecto elegido. Presioná 'Analizar'.")

    def browse_file(self):
        initial_dir = os.path.expanduser("~")
        file_path = filedialog.askopenfilename(
            title="Seleccionar draft_content.json",
            initialdir=initial_dir,
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if file_path:
            self.main_window.draft_path.set(file_path)
            self.ruta_label.configure(text=f"📁 {file_path}")
            self.analysis_label.configure(text="Archivo elegido. Presioná 'Analizar'.")
            self.next_btn.configure(state="disabled")

    # Analisis

    def diagnosticar(self):
        """Corre el diagnostico de solo lectura sobre el draft elegido y
        muestra el reporte en una ventana aparte. No modifica nada."""
        file_path = self.main_window.draft_path.get()
        if not file_path:
            self.analysis_label.configure(
                text="❌ Primero elegí un proyecto para diagnosticar."
            )
            return

        reporte = diagnosticar_draft(file_path)

        ventana = ctk.CTkToplevel(self)
        ventana.title("Diagnóstico del proyecto")
        ventana.geometry("640x520")
        ventana.grid_columnconfigure(0, weight=1)
        ventana.grid_rowconfigure(0, weight=1)

        caja = ctk.CTkTextbox(ventana, wrap="word")
        caja.grid(row=0, column=0, sticky="nsew", padx=15, pady=15)
        caja.insert("1.0", reporte)
        caja.configure(state="disabled")

        StyledButton(
            ventana, text="Cerrar", style="secondary",
            command=ventana.destroy,
        ).grid(row=1, column=0, pady=(0, 15))

        # Traer al frente
        ventana.transient(self.winfo_toplevel())
        ventana.after(100, ventana.lift)

    def analyze_draft(self):
        file_path = self.main_window.draft_path.get()
        if not file_path:
            self.analysis_label.configure(
                text="❌ Primero elegí un proyecto de la lista (o usá 'Examinar…')."
            )
            return

        self.analyze_btn.configure(state="disabled", text="Analizando…")
        self.progress.set(0.2)
        self.update_idletasks()

        try:
            manager = DraftManager(file_path)
            manager.analyze_async(
                callback=lambda error, result: self.after(
                    0, lambda: self.on_analysis_complete(error, result)
                )
            )
        except Exception as e:
            self.on_analysis_complete(e, None)

    def on_analysis_complete(self, error, result):
        self.progress.set(1.0)

        if error:
            diag = interpretar_error(error)
            self._mostrar_diagnostico(diag)
            self.next_btn.configure(state="disabled")
        else:
            self.main_window.analysis_result = result
            diag = interpretar_analisis(result)

            cab = (
                f"📹 Duracion: {result['duracion_video_seg']:.1f}s\n"
                f"📝 Oraciones a procesar: {result['cantidad_oraciones_procesables']}\n"
                f"🔤 Palabras a procesar: {result['cantidad_palabras_procesables']}\n"
            )
            if result.get("backup_name"):
                cab += f"💾 Backup creado: {result['backup_name']}\n"
            self._mostrar_diagnostico(diag, encabezado=cab)

            self.next_btn.configure(state="normal" if diag.puede_continuar else "disabled")

        self.analyze_btn.configure(state="normal", text="Analizar")

    def _mostrar_diagnostico(self, diag, encabezado=""):
        icono = {"ok": "✅", "aviso": "⚠️", "error": "❌"}.get(diag.nivel, "ℹ️")
        color = {
            "ok": COLORS["success"],
            "aviso": COLORS["warning"],
            "error": COLORS["danger"],
        }.get(diag.nivel, None)

        texto = encabezado + "\n" if encabezado else ""
        texto += f"{icono} {diag.titulo}\n"
        if diag.pasos:
            texto += "\n" + "\n".join(diag.pasos)

        self.analysis_label.configure(text=texto, text_color=color)
