"""
Paso 2: Configuración de estilo visual de los subtítulos.
"""

import json
from pathlib import Path
import customtkinter as ctk
from config import COLORS


class Step2Frame(ctk.CTkFrame):
    """Pantalla de configuración del estilo visual."""

    _SETTINGS_PATH = Path(__file__).parent.parent / "config" / "settings.json"

    def __init__(self, parent, main_window):
        super().__init__(parent, corner_radius=10)
        self.main_window = main_window
        self.grid_columnconfigure(0, weight=1)

        # ── Título ─────────────────────────────────────────────────────────────
        ctk.CTkLabel(
            self,
            text="Paso 2: Estilo Visual",
            font=ctk.CTkFont(size=18, weight="bold"),
        ).grid(row=0, column=0, padx=20, pady=(20, 10), sticky="w")

        # ── Cargar settings actuales ───────────────────────────────────────────
        settings = self._cargar_settings()
        style = settings.get("subtitle_style", {})
        layout = settings.get("layout", {})

        # ── Campos ────────────────────────────────────────────────────────────
        campos_frame = ctk.CTkFrame(self, fg_color="transparent")
        campos_frame.grid(row=1, column=0, padx=20, pady=10, sticky="ew")
        campos_frame.grid_columnconfigure(1, weight=1)

        fila = 0

        def _agregar_campo(label_text, var, fila_idx):
            ctk.CTkLabel(campos_frame, text=label_text, anchor="w").grid(
                row=fila_idx, column=0, padx=(0, 10), pady=6, sticky="w"
            )
            entrada = ctk.CTkEntry(campos_frame, textvariable=var)
            entrada.grid(row=fila_idx, column=1, pady=6, sticky="ew")

        self.var_text_size = ctk.StringVar(value=str(style.get("text_size", 30)))
        self.var_scale     = ctk.StringVar(value=str(style.get("scale_x", 3.037)))
        self.var_color     = ctk.StringVar(value=style.get("text_color", "#FFFFFF"))
        self.var_shadow_alpha = ctk.StringVar(value=str(style.get("shadow_alpha", 0.33)))
        self.var_ancla_izq = ctk.StringVar(value=str(layout.get("ancla_izquierda", -0.20)))
        self.var_ancla_der = ctk.StringVar(value=str(layout.get("ancla_derecha", 0.20)))
        self.var_ancho_car = ctk.StringVar(value=str(layout.get("ancho_por_caracter", 0.15)))
        self.var_max_palabras = ctk.StringVar(value=str(layout.get("max_palabras_por_bloque", 5)))

        _agregar_campo("Tamaño de texto:",      self.var_text_size,    fila); fila += 1
        _agregar_campo("Escala (scale_x/y):",   self.var_scale,        fila); fila += 1
        _agregar_campo("Color (#RRGGBB):",       self.var_color,        fila); fila += 1
        _agregar_campo("Alfa de sombra (0-1):", self.var_shadow_alpha, fila); fila += 1
        _agregar_campo("Ancla izquierda:",      self.var_ancla_izq,    fila); fila += 1
        _agregar_campo("Ancla derecha:",        self.var_ancla_der,    fila); fila += 1
        _agregar_campo("Ancho por carácter:",   self.var_ancho_car,    fila); fila += 1
        _agregar_campo("Máx. palabras/bloque:", self.var_max_palabras, fila); fila += 1

        # ── Mensaje de estado ─────────────────────────────────────────────────
        self.status_label = ctk.CTkLabel(
            self, text="", text_color=COLORS["success"], anchor="w"
        )
        self.status_label.grid(row=2, column=0, padx=20, pady=(0, 5), sticky="w")

        # ── Botones de navegación ─────────────────────────────────────────────
        nav_frame = ctk.CTkFrame(self, fg_color="transparent")
        nav_frame.grid(row=3, column=0, padx=20, pady=20, sticky="ew")
        nav_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkButton(
            nav_frame, text="← Atrás", fg_color="transparent",
            command=lambda: self.main_window.show_frame("step1"),
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkButton(
            nav_frame, text="Guardar y Siguiente →",
            fg_color=COLORS["active_btn"][0],
            command=self._guardar_y_siguiente,
        ).grid(row=0, column=2, sticky="e")

    # ── Acciones ──────────────────────────────────────────────────────────────

    def _guardar_y_siguiente(self):
        """Valida, guarda en settings.json y avanza al paso 3."""
        try:
            text_size    = float(self.var_text_size.get())
            scale        = float(self.var_scale.get())
            color        = self.var_color.get().strip()
            shadow_alpha = float(self.var_shadow_alpha.get())
            ancla_izq    = float(self.var_ancla_izq.get())
            ancla_der    = float(self.var_ancla_der.get())
            ancho_car    = float(self.var_ancho_car.get())
            max_pal      = int(self.var_max_palabras.get())
        except ValueError as e:
            self.status_label.configure(
                text=f"❌ Valor inválido: {e}",
                text_color=COLORS["danger"],
            )
            return

        # Actualizar settings
        settings = self._cargar_settings()
        settings.setdefault("subtitle_style", {}).update({
            "text_size": text_size,
            "scale_x": scale,
            "scale_y": scale,
            "text_color": color,
            "shadow_alpha": shadow_alpha,
        })
        settings.setdefault("layout", {}).update({
            "ancla_izquierda": ancla_izq,
            "ancla_derecha":   ancla_der,
            "ancho_por_caracter": ancho_car,
            "max_palabras_por_bloque": max_pal,
        })

        try:
            with open(self._SETTINGS_PATH, "w", encoding="utf-8") as f:
                json.dump(settings, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.status_label.configure(
                text=f"❌ Error guardando: {e}",
                text_color=COLORS["danger"],
            )
            return

        # Propagar el perfil actualizado a main_window
        self.main_window.style_profile = settings.get("subtitle_style", {})

        self.status_label.configure(
            text="✅ Estilo guardado.", text_color=COLORS["success"]
        )
        self.main_window.show_frame("step3")

    # ── Utilidades ────────────────────────────────────────────────────────────

    def _cargar_settings(self) -> dict:
        try:
            with open(self._SETTINGS_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}