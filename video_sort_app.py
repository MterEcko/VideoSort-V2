# Métodos para la pestaña de Jellyfin
    def test_jellyfin_connection(self):
        """Probar conexión con Jellyfin"""
        success = self.jellyfin_client.setup_jellyfin_connection(
            self.jellyfin_url_var.get(),
            self.jellyfin_api_key_var.get(),
            self.jellyfin_user_id_var.get()
        )
        
        if success:
            messagebox.showinfo("Éxito", "Conexión con Jellyfin exitosa!")
        else:
            messagebox.showerror("Error", "Error conectando con Jellyfin")
    
    def save_jellyfin_config(self):
        """Guardar configuración de Jellyfin"""
        config_updates = {
            'jellyfin_url': self.jellyfin_url_var.get(),
            'jellyfin_api_key': self.jellyfin_api_key_var.get(),
            'jellyfin_user_id': self.jellyfin_user_id_var.get()
        }
        
        if self.config_manager.save_config(config_updates):
            messagebox.showinfo("Éxito", "Configuración de Jellyfin guardada")
        else:
            messagebox.showerror("Error", "Error guardando configuración")
    
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
            for i, actor in enumerate(actors[:20]):  # Mostrar primeros 20
                self.jellyfin_log_message(f"  {i+1}. {actor}")
        
        threading.Thread(target=get_actors_thread, daemon=True).start()
    
    def check_missing_metadata(self):
        """Verificar metadatos faltantes"""
        def check_metadata_thread():
            missing = self.jellyfin_client.get_missing_metadata_items()
            self.jellyfin_log_message(f"Elementos con metadatos incompletos: {len(missing)}")
            for item in missing[:10]:  # Mostrar primeros 10
                self.jellyfin_log_message(f"  {item['name']}: {', '.join(item['issues'])}")
        
        threading.Thread(target=check_metadata_thread, daemon=True).start()
    
    def trigger_jellyfin_scan(self):
        """Disparar escaneo de biblioteca"""
        success = self.jellyfin_client.trigger_library_scan()
        if success:
            messagebox.showinfo("Éxito", "Escaneo de biblioteca iniciado")
        else:
            messagebox.showerror("Error", "Error iniciando escaneo")
    
    # Métodos para la pestaña de YouTube
    def save_youtube_credentials(self):
        """Guardar credenciales de YouTube"""
        self.youtube_manager.setup_oauth_credentials(
            self.youtube_client_id_var.get(),
            self.youtube_client_secret_var.get()
        )
        messagebox.showinfo("Éxito", "Credenciales de YouTube guardadas")
    
    def start_youtube_oauth(self):
        """Iniciar proceso OAuth con YouTube"""
        def oauth_thread():
            self.youtube_manager.start_oauth_flow()
        
        threading.Thread(target=oauth_thread, daemon=True).start()
    
    def train_with_jellyfin(self):
        """Entrenar modelo usando biblioteca Jellyfin"""
        def train_thread():
            try:
                # Obtener contenido de Jellyfin
                content = self.jellyfin_client.get_all_content()
                movies = content.get('movies', [])
                
                if not movies:
                    self.youtube_log_message("No se encontraron películas en Jellyfin", "ERROR")
                    return
                
                self.youtube_log_message(f"Iniciando entrenamiento con {len(movies)} películas de Jellyfin")
                
                trained_count = 0
                for i, movie in enumerate(movies[:50]):  # Limitar a primeras 50 por ahora
                    try:
                        movie_info = {
                            'title': movie.get('name', ''),
                            'year': str(movie.get('year', '')),
                            'tmdb_id': movie.get('tmdb_id', '')
                        }
                        
                        self.youtube_log_message(f"Procesando {i+1}/{len(movies[:50])}: {movie_info['title']}")
                        
                        # Descargar y procesar trailer
                        trailer_path = self.youtube_manager.download_trailer_for_movie(
                            movie_info, 
                            Path("temp"), 
                            self.tmdb_client
                        )
                        
                        if trailer_path and trailer_path.exists():
                            # Analizar trailer para entrenamiento
                            analysis = self.video_analyzer.analyze_video_with_ai(trailer_path)
                            if analysis['detected_actors']:
                                trained_count += 1
                                self.youtube_log_message(f"Entrenamiento exitoso: {len(analysis['detected_actors'])} actores")
                            
                            # Limpiar archivo temporal
                            trailer_path.unlink()
                    
                    except Exception as e:
                        self.youtube_log_message(f"Error procesando {movie_info.get('title', 'Unknown')}: {e}", "ERROR")
                
                self.youtube_log_message(f"Entrenamiento completado: {trained_count} películas procesadas")
                
            except Exception as e:
                self.youtube_log_message(f"Error en entrenamiento: {e}", "ERROR")
        
        threading.Thread(target=train_thread, daemon=True).start()
    
    def train_specific_video(self):
        """Entrenar con video específico"""
        video_file = filedialog.askopenfilename(
            title="Seleccionar video para entrenamiento",
            filetypes=[("Videos", "*.mp4 *.mkv *.avi *.mov")]
        )
        
        if not video_file:
            return
        
        def train_thread():
            try:
                video_path = Path(video_file)
                self.youtube_log_message(f"Analizando video para entrenamiento: {video_path.name}")
                
                analysis = self.video_analyzer.analyze_video_with_ai(video_path)
                
                if analysis['detected_actors']:
                    self.youtube_log_message(f"Actores detectados: {', '.join(set(analysis['detected_actors']))}")
                    self.youtube_log_message("Entrenamiento con video completado")
                else:
                    self.youtube_log_message("No se detectaron actores en el video", "WARNING")
                
            except Exception as e:
                self.youtube_log_message(f"Error en entrenamiento: {e}", "ERROR")
        
        threading.Thread(target=train_thread, daemon=True).start()
    
    # Métodos para la pestaña de Audio
    def save_audio_config(self):
        """Guardar configuración de audio"""
        config_updates = {
            'whisper_model': self.whisper_model_var.get(),
            'audio_language': self.audio_language_var.get()
        }
        
        if self.config_manager.save_config(config_updates):
            messagebox.showinfo("Éxito", "Configuración de audio guardada")
        else:
            messagebox.showerror("Error", "Error guardando configuración")
    
    def test_whisper(self):
        """Probar instalación de Whisper"""
        def test_thread():
            try:
                import whisper
                self.audio_log_message("Whisper está instalado correctamente")
                
                # Probar carga de modelo
                model_name = self.whisper_model_var.get()
                self.audio_log_message(f"Probando modelo: {model_name}")
                
                model = whisper.load_model(model_name)
                self.audio_log_message(f"Modelo {model_name} cargado exitosamente")
                
            except ImportError:
                self.audio_log_message("Whisper no está instalado. Ejecuta: pip install openai-whisper", "ERROR")
            except Exception as e:
                self.audio_log_message(f"Error probando Whisper: {e}", "ERROR")
        
    def test_audio_analysis(self):
        """Probar análisis de audio en un video"""
        video_file = filedialog.askopenfilename(
            title="Seleccionar video para análisis de audio",
            filetypes=[("Videos", "*.mp4 *.mkv *.avi *.mov")]
        )
        
        if not video_file:
            return
        
        def analyze_thread():
            try:
                video_path = Path(video_file)
                self.audio_log_message(f"Iniciando análisis de audio: {video_path.name}")
                
                result = self.audio_analyzer.analyze_video_for_identification(video_path)
                
                if result:
                    self.audio_log_message(f"Película identificada: {result['title']} ({result.get('year', 'N/A')})")
                    self.audio_log_message(f"Confianza: {result['confidence_score']:.2f}")
                    self.audio_log_message(f"Frases coincidentes: {result.get('matched_phrases', 0)}")
                else:
                    self.audio_log_message("No se pudo identificar la película por audio", "WARNING")
                
            except Exception as e:
                self.audio_log_message(f"Error en análisis de audio: {e}", "ERROR")
        
        threading.Thread(target=analyze_thread, daemon=True).start()
    
    def test_opensubtitles_search(self):
        """Probar búsqueda en OpenSubtitles"""
        query = simpledialog.askstring("Búsqueda", "Ingresa texto para buscar en OpenSubtitles:")
        if not query:
            return
        
        def search_thread():
            try:
                results = self.audio_analyzer.search_opensubtitles(query, max_results=5)
                
                if results:
                    self.audio_log_message(f"Encontrados {len(results)} resultados para: '{query}'")
                    for i, result in enumerate(results):
                        self.audio_log_message(f"  {i+1}. {result['title']} ({result['year']})")
                else:
                    self.audio_log_message(f"No se encontraron resultados para: '{query}'", "WARNING")
                
            except Exception as e:
                self.audio_log_message(f"Error en búsqueda: {e}", "ERROR")
        
        threading.Thread(target=search_thread, daemon=True).start()
    
    # Métodos para la pestaña de Conversión
    def save_conversion_config(self):
        """Guardar configuración de conversión"""
        config_updates = {
            'target_video_codec': self.video_codec_var.get(),
            'video_quality_preset': self.video_quality_var.get(),
            'max_video_bitrate': self.max_bitrate_var.get(),
            'enable_video_conversion': self.enable_conversion_var.get()
        }
        
        if self.config_manager.save_config(config_updates):
            messagebox.showinfo("Éxito", "Configuración de conversión guardada")
        else:
            messagebox.showerror("Error", "Error guardando configuración")
    
    def check_ffmpeg(self):
        """Verificar instalación de FFmpeg"""
        if self.video_converter.check_ffmpeg_available():
            self.conversion_log_message("FFmpeg está instalado y disponible")
            messagebox.showinfo("Éxito", "FFmpeg está disponible")
        else:
            self.conversion_log_message("FFmpeg no está instalado o no está en el PATH", "ERROR")
            messagebox.showerror("Error", "FFmpeg no está disponible. Instálalo desde https://ffmpeg.org/")
    
    def convert_single_video(self):
        """Convertir un video individual"""
        video_file = filedialog.askopenfilename(
            title="Seleccionar video para convertir",
            filetypes=[("Videos", "*.mp4 *.mkv *.avi *.mov *.wmv *.flv")]
        )
        
        if not video_file:
            return
        
        def convert_thread():
            try:
                video_path = Path(video_file)
                self.conversion_log_message(f"Iniciando conversión: {video_path.name}")
                
                # Analizar video
                video_info = self.video_converter.get_video_info(video_path)
                if not video_info:
                    self.conversion_log_message("No se pudo analizar el video", "ERROR")
                    return
                
                # Verificar si necesita conversión
                needs_conv, reasons = self.video_converter.needs_conversion(video_info)
                
                if not needs_conv:
                    self.conversion_log_message("El video ya es compatible con Jellyfin")
                    return
                
                self.conversion_log_message(f"Razones para conversión: {', '.join(reasons)}")
                
                # Convertir con backup
                success = self.video_converter.convert_video_with_backup(video_path)
                
                if success:
                    self.conversion_log_message("Conversión completada exitosamente")
                    messagebox.showinfo("Éxito", "Video convertido exitosamente")
                else:
                    self.conversion_log_message("Error en la conversión", "ERROR")
                    messagebox.showerror("Error", "Error durante la conversión")
                
            except Exception as e:
                self.conversion_log_message(f"Error en conversión: {e}", "ERROR")
        
        threading.Thread(target=convert_thread, daemon=True).start()
    
    def batch_convert_videos(self):
        """Conversión en lote de videos"""
        folder = filedialog.askdirectory(title="Seleccionar carpeta con videos para convertir")
        if not folder:
            return
        
        def batch_convert_thread():
            try:
                folder_path = Path(folder)
                video_extensions = set(self.config_manager.get('video_extensions', []))
                
                # Encontrar todos los videos
                videos_found = []
                for file_path in folder_path.rglob('*'):
                    if file_path.is_file() and file_path.suffix.lower() in video_extensions:
                        videos_found.append(file_path)
                
                if not videos_found:
                    self.conversion_log_message("No se encontraron videos en la carpeta", "WARNING")
                    return
                
                self.conversion_log_message(f"Iniciando conversión en lote: {len(videos_found)} videos")
                
                # Convertir videos
                def progress_callback(progress, message=""):
                    self.conversion_log_message(f"Progreso: {progress:.1f}% - {message}")
                
                stats = self.video_converter.batch_convert_videos(videos_found, progress_callback)
                
                self.conversion_log_message("Conversión en lote completada:")
                self.conversion_log_message(f"  Convertidos: {stats['converted']}")
                self.conversion_log_message(f"  Omitidos: {stats['skipped']}")
                self.conversion_log_message(f"  Fallidos: {stats['failed']}")
                
                messagebox.showinfo("Completado", 
                                  f"Conversión en lote completada:\n"
                                  f"Convertidos: {stats['converted']}\n"
                                  f"Omitidos: {stats['skipped']}\n"
                                  f"Fallidos: {stats['failed']}")
                
            except Exception as e:
                self.conversion_log_message(f"Error en conversión en lote: {e}", "ERROR")
        
        threading.Thread(target=batch_convert_thread, daemon=True).start()
    
    def check_video_integrity(self):
        """Verificar integridad de videos"""
        folder = filedialog.askdirectory(title="Seleccionar carpeta para verificar videos")
        if not folder:
            return
        
        def check_integrity_thread():
            try:
                folder_path = Path(folder)
                video_extensions = set(self.config_manager.get('video_extensions', []))
                
                # Encontrar todos los videos
                videos_found = []
                for file_path in folder_path.rglob('*'):
                    if file_path.is_file() and file_path.suffix.lower() in video_extensions:
                        videos_found.append(file_path)
                
                if not videos_found:
                    self.conversion_log_message("No se encontraron videos en la carpeta", "WARNING")
                    return
                
                self.conversion_log_message(f"Verificando integridad de {len(videos_found)} videos...")
                
                corrupted_count = 0
                for i, video_path in enumerate(videos_found):
                    try:
                        self.conversion_log_message(f"Verificando {i+1}/{len(videos_found)}: {video_path.name}")
                        
                        if not self.video_converter.verify_video_integrity(video_path):
                            corrupted_count += 1
                    
                    except Exception as e:
                        self.conversion_log_message(f"Error verificando {video_path.name}: {e}", "ERROR")
                        corrupted_count += 1
                
                self.conversion_log_message(f"Verificación completada: {corrupted_count} videos corruptos de {len(videos_found)}")
                
                if corrupted_count > 0:
                    messagebox.showwarning("Advertencia", f"Se encontraron {corrupted_count} videos corruptos")
                else:
                    messagebox.showinfo("Éxito", "Todos los videos están íntegros")
                
            except Exception as e:
                self.conversion_log_message(f"Error en verificación: {e}", "ERROR")
        
        threading.Thread(target=check_integrity_thread, daemon=True).start()"""
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

# Importar módulos locales
from config_manager import ConfigManager
from video_analyzer import VideoAnalyzer
from tmdb_client import TMDBClient
from actors_manager import ActorsManager
from file_organizer import FileOrganizer

class VideoSortPro:
    def __init__(self, root):
        self.root = root
        self.root.title("VideoSort Pro v2 - Organizador Avanzado para Jellyfin")
        self.root.geometry("1200x800")
        
        # Inicializar componentes
        self.config_manager = ConfigManager()
        self.setup_logging()
        
        # Variables de rutas
        self.source_folder = tk.StringVar()
        self.movies_folder = tk.StringVar()
        self.series_folder = tk.StringVar()
        self.unknown_folder = tk.StringVar()
        
        # Cargar últimas rutas utilizadas
        last_folders = self.config_manager.get_last_folders()
        self.source_folder.set(last_folders.get("source", ""))
        self.movies_folder.set(last_folders.get("movies", ""))
        self.series_folder.set(last_folders.get("series", ""))
        self.unknown_folder.set(last_folders.get("unknown", ""))
        
        # Variables de opciones
        self.use_facial_recognition = tk.BooleanVar(value=True)
        self.use_ocr_analysis = tk.BooleanVar(value=True)
        self.use_tmdb_api = tk.BooleanVar(value=True)
        self.analyze_audio = tk.BooleanVar(value=False)
        self.move_files = tk.BooleanVar(value=True)
        self.strict_matching = tk.BooleanVar(value=True)
        self.enable_video_conversion = tk.BooleanVar(value=False)
        
        # Inicializar clientes y módulos
        self.tmdb_client = TMDBClient(self.config_manager.get('tmdb_api_key', ''))
        self.video_analyzer = VideoAnalyzer(self.config_manager.config)
        self.actors_manager = ActorsManager(self.tmdb_client, self.actors_log_message)
        self.file_organizer = FileOrganizer(self.config_manager.config)
        self.youtube_manager = YouTubeManager(self.config_manager, self.youtube_log_message)
        self.jellyfin_client = JellyfinClient(self.config_manager.config, self.jellyfin_log_message)
        self.audio_analyzer = AudioAnalyzer(self.config_manager.config, self.audio_log_message)
        self.video_converter = VideoConverter(self.config_manager.config, self.conversion_log_message)
        
        # Crear interfaz
        self.create_widgets()
        
        # Configurar evento de cierre para guardar rutas
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
        """Crear interfaz gráfica"""
        # Notebook para pestañas
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Crear pestañas
        main_tab = ttk.Frame(notebook)
        notebook.add(main_tab, text="Organizar Videos")
        
        config_tab = ttk.Frame(notebook)
        notebook.add(config_tab, text="Configuración")
        
        analysis_tab = ttk.Frame(notebook)
        notebook.add(analysis_tab, text="Análisis Avanzado")
        
        actors_tab = ttk.Frame(notebook)
        notebook.add(actors_tab, text="Gestión de Actores")
        
        jellyfin_tab = ttk.Frame(notebook)
        notebook.add(jellyfin_tab, text="Jellyfin")
        
        youtube_tab = ttk.Frame(notebook)
        notebook.add(youtube_tab, text="YouTube/Entrenamiento")
        
        audio_tab = ttk.Frame(notebook)
        notebook.add(audio_tab, text="Análisis de Audio")
        
        conversion_tab = ttk.Frame(notebook)
        notebook.add(conversion_tab, text="Conversión de Video")
        
        # Llenar pestañas
        self.create_main_tab(main_tab)
        self.create_config_tab(config_tab)
        self.create_analysis_tab(analysis_tab)
        self.create_actors_tab(actors_tab)
        self.create_jellyfin_tab(jellyfin_tab)
        self.create_youtube_tab(youtube_tab)
        self.create_audio_tab(audio_tab)
        self.create_conversion_tab(conversion_tab)
    
    def create_main_tab(self, parent):
        """Crear pestaña principal"""
        # Frame de rutas
        paths_frame = ttk.LabelFrame(parent, text="Configuración de Rutas", padding="10")
        paths_frame.pack(fill='x', padx=10, pady=5)
        
        # Carpeta origen
        ttk.Label(paths_frame, text="Carpeta origen:").grid(row=0, column=0, sticky='w', pady=2)
        ttk.Entry(paths_frame, textvariable=self.source_folder, width=60).grid(row=0, column=1, padx=5, pady=2)
        ttk.Button(paths_frame, text="Buscar", command=self.browse_source_folder).grid(row=0, column=2, pady=2)
        
        # Carpeta películas
        ttk.Label(paths_frame, text="Carpeta películas:").grid(row=1, column=0, sticky='w', pady=2)
        ttk.Entry(paths_frame, textvariable=self.movies_folder, width=60).grid(row=1, column=1, padx=5, pady=2)
        ttk.Button(paths_frame, text="Buscar", command=self.browse_movies_folder).grid(row=1, column=2, pady=2)
        
        # Carpeta series
        ttk.Label(paths_frame, text="Carpeta series:").grid(row=2, column=0, sticky='w', pady=2)
        ttk.Entry(paths_frame, textvariable=self.series_folder, width=60).grid(row=2, column=1, padx=5, pady=2)
        ttk.Button(paths_frame, text="Buscar", command=self.browse_series_folder).grid(row=2, column=2, pady=2)
        
        # Carpeta desconocidos
        ttk.Label(paths_frame, text="Carpeta desconocidos:").grid(row=3, column=0, sticky='w', pady=2)
        ttk.Entry(paths_frame, textvariable=self.unknown_folder, width=60).grid(row=3, column=1, padx=5, pady=2)
        ttk.Button(paths_frame, text="Buscar", command=self.browse_unknown_folder).grid(row=3, column=2, pady=2)
        
        # Frame de opciones
        options_frame = ttk.LabelFrame(parent, text="Opciones de Análisis", padding="10")
        options_frame.pack(fill='x', padx=10, pady=5)
        
        ttk.Checkbutton(options_frame, text="Usar reconocimiento facial", variable=self.use_facial_recognition).grid(row=0, column=0, sticky='w', padx=10)
        ttk.Checkbutton(options_frame, text="Análisis OCR de texto", variable=self.use_ocr_analysis).grid(row=0, column=1, sticky='w', padx=10)
        ttk.Checkbutton(options_frame, text="Consultar TMDB API", variable=self.use_tmdb_api).grid(row=1, column=0, sticky='w', padx=10)
        ttk.Checkbutton(options_frame, text="Analizar audio/subtítulos", variable=self.analyze_audio).grid(row=1, column=1, sticky='w', padx=10)
        ttk.Checkbutton(options_frame, text="Solo mover si encuentra metadatos", variable=self.strict_matching).grid(row=2, column=0, sticky='w', padx=10)
        ttk.Checkbutton(options_frame, text="Mover archivos (desmarcar para solo análisis)", variable=self.move_files).grid(row=2, column=1, sticky='w', padx=10)
        ttk.Checkbutton(options_frame, text="Convertir videos incompatibles", variable=self.enable_video_conversion).grid(row=3, column=0, sticky='w', padx=10)
        
        # Frame de botones
        buttons_frame = ttk.Frame(parent)
        buttons_frame.pack(fill='x', padx=10, pady=10)
        
        ttk.Button(buttons_frame, text="Verificar Configuración", command=self.verify_setup).pack(side='left', padx=5)
        ttk.Button(buttons_frame, text="Escanear Videos", command=self.scan_videos).pack(side='left', padx=5)
        ttk.Button(buttons_frame, text="Procesar Videos", command=self.process_videos).pack(side='left', padx=5)
        ttk.Button(buttons_frame, text="Limpiar Log", command=self.clear_log).pack(side='left', padx=5)
        
        # Barra de progreso
        self.progress = ttk.Progressbar(parent, mode='determinate')
        self.progress.pack(fill='x', padx=10, pady=5)
        
        # Log de actividad
        log_frame = ttk.LabelFrame(parent, text="Log de Actividad", padding="5")
        log_frame.pack(fill='both', expand=True, padx=10, pady=5)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=15)
        self.log_text.pack(fill='both', expand=True)
    
    def create_config_tab(self, parent):
        """Crear pestaña de configuración"""
        config_frame = ttk.LabelFrame(parent, text="Configuración de APIs", padding="10")
        config_frame.pack(fill='x', padx=10, pady=5)
        
        # API Keys
        ttk.Label(config_frame, text="TMDB API Key:").grid(row=0, column=0, sticky='w', pady=2)
        self.tmdb_key_var = tk.StringVar(value=self.config_manager.get('tmdb_api_key', ''))
        ttk.Entry(config_frame, textvariable=self.tmdb_key_var, width=50, show='*').grid(row=0, column=1, padx=5, pady=2)
        
        ttk.Label(config_frame, text="TheTVDB API Key:").grid(row=1, column=0, sticky='w', pady=2)
        self.tvdb_key_var = tk.StringVar(value=self.config_manager.get('thetvdb_api_key', ''))
        ttk.Entry(config_frame, textvariable=self.tvdb_key_var, width=50, show='*').grid(row=1, column=1, padx=5, pady=2)
        
        # Configuración avanzada
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
        
        # Botones de configuración
        config_buttons_frame = ttk.Frame(parent)
        config_buttons_frame.pack(fill='x', padx=10, pady=10)
        
        ttk.Button(config_buttons_frame, text="Guardar Configuración", command=self.save_config).pack(side='left', padx=5)
        ttk.Button(config_buttons_frame, text="Probar API TMDB", command=self.test_tmdb_api).pack(side='left', padx=5)
        ttk.Button(config_buttons_frame, text="Cargar Configuración", command=self.load_config_file).pack(side='left', padx=5)
    
    def create_analysis_tab(self, parent):
        """Crear pestaña de análisis"""
        # Frame de estadísticas
        stats_frame = ttk.LabelFrame(parent, text="Estadísticas del Último Análisis", padding="10")
        stats_frame.pack(fill='x', padx=10, pady=5)
        
        self.stats_text = tk.Text(stats_frame, height=10, state='disabled')
        self.stats_text.pack(fill='both', expand=True)
        
        # Frame de vista previa
        preview_frame = ttk.LabelFrame(parent, text="Vista Previa de Análisis", padding="10")
        preview_frame.pack(fill='both', expand=True, padx=10, pady=5)
        
        self.preview_text = scrolledtext.ScrolledText(preview_frame, height=15)
        self.preview_text.pack(fill='both', expand=True)
    
    def create_actors_tab(self, parent):
        """Crear pestaña de gestión de actores"""
        # Frame de información
        info_frame = ttk.LabelFrame(parent, text="Información", padding="10")
        info_frame.pack(fill='x', padx=10, pady=5)
        
        info_text = """Esta sección permite gestionar la base de datos de actores para reconocimiento facial.
        
