import os
import re
import shutil
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext, simpledialog
from pathlib import Path
import threading
import requests
import json
import cv2
import pytesseract
import face_recognition
from datetime import datetime
import logging
from tqdm import tqdm
import sqlite3
from PIL import Image, ImageTk
import subprocess
import numpy as np
from urllib.parse import quote
import time

class VideoSortPro:
    def __init__(self, root):
        self.root = root
        self.root.title("VideoSort Pro v2 - Organizador Avanzado para Jellyfin")
        self.root.geometry("1000x700")
        
        # Variables de configuración
        self.config = self.load_config()
        self.source_folder = tk.StringVar()
        self.movies_folder = tk.StringVar()
        self.series_folder = tk.StringVar()
        self.unknown_folder = tk.StringVar()
        
        # Variables de opciones
        self.use_facial_recognition = tk.BooleanVar(value=True)
        self.use_ocr_analysis = tk.BooleanVar(value=True)
        self.use_tmdb_api = tk.BooleanVar(value=True)
        self.analyze_audio = tk.BooleanVar(value=False)
        self.move_files = tk.BooleanVar(value=True)
        self.strict_matching = tk.BooleanVar(value=True)  # Nueva opción
        
        # Setup logging
        self.setup_logging()
        
        # Crear widgets
        self.create_widgets()
        
        # Cargar actores database
        self.actors_db = self.load_actors_database()
        
    def load_config(self):
        """Cargar configuración desde archivo JSON"""
        default_config = {
            "tmdb_api_key": "f98a4a1f467421762760132e1b91df58",
            "thetvdb_api_key": "YOUR_TVDB_API_KEY",
            "video_extensions": [".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".m4v"],
            "max_processes": 4,
            "capture_frames": 30,
            "min_confidence": 0.7,
            "detect_actors": True,
            "detect_studios": True,
            "analyze_audio": False,
            "jellyfin_naming": True,
            "min_tmdb_score": 0.8,  # Puntuación mínima para aceptar resultado TMDB
            "require_metadata": True  # Requiere metadatos para mover archivo
        }
        
        try:
            config_path = Path("config/config.json")
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    loaded_config = json.load(f)
                    default_config.update(loaded_config)
        except Exception as e:
            print(f"Error cargando configuración: {e}")
        
        return default_config
    
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
        
        # Pestaña principal
        main_tab = ttk.Frame(notebook)
        notebook.add(main_tab, text="Organizar Videos")
        
        # Pestaña de configuración
        config_tab = ttk.Frame(notebook)
        notebook.add(config_tab, text="Configuración")
        
        # Pestaña de análisis
        analysis_tab = ttk.Frame(notebook)
        notebook.add(analysis_tab, text="Análisis Avanzado")
        
        # Pestaña de actores
        actors_tab = ttk.Frame(notebook)
        notebook.add(actors_tab, text="Gestión de Actores")
        
        self.create_main_tab(main_tab)
        self.create_config_tab(config_tab)
        self.create_analysis_tab(analysis_tab)
        self.create_actors_tab(actors_tab)
    
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
        self.tmdb_key_var = tk.StringVar(value=self.config.get('tmdb_api_key', ''))
        ttk.Entry(config_frame, textvariable=self.tmdb_key_var, width=50, show='*').grid(row=0, column=1, padx=5, pady=2)
        
        ttk.Label(config_frame, text="TheTVDB API Key:").grid(row=1, column=0, sticky='w', pady=2)
        self.tvdb_key_var = tk.StringVar(value=self.config.get('thetvdb_api_key', ''))
        ttk.Entry(config_frame, textvariable=self.tvdb_key_var, width=50, show='*').grid(row=1, column=1, padx=5, pady=2)
        
        # Configuración avanzada
        advanced_frame = ttk.LabelFrame(parent, text="Configuración Avanzada", padding="10")
        advanced_frame.pack(fill='x', padx=10, pady=5)
        
        ttk.Label(advanced_frame, text="Confianza mínima reconocimiento (0.0-1.0):").grid(row=0, column=0, sticky='w', pady=2)
        self.confidence_var = tk.DoubleVar(value=self.config.get('min_confidence', 0.7))
        confidence_scale = ttk.Scale(advanced_frame, from_=0.0, to=1.0, variable=self.confidence_var, orient='horizontal')
        confidence_scale.grid(row=0, column=1, sticky='ew', padx=5, pady=2)
        
        ttk.Label(advanced_frame, text="Puntuación mínima TMDB (0.0-1.0):").grid(row=1, column=0, sticky='w', pady=2)
        self.tmdb_score_var = tk.DoubleVar(value=self.config.get('min_tmdb_score', 0.8))
        tmdb_scale = ttk.Scale(advanced_frame, from_=0.0, to=1.0, variable=self.tmdb_score_var, orient='horizontal')
        tmdb_scale.grid(row=1, column=1, sticky='ew', padx=5, pady=2)
        
        ttk.Label(advanced_frame, text="Fotogramas a capturar:").grid(row=2, column=0, sticky='w', pady=2)
        self.frames_var = tk.IntVar(value=self.config.get('capture_frames', 30))
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
        
        info_text = """Esta sección te permite gestionar la base de datos de actores para reconocimiento facial.
        
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
        
        try:
            url = f"https://api.themoviedb.org/3/search/movie"
            params = {
                'api_key': self.tmdb_key_var.get(),
                'query': 'Toy Story'
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            if data.get('results'):
                messagebox.showinfo("Éxito", "✅ Conexión con TMDB exitosa!")
                self.log("✅ API de TMDB funcionando correctamente")
            else:
                messagebox.showwarning("Advertencia", "API conectada pero sin resultados")
        
        except Exception as e:
            messagebox.showerror("Error", f"Error conectando con TMDB: {str(e)}")
            self.log(f"❌ Error API TMDB: {str(e)}", "ERROR")
    
    def clean_filename_for_search(self, filename):
        """Limpiar nombre de archivo para búsqueda mejorada"""
        # Remover extensión
        name = Path(filename).stem
        
        # Remover caracteres especiales y patrones comunes
        patterns_to_remove = [
            r'\b(1080p|720p|480p|2160p|4K|HDRip|BRRip|DVDRip|WEBRip|HDTV)\b',
            r'\b(x264|x265|h264|h265|HEVC|AVC)\b',
            r'\b(BluRay|Blu-ray|DVD|WEB-DL|WEBRip)\b',
            r'\[(.*?)\]',  # Texto entre corchetes
            r'\{(.*?)\}',  # Texto entre llaves
            r'\((.*?)\)',  # Texto entre paréntesis (pero mantener años)
            r'[\.\-_]',    # Puntos, guiones, guiones bajos
            r'\s+',        # Múltiples espacios
        ]
        
        # Primero extraer año si existe
        year_match = re.search(r'\b(19|20)\d{2}\b', name)
        year = year_match.group(0) if year_match else None
        
        # Aplicar limpieza
        for pattern in patterns_to_remove[:-2]:  # No aplicar los últimos dos aún
            name = re.sub(pattern, ' ', name, flags=re.IGNORECASE)
        
        # Restaurar año si se encontró
        if year:
            name = f"{name} {year}"
        
        # Aplicar limpieza final
        name = re.sub(r'[\.\-_]', ' ', name)
        name = re.sub(r'\s+', ' ', name).strip()
        
        return name, year
    
    def extract_video_info(self, filename):
        """Extraer información básica del nombre del archivo"""
        # Detectar si es serie o película
        series_patterns = [
            r'[Ss]\d{1,2}[Ee]\d{1,2}',
            r'\d{1,2}x\d{1,2}',
            r'[Tt]emporada\s*\d+',
            r'[Ee]pisode\s*\d+',
        ]
        
        is_series = any(re.search(pattern, filename, re.IGNORECASE) for pattern in series_patterns)
        
        if is_series:
            return self.extract_series_info(filename)
        else:
            return self.extract_movie_info(filename)
    
    def extract_movie_info(self, filename):
        """Extraer información de película con limpieza mejorada"""
        clean_name, year = self.clean_filename_for_search(filename)
        
        return {
            'type': 'movie',
            'title': clean_name,
            'year': year,
            'original_filename': filename,
            'search_title': clean_name  # Título limpio para búsqueda
        }
    
    def extract_series_info(self, filename):
        """Extraer información de serie"""
        name = Path(filename).stem
        
        patterns = [
            r'(.+?)[Ss](\d{1,2})[Ee](\d{1,2})',
            r'(.+?)(\d{1,2})x(\d{1,2})',
            r'(.+?)[Tt]emporada\s*(\d+).*?[Cc]apitulo\s*(\d+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, name, re.IGNORECASE)
            if match:
                series_name = match.group(1).strip()
                season = int(match.group(2))
                episode = int(match.group(3))
                
                # Limpiar nombre de la serie
                clean_name, _ = self.clean_filename_for_search(series_name)
                
                return {
                    'type': 'series',
                    'title': clean_name,
                    'season': season,
                    'episode': episode,
                    'original_filename': filename,
                    'search_title': clean_name
                }
        
        return None
    
    def calculate_title_similarity(self, title1, title2):
        """Calcular similitud entre títulos"""
        title1 = title1.lower().strip()
        title2 = title2.lower().strip()
        
        # Similitud exacta
        if title1 == title2:
            return 1.0
        
        # Similitud de palabras
        words1 = set(title1.split())
        words2 = set(title2.split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        
        return len(intersection) / len(union)
    
    def query_tmdb_api(self, title, year=None, is_series=False):
        """Consultar TMDB API con validación mejorada"""
        if not self.tmdb_key_var.get():
            return None
        
        try:
            base_url = "https://api.themoviedb.org/3"
            endpoint = "/search/tv" if is_series else "/search/movie"
            
            params = {
                'api_key': self.tmdb_key_var.get(),
                'query': title,
                'language': 'es-ES'
            }
            
            if year and not is_series:
                params['year'] = year
            
            self.log(f"🔍 Buscando en TMDB: '{title}' (año: {year})")
            
            response = requests.get(f"{base_url}{endpoint}", params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            if not data.get('results'):
                self.log(f"⚠️ No se encontraron resultados en TMDB para: {title}", "WARNING")
                return None
            
            # Buscar el mejor match
            best_match = None
            best_score = 0
            
            for result in data['results'][:5]:  # Revisar los primeros 5 resultados
                result_title = result.get('title' if not is_series else 'name', '')
                result_original_title = result.get('original_title' if not is_series else 'original_name', '')
                result_year = result.get('release_date' if not is_series else 'first_air_date', '')[:4] if result.get('release_date' if not is_series else 'first_air_date') else ''
                
                # Calcular similitud con el título
                title_similarity = self.calculate_title_similarity(title, result_title)
                original_title_similarity = self.calculate_title_similarity(title, result_original_title)
                
                # Usar la mejor similitud
                similarity = max(title_similarity, original_title_similarity)
                
                # Bonus si el año coincide
                if year and result_year and year == result_year:
                    similarity += 0.2
                
                if similarity > best_score:
                    best_score = similarity
                    best_match = result
            
            # Verificar si la similitud es suficiente
            min_score = self.tmdb_score_var.get()
            if best_score < min_score:
                self.log(f"⚠️ Similitud muy baja ({best_score:.2f} < {min_score:.2f}) para: {title}", "WARNING")
                if self.strict_matching.get():
                    return None
            
            if best_match:
                result_info = {
                    'title': best_match.get('title' if not is_series else 'name'),
                    'original_title': best_match.get('original_title' if not is_series else 'original_name'),
                    'year': best_match.get('release_date' if not is_series else 'first_air_date', '')[:4],
                    'overview': best_match.get('overview'),
                    'tmdb_id': best_match.get('id'),
                    'similarity_score': best_score
                }
                
                self.log(f"✅ Encontrado en TMDB: '{result_info['title']}' (similitud: {best_score:.2f})")
                return result_info
        
        except Exception as e:
            self.log(f"❌ Error consultando TMDB: {str(e)}", "ERROR")
        
        return None
    
    def download_popular_actors(self):
        """Descargar imágenes de actores populares desde TMDB"""
        def download_thread():
            try:
                num_actors = self.num_actors_var.get()
                photos_per_actor = self.photos_per_actor_var.get()
                
                self.actors_log_message(f"🎬 Iniciando descarga de {num_actors} actores populares ({photos_per_actor} fotos por actor)...")
                
                if not self.tmdb_key_var.get():
                    self.actors_log_message("❌ API Key de TMDB no configurada", "ERROR")
                    return
                
                # Crear carpetas necesarias
                actors_dir = Path("data/actors")
                actors_dir.mkdir(parents=True, exist_ok=True)
                
                # Obtener actores populares desde TMDB
                self.actors_log_message("🔍 Obteniendo lista de actores populares desde TMDB...")
                
                popular_actors = []
                
                # Obtener actores populares de múltiples páginas
                for page in range(1, min(6, (num_actors // 20) + 2)):  # Máximo 5 páginas
                    try:
                        url = "https://api.themoviedb.org/3/person/popular"
                        params = {
                            'api_key': self.tmdb_key_var.get(),
                            'page': page
                        }
                        
                        response = requests.get(url, params=params, timeout=10)
                        response.raise_for_status()
                        
                        data = response.json()
                        for person in data.get('results', []):
                            if len(popular_actors) >= num_actors:
                                break
                            
                            if person.get('profile_path'):  # Solo actores con foto
                                popular_actors.append({
                                    'name': person['name'],
                                    'id': person['id'],
                                    'profile_path': person['profile_path'],
                                    'known_for': [item.get('title', item.get('name', '')) for item in person.get('known_for', [])]
                                })
                        
                        if len(popular_actors) >= num_actors:
                            break
                            
                        time.sleep(0.3)  # Evitar rate limiting
                        
                    except Exception as e:
                        self.actors_log_message(f"❌ Error obteniendo página {page}: {str(e)}", "ERROR")
                
                self.actors_log_message(f"✅ Obtenidos {len(popular_actors)} actores de TMDB")
                
                # Descargar fotos para cada actor
                for i, actor in enumerate(popular_actors):
                    try:
                        actor_name = actor['name']
                        self.actors_log_message(f"📥 Descargando: {actor_name} ({i+1}/{len(popular_actors)})")
                        
                        # Crear carpeta del actor
                        actor_folder = actors_dir / actor_name.replace(" ", "_")
                        actor_folder.mkdir(exist_ok=True)
                        
                        # Descargar foto principal
                        profile_url = f"https://image.tmdb.org/api/t/p/w500{actor['profile_path']}"
                        img_response = requests.get(profile_url, timeout=15)
                        img_response.raise_for_status()
                        
                        image_path = actor_folder / "profile.jpg"
                        with open(image_path, 'wb') as f:
                            f.write(img_response.content)
                        
                        photos_downloaded = 1
                        
                        # Descargar fotos adicionales si se solicita
                        if photos_per_actor > 1:
                            try:
                                # Obtener más fotos del actor
                                images_url = f"https://api.themoviedb.org/3/person/{actor['id']}/images"
                                params = {'api_key': self.tmdb_key_var.get()}
                                
                                img_response = requests.get(images_url, params=params, timeout=10)
                                img_response.raise_for_status()
                                
                                images_data = img_response.json()
                                profiles = images_data.get('profiles', [])
                                
                                for j, profile in enumerate(profiles[:photos_per_actor-1]):
                                    try:
                                        additional_url = f"https://image.tmdb.org/api/t/p/w500{profile['file_path']}"
                                        additional_response = requests.get(additional_url, timeout=15)
                                        additional_response.raise_for_status()
                                        
                                        additional_path = actor_folder / f"photo_{j+2}.jpg"
                                        with open(additional_path, 'wb') as f:
                                            f.write(additional_response.content)
                                        
                                        photos_downloaded += 1
                                        time.sleep(0.2)
                                        
                                    except Exception as e:
                                        self.actors_log_message(f"⚠️ Error descargando foto adicional {j+2} de {actor_name}: {str(e)}", "WARNING")
                            
                            except Exception as e:
                                self.actors_log_message(f"⚠️ Error obteniendo fotos adicionales de {actor_name}: {str(e)}", "WARNING")
                        
                        self.actors_log_message(f"✅ {actor_name}: {photos_downloaded} fotos descargadas")
                        time.sleep(0.5)  # Evitar rate limiting
                        
                    except Exception as e:
                        self.actors_log_message(f"❌ Error descargando {actor.get('name', 'desconocido')}: {str(e)}", "ERROR")
                
                self.actors_log_message("🎉 Descarga de actores completada!")
                self.actors_log_message(f"📊 Total descargado: {len(popular_actors)} actores")
                
            except Exception as e:
                self.actors_log_message(f"❌ Error en descarga masiva: {str(e)}", "ERROR")
        
        threading.Thread(target=download_thread, daemon=True).start()
                        self.actors_log_message(f"Descargando: {actor_name}")
                        
                        # Buscar actor en TMDB
                        search_url = "https://api.themoviedb.org/3/search/person"
                        params = {
                            'api_key': self.tmdb_key_var.get(),
                            'query': actor_name
                        }
                        
                        response = requests.get(search_url, params=params, timeout=10)
                        response.raise_for_status()
                        
                        data = response.json()
                        if not data.get('results'):
                            self.actors_log_message(f"⚠️ No encontrado: {actor_name}", "WARNING")
                            continue
                        
                        actor = data['results'][0]
                        profile_path = actor.get('profile_path')
                        
                        if not profile_path:
                            self.actors_log_message(f"⚠️ Sin imagen: {actor_name}", "WARNING")
                            continue
                        
                        # Descargar imagen
                        image_url = f"https://image.tmdb.org/api/t/p/w500{profile_path}"
                        img_response = requests.get(image_url, timeout=15)
                        img_response.raise_for_status()
                        
                        # Guardar imagen
                        actor_folder = actors_dir / actor_name.replace(" ", "_")
                        actor_folder.mkdir(exist_ok=True)
                        
                        image_path = actor_folder / "profile.jpg"
                        with open(image_path, 'wb') as f:
                            f.write(img_response.content)
                        
                        self.actors_log_message(f"✅ Descargado: {actor_name}")
                        time.sleep(0.5)  # Evitar rate limiting
                        
                    except Exception as e:
                        self.actors_log_message(f"❌ Error descargando {actor_name}: {str(e)}", "ERROR")
                
                self.actors_log_message("🎉 Descarga de actores completada!")
                
            except Exception as e:
                self.actors_log_message(f"❌ Error en descarga masiva: {str(e)}", "ERROR")
        
        threading.Thread(target=download_thread, daemon=True).start()
    
    def download_specific_actor(self):
        """Descargar actor específico"""
        actor_name = tk.simpledialog.askstring("Actor", "Nombre del actor a descargar:")
        if not actor_name:
            return
        
        def download_thread():
            try:
                self.actors_log_message(f"🎬 Descargando actor: {actor_name}")
                
                if not self.tmdb_key_var.get():
                    self.actors_log_message("❌ API Key de TMDB no configurada", "ERROR")
                    return
                
                # Crear carpeta
                actors_dir = Path("data/actors")
                actors_dir.mkdir(parents=True, exist_ok=True)
                
                # Buscar en TMDB
                search_url = "https://api.themoviedb.org/3/search/person"
                params = {
                    'api_key': self.tmdb_key_var.get(),
                    'query': actor_name
                }
                
                response = requests.get(search_url, params=params, timeout=10)
                response.raise_for_status()
                
                data = response.json()
                if not data.get('results'):
                    self.actors_log_message(f"❌ Actor no encontrado: {actor_name}", "ERROR")
                    return
                
                # Mostrar opciones si hay múltiples resultados
                if len(data['results']) > 1:
                    options = []
                    for i, person in enumerate(data['results'][:5]):
                        known_for = ", ".join([movie.get('title', movie.get('name', '')) for movie in person.get('known_for', [])[:2]])
                        options.append(f"{person['name']} - {known_for}")
                    
                    choice = tk.messagebox.askyesno("Múltiples resultados", 
                                                  f"Se encontraron varios actores. ¿Descargar el primero?\n\n{options[0]}")
                    if not choice:
                        return
                
                actor = data['results'][0]
                profile_path = actor.get('profile_path')
                
                if not profile_path:
                    self.actors_log_message(f"❌ Sin imagen disponible para: {actor['name']}", "ERROR")
                    return
                
                # Descargar imagen
                image_url = f"https://image.tmdb.org/api/t/p/w500{profile_path}"
                img_response = requests.get(image_url, timeout=15)
                img_response.raise_for_status()
                
                # Guardar imagen
                actor_folder = actors_dir / actor['name'].replace(" ", "_")
                actor_folder.mkdir(exist_ok=True)
                
                image_path = actor_folder / "profile.jpg"
                with open(image_path, 'wb') as f:
                    f.write(img_response.content)
                
                self.actors_log_message(f"✅ Actor descargado: {actor['name']}")
                
            except Exception as e:
                self.actors_log_message(f"❌ Error descargando actor: {str(e)}", "ERROR")
        
        threading.Thread(target=download_thread, daemon=True).start()
    
    def train_face_recognition_model(self):
        """Entrenar modelo de reconocimiento facial"""
        def train_thread():
            try:
                self.actors_log_message("🤖 Iniciando entrenamiento del modelo...")
                
                actors_dir = Path("data/actors")
                if not actors_dir.exists():
                    self.actors_log_message("❌ Carpeta de actores no existe. Descarga actores primero.", "ERROR")
                    return
                
                actors_db = {}
                total_actors = 0
                successful_encodings = 0
                
                # Procesar cada actor
                for actor_folder in actors_dir.iterdir():
                    if not actor_folder.is_dir():
                        continue
                    
                    actor_name = actor_folder.name.replace("_", " ")
                    self.actors_log_message(f"Procesando: {actor_name}")
                    
                    # Buscar imágenes en la carpeta del actor
                    image_files = list(actor_folder.glob("*.jpg")) + list(actor_folder.glob("*.png"))
                    
                    if not image_files:
                        self.actors_log_message(f"⚠️ Sin imágenes para: {actor_name}", "WARNING")
                        continue
                    
                    encodings = []
                    
                    for image_file in image_files:
                        try:
                            # Cargar imagen
                            image = face_recognition.load_image_file(str(image_file))
                            
                            # Detectar caras
                            face_locations = face_recognition.face_locations(image)
                            
                            if not face_locations:
                                self.actors_log_message(f"⚠️ Sin caras detectadas en: {image_file.name}", "WARNING")
                                continue
                            
                            # Obtener encodings
                            face_encodings = face_recognition.face_encodings(image, face_locations)
                            
                            if face_encodings:
                                encodings.extend(face_encodings)
                                self.actors_log_message(f"✅ Encoding generado para: {actor_name}")
                            
                        except Exception as e:
                            self.actors_log_message(f"❌ Error procesando {image_file.name}: {str(e)}", "ERROR")
                    
                    if encodings:
                        # Convertir a lista para JSON
                        actors_db[actor_name] = [encoding.tolist() for encoding in encodings]
                        successful_encodings += len(encodings)
                        total_actors += 1
                        self.actors_log_message(f"✅ {actor_name}: {len(encodings)} encodings")
                    else:
                        self.actors_log_message(f"❌ Sin encodings válidos para: {actor_name}", "ERROR")
                
                # Guardar base de datos
                if actors_db:
                    db_path = Path("data/actors_db.json")
                    with open(db_path, 'w', encoding='utf-8') as f:
                        json.dump(actors_db, f, indent=2, ensure_ascii=False)
                    
                    self.actors_log_message(f"🎉 Modelo entrenado exitosamente!")
                    self.actors_log_message(f"📊 Estadísticas:")
                    self.actors_log_message(f"   - Actores procesados: {total_actors}")
                    self.actors_log_message(f"   - Encodings generados: {successful_encodings}")
                    self.actors_log_message(f"   - Base de datos guardada en: {db_path}")
                    
                    # Recargar base de datos
                    self.actors_db = self.load_actors_database()
                    
                else:
                    self.actors_log_message("❌ No se generaron encodings válidos", "ERROR")
                
            except Exception as e:
                self.actors_log_message(f"❌ Error en entrenamiento: {str(e)}", "ERROR")
        
        threading.Thread(target=train_thread, daemon=True).start()
    
    def load_actors_database(self):
        """Cargar base de datos de actores conocidos"""
        try:
            actors_db_path = Path("data/actors_db.json")
            if actors_db_path.exists():
                with open(actors_db_path, 'r', encoding='utf-8') as f:
                    actors_data = json.load(f)
                
                # Convertir encodings de lista a numpy arrays
                actors_db = {}
                for actor_name, encodings_list in actors_data.items():
                    actors_db[actor_name] = [np.array(encoding) for encoding in encodings_list]
                
                self.log(f"✅ Base de datos de actores cargada: {len(actors_db)} actores")
                return actors_db
            else:
                self.log("⚠️ Base de datos de actores no encontrada", "WARNING")
                return {}
        
        except Exception as e:
            self.log(f"❌ Error cargando base de datos de actores: {str(e)}", "ERROR")
            return {}
    
    def show_actors_database(self):
        """Mostrar información de la base de datos actual"""
        if not self.actors_db:
            self.actors_log_message("❌ Base de datos de actores vacía", "WARNING")
            return
        
        self.actors_log_message("📊 BASE DE DATOS DE ACTORES ACTUAL:")
        self.actors_log_message("="*50)
        
        total_encodings = 0
        for actor_name, encodings in self.actors_db.items():
            encoding_count = len(encodings)
            total_encodings += encoding_count
            self.actors_log_message(f"👤 {actor_name}: {encoding_count} encodings")
        
        self.actors_log_message("="*50)
        self.actors_log_message(f"📈 Total: {len(self.actors_db)} actores, {total_encodings} encodings")
    
    def test_face_recognition(self):
        """Probar reconocimiento facial en un video"""
        if not self.actors_db:
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
                self.actors_log_message(f"🎬 Probando reconocimiento en: {Path(video_file).name}")
                
                # Analizar video
                analysis_result = self.analyze_video_with_ai(Path(video_file))
                
                detected_actors = analysis_result.get('detected_actors', [])
                
                if detected_actors:
                    unique_actors = list(set(detected_actors))
                    self.actors_log_message(f"🎭 Actores detectados: {', '.join(unique_actors)}")
                    
                    # Mostrar estadísticas
                    for actor in unique_actors:
                        count = detected_actors.count(actor)
                        self.actors_log_message(f"   - {actor}: {count} detecciones")
                else:
                    self.actors_log_message("❌ No se detectaron actores conocidos")
                
                self.actors_log_message(f"📊 Confianza del análisis: {analysis_result.get('confidence_score', 0):.2f}")
                
            except Exception as e:
                self.actors_log_message(f"❌ Error en prueba: {str(e)}", "ERROR")
        
        threading.Thread(target=test_thread, daemon=True).start()
    
    def detect_actors_in_frame(self, frame):
        """Detectar actores en un fotograma"""
        detected_actors = []
        
        if not self.actors_db:
            return detected_actors
        
        try:
            # Convertir BGR a RGB
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # Detectar caras
            face_locations = face_recognition.face_locations(rgb_frame)
            if not face_locations:
                return detected_actors
            
            face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)
            
            for face_encoding in face_encodings:
                best_match = None
                best_distance = float('inf')
                
                # Comparar con base de datos de actores
                for actor_name, known_encodings in self.actors_db.items():
                    for known_encoding in known_encodings:
                        distance = face_recognition.face_distance([known_encoding], face_encoding)[0]
                        
                        if distance < best_distance:
                            best_distance = distance
                            best_match = actor_name
                
                # Verificar si la distancia es aceptable
                tolerance = 1.0 - self.confidence_var.get()  # Convertir confianza a tolerancia
                if best_match and best_distance < tolerance:
                    detected_actors.append(best_match)
        
        except Exception as e:
            self.log(f"❌ Error en reconocimiento facial: {str(e)}", "ERROR")
        
        return detected_actors
    
    def analyze_video_with_ai(self, file_path):
        """Análisis avanzado con IA (reconocimiento facial, OCR, etc.)"""
        analysis_result = {
            'detected_actors': [],
            'extracted_text': [],
            'studio_logos': [],
            'confidence_score': 0.0
        }
        
        try:
            # Capturar fotogramas
            cap = cv2.VideoCapture(str(file_path))
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            frames_to_capture = min(self.frames_var.get(), total_frames)
            
            if frames_to_capture == 0:
                return analysis_result
            
            for i in range(frames_to_capture):
                frame_pos = int((i / frames_to_capture) * total_frames)
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_pos)
                ret, frame = cap.read()
                
                if not ret:
                    continue
                
                # Reconocimiento facial
                if self.use_facial_recognition.get():
                    actors = self.detect_actors_in_frame(frame)
                    analysis_result['detected_actors'].extend(actors)
                
                # OCR para texto
                if self.use_ocr_analysis.get():
                    text = self.extract_text_from_frame(frame)
                    if text:
                        analysis_result['extracted_text'].append(text)
            
            cap.release()
            
            # Calcular confianza basada en múltiples factores
            analysis_result['confidence_score'] = self.calculate_confidence_score(analysis_result)
            
        except Exception as e:
            self.log(f"❌ Error en análisis de video: {str(e)}", "ERROR")
        
        return analysis_result
    
    def extract_text_from_frame(self, frame):
        """Extraer texto de un fotograma usando OCR"""
        try:
            # Convertir a escala de grises para mejor OCR
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            # Mejorar contraste
            gray = cv2.convertScaleAbs(gray, alpha=1.5, beta=0)
            
            # Extraer texto
            text = pytesseract.image_to_string(gray, lang='spa+eng')
            return text.strip()
        
        except Exception as e:
            return ""
    
    def calculate_confidence_score(self, analysis_result):
        """Calcular puntuación de confianza del análisis"""
        score = 0.0
        
        # Puntos por actores detectados
        if analysis_result['detected_actors']:
            score += 0.4
        
        # Puntos por texto extraído
        if analysis_result['extracted_text']:
            score += 0.3
        
        # Puntos por logos de estudio
        if analysis_result['studio_logos']:
            score += 0.3
        
        return min(score, 1.0)
    
    def create_jellyfin_structure(self, video_info, dest_base_path):
        """Crear estructura de carpetas según convenciones de Jellyfin"""
        try:
            if video_info['type'] == 'movie':
                # Estructura para películas: Movies/Título (Año)/
                title = video_info['title']
                year = video_info.get('year', '')
                
                if year:
                    folder_name = f"{title} ({year})"
                else:
                    folder_name = title
                
                # Limpiar caracteres no válidos
                folder_name = re.sub(r'[<>:"/\\|?*]', '', folder_name)
                movie_folder = dest_base_path / folder_name
                movie_folder.mkdir(parents=True, exist_ok=True)
                
                return movie_folder
            
            elif video_info['type'] == 'series':
                # Estructura para series: Shows/Serie (Año)/Season XX/
                title = video_info['title']
                season = video_info['season']
                
                # Limpiar caracteres no válidos
                clean_title = re.sub(r'[<>:"/\\|?*]', '', title)
                
                series_folder = dest_base_path / clean_title
                season_folder = series_folder / f"Season {season:02d}"
                season_folder.mkdir(parents=True, exist_ok=True)
                
                return season_folder
        
        except Exception as e:
            self.log(f"❌ Error creando estructura: {str(e)}", "ERROR")
            return None
    
    def generate_jellyfin_filename(self, video_info, original_filename):
        """Generar nombre de archivo según convenciones de Jellyfin"""
        extension = Path(original_filename).suffix
        
        if video_info['type'] == 'movie':
            title = video_info['title']
            year = video_info.get('year', '')
            
            if year:
                filename = f"{title} ({year}){extension}"
            else:
                filename = f"{title}{extension}"
        
        elif video_info['type'] == 'series':
            title = video_info['title']
            season = video_info['season']
            episode = video_info['episode']
            
            filename = f"{title} - S{season:02d}E{episode:02d}{extension}"
        
        else:
            filename = original_filename
        
        # Limpiar caracteres no válidos
        filename = re.sub(r'[<>:"/\\|?*]', '', filename)
        return filename
    
    def verify_setup(self):
        """Verificar configuración y dependencias"""
        self.log("🔍 Verificando configuración...")
        
        issues = []
        
        # Verificar rutas
        if not self.source_folder.get():
            issues.append("❌ Falta carpeta origen")
        
        if not self.movies_folder.get():
            issues.append("⚠️ Falta carpeta de películas")
        
        if not self.series_folder.get():
            issues.append("⚠️ Falta carpeta de series")
        
        # Verificar dependencias
        try:
            import cv2
            self.log("✅ OpenCV disponible")
        except ImportError:
            issues.append("❌ OpenCV no encontrado")
        
        try:
            import pytesseract
            self.log("✅ Pytesseract disponible")
        except ImportError:
            issues.append("❌ Pytesseract no encontrado")
        
        try:
            import face_recognition
            self.log("✅ Face Recognition disponible")
        except ImportError:
            issues.append("❌ Face Recognition no encontrado")
        
        # Verificar APIs
        if self.use_tmdb_api.get() and not self.tmdb_key_var.get():
            issues.append("⚠️ Falta API Key de TMDB")
        
        # Verificar base de datos de actores
        if self.use_facial_recognition.get() and not self.actors_db:
            issues.append("⚠️ Base de datos de actores vacía")
        
        if issues:
            self.log("⚠️ Problemas encontrados:")
            for issue in issues:
                self.log(f"   {issue}")
        else:
            self.log("✅ Configuración verificada correctamente")
        
        return len(issues) == 0
    
    def scan_videos(self):
        """Escanear videos en la carpeta origen con análisis mejorado y validación visual"""
        if not self.source_folder.get():
            messagebox.showerror("Error", "Selecciona la carpeta origen")
            return
        
        def scan_thread():
            try:
                source_path = Path(self.source_folder.get())
                video_extensions = set(self.config['video_extensions'])
                
                self.log("🔍 Iniciando escaneo avanzado de videos...")
                
                videos_found = []
                for file_path in source_path.rglob('*'):
                    if file_path.is_file() and file_path.suffix.lower() in video_extensions:
                        videos_found.append(file_path)
                
                self.log(f"📁 Encontrados {len(videos_found)} archivos de video")
                
                # Configurar barra de progreso para el escaneo
                self.progress.configure(mode='determinate', maximum=min(len(videos_found), 20))
                
                # Análisis detallado con validación visual
                preview_text = "ESCANEO AVANZADO CON VALIDACIÓN VISUAL\n" + "="*70 + "\n\n"
                
                movies_count = 0
                series_count = 0
                problematic_count = 0
                validated_count = 0
                
                # Analizar primeros videos con mayor detalle
                sample_videos = videos_found[:20]  # Analizar primeros 20 para el escaneo
                
                for i, video_path in enumerate(sample_videos):
                    try:
                        self.progress['value'] = i + 1
                        self.root.update_idletasks()
                        
                        video_info = self.extract_video_info(video_path.name)
                        
                        if video_info:
                            preview_text += f"{i+1}. 📁 {video_path.name}\n"
                            preview_text += f"   🏷️  Título detectado: {video_info['title']}\n"
                            
                            # Análisis de calidad del nombre
                            clean_name, year = self.clean_filename_for_search(video_path.name)
                            if clean_name != video_info['title']:
                                preview_text += f"   🧹 Título limpio: {clean_name}\n"
                            
                            # Análisis visual con fotogramas (solo para archivos problemáticos)
                            visual_analysis = None
                            needs_visual_validation = False
                            
                            if video_info['type'] == 'movie':
                                movies_count += 1
                                if video_info.get('year'):
                                    preview_text += f"   📅 Año: {video_info['year']}\n"
                                else:
                                    preview_text += f"   ⚠️  Sin año detectado\n"
                                    needs_visual_validation = True
                                
                                # Verificar si el nombre es muy corto o problemático
                                if len(video_info['title'].split()) < 2:
                                    needs_visual_validation = True
                                    preview_text += f"   🔍 Nombre corto - Requiere validación visual\n"
                            
                            elif video_info['type'] == 'series':
                                series_count += 1
                                preview_text += f"   📺 Temporada: {video_info.get('season', 'N/A')}\n"
                                preview_text += f"   📺 Episodio: {video_info.get('episode', 'N/A')}\n"
                            
                            # Realizar análisis visual si es necesario
                            if needs_visual_validation and i < 5:  # Solo los primeros 5 archivos problemáticos
                                try:
                                    self.log(f"🔍 Análisis visual de: {video_path.name}")
                                    visual_analysis = self.perform_visual_analysis(video_path)
                                    
                                    if visual_analysis:
                                        preview_text += f"   👁️  Análisis Visual:\n"
                                        if visual_analysis.get('detected_text'):
                                            preview_text += f"      📝 Texto detectado: {visual_analysis['detected_text'][:100]}...\n"
                                        if visual_analysis.get('google_search_suggestion'):
                                            preview_text += f"      🌐 Sugerencia de búsqueda: {visual_analysis['google_search_suggestion']}\n"
                                        if visual_analysis.get('actors'):
                                            preview_text += f"      🎭 Actores detectados: {', '.join(visual_analysis['actors'])}\n"
                                        validated_count += 1
                                
                                except Exception as e:
                                    preview_text += f"   ❌ Error en análisis visual: {str(e)}\n"
                            
                            # Predicción de éxito en TMDB
                            if self.use_tmdb_api.get() and video_info['type'] == 'movie':
                                title_words = len(video_info['title'].split())
                                if title_words >= 3 and video_info.get('year'):
                                    preview_text += f"   🎯 Probabilidad TMDB: ⭐⭐⭐ Alta\n"
                                elif title_words >= 2:
                                    preview_text += f"   🎯 Probabilidad TMDB: ⭐⭐ Media\n"
                                else:
                                    preview_text += f"   🎯 Probabilidad TMDB: ⭐ Baja\n"
                            
                            # Simulación de consulta TMDB (solo para los primeros 3)
                            if self.use_tmdb_api.get() and i < 3:
                                try:
                                    self.log(f"🔍 Validando en TMDB: {video_info['title']}")
                                    tmdb_result = self.query_tmdb_api(
                                        video_info['search_title'],
                                        video_info.get('year'),
                                        video_info['type'] == 'series'
                                    )
                                    
                                    if tmdb_result:
                                        preview_text += f"   ✅ TMDB: '{tmdb_result['title']}' (similitud: {tmdb_result['similarity_score']:.2f})\n"
                                        validated_count += 1
                                    else:
                                        preview_text += f"   ❌ TMDB: No encontrado\n"
                                        
                                        # Sugerir búsqueda alternativa
                                        if visual_analysis and visual_analysis.get('google_search_suggestion'):
                                            preview_text += f"   💡 Prueba buscar: {visual_analysis['google_search_suggestion']}\n"
                                
                                except Exception as e:
                                    preview_text += f"   ⚠️ Error validando TMDB: {str(e)}\n"
                            
                            preview_text += "\n"
                            
                        else:
                            problematic_count += 1
                            preview_text += f"{i+1}. ❌ {video_path.name}\n"
                            preview_text += f"   🚫 No se pudo extraer información\n"
                            
                            # Análisis visual para archivos problemáticos
                            if i < 3:  # Solo los primeros 3 problemáticos
                                try:
                                    self.log(f"🔍 Análisis visual de archivo problemático: {video_path.name}")
                                    visual_analysis = self.perform_visual_analysis(video_path)
                                    
                                    if visual_analysis:
                                        if visual_analysis.get('google_search_suggestion'):
                                            preview_text += f"   🌐 Posible título: {visual_analysis['google_search_suggestion']}\n"
                                        if visual_analysis.get('detected_text'):
                                            preview_text += f"   📝 Texto encontrado: {visual_analysis['detected_text'][:50]}...\n"
                                
                                except Exception as e:
                                    preview_text += f"   ❌ Error en análisis: {str(e)}\n"
                            
                            preview_text += "\n"
                    
                    except Exception as e:
                        self.log(f"❌ Error analizando {video_path.name}: {str(e)}", "ERROR")
                        problematic_count += 1
                
                if len(videos_found) > 20:
                    preview_text += f"... y {len(videos_found) - 20} archivos más\n\n"
                
                # Resumen mejorado
                preview_text += "RESUMEN DEL ESCANEO AVANZADO\n" + "="*40 + "\n"
                preview_text += f"🎬 Películas detectadas: {movies_count}\n"
                preview_text += f"📺 Series detectadas: {series_count}\n"
                preview_text += f"⚠️  Archivos problemáticos: {problematic_count}\n"
                preview_text += f"👁️  Validados visualmente: {validated_count}\n"
                preview_text += f"📊 Total de archivos: {len(videos_found)}\n\n"
                
                if problematic_count > 0:
                    preview_text += "💡 RECOMENDACIONES:\n"
                    preview_text += "- Revisa los archivos problemáticos\n"
                    preview_text += "- El análisis visual puede ayudar con títulos no detectados\n"
                    preview_text += "- Usa la opción 'Solo mover si encuentra metadatos' para mayor precisión\n"
                    preview_text += "- Los archivos con análisis visual tienen mayor probabilidad de éxito\n"
                
                self.preview_text.delete(1.0, tk.END)
                self.preview_text.insert(1.0, preview_text)
                
                self.progress['value'] = 0
                self.log("✅ Escaneo avanzado completado")
                
            except Exception as e:
                self.log(f"❌ Error durante el escaneo: {str(e)}", "ERROR")
                self.progress['value'] = 0
        
        threading.Thread(target=scan_thread, daemon=True).start()
    
    def search_google_images_for_movie(self, search_query):
        """Buscar en Google Imágenes para identificar película"""
        try:
            # Esta función simula una búsqueda en Google Images
            # En una implementación real, podrías usar la Google Custom Search API
            # o servicios como SerpAPI
            
            self.log(f"🌐 Buscando en Google: '{search_query}'")
            
            # Simulación de búsqueda (en implementación real usar Google Custom Search API)
            search_url = f"https://www.google.com/search?q={quote(search_query + ' movie film')}&tbm=isch"
            
            # Por ahora, generar sugerencia basada en el texto
            suggestions = {
                'search_url': search_url,
                'suggested_queries': [
                    f"{search_query} movie",
                    f"{search_query} film",
                    f"{search_query} película",
                    f"what movie is {search_query}"
                ]
            }
            
            return suggestions
            
        except Exception as e:
            self.log(f"❌ Error en búsqueda Google: {str(e)}", "ERROR")
            return None
    
    def perform_visual_analysis(self, video_path):
        """Realizar análisis visual de un video para extraer información"""
        try:
            analysis_result = {
                'detected_text': '',
                'actors': [],
                'google_search_suggestion': '',
                'confidence': 0.0
            }
            
            # Capturar fotogramas estratégicos
            cap = cv2.VideoCapture(str(video_path))
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            
            if total_frames == 0:
                return None
            
            # Fotogramas estratégicos: inicio, 10%, 50%, 90%
            strategic_frames = [
                int(total_frames * 0.05),   # 5% - títulos iniciales
                int(total_frames * 0.1),    # 10% - créditos iniciales
                int(total_frames * 0.5),    # 50% - contenido principal
                int(total_frames * 0.9)     # 90% - créditos finales
            ]
            
            all_text = []
            detected_actors = []
            
            for frame_pos in strategic_frames:
                try:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_pos)
                    ret, frame = cap.read()
                    
                    if not ret:
                        continue
                    
                    # OCR para texto
                    if self.use_ocr_analysis.get():
                        text = self.extract_text_from_frame(frame)
                        if text and len(text.strip()) > 3:
                            all_text.append(text.strip())
                    
                    # Reconocimiento facial
                    if self.use_facial_recognition.get() and self.actors_db:
                        actors = self.detect_actors_in_frame(frame)
                        detected_actors.extend(actors)
                
                except Exception as e:
                    continue
            
            cap.release()
            
            # Procesar texto extraído
            if all_text:
                # Unir todo el texto
                combined_text = ' '.join(all_text)
                analysis_result['detected_text'] = combined_text
                
                # Generar sugerencia de búsqueda
                search_suggestion = self.generate_search_suggestion(combined_text)
                analysis_result['google_search_suggestion'] = search_suggestion
            
            # Procesar actores detectados
            if detected_actors:
                unique_actors = list(set(detected_actors))
                analysis_result['actors'] = unique_actors
                
                # Si hay actores conocidos, usar para mejorar búsqueda
                if not analysis_result['google_search_suggestion'] and unique_actors:
                    main_actor = max(set(detected_actors), key=detected_actors.count)
                    analysis_result['google_search_suggestion'] = f"película {main_actor}"
            
            # Calcular confianza
            confidence = 0.0
            if analysis_result['detected_text']:
                confidence += 0.5
            if analysis_result['actors']:
                confidence += 0.3
            if analysis_result['google_search_suggestion']:
                confidence += 0.2
            
            analysis_result['confidence'] = confidence
            
            return analysis_result if confidence > 0.3 else None
            
        except Exception as e:
            self.log(f"❌ Error en análisis visual: {str(e)}", "ERROR")
            return None
    
    def enhanced_search_with_visual_data(self, video_info, visual_analysis):
        """Búsqueda mejorada usando datos visuales cuando TMDB falla"""
        try:
            if not visual_analysis:
                return None
            
            # Intentar búsquedas alternativas
            search_attempts = []
            
            # 1. Usar sugerencia de búsqueda visual
            if visual_analysis.get('google_search_suggestion'):
                search_attempts.append(visual_analysis['google_search_suggestion'])
            
            # 2. Usar actores detectados
            if visual_analysis.get('actors'):
                main_actor = visual_analysis['actors'][0]
                search_attempts.append(f"movie {main_actor}")
                search_attempts.append(f"film {main_actor}")
            
            # 3. Usar texto extraído directamente
            if visual_analysis.get('detected_text'):
                # Extraer posibles títulos del texto
                text = visual_analysis['detected_text']
                possible_titles = self.extract_possible_titles_from_text(text)
                search_attempts.extend(possible_titles)
            
            # Intentar cada búsqueda
            for search_query in search_attempts:
                if len(search_query.strip()) < 3:
                    continue
                
                self.log(f"🔍 Búsqueda alternativa: '{search_query}'")
                
                # Intentar en TMDB con el nuevo query
                tmdb_result = self.query_tmdb_api(search_query, None, False)
                if tmdb_result and tmdb_result.get('similarity_score', 0) > 0.5:
                    self.log(f"✅ Encontrado con búsqueda alternativa: {tmdb_result['title']}")
                    return tmdb_result
                
                time.sleep(0.5)  # Evitar rate limiting
            
            # Si no encuentra nada, generar información básica
            fallback_info = {
                'title': visual_analysis.get('google_search_suggestion', video_info.get('title', 'Unknown')),
                'search_suggestion': visual_analysis.get('google_search_suggestion'),
                'detected_actors': visual_analysis.get('actors', []),
                'confidence_score': visual_analysis.get('confidence', 0),
                'needs_manual_review': True
            }
            
            return fallback_info
            
        except Exception as e:
            self.log(f"❌ Error en búsqueda mejorada: {str(e)}", "ERROR")
            return None
    
    def extract_possible_titles_from_text(self, text):
        """Extraer posibles títulos de películas del texto OCR"""
        possible_titles = []
        
        try:
            # Patrones para encontrar títulos
            title_patterns = [
                r'\b([A-Z][a-z]+(?: [A-Z][a-z]+){1,3})\b',  # Títulos en formato título (2-4 palabras)
                r'\b([A-Z]{3,}(?: [A-Z]{3,})*)\b',          # Títulos en mayúsculas
                r'"([^"]{5,30})"',                           # Texto entre comillas
                r"'([^']{5,30})'",                           # Texto entre comillas simples
            ]
            
            for pattern in title_patterns:
                matches = re.findall(pattern, text)
                for match in matches:
                    if isinstance(match, tuple):
                        match = match[0]
                    
                    # Filtrar matches válidos
                    if (len(match) > 4 and 
                        len(match) < 50 and 
                        not match.lower() in ['presents', 'production', 'entertainment', 'pictures']):
                        possible_titles.append(match.strip())
            
            # Remover duplicados manteniendo orden
            seen = set()
            unique_titles = []
            for title in possible_titles:
                if title.lower() not in seen:
                    seen.add(title.lower())
                    unique_titles.append(title)
            
            return unique_titles[:5]  # Máximo 5 intentos
            
        except Exception:
            return []
    
    def process_videos(self):
        """Procesar y organizar todos los videos con validación mejorada y análisis visual"""
        if not all([self.source_folder.get(), self.movies_folder.get(), self.series_folder.get()]):
            messagebox.showerror("Error", "Configura todas las rutas necesarias")
            return
        
        def process_thread():
            try:
                source_path = Path(self.source_folder.get())
                movies_dest = Path(self.movies_folder.get())
                series_dest = Path(self.series_folder.get())
                unknown_dest = Path(self.unknown_folder.get()) if self.unknown_folder.get() else source_path / "Unknown"
                
                # Crear carpetas destino
                movies_dest.mkdir(parents=True, exist_ok=True)
                series_dest.mkdir(parents=True, exist_ok=True)
                unknown_dest.mkdir(parents=True, exist_ok=True)
                
                video_extensions = set(self.config['video_extensions'])
                
                # Encontrar todos los videos
                videos_found = []
                for file_path in source_path.rglob('*'):
                    if file_path.is_file() and file_path.suffix.lower() in video_extensions:
                        videos_found.append(file_path)
                
                self.log(f"🎬 Procesando {len(videos_found)} archivos de video...")
                
                # Configurar barra de progreso
                self.progress.configure(mode='determinate', maximum=len(videos_found))
                
                stats = {
                    'movies_processed': 0,
                    'series_processed': 0,
                    'unknown_files': 0,
                    'errors': 0,
                    'skipped_low_confidence': 0,
                    'visual_analysis_used': 0,
                    'alternative_search_success': 0,
                    'actors_detected': set(),
                    'processing_time': datetime.now()
                }
                
                for i, video_path in enumerate(videos_found):
                    try:
                        self.progress['value'] = i + 1
                        self.root.update_idletasks()
                        
                        self.log(f"📁 Procesando: {video_path.name}")
                        
                        # Extraer información básica
                        video_info = self.extract_video_info(video_path.name)
                        
                        if not video_info:
                            self.log(f"⚠️ No se pudo extraer información de: {video_path.name}", "WARNING")
                            if self.move_files.get():
                                dest_file = unknown_dest / video_path.name
                                shutil.move(str(video_path), str(dest_file))
                                self.log(f"📦 Movido a desconocidos: {video_path.name}")
                            stats['unknown_files'] += 1
                            continue
                        
                        # Análisis visual para archivos problemáticos o cuando falla TMDB
                        visual_analysis = None
                        needs_visual_analysis = False
                        
                        # Determinar si necesita análisis visual
                        if (len(video_info['title'].split()) < 2 or 
                            not video_info.get('year') or
                            any(char in video_info['title'].lower() for char in ['~', 'tmp', 'temp'])):
                            needs_visual_analysis = True
                        
                        # Realizar análisis visual si es necesario
                        if needs_visual_analysis and any([self.use_facial_recognition.get(), self.use_ocr_analysis.get()]):
                            self.log(f"🔍 Realizando análisis visual de: {video_path.name}")
                            visual_analysis = self.perform_visual_analysis(video_path)
                            
                            if visual_analysis:
                                stats['visual_analysis_used'] += 1
                                self.log(f"👁️ Análisis visual completado (confianza: {visual_analysis['confidence']:.2f})")
                                
                                # Agregar actores detectados
                                if visual_analysis.get('actors'):
                                    stats['actors_detected'].update(visual_analysis['actors'])
                                    self.log(f"🎭 Actores detectados: {', '.join(visual_analysis['actors'])}")
                        
                        # Consultar TMDB
                        tmdb_info = None
                        if self.use_tmdb_api.get():
                            tmdb_info = self.query_tmdb_api(
                                video_info['search_title'], 
                                video_info.get('year'),
                                video_info['type'] == 'series'
                            )
                            
                            # Si TMDB falla y hay análisis visual, intentar búsqueda alternativa
                            if not tmdb_info and visual_analysis:
                                self.log(f"🔄 TMDB falló, intentando búsqueda alternativa...")
                                tmdb_info = self.enhanced_search_with_visual_data(video_info, visual_analysis)
                                
                                if tmdb_info and not tmdb_info.get('needs_manual_review'):
                                    stats['alternative_search_success'] += 1
                                    self.log(f"✅ Búsqueda alternativa exitosa!")
                            
                            if tmdb_info and not tmdb_info.get('needs_manual_review'):
                                video_info.update(tmdb_info)
                                similarity = tmdb_info.get('similarity_score', 1.0)
                                self.log(f"✅ Información TMDB: '{tmdb_info['title']}' (similitud: {similarity:.2f})")
                            elif not tmdb_info:
                                self.log(f"❌ No se encontró información en TMDB para: {video_info['title']}", "WARNING")
                        
                        # Decidir si procesar el archivo
                        should_process = True
                        
                        if self.strict_matching.get():
                            if self.use_tmdb_api.get() and not tmdb_info:
                                self.log(f"⏭️ Saltando (sin metadatos): {video_path.name}", "WARNING")
                                stats['skipped_low_confidence'] += 1
                                should_process = False
                            elif tmdb_info and tmdb_info.get('similarity_score', 0) < self.tmdb_score_var.get():
                                self.log(f"⏭️ Saltando (baja similitud): {video_path.name}", "WARNING")
                                stats['skipped_low_confidence'] += 1
                                should_process = False
                        
                        if not should_process:
                            # Mover a carpeta de desconocidos si es necesario
                            if self.move_files.get():
                                dest_file = unknown_dest / video_path.name
                                shutil.move(str(video_path), str(dest_file))
                                self.log(f"📦 Movido a desconocidos: {video_path.name}")
                            stats['unknown_files'] += 1
                            continue
                        
                        # Usar información visual como fallback para el naming
                        if not tmdb_info and visual_analysis and visual_analysis.get('google_search_suggestion'):
                            video_info['title'] = visual_analysis['google_search_suggestion']
                            self.log(f"📝 Usando título del análisis visual: {video_info['title']}")
                        
                        # Determinar carpeta destino
                        if video_info['type'] == 'movie':
                            dest_folder = self.create_jellyfin_structure(video_info, movies_dest)
                            stats['movies_processed'] += 1
                        elif video_info['type'] == 'series':
                            dest_folder = self.create_jellyfin_structure(video_info, series_dest)
                            stats['series_processed'] += 1
                        else:
                            dest_folder = unknown_dest
                            stats['unknown_files'] += 1
                        
                        if not dest_folder:
                            self.log(f"❌ Error creando carpeta para: {video_path.name}", "ERROR")
                            stats['errors'] += 1
                            continue
                        
                        # Generar nombre del archivo final
                        new_filename = self.generate_jellyfin_filename(video_info, video_path.name)
                        dest_file = dest_folder / new_filename
                        
                        # Mover archivo si está habilitado
                        if self.move_files.get():
                            # Verificar si el archivo ya existe
                            if dest_file.exists():
                                self.log(f"⚠️ Archivo ya existe: {dest_file}", "WARNING")
                                counter = 1
                                while dest_file.exists():
                                    name_without_ext = dest_file.stem
                                    ext = dest_file.suffix
                                    dest_file = dest_folder / f"{name_without_ext} ({counter}){ext}"
                                    counter += 1
                            
                            # Mover archivo
                            shutil.move(str(video_path), str(dest_file))
                            self.log(f"✅ Movido: {video_path.name} -> {dest_file}")
                        else:
                            self.log(f"📋 Análisis: {video_path.name} -> {dest_file}")
                        
                        # Crear archivo NFO para Jellyfin
                        if tmdb_info and tmdb_info.get('tmdb_id') and not tmdb_info.get('needs_manual_review'):
                            self.create_nfo_file(video_info, dest_file)
                        
                        # Crear archivo de información adicional si se usó análisis visual
                        if visual_analysis:
                            self.create_visual_analysis_file(visual_analysis, dest_file)
                        
                    except Exception as e:
                        self.log(f"❌ Error procesando {video_path.name}: {str(e)}", "ERROR")
                        stats['errors'] += 1
                
                # Mostrar estadísticas finales
                processing_time = datetime.now() - stats['processing_time']
                self.show_enhanced_processing_stats(stats, processing_time)
                
                self.log("🎉 Procesamiento completado!")
                self.progress['value'] = 0
                
                messagebox.showinfo("Completado", 
                                  f"Procesamiento completado:\n"
                                  f"🎬 Películas: {stats['movies_processed']}\n"
                                  f"📺 Series: {stats['series_processed']}\n"
                                  f"❓ Desconocidos: {stats['unknown_files']}\n"
                                  f"⏭️ Saltados: {stats['skipped_low_confidence']}\n"
                                  f"👁️ Análisis visual: {stats['visual_analysis_used']}\n"
                                  f"🔄 Búsquedas alternativas exitosas: {stats['alternative_search_success']}\n"
                                  f"❌ Errores: {stats['errors']}\n"
                                  f"🎭 Actores detectados: {len(stats['actors_detected'])}")
                
            except Exception as e:
                self.log(f"❌ Error crítico durante el procesamiento: {str(e)}", "ERROR")
                messagebox.showerror("Error", f"Error durante el procesamiento: {str(e)}")
            finally:
                self.progress['value'] = 0
        
        threading.Thread(target=process_thread, daemon=True).start()
    
    def create_visual_analysis_file(self, visual_analysis, video_file_path):
        """Crear archivo con información del análisis visual"""
        try:
            analysis_file_path = video_file_path.with_suffix('.analysis.txt')
            
            content = f"""ANÁLISIS VISUAL - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
{'='*60}

Archivo: {video_file_path.name}
Confianza del análisis: {visual_analysis.get('confidence', 0):.2f}

TEXTO DETECTADO:
{visual_analysis.get('detected_text', 'No se detectó texto')}

ACTORES DETECTADOS:
{', '.join(visual_analysis.get('actors', [])) if visual_analysis.get('actors') else 'No se detectaron actores conocidos'}

SUGERENCIA DE BÚSQUEDA:
{visual_analysis.get('google_search_suggestion', 'No se generó sugerencia')}

NOTA: Este archivo contiene información extraída automáticamente del video
usando reconocimiento óptico de caracteres (OCR) y reconocimiento facial.
"""
            
            with open(analysis_file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            self.log(f"📄 Archivo de análisis creado: {analysis_file_path.name}")
            
        except Exception as e:
            self.log(f"❌ Error creando archivo de análisis: {str(e)}", "ERROR")
    
    def show_enhanced_processing_stats(self, stats, processing_time):
        """Mostrar estadísticas mejoradas del procesamiento"""
        stats_text = f"""ESTADÍSTICAS DEL PROCESAMIENTO AVANZADO
{"="*70}

⏱️ Tiempo total: {processing_time}
🎬 Películas procesadas: {stats['movies_processed']}
📺 Series procesadas: {stats['series_processed']}
❓ Archivos no identificados: {stats['unknown_files']}
⏭️ Saltados (baja confianza): {stats['skipped_low_confidence']}
❌ Errores: {stats['errors']}

🤖 ANÁLISIS AVANZADO:
👁️ Videos con análisis visual: {stats['visual_analysis_used']}
🔄 Búsquedas alternativas exitosas: {stats['alternative_search_success']}
🎭 Actores únicos detectados: {len(stats['actors_detected'])}

🎭 ACTORES DETECTADOS:
{', '.join(sorted(stats['actors_detected'])) if stats['actors_detected'] else 'Ninguno'}

📊 EFICIENCIA DEL PROCESAMIENTO:
Total archivos: {stats['movies_processed'] + stats['series_processed'] + stats['unknown_files'] + stats['skipped_low_confidence'] + stats['errors']}
Exitosos: {stats['movies_processed'] + stats['series_processed']}
Problemáticos: {stats['unknown_files'] + stats['skipped_low_confidence'] + stats['errors']}
Tasa de éxito: {((stats['movies_processed'] + stats['series_processed']) / max(1, stats['movies_processed'] + stats['series_processed'] + stats['unknown_files'] + stats['skipped_low_confidence'] + stats['errors']) * 100):.1f}%

💡 MEJORAS APLICADAS:
- Análisis visual para archivos problemáticos
- Búsquedas alternativas cuando TMDB falla  
- Reconocimiento facial de actores
- OCR para extracción de títulos
- Archivos de análisis adicionales creados

🕐 Procesamiento completado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        
        self.stats_text.configure(state='normal')
        self.stats_text.delete(1.0, tk.END)
        self.stats_text.insert(1.0, stats_text)
        self.stats_text.configure(state='disabled') = f"película {main_actor}"
            
            # Calcular confianza
            confidence = 0.0
            if analysis_result['detected_text']:
                confidence += 0.5
            if analysis_result['actors']:
                confidence += 0.3
            if analysis_result['google_search_suggestion']:
                confidence += 0.2
            
            analysis_result['confidence'] = confidence
            
            return analysis_result if confidence > 0.3 else None
            
        except Exception as e:
            self.log(f"❌ Error en análisis visual: {str(e)}", "ERROR")
            return None
    
    def generate_search_suggestion(self, text):
        """Generar sugerencia de búsqueda basada en texto extraído"""
        try:
            # Limpiar el texto
            text = re.sub(r'[^\w\s]', ' ', text)
            words = text.split()
            
            # Filtrar palabras comunes y muy cortas
            stop_words = {
                'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by',
                'a', 'an', 'el', 'la', 'los', 'las', 'un', 'una', 'y', 'o', 'pero', 'en',
                'con', 'por', 'para', 'de', 'del', 'al', 'movie', 'film', 'película',
                'presents', 'production', 'productions', 'entertainment', 'pictures',
                'studios', 'studio', 'films', 'cinema'
            }
            
            # Filtrar palabras significativas
            significant_words = []
            for word in words:
                if (len(word) > 2 and 
                    word.lower() not in stop_words and 
                    not word.isdigit() and
                    len(word) < 15):  # Evitar palabras muy largas que suelen ser ruido
                    significant_words.append(word)
            
            # Buscar patrones de títulos
            title_patterns = [
                r'\b([A-Z][a-z]+ [A-Z][a-z]+(?:\s[A-Z][a-z]+)?)\b',  # Título en formato título
                r'\b([A-Z]{2,}(?:\s[A-Z]{2,})*)\b',  # Títulos en mayúsculas
            ]
            
            for pattern in title_patterns:
                matches = re.findall(pattern, text)
                if matches:
                    # Tomar el match más largo
                    best_match = max(matches, key=len)
                    if len(best_match) > 5:  # Mínimo 5 caracteres
                        return best_match
            
            # Si no hay patrones claros, usar palabras más significativas
            if significant_words:
                # Tomar las primeras 2-3 palabras más largas
                sorted_words = sorted(significant_words, key=len, reverse=True)
                search_terms = sorted_words[:3]
                
                if search_terms:
                    return ' '.join(search_terms)
            
            return ''
            
        except Exception:
            return '' = f"película {main_actor}"
            
            # Calcular confianza
            confidence = 0.0
            if analysis_result['detected_text']:
                confidence += 0.5
            if analysis_result['actors']:
                confidence += 0.3
            if analysis_result['google_search_suggestion']:
                confidence += 0.2
            
            analysis_result['confidence'] = confidence
            
            return analysis_result if confidence > 0.3 else None
            
        except Exception as e:
            self.log(f"❌ Error en análisis visual: {str(e)}", "ERROR")
            return None
    
    def generate_search_suggestion(self, text):
        """Generar sugerencia de búsqueda basada en texto extraído"""
        try:
            # Limpiar el texto
            text = re.sub(r'[^\w\s]', ' ', text)
            words = text.split()
            
            # Filtrar palabras comunes y muy cortas
            stop_words = {
                'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by',
                'a', 'an', 'el', 'la', 'los', 'las', 'un', 'una', 'y', 'o', 'pero', 'en',
                'con', 'por', 'para', 'de', 'del', 'al', 'movie', 'film', 'película',
                'presents', 'production', 'productions', 'entertainment', 'pictures',
                'studios', 'studio', 'films', 'cinema'
            }
            
            # Filtrar palabras significativas
            significant_words = []
            for word in words:
                if (len(word) > 2 and 
                    word.lower() not in stop_words and 
                    not word.isdigit() and
                    len(word) < 15):  # Evitar palabras muy largas que suelen ser ruido
                    significant_words.append(word)
            
            # Buscar patrones de títulos
            title_patterns = [
                r'\b([A-Z][a-z]+ [A-Z][a-z]+(?:\s[A-Z][a-z]+)?)\b',  # Título en formato título
                r'\b([A-Z]{2,}(?:\s[A-Z]{2,})*)\b',  # Títulos en mayúsculas
            ]
            
            for pattern in title_patterns:
                matches = re.findall(pattern, text)
                if matches:
                    # Tomar el match más largo
                    best_match = max(matches, key=len)
                    if len(best_match) > 5:  # Mínimo 5 caracteres
                        return best_match
            
            # Si no hay patrones claros, usar palabras más significativas
            if significant_words:
                # Tomar las primeras 2-3 palabras más largas
                sorted_words = sorted(significant_words, key=len, reverse=True)
                search_terms = sorted_words[:3]
                
                if search_terms:
                    return ' '.join(search_terms)
            
            return ''
            
        except Exception:
            return '' análisis mejorado"""
        if not self.source_folder.get():
            messagebox.showerror("Error", "Selecciona la carpeta origen")
            return
        
        def scan_thread():
            try:
                source_path = Path(self.source_folder.get())
                video_extensions = set(self.config['video_extensions'])
                
                self.log("🔍 Iniciando escaneo de videos...")
                
                videos_found = []
                for file_path in source_path.rglob('*'):
                    if file_path.is_file() and file_path.suffix.lower() in video_extensions:
                        videos_found.append(file_path)
                
                self.log(f"📁 Encontrados {len(videos_found)} archivos de video")
                
                # Análisis detallado
                preview_text = "VISTA PREVIA DEL ANÁLISIS MEJORADO\n" + "="*60 + "\n\n"
                
                movies_count = 0
                series_count = 0
                problematic_count = 0
                
                for i, video_path in enumerate(videos_found[:30]):  # Mostrar los primeros 30
                    video_info = self.extract_video_info(video_path.name)
                    
                    if video_info:
                        preview_text += f"{i+1}. {video_path.name}\n"
                        preview_text += f"   📁 Tipo: {video_info['type']}\n"
                        preview_text += f"   🏷️  Título detectado: {video_info['title']}\n"
                        
                        # Análisis de calidad del nombre
                        clean_name, year = self.clean_filename_for_search(video_path.name)
                        if clean_name != video_info['title']:
                            preview_text += f"   🧹 Título limpio: {clean_name}\n"
                        
                        if video_info['type'] == 'movie':
                            movies_count += 1
                            if video_info.get('year'):
                                preview_text += f"   📅 Año: {video_info['year']}\n"
                            else:
                                preview_text += f"   ⚠️  Sin año detectado\n"
                                problematic_count += 1
                        
                        elif video_info['type'] == 'series':
                            series_count += 1
                            preview_text += f"   📺 Temporada: {video_info.get('season', 'N/A')}\n"
                            preview_text += f"   📺 Episodio: {video_info.get('episode', 'N/A')}\n"
                        
                        # Predicción de éxito en TMDB
                        if self.use_tmdb_api.get() and video_info['type'] == 'movie':
                            if len(video_info['title'].split()) >= 2:
                                preview_text += f"   🎯 Probabilidad TMDB: Alta\n"
                            else:
                                preview_text += f"   🎯 Probabilidad TMDB: Media\n"
                        
                        preview_text += "\n"
                    else:
                        problematic_count += 1
                        preview_text += f"{i+1}. ❌ {video_path.name}\n"
                        preview_text += f"   🚫 No se pudo extraer información\n\n"
                
                if len(videos_found) > 30:
                    preview_text += f"... y {len(videos_found) - 30} archivos más\n\n"
                
                # Resumen
                preview_text += "RESUMEN DEL ESCANEO\n" + "="*30 + "\n"
                preview_text += f"🎬 Películas detectadas: {movies_count}\n"
                preview_text += f"📺 Series detectadas: {series_count}\n"
                preview_text += f"⚠️  Archivos problemáticos: {problematic_count}\n"
                preview_text += f"📊 Total de archivos: {len(videos_found)}\n\n"
                
                if problematic_count > 0:
                    preview_text += "💡 RECOMENDACIONES:\n"
                    preview_text += "- Revisa los archivos problemáticos\n"
                    preview_text += "- Considera renombrar archivos con nombres muy cortos\n"
                    preview_text += "- Usa la opción 'Solo mover si encuentra metadatos' para mayor precisión\n"
                
                self.preview_text.delete(1.0, tk.END)
                self.preview_text.insert(1.0, preview_text)
                
                self.log("✅ Escaneo completado")
                
            except Exception as e:
                self.log(f"❌ Error durante el escaneo: {str(e)}", "ERROR")
        
        threading.Thread(target=scan_thread, daemon=True).start()
    
    def process_videos(self):
        """Procesar y organizar todos los videos con validación mejorada"""
        if not all([self.source_folder.get(), self.movies_folder.get(), self.series_folder.get()]):
            messagebox.showerror("Error", "Configura todas las rutas necesarias")
            return
        
        def process_thread():
            try:
                source_path = Path(self.source_folder.get())
                movies_dest = Path(self.movies_folder.get())
                series_dest = Path(self.series_folder.get())
                unknown_dest = Path(self.unknown_folder.get()) if self.unknown_folder.get() else source_path / "Unknown"
                
                # Crear carpetas destino
                movies_dest.mkdir(parents=True, exist_ok=True)
                series_dest.mkdir(parents=True, exist_ok=True)
                unknown_dest.mkdir(parents=True, exist_ok=True)
                
                video_extensions = set(self.config['video_extensions'])
                
                # Encontrar todos los videos
                videos_found = []
                for file_path in source_path.rglob('*'):
                    if file_path.is_file() and file_path.suffix.lower() in video_extensions:
                        videos_found.append(file_path)
                
                self.log(f"🎬 Procesando {len(videos_found)} archivos de video...")
                
                # Configurar barra de progreso
                self.progress.configure(mode='determinate', maximum=len(videos_found))
                
                stats = {
                    'movies_processed': 0,
                    'series_processed': 0,
                    'unknown_files': 0,
                    'errors': 0,
                    'skipped_low_confidence': 0,
                    'actors_detected': set(),
                    'processing_time': datetime.now()
                }
                
                for i, video_path in enumerate(videos_found):
                    try:
                        self.progress['value'] = i + 1
                        self.root.update_idletasks()
                        
                        self.log(f"📁 Procesando: {video_path.name}")
                        
                        # Extraer información básica
                        video_info = self.extract_video_info(video_path.name)
                        
                        if not video_info:
                            self.log(f"⚠️ No se pudo extraer información de: {video_path.name}", "WARNING")
                            if self.move_files.get():
                                dest_file = unknown_dest / video_path.name
                                shutil.move(str(video_path), str(dest_file))
                                self.log(f"📦 Movido a desconocidos: {video_path.name}")
                            stats['unknown_files'] += 1
                            continue
                        
                        # Análisis avanzado si está habilitado
                        if any([self.use_facial_recognition.get(), self.use_ocr_analysis.get()]):
                            self.log(f"🤖 Analizando {self.frames_var.get()} fotogramas de {video_path.name}")
                            analysis_result = self.analyze_video_with_ai(video_path)
                            video_info['analysis'] = analysis_result
                            
                            # Agregar actores detectados a las estadísticas
                            if analysis_result['detected_actors']:
                                stats['actors_detected'].update(analysis_result['detected_actors'])
                                unique_actors = list(set(analysis_result['detected_actors']))
                                self.log(f"🎭 Actores detectados: {', '.join(unique_actors)}")
                        
                        # Consultar TMDB si está habilitado
                        tmdb_info = None
                        if self.use_tmdb_api.get():
                            tmdb_info = self.query_tmdb_api(
                                video_info['search_title'], 
                                video_info.get('year'),
                                video_info['type'] == 'series'
                            )
                            
                            if tmdb_info:
                                video_info.update(tmdb_info)
                                self.log(f"✅ Información TMDB encontrada: '{tmdb_info['title']}' (similitud: {tmdb_info['similarity_score']:.2f})")
                            else:
                                self.log(f"❌ No se encontró información en TMDB para: {video_info['title']}", "WARNING")
                        
                        # Decidir si procesar el archivo basado en configuración estricta
                        should_process = True
                        
                        if self.strict_matching.get():
                            if self.use_tmdb_api.get() and not tmdb_info:
                                self.log(f"⏭️ Saltando (sin metadatos): {video_path.name}", "WARNING")
                                stats['skipped_low_confidence'] += 1
                                should_process = False
                            elif tmdb_info and tmdb_info.get('similarity_score', 0) < self.tmdb_score_var.get():
                                self.log(f"⏭️ Saltando (baja similitud): {video_path.name}", "WARNING")
                                stats['skipped_low_confidence'] += 1
                                should_process = False
                        
                        if not should_process:
                            # Mover a carpeta de desconocidos si es necesario
                            if self.move_files.get():
                                dest_file = unknown_dest / video_path.name
                                shutil.move(str(video_path), str(dest_file))
                                self.log(f"📦 Movido a desconocidos: {video_path.name}")
                            stats['unknown_files'] += 1
                            continue
                        
                        # Determinar carpeta destino
                        if video_info['type'] == 'movie':
                            dest_folder = self.create_jellyfin_structure(video_info, movies_dest)
                            stats['movies_processed'] += 1
                        elif video_info['type'] == 'series':
                            dest_folder = self.create_jellyfin_structure(video_info, series_dest)
                            stats['series_processed'] += 1
                        else:
                            dest_folder = unknown_dest
                            stats['unknown_files'] += 1
                        
                        if not dest_folder:
                            self.log(f"❌ Error creando carpeta para: {video_path.name}", "ERROR")
                            stats['errors'] += 1
                            continue
                        
                        # Generar nombre del archivo final
                        new_filename = self.generate_jellyfin_filename(video_info, video_path.name)
                        dest_file = dest_folder / new_filename
                        
                        # Mover archivo si está habilitado
                        if self.move_files.get():
                            # Verificar si el archivo ya existe
                            if dest_file.exists():
                                self.log(f"⚠️ Archivo ya existe: {dest_file}", "WARNING")
                                # Agregar sufijo numérico
                                counter = 1
                                while dest_file.exists():
                                    name_without_ext = dest_file.stem
                                    ext = dest_file.suffix
                                    dest_file = dest_folder / f"{name_without_ext} ({counter}){ext}"
                                    counter += 1
                            
                            # Mover archivo
                            shutil.move(str(video_path), str(dest_file))
                            self.log(f"✅ Movido: {video_path.name} -> {dest_file}")
                        else:
                            self.log(f"📋 Análisis: {video_path.name} -> {dest_file}")
                        
                        # Crear archivo NFO para Jellyfin (metadatos)
                        if tmdb_info and tmdb_info.get('tmdb_id'):
                            self.create_nfo_file(video_info, dest_file)
                        
                    except Exception as e:
                        self.log(f"❌ Error procesando {video_path.name}: {str(e)}", "ERROR")
                        stats['errors'] += 1
                
                # Mostrar estadísticas finales
                processing_time = datetime.now() - stats['processing_time']
                self.show_processing_stats(stats, processing_time)
                
                self.log("🎉 Procesamiento completado!")
                self.progress['value'] = 0
                
                messagebox.showinfo("Completado", 
                                  f"Procesamiento completado:\n"
                                  f"🎬 Películas: {stats['movies_processed']}\n"
                                  f"📺 Series: {stats['series_processed']}\n"
                                  f"❓ Desconocidos: {stats['unknown_files']}\n"
                                  f"⏭️ Saltados: {stats['skipped_low_confidence']}\n"
                                  f"❌ Errores: {stats['errors']}\n"
                                  f"🎭 Actores detectados: {len(stats['actors_detected'])}")
                
            except Exception as e:
                self.log(f"❌ Error crítico durante el procesamiento: {str(e)}", "ERROR")
                messagebox.showerror("Error", f"Error durante el procesamiento: {str(e)}")
            finally:
                self.progress['value'] = 0
        
        threading.Thread(target=process_thread, daemon=True).start()
    
    def create_nfo_file(self, video_info, video_file_path):
        """Crear archivo NFO para Jellyfin con metadatos"""
        try:
            nfo_path = video_file_path.with_suffix('.nfo')
            
            # Crear contenido NFO básico
            if video_info['type'] == 'movie':
                nfo_content = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<movie>
    <title>{video_info['title']}</title>
    <originaltitle>{video_info.get('original_title', video_info['title'])}</originaltitle>
    <year>{video_info.get('year', '')}</year>
    <plot>{video_info.get('overview', '')}</plot>
    <tmdbid>{video_info.get('tmdb_id', '')}</tmdbid>
    <id>{video_info.get('tmdb_id', '')}</id>
    <uniqueid type="tmdb">{video_info.get('tmdb_id', '')}</uniqueid>
</movie>"""
            
            elif video_info['type'] == 'series':
                nfo_content = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<episodedetails>
    <title>{video_info['title']}</title>
    <season>{video_info.get('season', '')}</season>
    <episode>{video_info.get('episode', '')}</episode>
    <plot>{video_info.get('overview', '')}</plot>
    <tmdbid>{video_info.get('tmdb_id', '')}</tmdbid>
    <uniqueid type="tmdb">{video_info.get('tmdb_id', '')}</uniqueid>
</episodedetails>"""
            
            else:
                return
            
            with open(nfo_path, 'w', encoding='utf-8') as f:
                f.write(nfo_content)
            
            self.log(f"📄 Archivo NFO creado: {nfo_path.name}")
            
        except Exception as e:
            self.log(f"❌ Error creando archivo NFO: {str(e)}", "ERROR")
    
    def show_processing_stats(self, stats, processing_time):
        """Mostrar estadísticas del procesamiento"""
        stats_text = f"""ESTADÍSTICAS DEL PROCESAMIENTO
{"="*60}

⏱️ Tiempo total: {processing_time}
🎬 Películas procesadas: {stats['movies_processed']}
📺 Series procesadas: {stats['series_processed']}
❓ Archivos no identificados: {stats['unknown_files']}
⏭️ Saltados (baja confianza): {stats['skipped_low_confidence']}
❌ Errores: {stats['errors']}

🎭 Actores detectados ({len(stats['actors_detected'])}):
{', '.join(sorted(stats['actors_detected'])) if stats['actors_detected'] else 'Ninguno'}

📊 Eficiencia del procesamiento:
Total archivos: {stats['movies_processed'] + stats['series_processed'] + stats['unknown_files'] + stats['skipped_low_confidence'] + stats['errors']}
Exitosos: {stats['movies_processed'] + stats['series_processed']}
Problemáticos: {stats['unknown_files'] + stats['skipped_low_confidence'] + stats['errors']}

🕐 Procesamiento completado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
""
        
        self.stats_text.configure(state='normal')
        self.stats_text.delete(1.0, tk.END)
        self.stats_text.insert(1.0, stats_text)
        self.stats_text.configure(state='disabled')
    
    def save_config(self):
        """Guardar configuración actual"""
        try:
            self.config['tmdb_api_key'] = self.tmdb_key_var.get()
            self.config['thetvdb_api_key'] = self.tvdb_key_var.get()
            self.config['min_confidence'] = self.confidence_var.get()
            self.config['min_tmdb_score'] = self.tmdb_score_var.get()
            self.config['capture_frames'] = self.frames_var.get()
            
            config_dir = Path("config")
            config_dir.mkdir(exist_ok=True)
            
            config_path = config_dir / "config.json"
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
            
            self.log("✅ Configuración guardada")
            messagebox.showinfo("Éxito", "Configuración guardada correctamente")
            
        except Exception as e:
            self.log(f"❌ Error guardando configuración: {str(e)}", "ERROR")
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
                
                self.config.update(loaded_config)
                
                # Actualizar variables de la interfaz
                self.tmdb_key_var.set(self.config.get('tmdb_api_key', ''))
                self.tvdb_key_var.set(self.config.get('thetvdb_api_key', ''))
                self.confidence_var.set(self.config.get('min_confidence', 0.7))
                self.tmdb_score_var.set(self.config.get('min_tmdb_score', 0.8))
                self.frames_var.set(self.config.get('capture_frames', 30))
                
                self.log("✅ Configuración cargada")
                messagebox.showinfo("Éxito", "Configuración cargada correctamente")
                
            except Exception as e:
                self.log(f"❌ Error cargando configuración: {str(e)}", "ERROR")
                messagebox.showerror("Error", f"Error cargando configuración: {str(e)}")

def main():
    """Función principal"""
    import tkinter as tk
    from tkinter import messagebox, simpledialog
    
    # Verificar dependencias críticas
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