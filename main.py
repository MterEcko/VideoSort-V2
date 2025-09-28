#!/usr/bin/env python3
"""
VideoSort Pro v2 - Organizador Avanzado para Jellyfin
Archivo principal de la aplicación
"""

import tkinter as tk
from tkinter import messagebox
from video_sort_app import VideoSortPro

def check_dependencies():
    """Verificar dependencias críticas"""
    missing_deps = []
    
    try:
        import cv2
    except ImportError:
        missing_deps.append("opencv-python")
    
    try:
        import pytesseract
    except ImportError:
        missing_deps.append("pytesseract")
    
    try:
        import face_recognition
    except ImportError:
        missing_deps.append("face_recognition")
    
    try:
        import requests
    except ImportError:
        missing_deps.append("requests")
    
    try:
        import numpy as np
    except ImportError:
        missing_deps.append("numpy")
    
    try:
        from PIL import Image, ImageTk
    except ImportError:
        missing_deps.append("Pillow")
    
    return missing_deps

def main():
    """Función principal"""
    # Verificar dependencias
    missing_deps = check_dependencies()
    
    if missing_deps:
        root = tk.Tk()
        root.withdraw()  # Ocultar ventana principal
        
        message = "❌ Dependencias faltantes:\n\n"
        for dep in missing_deps:
            message += f"   • {dep}\n"
        message += "\nInstala las dependencias con:\n"
        message += f"pip install {' '.join(missing_deps)}"
        
        messagebox.showerror("Dependencias Faltantes", message)
        root.destroy()
        return
    
    # Crear y ejecutar aplicación
    root = tk.Tk()
    app = VideoSortPro(root)
    
    # Configurar cierre de aplicación
    def on_closing():
        if messagebox.askokcancel("Salir", "¿Estás seguro de que quieres salir?"):
            root.destroy()
    
    root.protocol("WM_DELETE_WINDOW", on_closing)
    
    # Mostrar mensaje de bienvenida
    app.log("🎬 VideoSort Pro v2 iniciado")
    app.log("💡 Mejoras en esta versión:")
    app.log("   • Validación inteligente de títulos")
    app.log("   • Control de similitud con TMDB")
    app.log("   • Gestión completa de actores")
    app.log("   • Modo estricto para mayor precisión")
    app.log("   • Análisis mejorado de nombres de archivos")
    
    root.mainloop()

if __name__ == "__main__":
    main()