import sys
import traceback
import customtkinter as ctk
from ui.main_window import MainWindow
from core.logger import logger

def main():
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    app = MainWindow()
    app.mainloop()

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.critical(f"Error fatal iniciando app: {e}\n{traceback.format_exc()}")
        print(f"Error fatal: {e}")
        sys.exit(1)