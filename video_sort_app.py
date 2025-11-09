"""
VideoSort Pro v2 - Aplicación principal
Organizador avanzado para Jellyfin con IA
"""

import os
import re
import shutil
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext, simpledialog
from pathlib import Path
import threading
import logging
from datetime import datetime
import json
import time

# Importaciones de tipado (corregidas)
from typing import Dict, List, Optional, Tuple, Any 

# Importar módulos locales
from config_manager import ConfigManager
from video_analyzer import VideoAnalyzer
from tmdb_client import TMDBClient
from actors_manager import ActorsManager
from file_organizer import FileOrganizer
from jellyfin_client import JellyfinClient
from audio_analyzer import AudioAnalyzer
from video_converter import VideoConverter
from reference_database_builder import ReferenceDatabaseBuilder
from youtube_manager_simple import YouTubeManagerSimple

# DUMMY YouTube Manager Class (para evitar errores de NameError y dependencia en la UI)
class YouTubeManagerDummy:
    def __init__(self, *args, **kwargs): pass
    def check_ytdlp_available(self):
        try:
            import subprocess
            subprocess.run(["yt-dlp", "--version"], capture_output=True, check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False
    def download_trailer_for_movie(self, movie_info: Dict, output_dir: Path, tmdb_client=None) -> Optional[Path]:
        try:
            Path("temp").mkdir(exist_ok=True)
        except Exception:
            pass
        return Path("temp") / f"{movie_info.get('title', 'dummy')}_trailer.mp4" 
    def log_progress(self, *args, **kwargs): pass

# === Clase Principal ===

class VideoSortPro:
    def __init__(self, root):
        self.root = root
        self.root.title("VideoSort Pro v2 - Organizador Avanzado para Jellyfin")
        self.root.geometry("1200x800")
        
        self.config_manager = ConfigManager()
        self.setup_logging()
        
        # Variables de rutas
        self.source_folder = tk.StringVar()
        self.movies_folder = tk.StringVar()
        self.series_folder = tk.StringVar()
        self.unknown_folder = tk.StringVar()
        
        last_folders = self.config_manager.get_last_folders()
        self.source_folder.set(last_folders.get("source", ""))
        self.movies_folder.set(last_folders.get("movies", ""))
        self.series_folder.set(last_folders.get("series", ""))
        self.unknown_folder.set(last_folders.get("unknown", ""))
        
        # Variables de Capas y Módulos
        self.move_files = tk.BooleanVar(value=True)
        self.enable_video_conversion = tk.BooleanVar(value=False)
        self.youtube_quality_var = tk.StringVar(value=self.config_manager.get('youtube_quality', '480p'))
        
        self.use_facial_recognition = tk.BooleanVar(value=self.config_manager.get('detect_actors', True))
        self.use_ocr_analysis = tk.BooleanVar(value=self.config_manager.get('use_ocr', True))
        self.analyze_audio_whisper = tk.BooleanVar(value=self.config_manager.get('analyze_audio', False))
        
        self.capa_0_enabled = tk.BooleanVar(value=True)
        self.capa_1_enabled = tk.BooleanVar(value=self.config_manager.get('capa_1_habilitada', True))
        self.capa_2_enabled = tk.BooleanVar(value=self.config_manager.get('capa_2_habilitada', True))
        self.capa_3_enabled = tk.BooleanVar(value=self.config_manager.get('capa_3_habilitada', True))
        
        # Inicialización de clientes (NOTA: Antes de crear widgets)
        self.tmdb_client = TMDBClient(self.config_manager.get('tmdb_api_key', ''))
        self.video_analyzer = VideoAnalyzer(self.config_manager.config)
        self.actors_manager = ActorsManager(self.tmdb_client, self.actors_log_message)
        self.file_organizer = FileOrganizer(self.config_manager.config)
        
        self.youtube_manager = YouTubeManagerSimple(self.config_manager.config, self.youtube_log_message)

        # Inicialización de clientes con loggers
        self.jellyfin_client = JellyfinClient(self.config_manager.config, self.jellyfin_log_message)
        self.audio_analyzer = AudioAnalyzer(self.config_manager.config, self.audio_log_message)
        self.video_converter = VideoConverter(self.config_manager.config, self.conversion_log_message)
        
        self.db_builder = ReferenceDatabaseBuilder(self.config_manager, self.db_builder_log_message)

        # Crear interfaz
        self.create_widgets()

        # INICIALIZACIÓN FINAL: Llamar a init_database solo después de crear todos los logs/widgets
        self.db_builder.init_database() 
        self.log("🎬 VideoSort Pro v2 iniciado. BD inicializada con éxito.")
        
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def setup_logging(self):
        """Configurar logging"""
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        
        log_filename = f"videosort_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        log_path = log_dir / log_filename
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_path, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)

    def create_widgets(self):
        """Crear interfaz gráfica y todas las pestañas"""
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill='both', expand=True, padx=10, pady=10)
        
        main_tab = ttk.Frame(notebook); notebook.add(main_tab, text="Organizar Videos")
        config_tab = ttk.Frame(notebook); notebook.add(config_tab, text="Configuración")
        analysis_tab = ttk.Frame(notebook); notebook.add(analysis_tab, text="Análisis Avanzado")
        actors_tab = ttk.Frame(notebook); notebook.add(actors_tab, text="Gestión de Actores")
        jellyfin_tab = ttk.Frame(notebook); notebook.add(jellyfin_tab, text="Jellyfin")
        youtube_tab = ttk.Frame(notebook); notebook.add(youtube_tab, text="YouTube/Entrenamiento")
        audio_tab = ttk.Frame(notebook); notebook.add(audio_tab, text="Análisis de Audio")
        conversion_tab = ttk.Frame(notebook); notebook.add(conversion_tab, text="Conversión de Video")
        reference_db_tab = ttk.Frame(notebook); notebook.add(reference_db_tab, text="Base de Datos de Referencia")
        
        # NOTA: Aseguramos que todos estos métodos estén definidos a continuación.
        self.create_main_tab(main_tab)
        self.create_config_tab(config_tab)
        self.create_analysis_tab(analysis_tab)
        self.create_actors_tab(actors_tab)
        self.create_jellyfin_tab(jellyfin_tab)
        self.create_youtube_tab(youtube_tab)
        self.create_audio_tab(audio_tab)
        self.create_conversion_tab(conversion_tab)
        self.create_reference_db_tab(reference_db_tab)
        
        return notebook

    def create_main_tab(self, parent):
        """Crear pestaña principal"""
        paths_frame = ttk.LabelFrame(parent, text="Configuración de Rutas", padding="10")
        paths_frame.pack(fill='x', padx=10, pady=5)
        
        ttk.Label(paths_frame, text="Carpeta origen:").grid(row=0, column=0, sticky='w', pady=2)
        ttk.Entry(paths_frame, textvariable=self.source_folder, width=60).grid(row=0, column=1, padx=5, pady=2)
        ttk.Button(paths_frame, text="Buscar", command=self.browse_source_folder).grid(row=0, column=2, pady=2)
        
        ttk.Label(paths_frame, text="Carpeta películas:").grid(row=1, column=0, sticky='w', pady=2)
        ttk.Entry(paths_frame, textvariable=self.movies_folder, width=60).grid(row=1, column=1, padx=5, pady=2)
        ttk.Button(paths_frame, text="Buscar", command=self.browse_movies_folder).grid(row=1, column=2, pady=2)
        
        ttk.Label(paths_frame, text="Carpeta series:").grid(row=2, column=0, sticky='w', pady=2)
        ttk.Entry(paths_frame, textvariable=self.series_folder, width=60).grid(row=2, column=1, padx=5, pady=2)
        ttk.Button(paths_frame, text="Buscar", command=self.browse_series_folder).grid(row=2, column=2, pady=2)
        
        ttk.Label(paths_frame, text="Carpeta desconocidos:").grid(row=3, column=0, sticky='w', pady=2)
        ttk.Entry(paths_frame, textvariable=self.unknown_folder, width=60).grid(row=3, column=1, padx=5, pady=2)
        ttk.Button(paths_frame, text="Buscar", command=self.browse_unknown_folder).grid(row=3, column=2, pady=2)

        # --- ESTRUCTURA DE CAPAS Y MÓDULOS DE ANÁLISIS ---

        input_modules_frame = ttk.LabelFrame(parent, text="Módulos de Análisis de Entrada (AI)", padding="10")
        input_modules_frame.pack(fill='x', padx=10, pady=5)
        
        ttk.Checkbutton(input_modules_frame, text="Reconocimiento Facial (Actores Conocidos)", variable=self.use_facial_recognition).grid(row=0, column=0, sticky='w', padx=10)
        ttk.Checkbutton(input_modules_frame, text="OCR de Títulos (Texto en Video)", variable=self.use_ocr_analysis).grid(row=0, column=1, sticky='w', padx=10)
        ttk.Checkbutton(input_modules_frame, text="Whisper (Transcribir Audio para búsqueda)", variable=self.analyze_audio_whisper).grid(row=0, column=2, sticky='w', padx=10)

        layers_frame = ttk.LabelFrame(parent, text="Capas de Decisión Progresivas [structure.txt]", padding="10")
        layers_frame.pack(fill='x', padx=10, pady=5)

        ttk.Label(layers_frame, text="Secuencia de Ejecución (de arriba a abajo):").grid(row=0, column=0, columnspan=2, sticky='w', padx=10, pady=5)

        ttk.Checkbutton(layers_frame, text="Capa 0: Metadatos Textuales (TMDb, Nombre)", variable=self.capa_0_enabled).grid(row=1, column=0, sticky='w', padx=10)
        ttk.Label(layers_frame, text="Prioridad: 1 (Siempre se ejecuta primero)").grid(row=1, column=1, sticky='w', padx=10)

        ttk.Checkbutton(layers_frame, text="Capa 1: Hashing Perceptual (pHash DB Local)", variable=self.capa_1_enabled).grid(row=2, column=0, sticky='w', padx=10)
        ttk.Label(layers_frame, text="Condición: Capa 0 ambigua o fallida. (Mejor rendimiento/costo)").grid(row=2, column=1, sticky='w', padx=10)

        ttk.Checkbutton(layers_frame, text="Capa 2: Audio Fingerprint (AcoustID)", variable=self.capa_2_enabled).grid(row=3, column=0, sticky='w', padx=10)
        ttk.Label(layers_frame, text="Condición: Capa 1 ambigua o Capa 0 baja confianza. (Alta veracidad)").grid(row=3, column=1, sticky='w', padx=10)

        ttk.Checkbutton(layers_frame, text="Capa 3: Verificación IA (Gemini - Costo)", variable=self.capa_3_enabled).grid(row=4, column=0, sticky='w', padx=10)
        ttk.Label(layers_frame, text="Condición: Último recurso, Capa 2 fallida o Capa 1 refutada. (Alto costo)").grid(row=4, column=1, sticky='w', padx=10)

        options_frame = ttk.LabelFrame(parent, text="Acciones Finales", padding="10")
        options_frame.pack(fill='x', padx=10, pady=5)

        ttk.Checkbutton(options_frame, text="Mover archivos a destino (desmarcar para solo análisis)", variable=self.move_files).grid(row=0, column=0, sticky='w', padx=10)
        ttk.Checkbutton(options_frame, text="Convertir videos incompatibles antes de mover", variable=self.enable_video_conversion).grid(row=0, column=1, sticky='w', padx=10)
        
        # --- FIN DE LA NUEVA ESTRUCTURA ---
        
        buttons_frame = ttk.Frame(parent)
        buttons_frame.pack(fill='x', padx=10, pady=10)
        
        ttk.Button(buttons_frame, text="Verificar Configuración", command=self.verify_setup).pack(side='left', padx=5)
        ttk.Button(buttons_frame, text="Escanear Videos", command=self.scan_videos).pack(side='left', padx=5)
        ttk.Button(buttons_frame, text="Procesar Videos", command=self.process_videos).pack(side='left', padx=5)
        ttk.Button(buttons_frame, text="Limpiar Log", command=self.clear_log).pack(side='left', padx=5)
        
        self.progress = ttk.Progressbar(parent, mode='determinate')
        self.progress.pack(fill='x', padx=10, pady=5)
        
        log_frame = ttk.LabelFrame(parent, text="Log de Actividad", padding="5")
        log_frame.pack(fill='both', expand=True, padx=10, pady=5)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=15)
        self.log_text.pack(fill='both', expand=True)

    def create_config_tab(self, parent):
        """Crear pestaña de configuración"""
        config_frame = ttk.LabelFrame(parent, text="Configuración de APIs", padding="10")
        config_frame.pack(fill='x', padx=10, pady=5)
        
        ttk.Label(config_frame, text="TMDB API Key:").grid(row=0, column=0, sticky='w', pady=2)
        self.tmdb_key_var = tk.StringVar(value=self.config_manager.get('tmdb_api_key', ''))
        ttk.Entry(config_frame, textvariable=self.tmdb_key_var, width=50, show='*').grid(row=0, column=1, padx=5, pady=2)
        
        ttk.Label(config_frame, text="TheTVDB API Key:").grid(row=1, column=0, sticky='w', pady=2)
        self.tvdb_key_var = tk.StringVar(value=self.config_manager.get('thetvdb_api_key', ''))
        ttk.Entry(config_frame, textvariable=self.tvdb_key_var, width=50, show='*').grid(row=1, column=1, padx=5, pady=2)
        
        advanced_frame = ttk.LabelFrame(parent, text="Configuración Avanzada", padding="10")
        advanced_frame.pack(fill='x', padx=10, pady=5)
        
        ttk.Label(advanced_frame, text="Confianza mínima reconocimiento (0.0-1.0):").grid(row=0, column=0, sticky='w', pady=2)
        self.confidence_var = tk.DoubleVar(value=self.config_manager.get('min_confidence', 0.7))
        confidence_scale = ttk.Scale(advanced_frame, from_=0.0, to=1.0, variable=self.confidence_var, orient='horizontal')
        confidence_scale.grid(row=0, column=1, sticky='ew', padx=5, pady=2)
        
        ttk.Label(advanced_frame, text="Puntuación mínima TMDB (0.0-1.0):").grid(row=1, column=0, sticky='w', pady=2)
        self.tmdb_score_var = tk.DoubleVar(value=self.config_manager.get('min_tmdb_score', 0.8))
        tmdb_scale = ttk.Scale(advanced_frame, from_=0.0, to=1.0, variable=self.tmdb_score_var, orient='horizontal')
        tmdb_scale.grid(row=1, column=1, sticky='ew', padx=5, pady=2)
        
        ttk.Label(advanced_frame, text="Fotogramas a capturar:").grid(row=2, column=0, sticky='w', pady=2)
        self.frames_var = tk.IntVar(value=self.config_manager.get('capture_frames', 30))
        ttk.Spinbox(advanced_frame, from_=10, to=100, textvariable=self.frames_var, width=10).grid(row=2, column=1, sticky='w', padx=5, pady=2)
        
        config_buttons_frame = ttk.Frame(parent)
        config_buttons_frame.pack(fill='x', padx=10, pady=10)
        
        ttk.Button(config_buttons_frame, text="Guardar Configuración", command=self.save_config).pack(side='left', padx=5)
        ttk.Button(config_buttons_frame, text="Probar API TMDB", command=self.test_tmdb_api).pack(side='left', padx=5)
        ttk.Button(config_buttons_frame, text="Cargar Configuración", command=self.load_config_file).pack(side='left', padx=5)

    def create_analysis_tab(self, parent):
        """Crear pestaña de análisis"""
        stats_frame = ttk.LabelFrame(parent, text="Estadísticas del Último Análisis", padding="10")
        stats_frame.pack(fill='x', padx=10, pady=5)
        
        self.stats_text = tk.Text(stats_frame, height=10, state='disabled')
        self.stats_text.pack(fill='both', expand=True)
        
        preview_frame = ttk.LabelFrame(parent, text="Vista Previa de Análisis", padding="10")
        preview_frame.pack(fill='both', expand=True, padx=10, pady=5)
        
        self.preview_text = scrolledtext.ScrolledText(preview_frame, height=15)
        self.preview_text.pack(fill='both', expand=True)

    def create_actors_tab(self, parent):
        """Crear pestaña de gestión de actores"""
        info_frame = ttk.LabelFrame(parent, text="Información", padding="10")
        info_frame.pack(fill='x', padx=10, pady=5)
        
        info_text = """Esta sección permite gestionar la base de datos de actores para reconocimiento facial.
        
1. Descarga fotos de actores populares desde TMDB
2. Entrena el modelo de reconocimiento facial
3. Prueba el reconocimiento en videos"""
        
        ttk.Label(info_frame, text=info_text, justify='left').pack(anchor='w')
        
        download_config_frame = ttk.LabelFrame(parent, text="Configuración de Descarga", padding="10")
        download_config_frame.pack(fill='x', padx=10, pady=5)
        
        ttk.Label(download_config_frame, text="Número de actores populares:").grid(row=0, column=0, sticky='w', pady=2)
        self.num_actors_var = tk.IntVar(value=30)
        ttk.Spinbox(download_config_frame, from_=10, to=100, textvariable=self.num_actors_var, width=10).grid(row=0, column=1, sticky='w', padx=5, pady=2)
        
        ttk.Label(download_config_frame, text="Fotos por actor:").grid(row=1, column=0, sticky='w', pady=2)
        self.photos_per_actor_var = tk.IntVar(value=3)
        ttk.Spinbox(download_config_frame, from_=1, to=10, textvariable=self.photos_per_actor_var, width=10).grid(row=1, column=1, sticky='w', padx=5, pady=2)
        
        actions_frame = ttk.LabelFrame(parent, text="Acciones", padding="10")
        actions_frame.pack(fill='x', padx=10, pady=5)
        
        ttk.Button(actions_frame, text="Descargar Actores Populares", 
                  command=self.download_popular_actors, width=30).pack(pady=5, fill='x')
        ttk.Button(actions_frame, text="Descargar Actor Específico", 
                  command=self.download_specific_actor, width=30).pack(pady=5, fill='x')
        ttk.Button(actions_frame, text="Entrenar Modelo de Reconocimiento", 
                  command=self.train_face_recognition_model, width=30).pack(pady=5, fill='x')
        ttk.Button(actions_frame, text="Probar Reconocimiento", 
                  command=self.test_face_recognition, width=30).pack(pady=5, fill='x')
        ttk.Button(actions_frame, text="Ver Base de Datos Actual", 
                  command=self.show_actors_database, width=30).pack(pady=5, fill='x')
        
        actors_log_frame = ttk.LabelFrame(parent, text="Log de Gestión de Actores", padding="5")
        actors_log_frame.pack(fill='both', expand=True, padx=10, pady=5)
        
        self.actors_log = scrolledtext.ScrolledText(actors_log_frame, height=15)
        self.actors_log.pack(fill='both', expand=True)

    def create_jellyfin_tab(self, parent):
        """Crear pestaña de Jellyfin"""
        config_frame = ttk.LabelFrame(parent, text="Configuración de Jellyfin", padding="10")
        config_frame.pack(fill='x', padx=10, pady=5)
        
        ttk.Label(config_frame, text="URL del servidor:").grid(row=0, column=0, sticky='w', pady=2)
        self.jellyfin_url_var = tk.StringVar(value=self.config_manager.get('jellyfin_url', ''))
        ttk.Entry(config_frame, textvariable=self.jellyfin_url_var, width=50).grid(row=0, column=1, padx=5, pady=2)
        
        ttk.Label(config_frame, text="API Key:").grid(row=1, column=0, sticky='w', pady=2)
        self.jellyfin_api_key_var = tk.StringVar(value=self.config_manager.get('jellyfin_api_key', ''))
        ttk.Entry(config_frame, textvariable=self.jellyfin_api_key_var, width=50, show='*').grid(row=1, column=1, padx=5, pady=2)
        
        ttk.Label(config_frame, text="User ID:").grid(row=2, column=0, sticky='w', pady=2)
        self.jellyfin_user_id_var = tk.StringVar(value=self.config_manager.get('jellyfin_user_id', ''))
        ttk.Entry(config_frame, textvariable=self.jellyfin_user_id_var, width=50).grid(row=2, column=1, padx=5, pady=2)
        
        buttons_frame = ttk.Frame(config_frame)
        buttons_frame.grid(row=3, column=0, columnspan=2, pady=10)
        
        ttk.Button(buttons_frame, text="Probar Conexión", command=self.test_jellyfin_connection).pack(side='left', padx=5)
        ttk.Button(buttons_frame, text="Guardar Configuración", command=self.save_jellyfin_config).pack(side='left', padx=5)
        ttk.Button(buttons_frame, text="Obtener Biblioteca", command=self.get_jellyfin_library).pack(side='left', padx=5)
        
        actions_frame = ttk.LabelFrame(parent, text="Acciones", padding="10")
        actions_frame.pack(fill='x', padx=10, pady=5)
        
        ttk.Button(actions_frame, text="Obtener Actores de Biblioteca", 
                  command=self.get_jellyfin_actors, width=30).pack(pady=5, fill='x')
        ttk.Button(actions_frame, text="Verificar Metadatos Faltantes", 
                  command=self.check_missing_metadata, width=30).pack(pady=5, fill='x')
        ttk.Button(actions_frame, text="Disparar Escaneo de Biblioteca", 
                  command=self.trigger_jellyfin_scan, width=30).pack(pady=5, fill='x')
        
        log_frame = ttk.LabelFrame(parent, text="Log de Jellyfin", padding="5")
        log_frame.pack(fill='both', expand=True, padx=10, pady=5)
        
        self.jellyfin_log = scrolledtext.ScrolledText(log_frame, height=15)
        self.jellyfin_log.pack(fill='both', expand=True)

    def create_youtube_tab(self, parent):
        """Crear pestaña de YouTube/Entrenamiento - SIMPLIFICADA (yt-dlp)"""
        info_frame = ttk.LabelFrame(parent, text="Información", padding="10")
        info_frame.pack(fill='x', padx=10, pady=5)
        
        info_text = """Esta sección permite descargar trailers automáticamente desde YouTube (vía yt-dlp).

IMPORTANTE: Requiere yt-dlp instalado (pip install yt-dlp)
NO requiere OAuth ni credenciales de Google."""
        
        ttk.Label(info_frame, text=info_text, justify='left').pack(anchor='w')
        
        config_frame = ttk.LabelFrame(parent, text="Configuración de Descarga", padding="10")
        config_frame.pack(fill='x', padx=10, pady=5)
        
        ttk.Label(config_frame, text="Calidad de descarga:").grid(row=0, column=0, sticky='w', pady=2)
        self.youtube_quality_var = tk.StringVar(value=self.config_manager.get('youtube_quality', '480p'))
        quality_combo = ttk.Combobox(config_frame, textvariable=self.youtube_quality_var, 
                                   values=["480p", "720p", "1080p"], state="readonly", width=10)
        quality_combo.grid(row=0, column=1, sticky='w', padx=5, pady=2)
        
        ttk.Button(config_frame, text="Guardar Configuración", 
                  command=self.save_youtube_config).grid(row=1, column=0, columnspan=2, pady=10)
        
        actions_frame = ttk.LabelFrame(parent, text="Acciones", padding="10")
        actions_frame.pack(fill='x', padx=10, pady=5)
        
        ttk.Button(actions_frame, text="Verificar yt-dlp Instalado", 
                  command=self.check_ytdlp, width=30).pack(pady=5, fill='x')
        ttk.Button(actions_frame, text="Entrenar con Jellyfin (Descargar Trailers)", 
                  command=self.train_with_jellyfin, width=30).pack(pady=5, fill='x')
        ttk.Button(actions_frame, text="Descargar Trailer Específico", 
                  command=self.download_specific_trailer, width=30).pack(pady=5, fill='x')
        
        youtube_log_frame = ttk.LabelFrame(parent, text="Log de YouTube/Entrenamiento", padding="5")
        youtube_log_frame.pack(fill='both', expand=True, padx=10, pady=5)
        
        self.youtube_log = scrolledtext.ScrolledText(youtube_log_frame, height=15)
        self.youtube_log.pack(fill='both', expand=True)

    def create_audio_tab(self, parent):
        """Crear pestaña de análisis de audio"""
        config_frame = ttk.LabelFrame(parent, text="Configuración de Audio", padding="10")
        config_frame.pack(fill='x', padx=10, pady=5)
        
        ttk.Label(config_frame, text="Modelo Whisper:").grid(row=0, column=0, sticky='w', pady=2)
        self.whisper_model_var = tk.StringVar(value=self.config_manager.get('whisper_model', 'base'))
        model_combo = ttk.Combobox(config_frame, textvariable=self.whisper_model_var,
                                 values=["tiny", "base", "small", "medium", "large"], state="readonly")
        model_combo.grid(row=0, column=1, sticky='w', padx=5, pady=2)
        
        ttk.Label(config_frame, text="Idioma de audio:").grid(row=1, column=0, sticky='w', pady=2)
        self.audio_language_var = tk.StringVar(value=self.config_manager.get('audio_language', 'es'))
        lang_combo = ttk.Combobox(config_frame, textvariable=self.audio_language_var,
                                values=["es", "en", "auto"], state="readonly")
        lang_combo.grid(row=1, column=1, sticky='w', padx=5, pady=2)
        
        ttk.Checkbutton(config_frame, text="Habilitar análisis de audio", 
                       variable=tk.BooleanVar(value=self.config_manager.get('enable_audio_analysis', True))).grid(row=2, column=0, sticky='w', pady=2)
        ttk.Checkbutton(config_frame, text="Buscar en OpenSubtitles", 
                       variable=tk.BooleanVar(value=self.config_manager.get('enable_subtitle_search', True))).grid(row=2, column=1, sticky='w', pady=2)
        
        audio_buttons_frame = ttk.Frame(config_frame)
        audio_buttons_frame.grid(row=3, column=0, columnspan=2, pady=10)
        
        ttk.Button(audio_buttons_frame, text="Guardar Configuración", command=self.save_audio_config).pack(side='left', padx=5)
        ttk.Button(audio_buttons_frame, text="Probar Whisper", command=self.test_whisper).pack(side='left', padx=5)
        
        test_frame = ttk.LabelFrame(parent, text="Pruebas de Audio", padding="10")
        test_frame.pack(fill='x', padx=10, pady=5)
        
        ttk.Button(test_frame, text="Analizar Video Individual", 
                  command=self.test_audio_analysis, width=30).pack(pady=5, fill='x')
        ttk.Button(test_frame, text="Buscar en OpenSubtitles", 
                  command=self.test_opensubtitles_search, width=30).pack(pady=5, fill='x')
        
        log_frame = ttk.LabelFrame(parent, text="Log de Análisis de Audio", padding="5")
        log_frame.pack(fill='both', expand=True, padx=10, pady=5)
        
        self.audio_log = scrolledtext.ScrolledText(log_frame, height=15)
        self.audio_log.pack(fill='both', expand=True)

    def create_conversion_tab(self, parent):
        """Crear pestaña de conversión de video"""
        config_frame = ttk.LabelFrame(parent, text="Configuración de Conversión", padding="10")
        config_frame.pack(fill='x', padx=10, pady=5)
        
        ttk.Label(config_frame, text="Codec de video:").grid(row=0, column=0, sticky='w', pady=2)
        self.video_codec_var = tk.StringVar(value=self.config_manager.get('target_video_codec', 'h264'))
        codec_combo = ttk.Combobox(config_frame, textvariable=self.video_codec_var,
                                 values=["h264", "h265", "hevc"], state="readonly")
        codec_combo.grid(row=0, column=1, sticky='w', padx=5, pady=2)
        
        ttk.Label(config_frame, text="Calidad:").grid(row=1, column=0, sticky='w', pady=2)
        self.video_quality_var = tk.StringVar(value=self.config_manager.get('video_quality_preset', 'medium'))
        quality_combo = ttk.Combobox(config_frame, textvariable=self.video_quality_var,
                                   values=["ultrafast", "fast", "medium", "slow", "veryslow"], state="readonly")
        quality_combo.grid(row=1, column=1, sticky='w', padx=5, pady=2)
        
        ttk.Label(config_frame, text="Bitrate máximo:").grid(row=2, column=0, sticky='w', pady=2)
        self.max_bitrate_var = tk.StringVar(value=self.config_manager.get('max_video_bitrate', '2M'))
        ttk.Entry(config_frame, textvariable=self.max_bitrate_var, width=10).grid(row=2, column=1, sticky='w', padx=5, pady=2)
        
        self.enable_conversion_var = tk.BooleanVar(value=self.config_manager.get('enable_video_conversion', True))
        ttk.Checkbutton(config_frame, text="Habilitar conversión automática", 
                       variable=self.enable_conversion_var).grid(row=3, column=0, columnspan=2, sticky='w', pady=2)
        
        conv_buttons_frame = ttk.Frame(config_frame)
        conv_buttons_frame.grid(row=4, column=0, columnspan=2, pady=10)
        
        ttk.Button(conv_buttons_frame, text="Guardar Configuración", command=self.save_conversion_config).pack(side='left', padx=5)
        ttk.Button(conv_buttons_frame, text="Verificar FFmpeg", command=self.check_ffmpeg).pack(side='left', padx=5)
        
        actions_frame = ttk.LabelFrame(parent, text="Acciones de Conversión", padding="10")
        actions_frame.pack(fill='x', padx=10, pady=5)
        
        ttk.Button(actions_frame, text="Convertir Video Individual", 
                  command=self.convert_single_video, width=30).pack(pady=5, fill='x')
        ttk.Button(actions_frame, text="Conversión en Lote", 
                  command=self.batch_convert_videos, width=30).pack(pady=5, fill='x')
        ttk.Button(actions_frame, text="Verificar Videos Corruptos", 
                  command=self.check_video_integrity, width=30).pack(pady=5, fill='x')
        
        conversion_log_frame = ttk.LabelFrame(parent, text="Log de Conversión", padding="5")
        conversion_log_frame.pack(fill='both', expand=True, padx=10, pady=5)
        
        self.conversion_log = scrolledtext.ScrolledText(conversion_log_frame, height=15)
        self.conversion_log.pack(fill='both', expand=True)

    def create_reference_db_tab(self, parent):
        """Crear pestaña de construcción de base de datos de referencia"""
        
        info_frame = ttk.LabelFrame(parent, text="Información", padding="10")
        info_frame.pack(fill='x', padx=10, pady=5)
        
        info_text = """Base de Datos de Referencia para ContentID (pHash y Chromaprint)
        
Esta herramienta construye una base de datos de huellas digitales (hashes) 
para identificar películas y series automáticamente.

MODOS DE PROCESAMIENTO:
- Imágenes: Descarga posters/backdrops de TMDb y genera hashes visuales (rápido)
- Video: Descarga trailers de YouTube y genera hashes de video + audio (lento)
- Ambos: Combina imágenes + video para máxima precisión"""
        
        ttk.Label(info_frame, text=info_text, justify='left').pack(anchor='w')
        
        stats_frame = ttk.LabelFrame(parent, text="Estadísticas de la Base de Datos", padding="10")
        stats_frame.pack(fill='x', padx=10, pady=5)
        
        self.db_stats_text = tk.Text(stats_frame, height=6, state='disabled')
        self.db_stats_text.pack(fill='x')
        
        ttk.Button(stats_frame, text="🔄 Actualizar Estadísticas", 
                  command=self.refresh_db_stats).pack(pady=5)
        
        config_frame = ttk.LabelFrame(parent, text="Configuración de Construcción", padding="10")
        config_frame.pack(fill='x', padx=10, pady=5)
        
        ttk.Label(config_frame, text="Modo de procesamiento:").grid(row=0, column=0, sticky='w', pady=2)
        self.db_mode_var = tk.StringVar(value="images")
        ttk.Radiobutton(config_frame, text="Solo Imágenes (Rápido)", 
                       variable=self.db_mode_var, value="images").grid(row=0, column=1, sticky='w', padx=5)
        ttk.Radiobutton(config_frame, text="Solo Video (Lento)", 
                       variable=self.db_mode_var, value="video").grid(row=0, column=2, sticky='w', padx=5)
        ttk.Radiobutton(config_frame, text="Ambos (Completo)", 
                       variable=self.db_mode_var, value="both").grid(row=0, column=3, sticky='w', padx=5)
        
        ttk.Label(config_frame, text="Fuente de datos:").grid(row=1, column=0, sticky='w', pady=2)
        self.db_source_var = tk.StringVar(value="tmdb")
        ttk.Radiobutton(config_frame, text="TMDb Populares", 
                       variable=self.db_source_var, value="tmdb").grid(row=1, column=1, sticky='w', padx=5)
        ttk.Radiobutton(config_frame, text="Biblioteca Jellyfin", 
                       variable=self.db_source_var, value="jellyfin").grid(row=1, column=2, sticky='w', padx=5)
        
        ttk.Label(config_frame, text="Número de items a procesar:").grid(row=2, column=0, sticky='w', pady=2)
        self.db_max_items_var = tk.IntVar(value=100)
        ttk.Spinbox(config_frame, from_=10, to=10000, increment=10, 
                   textvariable=self.db_max_items_var, width=15).grid(row=2, column=1, sticky='w', padx=5)
        
        ttk.Button(config_frame, text="📊 Estimar Tiempo/Espacio", 
                  command=self.estimate_db_processing).grid(row=2, column=2, padx=5)
        
        controls_frame = ttk.LabelFrame(parent, text="Controles", padding="10")
        controls_frame.pack(fill='x', padx=10, pady=5)
        
        button_frame = ttk.Frame(controls_frame)
        button_frame.pack()
        
        self.db_start_btn = ttk.Button(button_frame, text="▶️ Iniciar Construcción", 
                                        command=self.start_db_construction, width=25)
        self.db_start_btn.pack(side='left', padx=5)
        
        self.db_pause_btn = ttk.Button(button_frame, text="⏸️ Pausar", 
                                       command=self.pause_db_construction, width=15, state='disabled')
        self.db_pause_btn.pack(side='left', padx=5)
        
        self.db_stop_btn = ttk.Button(button_frame, text="⏹️ Detener", 
                                      command=self.stop_db_construction, width=15, state='disabled')
        self.db_stop_btn.pack(side='left', padx=5)
        
        ttk.Button(button_frame, text="💾 Exportar Resumen", 
                  command=self.export_db_summary, width=20).pack(side='left', padx=5)
        
        self.db_progress = ttk.Progressbar(parent, mode='determinate')
        self.db_progress.pack(fill='x', padx=10, pady=5)
        
        log_frame = ttk.LabelFrame(parent, text="Log de Construcción", padding="5")
        log_frame.pack(fill='both', expand=True, padx=10, pady=5)
        
        self.db_builder_log = scrolledtext.ScrolledText(log_frame, height=15)
        self.db_builder_log.pack(fill='both', expand=True)
        
        self.refresh_db_stats()

    # --- Métodos de Lógica ---
    def process_videos(self):
        """Procesar y organizar todos los videos"""
        if not all([self.source_folder.get(), self.movies_folder.get(), self.series_folder.get()]):
            messagebox.showerror("Error", "Configura todas las rutas necesarias")
            return
        
        def process_thread():
            try:
                paths = {
                    'source': Path(self.source_folder.get()), 'movies': Path(self.movies_folder.get()),
                    'series': Path(self.series_folder.get()), 'unknown': Path(self.unknown_folder.get()) if self.unknown_folder.get() else None
                }
                
                # Configuración de opciones y Capas
                options = {
                    'capas_activas': {
                        'capa_0': self.capa_0_enabled.get(), 'capa_1': self.capa_1_enabled.get(),
                        'capa_2': self.capa_2_enabled.get(), 'capa_3': self.capa_3_enabled.get()
                    },
                    'modulos_entrada': {
                        'facial_recognition': self.use_facial_recognition.get(),
                        'ocr_analysis': self.use_ocr_analysis.get(),
                        'audio_whisper': self.analyze_audio_whisper.get()
                    },
                    'move_files': self.move_files.get(),
                    'tmdb_min_score': self.config_manager.get('min_tmdb_score', 0.8)
                }
                
                self.tmdb_client.api_key = self.config_manager.get('tmdb_api_key', '')
                
                stats = self.file_organizer.process_videos(
                    paths, 
                    options, 
                    self.tmdb_client, 
                    self.video_analyzer,
                    self.audio_analyzer,
                    self.progress,
                    self.log
                )
                
                self.show_processing_stats(stats)
                
                messagebox.showinfo("Completado", 
                                  f"Procesamiento completado:\n"
                                  f"Películas: {stats.get('movies_processed', 0)}\n"
                                  f"Series: {stats.get('series_processed', 0)}\n"
                                  f"No Identificados (en origen): {stats.get('unknown_files', 0)}\n"
                                  f"Errores: {stats.get('errors', 0)}")
                
            except Exception as e:
                self.log(f"Error crítico durante el procesamiento: {str(e)}", "ERROR")
                messagebox.showerror("Error", f"Error durante el procesamiento: {str(e)}")
            finally:
                self.progress['value'] = 0
        
        threading.Thread(target=process_thread, daemon=True).start()

    def on_closing(self):
        """Guardar configuración al cerrar y cerrar la aplicación."""
        if messagebox.askokcancel("Salir", "¿Estás seguro de que quieres salir?"):
            # Guardar últimas rutas utilizadas
            self.config_manager.save_last_folders(
                self.source_folder.get(),
                self.movies_folder.get(),
                self.series_folder.get(),
                self.unknown_folder.get()
            )
            self.root.destroy()
            
    # --- Métodos de UI / Callbacks / Lógica Secundaria ---

    def show_processing_stats(self, stats):
        """Mostrar estadísticas del procesamiento"""
        processing_time = stats.get('processing_time', 'N/A')
        stats_text = f"""ESTADÍSTICAS DEL PROCESAMIENTO
{"="*60}
Tiempo total: {processing_time}
Películas procesadas: {stats.get('movies_processed', 0)}
Series procesadas: {stats.get('series_processed', 0)}
Archivos no identificados: {stats.get('unknown_files', 0)}
Saltados (baja confianza): {stats.get('skipped_low_confidence', 0)}
Errores: {stats.get('errors', 0)}
Actores detectados: {len(stats.get('actors_detected', set()))}
{', '.join(sorted(stats.get('actors_detected', set()))) if stats.get('actors_detected') else 'Ninguno'}
Procesamiento completado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        self.stats_text.configure(state='normal'); self.stats_text.delete(1.0, tk.END); self.stats_text.insert(1.0, stats_text); self.stats_text.configure(state='disabled')

    def browse_source_folder(self):
        folder = filedialog.askdirectory(title="Seleccionar carpeta origen")
        if folder: self.source_folder.set(folder)
    
    def browse_movies_folder(self):
        folder = filedialog.askdirectory(title="Seleccionar carpeta de películas")
        if folder: self.movies_folder.set(folder)
    
    def browse_series_folder(self):
        folder = filedialog.askdirectory(title="Seleccionar carpeta de series")
        if folder: self.series_folder.set(folder)
    
    def browse_unknown_folder(self):
        folder = filedialog.askdirectory(title="Seleccionar carpeta de desconocidos")
        if folder: self.unknown_folder.set(folder)

    # Métodos de Logging (Callbacks)
    def log(self, message, level="INFO"):
        """Agregar mensaje al log principal"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_message = f"[{timestamp}] {level}: {message}"
        
        self.log_text.insert(tk.END, log_message + "\n")
        self.log_text.see(tk.END)
        self.root.update_idletasks()
        
        if level == "ERROR": self.logger.error(message)
        elif level == "WARNING": self.logger.warning(message)
        else: self.logger.info(message)
            
    def db_builder_log_message(self, message: str, level: str = "INFO"):
        """Log para construcción de DB (Callback)"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_message = f"[{timestamp}] {level}: {message}"
        self.db_builder_log.insert(tk.END, log_message + "\n")
        self.db_builder_log.see(tk.END)
        self.root.update_idletasks()
        
    def actors_log_message(self, message, level="INFO"):
        """Log específico para actores"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_message = f"[{timestamp}] {level}: {message}"
        self.actors_log.insert(tk.END, log_message + "\n")
        self.actors_log.see(tk.END)
        self.root.update_idletasks()
    
    def jellyfin_log_message(self, message, level="INFO"):
        """Log específico para Jellyfin"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_message = f"[{timestamp}] {level}: {message}"
        self.jellyfin_log.insert(tk.END, log_message + "\n")
        self.jellyfin_log.see(tk.END)
        self.root.update_idletasks()
    
    def youtube_log_message(self, message, level="INFO"):
        """Log específico para YouTube"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_message = f"[{timestamp}] {level}: {message}"
        self.youtube_log.insert(tk.END, log_message + "\n")
        self.youtube_log.see(tk.END)
        self.root.update_idletasks()
    
    def audio_log_message(self, message, level="INFO"):
        """Log específico para audio"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_message = f"[{timestamp}] {level}: {message}"
        self.audio_log.insert(tk.END, log_message + "\n")
        self.audio_log.see(tk.END)
        self.root.update_idletasks()
    
    def conversion_log_message(self, message, level="INFO"):
        """Log específico para conversión"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_message = f"[{timestamp}] {level}: {message}"
        self.conversion_log.insert(tk.END, log_message + "\n")
        self.conversion_log.see(tk.END)
        self.root.update_idletasks()

    def clear_log(self):
        """Limpiar el log"""
        self.log_text.delete(1.0, tk.END)
    
    def test_tmdb_api(self):
        """Probar conexión con TMDB API"""
        if not self.tmdb_key_var.get(): messagebox.showerror("Error", "Ingresa tu API Key de TMDB"); return
        self.tmdb_client.api_key = self.tmdb_key_var.get()
        if self.tmdb_client.test_connection(): messagebox.showinfo("Éxito", "Conexión con TMDB exitosa!")
        else: messagebox.showerror("Error", "Error conectando con TMDB")
    
    def verify_setup(self):
        """Verificar configuración y dependencias"""
        self.log("Verificando configuración...")
        issues = []
        if not self.source_folder.get(): issues.append("Falta carpeta origen")
        if not self.movies_folder.get(): issues.append("Falta carpeta de películas")
        if not self.series_folder.get(): issues.append("Falta carpeta de series")
        try: import cv2; self.log("OpenCV disponible")
        except ImportError: issues.append("OpenCV no encontrado")
        try: import pytesseract; self.log("Pytesseract disponible")
        except ImportError: issues.append("Pytesseract no encontrado")
        try: import face_recognition; self.log("Face Recognition disponible")
        except ImportError: issues.append("Face Recognition no encontrado")
        self.tmdb_client.api_key = self.config_manager.get('tmdb_api_key', '')
        if self.tmdb_client.api_key and not self.tmdb_client.test_connection(): issues.append("TMDB API Key inválida o sin conexión.")
        if self.use_facial_recognition.get():
            db_info = self.actors_manager.get_database_info()
            if db_info['actors'] == 0: issues.append("Base de datos de actores vacía")
        if issues:
            self.log("Problemas encontrados:")
            for issue in issues: self.log(f"   {issue}")
        else: self.log("Configuración verificada correctamente")
    
    def scan_videos(self):
        """Escanear videos en la carpeta origen"""
        if not self.source_folder.get(): messagebox.showerror("Error", "Selecciona la carpeta origen"); return
        def scan_thread():
            try:
                source_path = Path(self.source_folder.get()); video_extensions = set(self.config_manager.get('video_extensions', []))
                self.log("Iniciando escaneo de videos...")
                videos_found = [file_path for file_path in source_path.rglob('*') if file_path.is_file() and file_path.suffix.lower() in video_extensions]
                self.log(f"Encontrados {len(videos_found)} archivos de video")
                preview_text = "VISTA PREVIA DEL ANÁLISIS\n" + "="*50 + "\n\n"; counts = {'movies': 0, 'series': 0, 'extras': 0, 'problematic': 0}
                for i, video_path in enumerate(videos_found[:20]):
                    video_info = self.video_analyzer.extract_video_info(video_path.name, str(video_path))
                    if video_info:
                        preview_text += f"{i+1}. {video_path.name}\n"; preview_text += f"   Tipo: {video_info['type']}\n"; preview_text += f"   Título: {video_info['title']}\n"
                        counts[video_info['type']] += 1
                        if video_info['type'] == 'series': preview_text += f"   Temporada: {video_info.get('season', 'N/A')}\n"; preview_text += f"   Episodio: {video_info.get('episode', 'N/A')}\n"
                        preview_text += "\n"
                    else: counts['problematic'] += 1; preview_text += f"{i+1}. ❌ {video_path.name}\n"; preview_text += "   No se pudo extraer información\n\n"
                if len(videos_found) > 20: preview_text += f"... y {len(videos_found) - 20} archivos más\n\n"
                preview_text += "RESUMEN\n" + "="*20 + "\n"; preview_text += f"Películas: {counts['movies']}\n"; preview_text += f"Series: {counts['series']}\n"
                preview_text += f"Extras: {counts['extras']}\n"; preview_text += f"Problemáticos: {counts['problematic']}\n"; preview_text += f"Total: {len(videos_found)}\n"
                self.preview_text.delete(1.0, tk.END); self.preview_text.insert(1.0, preview_text); self.log("Escaneo completado")
            except Exception as e: self.log(f"Error durante el escaneo: {str(e)}", "ERROR")
        threading.Thread(target=scan_thread, daemon=True).start()
    
    def save_config(self):
        """Guardar configuración actual"""
        try:
            config_updates = {
                'tmdb_api_key': self.tmdb_key_var.get(), 'thetvdb_api_key': self.tvdb_key_var.get(),
                'min_confidence': self.confidence_var.get(), 'min_tmdb_score': self.tmdb_score_var.get(),
                'capture_frames': self.frames_var.get()
            }
            if self.config_manager.save_config(config_updates): messagebox.showinfo("Éxito", "Configuración guardada correctamente")
            else: messagebox.showerror("Error", "Error guardando configuración")
        except Exception as e: messagebox.showerror("Error", f"Error guardando configuración: {str(e)}")
    
    def load_config_file(self):
        """Cargar configuración desde archivo"""
        config_file = filedialog.askopenfilename(title="Seleccionar archivo de configuración", filetypes=[("JSON", "*.json")])
        if config_file:
            try:
                with open(config_file, 'r', encoding='utf-8') as f: loaded_config = json.load(f)
                self.config_manager.update(loaded_config)
                self.tmdb_key_var.set(self.config_manager.get('tmdb_api_key', '')); self.tvdb_key_var.set(self.config_manager.get('thetvdb_api_key', ''))
                self.confidence_var.set(self.config_manager.get('min_confidence', 0.7)); self.tmdb_score_var.set(self.config_manager.get('min_tmdb_score', 0.8))
                self.frames_var.set(self.config_manager.get('capture_frames', 30))
                messagebox.showinfo("Éxito", "Configuración cargada correctamente")
            except Exception as e: messagebox.showerror("Error", f"Error cargando configuración: {str(e)}")
    
    def test_jellyfin_connection(self):
        """Probar conexión con Jellyfin"""
        success = self.jellyfin_client.setup_jellyfin_connection(self.jellyfin_url_var.get(), self.jellyfin_api_key_var.get(), self.jellyfin_user_id_var.get())
        if success: messagebox.showinfo("Éxito", "Conexión con Jellyfin exitosa!")
        else: messagebox.showerror("Error", "Error conectando con Jellyfin")
    
    def save_jellyfin_config(self):
        """Guardar configuración de Jellyfin"""
        config_updates = { 'jellyfin_url': self.jellyfin_url_var.get(), 'jellyfin_api_key': self.jellyfin_api_key_var.get(), 'jellyfin_user_id': self.jellyfin_user_id_var.get() }
        if self.config_manager.save_config(config_updates): messagebox.showinfo("Éxito", "Configuración de Jellyfin guardada")
        else: messagebox.showerror("Error", "Error guardando configuración")
    
    def get_jellyfin_library(self):
        """Obtener biblioteca de Jellyfin"""
        def get_library_thread():
            content = self.jellyfin_client.get_all_content()
            self.jellyfin_log_message(f"Biblioteca obtenida: {content['total_movies']} películas, {content['total_series']} series")
        threading.Thread(target=get_library_thread, daemon=True).start()
    
    def get_jellyfin_actors(self):
        """Obtener actores de la biblioteca Jellyfin"""
        def get_actors_thread():
            actors = self.jellyfin_client.get_actors_from_library()
            self.jellyfin_log_message(f"Actores encontrados: {len(actors)}")
            for i, actor in enumerate(actors[:20]): self.jellyfin_log_message(f"  {i+1}. {actor}")
        threading.Thread(target=get_actors_thread, daemon=True).start()
    
    def check_missing_metadata(self):
        """Verificar metadatos faltantes"""
        def check_metadata_thread():
            missing = self.jellyfin_client.get_missing_metadata_items()
            self.jellyfin_log_message(f"Elementos con metadatos incompletos: {len(missing)}")
            for item in missing[:10]: self.jellyfin_log_message(f"  {item['name']}: {', '.join(item['issues'])}")
        threading.Thread(target=check_metadata_thread, daemon=True).start()
    
    def trigger_jellyfin_scan(self):
        """Disparar escaneo de biblioteca"""
        success = self.jellyfin_client.trigger_library_scan()
        if success: messagebox.showinfo("Éxito", "Escaneo de biblioteca iniciado")
        else: messagebox.showerror("Error", "Error iniciando escaneo")
    
    def save_youtube_config(self):
        """Guardar configuración de YouTube"""
        config_updates = { 'youtube_quality': self.youtube_quality_var.get() }
        if self.config_manager.save_config(config_updates): messagebox.showinfo("Éxito", "Configuración de YouTube guardada")
        else: messagebox.showerror("Error", "Error guardando configuración")

    def check_ytdlp(self):
        """Verificar instalación de yt-dlp"""
        if self.youtube_manager.check_ytdlp_available():
            self.youtube_log_message("✅ yt-dlp está instalado y disponible")
            messagebox.showinfo("Éxito", "yt-dlp está disponible")
        else:
            self.youtube_log_message("❌ yt-dlp no está instalado", "ERROR")
            messagebox.showerror("Error", "yt-dlp no está disponible.\n\nInstálalo con:\npip install yt-dlp")

    def train_with_jellyfin(self):
        """Entrenar modelo usando biblioteca Jellyfin"""
        messagebox.showinfo("Entrenamiento", "La función de entrenamiento con Jellyfin está pendiente de implementación.")
        self.youtube_log_message("Función 'Entrenar con Jellyfin' no implementada aún.", "WARNING")
    
    def download_specific_trailer(self):
        """Descargar trailer específico"""
        movie_title = simpledialog.askstring("Película", "Nombre de la película:")
        if not movie_title: return
        year = simpledialog.askstring("Año", "Año de la película (opcional):")
        def download_thread():
            try:
                movie_info = { 'title': movie_title, 'year': year if year else None }
                trailer_path = self.youtube_manager.download_trailer_for_movie(movie_info, Path("temp"), self.tmdb_client)
                if trailer_path: self.youtube_log_message(f"✅ Trailer descargado: {trailer_path}")
                else: self.youtube_log_message(f"❌ No se pudo descargar trailer para: {movie_title}", "ERROR")
            except Exception as e: self.youtube_log_message(f"❌ Error: {e}", "ERROR")
        threading.Thread(target=download_thread, daemon=True).start()

    def save_audio_config(self):
        """Guardar configuración de audio"""
        config_updates = { 'whisper_model': self.whisper_model_var.get(), 'audio_language': self.audio_language_var.get() }
        if self.config_manager.save_config(config_updates): messagebox.showinfo("Éxito", "Configuración de audio guardada")
        else: messagebox.showerror("Error", "Error guardando configuración")
    
    def test_whisper(self):
        """Probar instalación de Whisper"""
        def test_thread():
            try:
                import whisper; self.audio_log_message("Whisper está instalado correctamente")
                model_name = self.whisper_model_var.get(); self.audio_log_message(f"Probando modelo: {model_name}")
                model = whisper.load_model(model_name); self.audio_log_message(f"Modelo {model_name} cargado exitosamente")
            except ImportError: self.audio_log_message("Whisper no está instalado. Ejecuta: pip install openai-whisper", "ERROR")
            except Exception as e: self.audio_log_message(f"Error probando Whisper: {e}", "ERROR")
        threading.Thread(target=test_thread, daemon=True).start()
    
    def test_audio_analysis(self):
        """Probar análisis de audio en un video"""
        video_file = filedialog.askopenfilename(title="Seleccionar video para análisis de audio", filetypes=[("Videos", "*.mp4 *.mkv *.avi *.mov")])
        if not video_file: return
        def analyze_thread():
            try:
                video_path = Path(video_file); self.audio_log_message(f"Iniciando análisis de audio: {video_path.name}")
                result = self.audio_analyzer.analyze_video_for_identification(video_path)
                if result:
                    self.audio_log_message(f"Película identificada: {result['title']} ({result.get('year', 'N/A')})")
                    self.audio_log_message(f"Confianza: {result['confidence_score']:.2f}")
                else: self.audio_log_message("No se pudo identificar la película por audio", "WARNING")
            except Exception as e: self.audio_log_message(f"Error en análisis de audio: {e}", "ERROR")
        threading.Thread(target=analyze_thread, daemon=True).start()
    
    def test_opensubtitles_search(self):
        """Probar búsqueda en OpenSubtitles"""
        query = simpledialog.askstring("Búsqueda", "Ingresa texto para buscar en OpenSubtitles:")
        if not query: return
        def search_thread():
            try:
                results = self.audio_analyzer.search_opensubtitles(query, max_results=5)
                if results:
                    self.audio_log_message(f"Encontrados {len(results)} resultados para: '{query}'")
                    for i, result in enumerate(results): self.audio_log_message(f"  {i+1}. {result['title']} ({result['year']})")
                else: self.audio_log_message(f"No se encontraron resultados para: '{query}'", "WARNING")
            except Exception as e: self.audio_log_message(f"Error en búsqueda: {e}", "ERROR")
        threading.Thread(target=search_thread, daemon=True).start()
    
    def save_conversion_config(self):
        """Guardar configuración de conversión"""
        config_updates = {
            'target_video_codec': self.video_codec_var.get(), 'video_quality_preset': self.video_quality_var.get(),
            'max_video_bitrate': self.max_bitrate_var.get(), 'enable_video_conversion': self.enable_conversion_var.get()
        }
        if self.config_manager.save_config(config_updates): messagebox.showinfo("Éxito", "Configuración de conversión guardada")
        else: messagebox.showerror("Error", "Error guardando configuración")
    
    def check_ffmpeg(self):
        """Verificar instalación de FFmpeg"""
        if self.video_converter.check_ffmpeg_available(): messagebox.showinfo("Éxito", "FFmpeg está disponible")
        else: messagebox.showerror("Error", "FFmpeg no está disponible. Instálalo desde https://ffmpeg.org/")
    
    def convert_single_video(self):
        """Convertir un video individual"""
        video_file = filedialog.askopenfilename(title="Seleccionar video para convertir", filetypes=[("Videos", "*.mp4 *.mkv *.avi *.mov *.wmv *.flv")])
        if not video_file: return
        def convert_thread():
            try:
                video_path = Path(video_file); self.conversion_log_message(f"Iniciando conversión: {video_path.name}")
                video_info = self.video_converter.get_video_info(video_path)
                if not video_info: self.conversion_log_message("No se pudo analizar el video", "ERROR"); return
                needs_conv, reasons = self.video_converter.needs_conversion(video_info)
                if not needs_conv: self.conversion_log_message("El video ya es compatible con Jellyfin"); return
                self.conversion_log_message(f"Razones para conversión: {', '.join(reasons)}")
                success = self.video_converter.convert_video_with_backup(video_path)
                if success: messagebox.showinfo("Éxito", "Video convertido exitosamente")
                else: messagebox.showerror("Error", "Error durante la conversión")
            except Exception as e: self.conversion_log_message(f"Error en conversión: {e}", "ERROR")
        threading.Thread(target=convert_thread, daemon=True).start()
    
    def batch_convert_videos(self):
        """Conversión en lote de videos"""
        folder = filedialog.askdirectory(title="Seleccionar carpeta con videos para convertir")
        if not folder: return
        def batch_convert_thread():
            try:
                folder_path = Path(folder); video_extensions = set(self.config_manager.get('video_extensions', []))
                videos_found = [file_path for file_path in folder_path.rglob('*') if file_path.is_file() and file_path.suffix.lower() in video_extensions]
                if not videos_found: self.conversion_log_message("No se encontraron videos en la carpeta", "WARNING"); return
                self.conversion_log_message(f"Iniciando conversión en lote: {len(videos_found)} videos")
                def progress_callback(progress, message=""): self.conversion_log_message(f"Progreso: {progress:.1f}% - {message}")
                stats = self.video_converter.batch_convert_videos(videos_found, progress_callback)
                messagebox.showinfo("Completado", f"Conversión en lote completada:\nConvertidos: {stats['converted']}\nOmitidos: {stats['skipped']}\nFallidos: {stats['failed']}")
            except Exception as e: self.conversion_log_message(f"Error en conversión en lote: {e}", "ERROR")
        threading.Thread(target=batch_convert_thread, daemon=True).start()
    
    def check_video_integrity(self):
        """Verificar integridad de videos"""
        folder = filedialog.askdirectory(title="Seleccionar carpeta para verificar videos")
        if not folder: return
        def check_integrity_thread():
            try:
                folder_path = Path(folder); video_extensions = set(self.config_manager.get('video_extensions', []))
                videos_found = [file_path for file_path in folder_path.rglob('*') if file_path.is_file() and file_path.suffix.lower() in video_extensions]
                if not videos_found: self.conversion_log_message("No se encontraron videos en la carpeta", "WARNING"); return
                self.conversion_log_message(f"Verificando integridad de {len(videos_found)} videos...")
                corrupted_count = 0
                for i, video_path in enumerate(videos_found):
                    try:
                        self.conversion_log_message(f"Verificando {i+1}/{len(videos_found)}: {video_path.name}")
                        if not self.video_converter.verify_video_integrity(video_path): corrupted_count += 1
                    except Exception as e: self.conversion_log_message(f"Error verificando {video_path.name}: {e}", "ERROR"); corrupted_count += 1
                if corrupted_count > 0: messagebox.showwarning("Advertencia", f"Se encontraron {corrupted_count} videos corruptos")
                else: messagebox.showinfo("Éxito", "Todos los videos están íntegros")
            except Exception as e: self.conversion_log_message(f"Error en verificación: {e}", "ERROR")
        threading.Thread(target=check_integrity_thread, daemon=True).start()

    def refresh_db_stats(self):
        """Actualizar estadísticas de la base de datos"""
        try:
            stats = self.db_builder.get_database_stats()
            stats_text = f"""📊 ESTADÍSTICAS DE LA BASE DE DATOS
{'='*50}
📽️  Películas procesadas: {stats.get('total_movies', 0)}
📺  Series procesadas: {stats.get('total_series', 0)}
📺  Episodios procesados: {stats.get('total_episodes', 0)}
🖼️  Hashes visuales: {stats.get('total_visual_hashes', 0):,}
🎵  Hashes de audio: {stats.get('total_audio_hashes', 0):,}

DESGLOSE POR TIPO:
    • Con imágenes procesadas: {stats.get('images_processed', 0)}
    • Con video procesado: {stats.get('videos_processed', 0)}
    • Con audio procesado: {stats.get('audio_processed', 0)}
"""
            self.db_stats_text.configure(state='normal'); self.db_stats_text.delete(1.0, tk.END); self.db_stats_text.insert(1.0, stats_text); self.db_stats_text.configure(state='disabled')
        except Exception as e: self.db_builder_log_message(f"Error actualizando estadísticas: {e}", "ERROR")

    def estimate_db_processing(self):
        """Estimar tiempo y espacio de procesamiento"""
        try:
            num_items = self.db_max_items_var.get(); mode = self.db_mode_var.get()
            estimate = self.db_builder.estimate_processing_time(num_items, mode)
            message = f"""ESTIMACIÓN DE PROCESAMIENTO
{'='*40}
📊 Items a procesar: {estimate['total_items']}
⚙️  Modo: {estimate['mode']}
⏱️  TIEMPO ESTIMADO:
    • Total: {estimate['human_readable']}
    • Aproximado: {estimate['total_seconds']} segundos
💾 ESPACIO ESTIMADO:
    • Base de datos: ~{estimate['database_size_mb']} MB
    • Cache temporal: ~{estimate['temp_cache_mb']} MB/video
"""
            messagebox.showinfo("Estimación de Procesamiento", message)
        except Exception as e: messagebox.showerror("Error", f"Error en estimación: {e}")

    def start_db_construction(self):
        """Iniciar construcción de base de datos"""
        def construction_thread():
            try:
                current_stats = self.db_builder.get_database_stats()
                total_processed = current_stats.get('total_content', 0)
                new_limit = total_processed + self.db_max_items_var.get()
                
                self.db_start_btn.configure(state='disabled'); self.db_pause_btn.configure(state='normal'); self.db_stop_btn.configure(state='normal')
                mode = self.db_mode_var.get(); source = self.db_source_var.get()
                
                self.db_builder_log_message(f"Se intentará procesar hasta el item #{new_limit} (acumulación: {self.db_max_items_var.get()})", "INFO")

                if source == "tmdb": self.db_builder.build_database_from_tmdb_popular(mode=mode, max_items=new_limit)
                else: self.db_builder.build_database_from_jellyfin(jellyfin_client=self.jellyfin_client, mode=mode, content_type="both", max_items=new_limit)
                
                self.refresh_db_stats(); messagebox.showinfo("Completado", "Construcción de base de datos completada")
            except Exception as e:
                self.db_builder_log_message(f"Error en construcción: {e}", "ERROR"); messagebox.showerror("Error", f"Error durante la construcción: {e}")
            finally:
                self.db_start_btn.configure(state='normal'); self.db_pause_btn.configure(state='disabled'); self.db_stop_btn.configure(state='disabled')
        threading.Thread(target=construction_thread, daemon=True).start()

    def pause_db_construction(self):
        """Pausar/Reanudar construcción"""
        if self.db_builder.paused: self.db_builder.resume_processing(); self.db_pause_btn.configure(text="⏸️ Pausar")
        else: self.db_builder.pause_processing(); self.db_pause_btn.configure(text="▶️ Reanudar")

    def stop_db_construction(self):
        """Detener construcción"""
        if messagebox.askyesno("Confirmar", "¿Detener la construcción de la base de datos?"): self.db_builder.stop_processing(); self.db_builder_log_message("🛑 Deteniendo construcción...", "WARNING")

    def export_db_summary(self):
        """Exportar resumen de la base de datos"""
        try:
            output_path = filedialog.asksaveasfilename(title="Guardar resumen de la base de datos", defaultextension=".json", filetypes=[("JSON", "*.json")])
            if output_path: self.db_builder.export_database_summary(Path(output_path)); messagebox.showinfo("Éxito", f"Resumen exportado a:\n{output_path}")
        except Exception as e: messagebox.showerror("Error", f"Error exportando resumen: {e}")

    def download_popular_actors(self):
        """Descargar actores populares"""
        num_actors = self.num_actors_var.get(); photos_per_actor = self.photos_per_actor_var.get()
        def download_thread():
            success = self.actors_manager.download_popular_actors(num_actors, photos_per_actor)
            if success: self.actors_log_message("Descarga completada exitosamente!")
            else: self.actors_log_message("Error en la descarga", "ERROR")
        threading.Thread(target=download_thread, daemon=True).start()
    
    def download_specific_actor(self):
        """Descargar actor específico"""
        actor_name = simpledialog.askstring("Actor", "Nombre del actor a descargar:")
        if not actor_name: return
        def download_thread():
            success = self.actors_manager.download_specific_actor(actor_name)
            if success: self.actors_log_message(f"Actor {actor_name} descargado exitosamente!")
            else: self.actors_log_message(f"Error descargando {actor_name}", "ERROR")
        threading.Thread(target=download_thread, daemon=True).start()
    
    def train_face_recognition_model(self):
        """Entrenar modelo de reconocimiento facial"""
        def train_thread():
            success = self.actors_manager.train_face_recognition_model()
            if success: 
                self.video_analyzer.actors_db = self.video_analyzer.load_actors_database()
                self.actors_log_message("Modelo entrenado exitosamente!")
            else: self.actors_log_message("Error en el entrenamiento", "ERROR")
        threading.Thread(target=train_thread, daemon=True).start()
    
    def test_face_recognition(self):
        """Probar reconocimiento facial en un video"""
        db_info = self.actors_manager.get_database_info()
        if db_info['actors'] == 0: messagebox.showwarning("Advertencia", "Base de datos de actores vacía. Entrena el modelo primero."); return
        video_file = filedialog.askopenfilename(title="Seleccionar video para probar", filetypes=[("Videos", "*.mp4 *.mkv *.avi *.mov")])
        if not video_file: return
        def test_thread():
            try:
                self.actors_log_message(f"Probando reconocimiento en: {Path(video_file).name}")
                analysis_result = self.video_analyzer.analyze_video_with_ai(Path(video_file))
                detected_actors = analysis_result.get('detected_actors', [])
                if detected_actors:
                    unique_actors = list(set(detected_actors))
                    self.actors_log_message(f"Actores detectados: {', '.join(unique_actors)}")
                else: self.actors_log_message("No se detectaron actores conocidos")
            except Exception as e: self.actors_log_message(f"Error en prueba: {str(e)}", "ERROR")
        threading.Thread(target=test_thread, daemon=True).start()
    
    def show_actors_database(self):
        """Mostrar información de la base de datos actual"""
        db_info = self.actors_manager.get_database_info()
        if db_info['actors'] == 0: self.actors_log_message("Base de datos de actores vacía", "WARNING"); return
        self.actors_log_message("BASE DE DATOS DE ACTORES ACTUAL:"); self.actors_log_message("="*50)
        for i, actor_name in enumerate(db_info['actors_list'], 1): self.actors_log_message(f"{i:2d}. {actor_name}")
        self.actors_log_message(f"Total: {db_info['actors']} actores, {db_builder.get_database_stats().get('total_visual_hashes', 0)} encodings") # Corregido: Usa get_database_stats