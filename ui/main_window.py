import customtkinter as ctk
from config import APP_WIDTH, APP_HEIGHT, APP_MIN_WIDTH, APP_MIN_HEIGHT, COLORS
from ui.step1_project import Step1Frame

class MainWindow(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Subtilearn - Automatización CapCut")
        self.geometry(f"{APP_WIDTH}x{APP_HEIGHT}")
        self.minsize(APP_MIN_WIDTH, APP_MIN_HEIGHT)

        self.draft_path = ctk.StringVar()
        self.analysis_result = None

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

        self.frames = {}
        self.frames["step1"] = Step1Frame(self.content, self)
        
        for step_name in ["step2", "step3", "step4"]:
            frame = ctk.CTkFrame(self.content, corner_radius=10)
            frame.grid_columnconfigure(0, weight=1)
            frame.grid_rowconfigure(0, weight=1)
            ctk.CTkLabel(frame, text=f"Pantalla {step_name} (Próximamente)", font=ctk.CTkFont(size=16)).grid(row=0, column=0, pady=50)
            self.frames[step_name] = frame

        for frame in self.frames.values():
            frame.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)

        self.show_frame("step1")

    def show_frame(self, frame_name):
        if frame_name not in self.frames:
            return
        self.frames[frame_name].tkraise()
        for step_id, btn in self.nav_buttons.items():
            btn.configure(fg_color=COLORS["active_btn"][0] if step_id == frame_name else "transparent")