1. Descarga fotos de actores populares desde TMDB
2. Entrena el modelo de reconocimiento facial
3. Prueba el reconocimiento en videos"""
        
        ttk.Label(info_frame, text=info_text, justify='left').pack(anchor='w')
        
        # Frame de configuración de descarga
        download_config_frame = ttk.LabelFrame(parent, text="Configuración de Descarga", padding="10")
        download_config_frame.pack(fill='x', padx=10, pady=5)
        
        # Número de actores a descargar
        ttk.Label(download_config_frame, text="Número de actores populares:").grid(row=0, column=0, sticky='w', pady=2)
        self.num_actors_var = tk.IntVar(value=30)
        ttk.Spinbox(download_config_frame, from_=10, to=100, textvariable=self.num_actors_var, width=10).grid(row=0, column=1, sticky='w', padx=5, pady=2)
        
        # Número de fotos por actor
        ttk.Label(download_config_frame, text="Fotos por actor:").grid(row=1, column=0, sticky='w', pady=2)
        self.photos_per_actor_var = tk.IntVar(value=3)
        ttk.Spinbox(download_config_frame, from_=1, to=10, textvariable=self.photos_per_actor_var, width=10).grid(row=1, column=1, sticky='w', padx=5, pady=2)
        
        # Frame de acciones
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
        
        # Log específico para actores
        actors_log_frame = ttk.LabelFrame(parent, text="Log de Gestión de Actores", padding="5")
        actors_log_frame.pack(fill='both', expand=True, padx=10, pady=5)
        
        self.actors_log = scrolledtext.ScrolledText(actors_log_frame, height=15)
        self.actors_log.pack(fill='both', expand=True)
    
    # Métodos de navegación de carpetas
    def browse_source_folder(self):
        folder = filedialog.askdirectory(title="Seleccionar carpeta origen")
        if folder:
            self.source_folder.set(folder)
    
    def browse_movies_folder(self):
        folder = filedialog.askdirectory(title="Seleccionar carpeta de películas")
        if folder:
            self.movies_folder.set(folder)
    
    def browse_series_folder(self):
        folder = filedialog.askdirectory(title="Seleccionar carpeta de series")
        if folder:
            self.series_folder.set(folder)
    
    def browse_unknown_folder(self):
        folder = filedialog.askdirectory(title="Seleccionar carpeta de desconocidos")
        if folder:
            self.unknown_folder.set(folder)
    
    def log(self, message, level="INFO"):
        """Agregar mensaje al log"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_message = f"[{timestamp}] {level}: {message}"
        
        self.log_text.insert(tk.END, log_message + "\n")
        self.log_text.see(tk.END)
        self.root.update_idletasks()
        
        # También log a archivo
        if level == "ERROR":
            self.logger.error(message)
        elif level == "WARNING":
            self.logger.warning(message)
        else:
            self.logger.info(message)
    
    def actors_log_message(self, message, level="INFO"):
        """Log específico para actores"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_message = f"[{timestamp}] {level}: {message}"
        
        self.actors_log.insert(tk.END, log_message + "\n")
        self.actors_log.see(tk.END)
        self.root.update_idletasks()
    
    def clear_log(self):
        """Limpiar el log"""
        self.log_text.delete(1.0, tk.END)
    
    def test_tmdb_api(self):
        """Probar conexión con TMDB API"""
        if not self.tmdb_key_var.get():
            messagebox.showerror("Error", "Ingresa tu API Key de TMDB")
            return
        
        # Actualizar cliente TMDB
        self.tmdb_client.api_key = self.tmdb_key_var.get()
        
        if self.tmdb_client.test_connection():
            messagebox.showinfo("Éxito", "Conexión con TMDB exitosa!")
            self.log("API de TMDB funcionando correctamente")
        else:
            messagebox.showerror("Error", "Error conectando con TMDB")
            self.log("Error API TMDB", "ERROR")
    
    def verify_setup(self):
        """Verificar configuración y dependencias"""
        self.log("Verificando configuración...")
        
        issues = []
        
        # Verificar rutas
        if not self.source_folder.get():
            issues.append("Falta carpeta origen")
        
        if not self.movies_folder.get():
            issues.append("Falta carpeta de películas")
        
        if not self.series_folder.get():
            issues.append("Falta carpeta de series")
        
        # Verificar dependencias
        try:
            import cv2
            self.log("OpenCV disponible")
        except ImportError:
            issues.append("OpenCV no encontrado")
        
        try:
            import pytesseract
            self.log("Pytesseract disponible")
        except ImportError:
            issues.append("Pytesseract no encontrado")
        
        try:
            import face_recognition
            self.log("Face Recognition disponible")
        except ImportError:
            issues.append("Face Recognition no encontrado")
        
        # Verificar APIs
        if self.use_tmdb_api.get() and not self.tmdb_key_var.get():
            issues.append("Falta API Key de TMDB")
        
        # Verificar base de datos de actores
        if self.use_facial_recognition.get():
            db_info = self.actors_manager.get_database_info()
            if db_info['actors'] == 0:
                issues.append("Base de datos de actores vacía")
        
        if issues:
            self.log("Problemas encontrados:")
            for issue in issues:
                self.log(f"   {issue}")
        else:
            self.log("Configuración verificada correctamente")
        
    
    def scan_videos(self):
        """Escanear videos en la carpeta origen"""
        if not self.source_folder.get():
            messagebox.showerror("Error", "Selecciona la carpeta origen")
            return
        
        def scan_thread():
            try:
                source_path = Path(self.source_folder.get())
                video_extensions = set(self.config_manager.get('video_extensions', []))
                
                self.log("Iniciando escaneo de videos...")
                
                videos_found = []
                for file_path in source_path.rglob('*'):
                    if file_path.is_file() and file_path.suffix.lower() in video_extensions:
                        videos_found.append(file_path)
                
                self.log(f"Encontrados {len(videos_found)} archivos de video")
                
                # Análisis detallado
                preview_text = "VISTA PREVIA DEL ANÁLISIS\n" + "="*50 + "\n\n"
                
                movies_count = 0
                series_count = 0
                extras_count = 0
                problematic_count = 0
                
                # Analizar muestra de archivos
                for i, video_path in enumerate(videos_found[:20]):
                    video_info = self.video_analyzer.extract_video_info(video_path.name, str(video_path))
                    
                    if video_info:
                        preview_text += f"{i+1}. {video_path.name}\n"
                        preview_text += f"   Tipo: {video_info['type']}\n"
                        preview_text += f"   Título: {video_info['title']}\n"
                        
                        if video_info['type'] == 'movie':
                            movies_count += 1
                            if video_info.get('year'):
                                preview_text += f"   Año: {video_info['year']}\n"
                        elif video_info['type'] == 'series':
                            series_count += 1
                            preview_text += f"   Temporada: {video_info.get('season', 'N/A')}\n"
                            preview_text += f"   Episodio: {video_info.get('episode', 'N/A')}\n"
                        elif video_info['type'] == 'extra':
                            extras_count += 1
                            preview_text += f"   Tipo de extra: {video_info.get('extra_type', 'extra')}\n"
                            preview_text += f"   Serie: {video_info['title']}\n"
                        
                        preview_text += "\n"
                    else:
                        problematic_count += 1
                        preview_text += f"{i+1}. ❌ {video_path.name}\n"
                        preview_text += "   No se pudo extraer información\n\n"
                
                if len(videos_found) > 20:
                    preview_text += f"... y {len(videos_found) - 20} archivos más\n\n"
                
                # Resumen
                preview_text += "RESUMEN\n" + "="*20 + "\n"
                preview_text += f"Películas: {movies_count}\n"
                preview_text += f"Series: {series_count}\n"
                preview_text += f"Extras: {extras_count}\n"
                preview_text += f"Problemáticos: {problematic_count}\n"
                preview_text += f"Total: {len(videos_found)}\n"
                
                self.preview_text.delete(1.0, tk.END)
                self.preview_text.insert(1.0, preview_text)
                
                self.log("Escaneo completado")
                
            except Exception as e:
                self.log(f"Error durante el escaneo: {str(e)}", "ERROR")
        
        threading.Thread(target=scan_thread, daemon=True).start()
    
    def process_videos(self):
        """Procesar y organizar todos los videos"""
        if not all([self.source_folder.get(), self.movies_folder.get(), self.series_folder.get()]):
            messagebox.showerror("Error", "Configura todas las rutas necesarias")
            return
        
        def process_thread():
            try:
                # Configurar organizador con rutas actuales
                paths = {
                    'source': Path(self.source_folder.get()),
                    'movies': Path(self.movies_folder.get()),
                    'series': Path(self.series_folder.get()),
                    'unknown': Path(self.unknown_folder.get()) if self.unknown_folder.get() else None
                }
                
                # Configurar opciones
                options = {
                    'use_tmdb': self.use_tmdb_api.get(),
                    'use_facial_recognition': self.use_facial_recognition.get(),
                    'use_ocr': self.use_ocr_analysis.get(),
                    'strict_matching': self.strict_matching.get(),
                    'move_files': self.move_files.get(),
                    'tmdb_min_score': self.tmdb_score_var.get()
                }
                
                # Actualizar cliente TMDB
                self.tmdb_client.api_key = self.tmdb_key_var.get()
                
                # Procesar videos
                stats = self.file_organizer.process_videos(
                    paths, 
                    options, 
                    self.tmdb_client, 
                    self.video_analyzer,
                    self.progress,
                    self.log
                )
                
                # Mostrar estadísticas
                self.show_processing_stats(stats)
                
                messagebox.showinfo("Completado", 
                                  f"Procesamiento completado:\n"
                                  f"Películas: {stats.get('movies_processed', 0)}\n"
                                  f"Series: {stats.get('series_processed', 0)}\n"
                                  f"Desconocidos: {stats.get('unknown_files', 0)}\n"
                                  f"Errores: {stats.get('errors', 0)}")
                
            except Exception as e:
                self.log(f"Error crítico durante el procesamiento: {str(e)}", "ERROR")
                messagebox.showerror("Error", f"Error durante el procesamiento: {str(e)}")
            finally:
                self.progress['value'] = 0
        
        threading.Thread(target=process_thread, daemon=True).start()
    
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
        
        self.stats_text.configure(state='normal')
        self.stats_text.delete(1.0, tk.END)
        self.stats_text.insert(1.0, stats_text)
        self.stats_text.configure(state='disabled')
    
    def download_popular_actors(self):
        """Descargar actores populares"""
        num_actors = self.num_actors_var.get()
        photos_per_actor = self.photos_per_actor_var.get()
        
        def download_thread():
            success = self.actors_manager.download_popular_actors(num_actors, photos_per_actor)
            if success:
                self.actors_log_message("Descarga completada exitosamente!")
            else:
                self.actors_log_message("Error en la descarga", "ERROR")
        
        threading.Thread(target=download_thread, daemon=True).start()
    
    def download_specific_actor(self):
        """Descargar actor específico"""
        actor_name = simpledialog.askstring("Actor", "Nombre del actor a descargar:")
        if not actor_name:
            return
        
        def download_thread():
            success = self.actors_manager.download_specific_actor(actor_name)
            if success:
                self.actors_log_message(f"Actor {actor_name} descargado exitosamente!")
            else:
                self.actors_log_message(f"Error descargando {actor_name}", "ERROR")
        
        threading.Thread(target=download_thread, daemon=True).start()
    
    def train_face_recognition_model(self):
        """Entrenar modelo de reconocimiento facial"""
        def train_thread():
            success = self.actors_manager.train_face_recognition_model()
            if success:
                # Recargar base de datos en el analizador
                self.video_analyzer.actors_db = self.video_analyzer.load_actors_database()
                self.actors_log_message("Modelo entrenado exitosamente!")
            else:
                self.actors_log_message("Error en el entrenamiento", "ERROR")
        
        threading.Thread(target=train_thread, daemon=True).start()
    
    def test_face_recognition(self):
        """Probar reconocimiento facial en un video"""
        db_info = self.actors_manager.get_database_info()
        if db_info['actors'] == 0:
            messagebox.showwarning("Advertencia", "Base de datos de actores vacía. Entrena el modelo primero.")
            return
        
        video_file = filedialog.askopenfilename(
            title="Seleccionar video para probar",
            filetypes=[("Videos", "*.mp4 *.mkv *.avi *.mov")]
        )
        
        if not video_file:
            return
        
        def test_thread():
            try:
                self.actors_log_message(f"Probando reconocimiento en: {Path(video_file).name}")
                
                analysis_result = self.video_analyzer.analyze_video_with_ai(Path(video_file))
                detected_actors = analysis_result.get('detected_actors', [])
                
                if detected_actors:
                    unique_actors = list(set(detected_actors))
                    self.actors_log_message(f"Actores detectados: {', '.join(unique_actors)}")
                    
                    for actor in unique_actors:
                        count = detected_actors.count(actor)
                        self.actors_log_message(f"   - {actor}: {count} detecciones")
                else:
                    self.actors_log_message("No se detectaron actores conocidos")
                
                self.actors_log_message(f"Confianza del análisis: {analysis_result.get('confidence_score', 0):.2f}")
                
            except Exception as e:
                self.actors_log_message(f"Error en prueba: {str(e)}", "ERROR")
        
        threading.Thread(target=test_thread, daemon=True).start()
    
    def show_actors_database(self):
        """Mostrar información de la base de datos actual"""
        db_info = self.actors_manager.get_database_info()
        
        if db_info['actors'] == 0:
            self.actors_log_message("Base de datos de actores vacía", "WARNING")
            return
        
        self.actors_log_message("BASE DE DATOS DE ACTORES ACTUAL:")
        self.actors_log_message("="*50)
        
        for i, actor_name in enumerate(db_info['actors_list'], 1):
            self.actors_log_message(f"{i:2d}. {actor_name}")
        
        self.actors_log_message("="*50)
        self.actors_log_message(f"Total: {db_info['actors']} actores, {db_info['encodings']} encodings")
    
    def save_config(self):
        """Guardar configuración actual"""
        try:
            config_updates = {
                'tmdb_api_key': self.tmdb_key_var.get(),
                'thetvdb_api_key': self.tvdb_key_var.get(),
                'min_confidence': self.confidence_var.get(),
                'min_tmdb_score': self.tmdb_score_var.get(),
                'capture_frames': self.frames_var.get()
            }
            
            if self.config_manager.save_config(config_updates):
                self.log("Configuración guardada")
                messagebox.showinfo("Éxito", "Configuración guardada correctamente")
            else:
                self.log("Error guardando configuración", "ERROR")
                messagebox.showerror("Error", "Error guardando configuración")
            
        except Exception as e:
            self.log(f"Error guardando configuración: {str(e)}", "ERROR")
            messagebox.showerror("Error", f"Error guardando configuración: {str(e)}")
    
    def load_config_file(self):
        """Cargar configuración desde archivo"""
        config_file = filedialog.askopenfilename(
            title="Seleccionar archivo de configuración",
            filetypes=[("JSON", "*.json")]
        )
        
        if config_file:
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    loaded_config = json.load(f)
                
                self.config_manager.update(loaded_config)
                
                # Actualizar variables de la interfaz
                self.tmdb_key_var.set(self.config_manager.get('tmdb_api_key', ''))
                self.tvdb_key_var.set(self.config_manager.get('thetvdb_api_key', ''))
                self.confidence_var.set(self.config_manager.get('min_confidence', 0.7))
                self.tmdb_score_var.set(self.config_manager.get('min_tmdb_score', 0.8))
                self.frames_var.set(self.config_manager.get('capture_frames', 30))
                
                self.log("Configuración cargada")
                messagebox.showinfo("Éxito", "Configuración cargada correctamente")
                
            except Exception as e:
                self.log(f"Error cargando configuración: {str(e)}", "ERROR")
    def create_jellyfin_tab(self, parent):
        """Crear pestaña de Jellyfin"""
        # Frame de configuración
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
        
        # Botones de acción
        buttons_frame = ttk.Frame(config_frame)
        buttons_frame.grid(row=3, column=0, columnspan=2, pady=10)
        
        ttk.Button(buttons_frame, text="Probar Conexión", command=self.test_jellyfin_connection).pack(side='left', padx=5)
        ttk.Button(buttons_frame, text="Guardar Configuración", command=self.save_jellyfin_config).pack(side='left', padx=5)
        ttk.Button(buttons_frame, text="Obtener Biblioteca", command=self.get_jellyfin_library).pack(side='left', padx=5)
        
        # Frame de acciones
        actions_frame = ttk.LabelFrame(parent, text="Acciones", padding="10")
        actions_frame.pack(fill='x', padx=10, pady=5)
        
        ttk.Button(actions_frame, text="Obtener Actores de Biblioteca", 
                  command=self.get_jellyfin_actors, width=30).pack(pady=5, fill='x')
        ttk.Button(actions_frame, text="Verificar Metadatos Faltantes", 
                  command=self.check_missing_metadata, width=30).pack(pady=5, fill='x')
        ttk.Button(actions_frame, text="Disparar Escaneo de Biblioteca", 
                  command=self.trigger_jellyfin_scan, width=30).pack(pady=5, fill='x')
        
        # Log de Jellyfin
        log_frame = ttk.LabelFrame(parent, text="Log de Jellyfin", padding="5")
        log_frame.pack(fill='both', expand=True, padx=10, pady=5)
        
        self.jellyfin_log = scrolledtext.ScrolledText(log_frame, height=15)
        self.jellyfin_log.pack(fill='both', expand=True)
    
    def create_youtube_tab(self, parent):
        """Crear pestaña de YouTube/Entrenamiento"""
        # Frame de configuración OAuth
        oauth_frame = ttk.LabelFrame(parent, text="Configuración OAuth de Google", padding="10")
        oauth_frame.pack(fill='x', padx=10, pady=5)
        
        ttk.Label(oauth_frame, text="Client ID:").grid(row=0, column=0, sticky='w', pady=2)
        self.youtube_client_id_var = tk.StringVar(value=self.config_manager.get('youtube_client_id', ''))
        ttk.Entry(oauth_frame, textvariable=self.youtube_client_id_var, width=60).grid(row=0, column=1, padx=5, pady=2)
        
        ttk.Label(oauth_frame, text="Client Secret:").grid(row=1, column=0, sticky='w', pady=2)
        self.youtube_client_secret_var = tk.StringVar(value=self.config_manager.get('youtube_client_secret', ''))
        ttk.Entry(oauth_frame, textvariable=self.youtube_client_secret_var, width=60, show='*').grid(row=1, column=1, padx=5, pady=2)
        
        # Botones OAuth
        oauth_buttons_frame = ttk.Frame(oauth_frame)
        oauth_buttons_frame.grid(row=2, column=0, columnspan=2, pady=10)
        
        ttk.Button(oauth_buttons_frame, text="Guardar Credenciales", command=self.save_youtube_credentials).pack(side='left', padx=5)
        ttk.Button(oauth_buttons_frame, text="Iniciar Login con Google", command=self.start_youtube_oauth).pack(side='left', padx=5)
        
        # Frame de entrenamiento automático
        training_frame = ttk.LabelFrame(parent, text="Entrenamiento Automático", padding="10")
        training_frame.pack(fill='x', padx=10, pady=5)
        
        ttk.Label(training_frame, text="Entrenar con trailers desde:").grid(row=0, column=0, sticky='w', pady=2)
        self.training_source_var = tk.StringVar(value="jellyfin")
        ttk.Radiobutton(training_frame, text="Biblioteca Jellyfin", 
                       variable=self.training_source_var, value="jellyfin").grid(row=0, column=1, sticky='w', padx=5)
        ttk.Radiobutton(training_frame, text="Lista personalizada", 
                       variable=self.training_source_var, value="custom").grid(row=0, column=2, sticky='w', padx=5)
        
        ttk.Label(training_frame, text="Calidad de descarga:").grid(row=1, column=0, sticky='w', pady=2)
        self.youtube_quality_var = tk.StringVar(value="480p")
        quality_combo = ttk.Combobox(training_frame, textvariable=self.youtube_quality_var, 
                                   values=["480p", "720p", "1080p"], state="readonly", width=10)
        quality_combo.grid(row=1, column=1, sticky='w', padx=5, pady=2)
        
        # Botones de entrenamiento
        training_buttons_frame = ttk.Frame(training_frame)
        training_buttons_frame.grid(row=2, column=0, columnspan=3, pady=10)
        
        ttk.Button(training_buttons_frame, text="Entrenar con Jellyfin", 
                  command=self.train_with_jellyfin, width=25).pack(side='left', padx=5)
        ttk.Button(training_buttons_frame, text="Entrenar Video Específico", 
                  command=self.train_specific_video, width=25).pack(side='left', padx=5)
        
        # Log de YouTube
        youtube_log_frame = ttk.LabelFrame(parent, text="Log de YouTube/Entrenamiento", padding="5")
        youtube_log_frame.pack(fill='both', expand=True, padx=10, pady=5)
        
        self.youtube_log = scrolledtext.ScrolledText(youtube_log_frame, height=15)
        self.youtube_log.pack(fill='both', expand=True)
    
    def create_audio_tab(self, parent):
        """Crear pestaña de análisis de audio"""
        # Frame de configuración
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
        
        # Opciones
        ttk.Checkbutton(config_frame, text="Habilitar análisis de audio", 
                       variable=tk.BooleanVar(value=self.config_manager.get('enable_audio_analysis', True))).grid(row=2, column=0, sticky='w', pady=2)
        ttk.Checkbutton(config_frame, text="Buscar en OpenSubtitles", 
                       variable=tk.BooleanVar(value=self.config_manager.get('enable_subtitle_search', True))).grid(row=2, column=1, sticky='w', pady=2)
        
        # Botones de configuración
        audio_buttons_frame = ttk.Frame(config_frame)
        audio_buttons_frame.grid(row=3, column=0, columnspan=2, pady=10)
        
        ttk.Button(audio_buttons_frame, text="Guardar Configuración", command=self.save_audio_config).pack(side='left', padx=5)
        ttk.Button(audio_buttons_frame, text="Probar Whisper", command=self.test_whisper).pack(side='left', padx=5)
        
        # Frame de pruebas
        test_frame = ttk.LabelFrame(parent, text="Pruebas de Audio", padding="10")
        test_frame.pack(fill='x', padx=10, pady=5)
        
        ttk.Button(test_frame, text="Analizar Video Individual", 
                  command=self.test_audio_analysis, width=30).pack(pady=5, fill='x')
        ttk.Button(test_frame, text="Buscar en OpenSubtitles", 
                  command=self.test_opensubtitles_search, width=30).pack(pady=5, fill='x')
        
        # Log de audio
        audio_log_frame = ttk.LabelFrame(parent, text="Log de Análisis de Audio", padding="5")
        audio_log_frame.pack(fill='both', expand=True, padx=10, pady=5)
        
        self.audio_log = scrolledtext.ScrolledText(audio_log_frame, height=15)
        self.audio_log.pack(fill='both', expand=True)
    
    def create_conversion_tab(self, parent):
        """Crear pestaña de conversión de video"""
        # Frame de configuración
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
        
        # Opciones
        self.enable_conversion_var = tk.BooleanVar(value=self.config_manager.get('enable_video_conversion', True))
        ttk.Checkbutton(config_frame, text="Habilitar conversión automática", 
                       variable=self.enable_conversion_var).grid(row=3, column=0, columnspan=2, sticky='w', pady=2)
        
        # Botones de configuración
        conv_buttons_frame = ttk.Frame(config_frame)
        conv_buttons_frame.grid(row=4, column=0, columnspan=2, pady=10)
        
        ttk.Button(conv_buttons_frame, text="Guardar Configuración", command=self.save_conversion_config).pack(side='left', padx=5)
        ttk.Button(conv_buttons_frame, text="Verificar FFmpeg", command=self.check_ffmpeg).pack(side='left', padx=5)
        
        # Frame de acciones
        actions_frame = ttk.LabelFrame(parent, text="Acciones de Conversión", padding="10")
        actions_frame.pack(fill='x', padx=10, pady=5)
        
        ttk.Button(actions_frame, text="Convertir Video Individual", 
                  command=self.convert_single_video, width=30).pack(pady=5, fill='x')
        ttk.Button(actions_frame, text="Conversión en Lote", 
                  command=self.batch_convert_videos, width=30).pack(pady=5, fill='x')
        ttk.Button(actions_frame, text="Verificar Videos Corruptos", 
                  command=self.check_video_integrity, width=30).pack(pady=5, fill='x')
        
        # Log de conversión
        conversion_log_frame = ttk.LabelFrame(parent, text="Log de Conversión", padding="5")
        conversion_log_frame.pack(fill='both', expand=True, padx=10, pady=5)
        
        self.conversion_log = scrolledtext.ScrolledText(conversion_log_frame, height=15)
        self.conversion_log.pack(fill='both', expand=True)
    
    # Métodos de logging para las nuevas pestañas
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
    
    def on_closing(self):
        """Guardar configuración al cerrar"""
        # Guardar últimas rutas utilizadas
        self.config_manager.save_last_folders(
            self.source_folder.get(),
            self.movies_folder.get(),
            self.series_folder.get(),
            self.unknown_folder.get()
        )
        
        # Cerrar aplicación
        self.root.destroy()