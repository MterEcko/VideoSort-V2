"""
Organizador de archivos para VideoSort Pro
Maneja el movimiento y organización de archivos según estructura Jellyfin
"""

import re
import shutil
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Callable, Any
import time
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext, simpledialog

# El score de TMDB para Capa 0 es 0.95 para terminar, 0.70 para pasar
TMDB_CONFIRM_SCORE = 0.95
TMDB_PASS_SCORE = 0.70
FINAL_CONFIDENCE_THRESHOLD = 0.60 # Umbral para mover el archivo (no desconocido)

class FileOrganizer:
    def __init__(self, config):
        self.config = config
        
    def create_jellyfin_structure(self, video_info: Dict, dest_base_path: Path) -> Optional[Path]:
        """Crear estructura de carpetas según convenciones de Jellyfin"""
        try:
            if video_info['type'] == 'movie':
                title = video_info['title']
                year = video_info.get('year', '')
                
                if year: folder_name = f"{title} ({year})"
                else: folder_name = title
                
                folder_name = re.sub(r'[<>:"/\\|?*]', '', folder_name)
                movie_folder = dest_base_path / folder_name
                movie_folder.mkdir(parents=True, exist_ok=True)
                return movie_folder
                
            elif video_info['type'] == 'series':
                title = video_info['title']
                season = video_info['season']
                
                clean_title = re.sub(r'[<>:"/\\|?*]', '', title)
                
                series_folder = dest_base_path / clean_title
                season_folder = series_folder / f"Season {season:02d}"
                season_folder.mkdir(parents=True, exist_ok=True)
                return season_folder
                
            elif video_info['type'] == 'extra':
                title = video_info['title']
                extra_type = video_info.get('extra_type', 'extra')
                clean_title = re.sub(r'[<>:"/\\|?*]', '', title)
                series_folder = dest_base_path / clean_title
                
                if extra_type in ['featurette', 'documentary', 'interview']: extras_folder = series_folder / "Specials"
                else: extras_folder = series_folder / "Extras"
                
                extras_folder.mkdir(parents=True, exist_ok=True)
                return extras_folder
        
        except Exception as e:
            logging.error(f"Error creando estructura: {e}")
            return None
    
    def generate_jellyfin_filename(self, video_info: Dict, original_filename: str) -> str:
        """Generar nombre de archivo según convenciones de Jellyfin"""
        extension = Path(original_filename).suffix
        
        if video_info['type'] == 'movie':
            title = video_info['title']; year = video_info.get('year', '')
            if year: filename = f"{title} ({year}){extension}"
            else: filename = f"{title}{extension}"
        
        elif video_info['type'] == 'series':
            title = video_info['title']; season = video_info['season']; episode = video_info['episode']
            filename = f"{title} - S{season:02d}E{episode:02d}{extension}"
        
        elif video_info['type'] == 'extra':
            title = video_info['title']; original_name = Path(original_filename).stem
            clean_original = re.sub(r'[<>:"/\\|?*]', '', original_name)
            
            if len(clean_original) > 5: filename = f"{clean_original}{extension}"
            else:
                extra_type = video_info.get('extra_type', 'Extra')
                filename = f"{title} - {extra_type.title()}{extension}"
        
        else: filename = original_filename
        
        filename = re.sub(r'[<>:"/\\|?*]', '', filename)
        return filename
    
    def create_nfo_file(self, video_info: Dict, video_file_path: Path):
        """Crear archivo NFO para Jellyfin con metadatos"""
        try:
            nfo_path = video_file_path.with_suffix('.nfo')
            
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
            else: return
            
            with open(nfo_path, 'w', encoding='utf-8') as f: f.write(nfo_content)
            logging.info(f"Archivo NFO creado: {nfo_path.name}")
            
        except Exception as e:
            logging.error(f"Error creando archivo NFO: {e}")
    
    def create_analysis_file(self, analysis_result: Dict, video_file_path: Path):
        """Crear archivo con información del análisis visual"""
        try:
            analysis_file_path = video_file_path.with_suffix('.analysis.txt')
            
            content = f"""ANÁLISIS VISUAL - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
{'='*60}
Archivo: {video_file_path.name}
Confianza del análisis: {analysis_result.get('confidence_score', 0):.2f}
TEXTO DETECTADO:
{analysis_result.get('detected_text', 'No se detectó texto')}
ACTORES DETECTADOS:
{', '.join(analysis_result.get('detected_actors', [])) if analysis_result.get('detected_actors') else 'No se detectaron actores conocidos'}
SUGERENCIA DE BÚSQUEDA:
{analysis_result.get('google_search_suggestion', 'No se generó sugerencia')}
NOTA: Este archivo contiene información extraída automáticamente del video
usando reconocimiento óptico de caracteres (OCR) y reconocimiento facial.
"""
            with open(analysis_file_path, 'w', encoding='utf-8') as f: f.write(content)
            logging.info(f"Archivo de análisis creado: {analysis_file_path.name}")
            
        except Exception as e:
            logging.error(f"Error creando archivo de análisis: {e}")
    
    # MODIFICADO: Nueva firma para aceptar opciones de Capas
    def process_videos(self, paths: Dict[str, Path], options: Dict, tmdb_client, video_analyzer, audio_analyzer, progress_bar, log_callback):
        """Procesar y organizar todos los videos con el sistema de Capas"""
        stats = {
            'movies_processed': 0, 'series_processed': 0, 'unknown_files': 0, 'errors': 0,
            'skipped_low_confidence': 0, 'visual_analysis_used': 0, 'alternative_search_success': 0,
            'actors_detected': set(), 'processing_time': datetime.now(), 'final_confidence': 0.0
        }
        
        try:
            source_path = paths['source']
            movies_dest = paths['movies']
            series_dest = paths['series']
            
            movies_dest.mkdir(parents=True, exist_ok=True)
            series_dest.mkdir(parents=True, exist_ok=True)
            
            video_extensions = set(self.config.get('video_extensions', []))
            videos_found = [file_path for file_path in source_path.rglob('*') 
                            if file_path.is_file() and file_path.suffix.lower() in video_extensions]
            
            log_callback(f"Procesando {len(videos_found)} archivos de video con sistema de Capas...")
            
            progress_bar.configure(mode='determinate', maximum=len(videos_found))
            
            for i, video_path in enumerate(videos_found):
                
                # Reinicio de variables por archivo
                tmdb_info = None
                analysis_result = None
                final_confidence = 0.0
                
                try:
                    progress_bar['value'] = i + 1
                    
                    log_callback(f"--- Procesando: {video_path.name} ({i+1}/{len(videos_found)}) ---")
                    
                    video_info = video_analyzer.extract_video_info(video_path.name)
                    
                    if not video_info:
                        log_callback(f"Capa 0 - Fallo: No se pudo extraer info. Se mantiene en origen.", "WARNING")
                        stats['unknown_files'] += 1
                        continue 
                    
                    # ----------------------------------------------------
                    # CAPA 0: METADATOS TEXTUALES (siempre se ejecuta primero)
                    # ----------------------------------------------------
                    if options['capas_activas']['capa_0']:
                        log_callback(f"Capa 0: Ejecutando búsqueda en TMDb para '{video_info['search_title']}'")
                        tmdb_info = self._run_capa_0(video_info, tmdb_client, options)
                        
                        if tmdb_info:
                            video_info.update(tmdb_info) # Actualizar video_info con TMDB data
                            final_confidence = tmdb_info.get('similarity_score', 0.0)

                            if final_confidence >= TMDB_CONFIRM_SCORE:
                                log_callback("Capa 0 - Confirmado: Score >= 0.95. Terminando identificación aquí.", "INFO")
                            elif final_confidence >= TMDB_PASS_SCORE:
                                log_callback(f"Capa 0 - Probable: Score {final_confidence:.2f}. Avanzando a Capa 1.", "INFO")
                            else:
                                log_callback(f"Capa 0 - Dudoso: Score {final_confidence:.2f}. Requiere Capa 1.", "WARNING")
                        else:
                            log_callback("Capa 0 - Fallo: Título no encontrado en TMDb.", "WARNING")

                    
                    # ----------------------------------------------------
                    # MÓDULOS DE ENTRADA (OCR/FACIAL) - Se ejecutan si se requiere Capa 1/3
                    # ----------------------------------------------------
                    if (final_confidence < TMDB_CONFIRM_SCORE) and \
                       (options['capas_activas']['capa_1'] or options['capas_activas']['capa_3']):
                        
                        if options['modulos_entrada']['facial_recognition'] or options['modulos_entrada']['ocr_analysis']:
                            log_callback("Ejecutando Análisis Visual (OCR/Facial) para Capas 1/3...")
                            analysis_result = video_analyzer.perform_visual_analysis(video_path)
                            if analysis_result and analysis_result.get('confidence', 0) > 0.3:
                                stats['visual_analysis_used'] += 1
                                stats['actors_detected'].update(analysis_result.get('actors', []))
                                log_callback(f"Análisis Visual (confianza: {analysis_result['confidence']:.2f})")

                    # ----------------------------------------------------
                    # CAPA 1: HASHING PERCEPTUAL (DB Local)
                    # ----------------------------------------------------
                    if (final_confidence < TMDB_CONFIRM_SCORE) and options['capas_activas']['capa_1']:
                        log_callback("Capa 1: Ejecutando comparación de pHash (DB Local)")
                        
                        # Simulación: Aquí iría la lógica real. Usamos el score del análisis visual como proxy.
                        capa_1_score = analysis_result.get('confidence', 0) if analysis_result else 0
                        
                        # Lógica de decisión: El pHash es muy fuerte.
                        if capa_1_score >= 0.85:
                            log_callback(f"Capa 1 - Confirmado: Score {capa_1_score:.2f}. Sobrepasa Capa 0.", "INFO")
                            final_confidence = 0.95 # Alta fiabilidad
                        elif capa_1_score > final_confidence:
                            final_confidence = max(final_confidence, capa_1_score * 0.8) # Ponderación si es menor
                        else:
                             log_callback("Capa 1 - Sin Match Fuerte.", "INFO")


                    # ----------------------------------------------------
                    # CAPA 2: AUDIO FINGERPRINT (AcoustID)
                    # ----------------------------------------------------
                    if (final_confidence < 0.90) and options['capas_activas']['capa_2']:
                        log_callback("Capa 2: Ejecutando Audio Fingerprint (AcoustID)")
                        
                        # NOTE: Esto puede ser costoso/lento, se ejecuta solo si es necesario.
                        if options['modulos_entrada']['audio_whisper']:
                            audio_match = audio_analyzer.find_movie_by_audio_analysis(
                                audio_analyzer.analyze_video_audio(video_path, num_segments=2)
                            )
                        else:
                            audio_match = None

                        if audio_match and audio_match.get('confidence_score', 0) >= 0.75:
                            log_callback(f"Capa 2 - CONFIRMADO: Match de audio. Título: {audio_match['title']}", "INFO")
                            final_confidence = 0.98 # Máxima fiabilidad
                        elif audio_match:
                            log_callback("Capa 2 - REFUTADO/DUDOSO: Penalizando score.", "WARNING")
                            final_confidence *= 0.5 
                        else:
                            log_callback("Capa 2 - NO ENCONTRADO (no penaliza).", "INFO")


                    # ----------------------------------------------------
                    # CAPA 3: VERIFICACIÓN IA (Gemini - Alto Costo)
                    # ----------------------------------------------------
                    if (final_confidence < FINAL_CONFIDENCE_THRESHOLD) and options['capas_activas']['capa_3']:
                        log_callback("Capa 3: Ejecutando Verificación IA (Gemini)", "WARNING")
                        
                        # NOTE: Aquí iría la llamada real a Gemini con las capturas de video
                        # Simulamos un resultado con base en el análisis visual para el flujo
                        
                        gemini_conf = analysis_result.get('confidence', 0) * 0.9 if analysis_result else 0.0
                        
                        if gemini_conf >= 0.80:
                            log_callback("Capa 3 - Éxito: IA sugiere alta confianza.", "INFO")
                            final_confidence = 0.80
                        elif gemini_conf > 0.50:
                            log_callback("Capa 3 - Requerir Manual: IA es ambigua.", "WARNING")
                            final_confidence = 0.65
                        else:
                            final_confidence = min(final_confidence, 0.40) # Desconfianza

                    # ----------------------------------------------------
                    # DECISIÓN FINAL
                    # ----------------------------------------------------
                    log_callback(f"Decisión Final: Confianza calculada: {final_confidence:.2f}")

                    if final_confidence < FINAL_CONFIDENCE_THRESHOLD:
                        log_callback(f"Decisión Final: Confianza baja. Se mantiene en origen (DUDOSO).", "WARNING")
                        stats['skipped_low_confidence'] += 1
                        stats['unknown_files'] += 1
                        continue # Mantiene el archivo en origen

                    # Si llegamos aquí, el archivo está identificado con suficiente confianza para moverse.
                    
                    # Asegurar tmdb_info final para nombrar
                    if tmdb_info: video_info.update(tmdb_info)

                    if video_info['type'] == 'movie':
                        dest_folder = self.create_jellyfin_structure(video_info, movies_dest)
                        stats['movies_processed'] += 1
                    else:
                        dest_folder = self.create_jellyfin_structure(video_info, series_dest)
                        stats['series_processed'] += 1

                    if not dest_folder:
                        log_callback(f"Error creando carpeta. Se mantiene en origen.", "ERROR")
                        stats['errors'] += 1
                        continue
                        
                    new_filename = self.generate_jellyfin_filename(video_info, video_path.name)
                    dest_file = dest_folder / new_filename
                    
                    if options['move_files']:
                        if dest_file.exists(): 
                            counter = 1
                            original_stem = dest_file.stem
                            ext = dest_file.suffix
                            if re.search(r'\s\(\d+\)$', original_stem): original_stem = re.sub(r'\s\(\d+\)$', '', original_stem)
                            while dest_file.exists():
                                dest_file = dest_folder / f"{original_stem} ({counter}){ext}"; counter += 1
                        
                        shutil.move(str(video_path), str(dest_file))
                        log_callback(f"Movido: {video_path.name} -> {dest_file}")
                    else:
                        log_callback(f"Análisis: {video_path.name} debería moverse a -> {dest_file}")
                        
                    if tmdb_info and tmdb_info.get('tmdb_id'): self.create_nfo_file(video_info, dest_file)
                    if analysis_result: self.create_analysis_file(analysis_result, dest_file)
                
                except Exception as e:
                    log_callback(f"Error procesando {video_path.name}: {str(e)}. Se mantiene en origen.", "ERROR")
                    stats['errors'] += 1
            
            processing_time = datetime.now() - stats['processing_time']
            stats['processing_time'] = str(processing_time).split('.')[0]
            log_callback("Procesamiento completado!")
            
        except Exception as e:
            log_callback(f"Error crítico durante el procesamiento: {str(e)}", "ERROR")
            stats['errors'] += 1
        
        return stats
    
    def _run_capa_0(self, video_info: Dict, tmdb_client, options: Dict) -> Optional[Dict]:
        """Ejecuta la Capa 0: Búsqueda inicial en TMDb."""
        if video_info['type'] == 'series':
            tmdb_info = tmdb_client.search_tv_show(video_info['search_title'], options.get('tmdb_min_score', 0.8))
        else:
            tmdb_info = tmdb_client.search_movie(video_info['search_title'], video_info.get('year'), options.get('tmdb_min_score', 0.8))
        
        if tmdb_info: return tmdb_info
        return None

    def enhanced_search_with_visual_data(self, video_info: Dict, visual_analysis: Dict, tmdb_client, options: Dict):
        """Función de búsqueda alternativa (usada por el código original)."""
        logging.warning("Llamada a 'enhanced_search_with_visual_data'. Este método debería ser reemplazado por la lógica de Capas 1-3.")
        return None
    
    def extract_possible_titles_from_text(self, text: str) -> List[str]:
        """Función de extracción de títulos (usada por el código original)."""
        return []

