"""
Paso 3: Configuración de clicks de audio.
"""

import os
from tkinter import filedialog
import customtkinter as ctk
from config import COLORS


class Step3Frame(ctk.CTkFrame):
    """Pantalla de configuración de clicks de audio."""

    def __init__(self, parent, main_window):
        super().__init__(parent, corner_radius=10)
        self.main_window = main_window
        self.grid_columnconfigure(0, weight=1)

        # ── Título ─────────────────────────────────────────────────────────────
        ctk.CTkLabel(
            self,
            text="Paso 3: Clicks de Audio",
            font=ctk.CTkFont(size=18, weight="bold"),
        ).grid(row=0, column=0, padx=20, pady=(20, 10), sticky="w")

        ctk.CTkLabel(
            self,
            text="Selecciona el archivo de click y el modo de inserción.\n"
                 "Si omitís el archivo, no se generarán clicks.",
            justify="left", anchor="w",
        ).grid(row=1, column=0, padx=20, pady=(0, 10), sticky="w")

        # ── Selector de archivo ────────────────────────────────────────────────
        file_frame = ctk.CTkFrame(self, fg_color="transparent")
        file_frame.grid(row=2, column=0, padx=20, pady=5, sticky="ew")
        file_frame.grid_columnconfigure(0, weight=1)

        self.var_ruta_sonido = ctk.StringVar(
            value=str(
                os.path.join(
                    os.path.dirname(os.path.dirname(__file__)), "assets", "click_sonido.mp3"
                )
            )
        )
        ctk.CTkEntry(
            file_frame,
            textvariable=self.var_ruta_sonido,
            placeholder_text="Ruta al archivo de click (.mp3)...",
        ).grid(row=0, column=0, padx=(0, 10), sticky="ew")

        ctk.CTkButton(
            file_frame, text="Examinar", width=100,
            fg_color="transparent",
            command=self._browse_audio,
        ).grid(row=0, column=1)

        # ── Modo de clicks ────────────────────────────────────────────────────
        modo_frame = ctk.CTkFrame(self, fg_color="transparent")
        modo_frame.grid(row=3, column=0, padx=20, pady=15, sticky="w")

        ctk.CTkLabel(modo_frame, text="Modo de clicks:", anchor="w").grid(
            row=0, column=0, padx=(0, 10), sticky="w"
        )

        self.var_modo = ctk.StringVar(value="2_por_oracion")
        ctk.CTkOptionMenu(
            modo_frame,
            variable=self.var_modo,
            values=["2_por_oracion", "3_por_oracion"],
        ).grid(row=0, column=1)

        ctk.CTkLabel(
            modo_frame,
            text="  2_por_oracion: click al inicio y fin de cada oración\n"
                 "  3_por_oracion: inicio, mitad y fin",
            justify="left", text_color="gray",
        ).grid(row=1, column=0, columnspan=2, pady=(5, 0), sticky="w")

        # ── Checkbox "omitir clicks" ───────────────────────────────────────────
        self.var_omitir = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            self,
            text="Omitir clicks (solo generar subtítulos)",
            variable=self.var_omitir,
            command=self._toggle_omitir,
        ).grid(row=4, column=0, padx=20, pady=10, sticky="w")

        # ── Botones de navegación ─────────────────────────────────────────────
        nav_frame = ctk.CTkFrame(self, fg_color="transparent")
        nav_frame.grid(row=5, column=0, padx=20, pady=20, sticky="ew")
        nav_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkButton(
            nav_frame, text="← Atrás", fg_color="transparent",
            command=lambda: self.main_window.show_frame("step2"),
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkButton(
            nav_frame, text="Siguiente →",
            fg_color=COLORS["active_btn"][0],
            command=self._siguiente,
        ).grid(row=0, column=2, sticky="e")

    # ── Acciones ──────────────────────────────────────────────────────────────

    def _browse_audio(self):
        path = filedialog.askopenfilename(
            title="Seleccionar archivo de click",
            filetypes=[("Archivos de audio", "*.mp3 *.wav *.ogg"), ("Todos", "*.*")],
        )
        if path:
            self.var_ruta_sonido.set(path)

    def _toggle_omitir(self):
        """Habilita/deshabilita el campo de ruta según checkbox."""
        pass  # La lógica se lee en _siguiente

    def _siguiente(self):
        """Guarda la configuración de audio en main_window y avanza al paso 4."""
        if self.var_omitir.get():
            self.main_window.ruta_sonido = None
        else:
            ruta = self.var_ruta_sonido.get().strip()
            self.main_window.ruta_sonido = ruta if ruta else None

        self.main_window.modo_clicks = self.var_modo.get()
        self.main_window.show_frame("step4")