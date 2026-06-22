import customtkinter as ctk
from config import APP_WIDTH, APP_HEIGHT, APP_MIN_WIDTH, APP_MIN_HEIGHT, COLORS
from ui.step1_project import Step1Frame
from ui.step2_style import Step2Frame
from ui.step3_audio import Step3Frame
from ui.step4_execute import Step4Frame

class MainWindow(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Subtilearn - Automatización CapCut")
        self.geometry(f"{APP_WIDTH}x{APP_HEIGHT}")
        self.minsize(APP_MIN_WIDTH, APP_MIN_HEIGHT)

        # Estado compartido entre pasos
        self.draft_path = ctk.StringVar()
        self.analysis_result = None
        self.style_profile = None
        self.ruta_sonido = None
        self.modo_clicks = "2_por_oracion"

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self.banner = ctk.CTkFrame(self, height=30, corner_radius=0, fg_color=COLORS["banner"])
        self.banner.grid(row=0, column=0, columnspan=2, sticky="ew")
        self.banner.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self.banner, text="⚠️ CERRÁ CAPCUT ANTES DE ANALIZAR O GENERAR", text_color="white", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, pady=5)

        self.sidebar = ctk.CTkFrame(self, width=200, corner_radius=0)
        self.sidebar.grid(row=1, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(5, weight=1)

        ctk.CTkLabel(self.sidebar, text="Subtilearn", font=ctk.CTkFont(size=20, weight="bold")).grid(row=0, column=0, padx=20, pady=(20, 30))

        self.nav_buttons = {}
        steps = [("step1", "1. Proyecto"), ("step2", "2. Estilo"), ("step3", "3. Clicks"), ("step4", "4. Generar")]
        for i, (step_id, text) in enumerate(steps, start=1):
            btn = ctk.CTkButton(self.sidebar, text=text, command=lambda s=step_id: self.show_frame(s), fg_color="transparent", anchor="w")
            btn.grid(row=i, column=0, padx=20, pady=10, sticky="ew")
            self.nav_buttons[step_id] = btn

        self.content = ctk.CTkFrame(self, fg_color="transparent")
        self.content.grid(row=1, column=1, sticky="nsew")
        self.content.grid_rowconfigure(0, weight=1)
        self.content.grid_columnconfigure(0, weight=1)

        self.frames = {
            "step1": Step1Frame(self.content, self),
            "step2": Step2Frame(self.content, self),
            "step3": Step3Frame(self.content, self),
            "step4": Step4Frame(self.content, self),
        }

        for frame in self.frames.values():
            frame.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)

        self.show_frame("step1")

    def show_frame(self, frame_name):
        if frame_name not in self.frames:
            return
        self.frames[frame_name].tkraise()
        for step_id, btn in self.nav_buttons.items():
            btn.configure(fg_color=COLORS["active_btn"][0] if step_id == frame_name else "transparent")