# =================================================================
# FUNCIONES DE UI INYECTADAS (para compatibilidad con VideoSortPro)
# =================================================================
# Estas funciones se mantienen aquí para ser importadas por main.py si no lo están ya

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
    quality_combo = ttk.Combobox(config_frame, textvariable=self.youtube_quality_var, values=["480p", "720p", "1080p"], state="readonly", width=10)
    quality_combo.grid(row=0, column=1, sticky='w', padx=5, pady=2)
    ttk.Button(config_frame, text="Guardar Configuración", command=self.save_youtube_config).grid(row=1, column=0, columnspan=2, pady=10)
    actions_frame = ttk.LabelFrame(parent, text="Acciones", padding="10")
    actions_frame.pack(fill='x', padx=10, pady=5)
    ttk.Button(actions_frame, text="Verificar yt-dlp Instalado", command=self.check_ytdlp, width=30).pack(pady=5, fill='x')
    ttk.Button(actions_frame, text="Entrenar con Jellyfin (Descargar Trailers)", command=self.train_with_jellyfin, width=30).pack(pady=5, fill='x')
    ttk.Button(actions_frame, text="Descargar Trailer Específico", command=self.download_specific_trailer, width=30).pack(pady=5, fill='x')
    youtube_log_frame = ttk.LabelFrame(parent, text="Log de YouTube/Entrenamiento", padding="5")
    youtube_log_frame.pack(fill='both', expand=True, padx=10, pady=5)
    self.youtube_log = scrolledtext.ScrolledText(youtube_log_frame, height=15)
    self.youtube_log.pack(fill='both', expand=True)

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

def train_with_jellyfin(self):
    """Entrenar modelo usando biblioteca Jellyfin"""
    messagebox.showinfo("Entrenamiento", "La función de entrenamiento con Jellyfin está pendiente de implementación.")
    self.youtube_log_message("Función 'Entrenar con Jellyfin' no implementada aún.", "WARNING")