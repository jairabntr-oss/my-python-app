import customtkinter as ctk
from tkinter import filedialog
import os
from core.draft_manager import DraftManager
from ui.components.buttons import AnalyzeButton, StyledButton
from config import COLORS

class Step1Frame(ctk.CTkFrame):
    def __init__(self, parent, main_window):
        super().__init__(parent, corner_radius=10)
        self.main_window = main_window
        self.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(self, text="Paso 1: Seleccionar Proyecto CapCut", font=ctk.CTkFont(size=18, weight="bold")).grid(row=0, column=0, padx=20, pady=(20, 10), sticky="w")

        folder_frame = ctk.CTkFrame(self, fg_color="transparent")
        folder_frame.grid(row=1, column=0, padx=20, pady=10, sticky="ew")
        folder_frame.grid_columnconfigure(0, weight=1)
        
        self.file_entry = ctk.CTkEntry(folder_frame, placeholder_text="Ruta al archivo draft_content.json...", textvariable=self.main_window.draft_path)
        self.file_entry.grid(row=0, column=0, padx=(0, 10), sticky="ew")
        
        StyledButton(folder_frame, text="Examinar", width=100, command=self.browse_file, style="secondary").grid(row=0, column=1)

        # Progress bar
        self.progress = ctk.CTkProgressBar(folder_frame)
        self.progress.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        self.progress.set(0)

        info_frame = ctk.CTkFrame(self, fg_color="transparent")
        info_frame.grid(row=2, column=0, padx=20, pady=20, sticky="ew")
        info_frame.grid_columnconfigure(0, weight=1)
        
        self.analysis_label = ctk.CTkLabel(info_frame, text="Aún no se ha analizado ningún proyecto.\nSelecciona un archivo y presiona 'Analizar'.", justify="left", anchor="w")
        self.analysis_label.grid(row=0, column=0, sticky="w")

        actions_frame = ctk.CTkFrame(self, fg_color="transparent")
        actions_frame.grid(row=3, column=0, padx=20, pady=20, sticky="ew")
        actions_frame.grid_columnconfigure(1, weight=1)

        StyledButton(actions_frame, text="<- Atrás", style="secondary", state="disabled").grid(row=0, column=0, padx=(0, 10), sticky="w")
        self.analyze_btn = AnalyzeButton(actions_frame, command=self.analyze_draft)
        self.analyze_btn.grid(row=0, column=1, sticky="e", padx=(0, 10))
        self.next_btn = StyledButton(actions_frame, text="Siguiente ->", command=lambda: self.main_window.show_frame("step2"), style="success", state="disabled")
        self.next_btn.grid(row=0, column=2, sticky="e")

    def browse_file(self):
        initial_dir = os.path.expanduser("~")
        file_path = filedialog.askopenfilename(title="Seleccionar draft_content.json", initialdir=initial_dir, filetypes=[("JSON files", "*.json"), ("All files", "*.*")])
        if file_path:
            self.main_window.draft_path.set(file_path)
            self.analysis_label.configure(text="Archivo seleccionado. Presiona 'Analizar'.")
            self.next_btn.configure(state="disabled")

    def analyze_draft(self):
        file_path = self.main_window.draft_path.get()
        if not file_path:
            self.analysis_label.configure(text="❌ Primero seleccioná un archivo.")
            return

        self.analyze_btn.configure(state="disabled", text="Analizando...")
        self.progress.set(0.2)
        self.update_idletasks()
        
        manager = DraftManager(file_path)
        manager.analyze_async(callback=self.on_analysis_complete)

    def on_analysis_complete(self, error, result):
        self.progress.set(1.0)
        if error:
            self.analysis_label.configure(text=f"❌ Error:\n{str(error)}")
            self.next_btn.configure(state="disabled")
        else:
            self.main_window.analysis_result = result
            msg  = f"📹 Duración: {result['duracion_video_seg']:.1f}s\n"
            msg += f"✅ Oraciones a procesar: {result['cantidad_oraciones_procesables']}\n"
            msg += f"✅ Palabras a procesar: {result['cantidad_palabras_procesables']}\n\n"
            msg += f"✍️  Oraciones ya estilizadas: {result['cantidad_oraciones_ya_estiladas']}\n\n"
            if result['tracks_residuales_texto']:
                msg += f"⚠️  Tracks TEXTO residuales: {len(result['tracks_residuales_texto'])}\n"
            if result['tracks_residuales_audio']:
                msg += f"⚠️  Tracks AUDIO residuales: {len(result['tracks_residuales_audio'])}\n"
            if not (result['tracks_residuales_texto'] or result['tracks_residuales_audio']):
                msg += "✔️  Sin tracks residuales.\n"
            msg += f"\n💾 Backup: {result.get('backup_name', 'N/A')}"
            
            if result['cantidad_oraciones_procesables'] > 0:
                self.next_btn.configure(state="normal")
            else:
                self.next_btn.configure(state="disabled")
                msg += "\n\n⚠️ No hay oraciones procesables."
            self.analysis_label.configure(text=msg)
            
        self.analyze_btn.configure(state="normal", text="Analizar Auto-Captions")