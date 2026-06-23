"""
RadCutTool — Entry Point
Run: python main.py
"""
import tkinter as tk
from ui.main_window import RadCutApp

if __name__ == '__main__':
    root = tk.Tk()
    app = RadCutApp(root)
    try:
        root.iconbitmap('icon.ico')
    except Exception:
        pass
    root.mainloop()
