import customtkinter as ctk
from config import COLORS

class StyledButton(ctk.CTkButton):
    def __init__(self, parent, text, command=None, style="primary", **kwargs):
        styles = {
            "primary": {"fg_color": COLORS["active_btn"][0]},
            "success": {"fg_color": COLORS["success"], "hover_color": "darkgreen"},
            "danger": {"fg_color": COLORS["danger"]},
            "secondary": {"fg_color": "transparent"},
        }
        super().__init__(parent, text=text, command=command, **styles.get(style, {}), **kwargs)

class AnalyzeButton(StyledButton):
    def __init__(self, parent, command=None):
        super().__init__(parent, text="Analizar Auto-Captions", command=command, style="primary")