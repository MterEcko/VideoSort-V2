"""
Constructor de Base de Datos de Referencia para ContentID
Genera hashes de referencia desde TMDb y trailers de YouTube
"""

import json
import sqlite3
import hashlib
import logging
import requests
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
import cv2
import numpy as np
import re

# Importamos YouTubeManagerSimple para usar su lógica de descarga
from youtube_manager_simple import YouTubeManagerSimple

try:
    import imagehash
    from PIL import Image
    IMAGEHASH_AVAILABLE = True
except ImportError:
    IMAGEHASH_AVAILABLE = False
    logging.warning("imagehash no está instalado. Instala con: pip install imagehash pillow")

try:
    import acoustid
    import chromaprint
    CHROMAPRINT_AVAILABLE = True
except ImportError:
    CHROMAPRINT_AVAILABLE = False
    logging.warning("chromaprint no está instalado. Instala con: pip install pyacoustid")


class ReferenceDatabaseBuilder:
    def __init__(self, config_manager, progress_callback=None):
        self.config = config_manager
        self.progress_callback = progress_callback
        self.db_path = Path("data/reference_hashes.db")
        self.tmdb_base_url = "https://api.themoviedb.org/3"
        self.tmdb_image_base = "https://image.tmdb.org/t/p"
        
        # Crear carpetas necesarias
        self.images_cache = Path("data/cache/images")
        self.videos_cache = Path("data/cache/videos")
        self.images_cache.mkdir(parents=True, exist_ok=True)
        self.videos_cache.mkdir(parents=True, exist_ok=True)
        
        # Estado de pausa
        self.paused = False
        self.should_stop = False
        
        # NOTA: La inicialización de la DB (self.init_database()) se llama desde 
        # VideoSortPro.__init__ después de crear los logs.
    
    def log(self, message: str, level: str = "INFO"):
        """Logging con callback"""
        if self.progress_callback:
            self.progress_callback(message, level)
        
        if level == "ERROR":
            logging.error(message)
        elif level == "WARNING":
            logging.warning(message)
        else:
            logging.info(message)
    
    def init_database(self):
        """Inicializar base de datos SQLite"""
        try:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Tabla de películas/series procesadas
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS content_processed (
                    tmdb_id INTEGER PRIMARY KEY,
                    content_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    original_title TEXT,
                    year INTEGER,
                    images_processed BOOLEAN DEFAULT 0,
                    video_processed BOOLEAN DEFAULT 0,
                    audio_processed BOOLEAN DEFAULT 0,
                    date_added DATETIME DEFAULT CURRENT_TIMESTAMP,
                    last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Tabla de episodios (para series)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS episodes_processed (
                    episode_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tmdb_id INTEGER NOT NULL,
                    season_number INTEGER NOT NULL,
                    episode_number INTEGER NOT NULL,
                    episode_title TEXT,
                    images_processed BOOLEAN DEFAULT 0,
                    video_processed BOOLEAN DEFAULT 0,
                    audio_processed BOOLEAN DEFAULT 0,
                    date_added DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(tmdb_id, season_number, episode_number),
                    FOREIGN KEY (tmdb_id) REFERENCES content_processed(tmdb_id)
                )
            ''')
            
            # Tabla de hashes visuales (pHash)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS visual_hashes (
                    hash_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tmdb_id INTEGER NOT NULL,
                    episode_id INTEGER,
                    hash_type TEXT NOT NULL,
                    hash_value TEXT NOT NULL,
                    time_seconds INTEGER,
                    source_type TEXT,
                    resolution TEXT,
                    date_created DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (tmdb_id) REFERENCES content_processed(tmdb_id),
                    FOREIGN KEY (episode_id) REFERENCES episodes_processed(episode_id)
                )
            ''')
            
            # Tabla de hashes de audio (Chromaprint)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS audio_hashes (
                    hash_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tmdb_id INTEGER NOT NULL,
                    episode_id INTEGER,
                    fingerprint TEXT NOT NULL,
                    duration_seconds INTEGER,
                    source_type TEXT,
                    date_created DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (tmdb_id) REFERENCES content_processed(tmdb_id),
                    FOREIGN KEY (episode_id) REFERENCES episodes_processed(episode_id)
                )
            ''')
            
            # Índices para búsqueda rápida
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_visual_hash ON visual_hashes(hash_value)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_tmdb_content ON visual_hashes(tmdb_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_episode ON visual_hashes(episode_id)')
            
            conn.commit()
            conn.close()
            
            self.log("✅ Base de datos inicializada correctamente")
            
        except Exception as e:
            self.log(f"❌ Error inicializando base de datos: {e}", "ERROR")
    
    def get_database_stats(self) -> Dict:
        """Obtener estadísticas de la base de datos"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            movies_count = cursor.execute('SELECT COUNT(*) FROM content_processed WHERE content_type = "movie"').fetchone()[0]
            series_count = cursor.execute('SELECT COUNT(*) FROM content_processed WHERE content_type = "tv"').fetchone()[0]
            episodes_count = cursor.execute('SELECT COUNT(*) FROM episodes_processed').fetchone()[0]
            visual_hashes_count = cursor.execute('SELECT COUNT(*) FROM visual_hashes').fetchone()[0]
            audio_hashes_count = cursor.execute('SELECT COUNT(*) FROM audio_hashes').fetchone()[0]
            images_processed = cursor.execute('SELECT COUNT(*) FROM content_processed WHERE images_processed = 1').fetchone()[0]
            videos_processed = cursor.execute('SELECT COUNT(*) FROM content_processed WHERE video_processed = 1').fetchone()[0]
            audio_processed = cursor.execute('SELECT COUNT(*) FROM content_processed WHERE audio_processed = 1').fetchone()[0]
            
            conn.close()
            
            return {
                'total_movies': movies_count, 'total_series': series_count, 'total_episodes': episodes_count,
                'total_visual_hashes': visual_hashes_count, 'total_audio_hashes': audio_hashes_count,
                'images_processed': images_processed, 'videos_processed': videos_processed,
                'audio_processed': audio_processed, 'total_content': movies_count + series_count
            }
            
        except Exception as e:
            self.log(f"❌ Error obteniendo estadísticas: {e}", "ERROR")
            return {}
    
    def is_content_processed(self, tmdb_id: int, process_type: str) -> bool:
        """Verificar si el contenido ya fue procesado"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            column_map = {'images': 'images_processed', 'video': 'video_processed', 'audio': 'audio_processed'}
            column = column_map.get(process_type)
            if not column: return False
            
            cursor.execute(f'SELECT {column} FROM content_processed WHERE tmdb_id = ?', (tmdb_id,))
            result = cursor.fetchone()
            conn.close()
            return result and result[0] == 1
            
        except Exception as e:
            self.log(f"⚠️ Error verificando procesamiento: {e}", "WARNING")
            return False
    
    def mark_content_processed(self, tmdb_id: int, content_type: str, title: str, 
                              year: int, process_type: str):
        """Marcar contenido como procesado"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO content_processed (tmdb_id, content_type, title, year)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(tmdb_id) DO UPDATE SET
                    title = excluded.title,
                    year = excluded.year,
                    last_updated = CURRENT_TIMESTAMP
            ''', (tmdb_id, content_type, title, year))
            
            column_map = {'images': 'images_processed', 'video': 'video_processed', 'audio': 'audio_processed'}
            column = column_map.get(process_type)
            if column:
                cursor.execute(f'''
                    UPDATE content_processed 
                    SET {column} = 1, last_updated = CURRENT_TIMESTAMP
                    WHERE tmdb_id = ?
                ''', (tmdb_id,))
            
            conn.commit(); conn.close()
        except Exception as e:
            self.log(f"❌ Error marcando contenido procesado: {e}", "ERROR")
    
    def download_tmdb_images(self, tmdb_id: int, content_type: str = "movie") -> List[Path]:
        """Descargar imágenes de TMDb (posters, backdrops)"""
        try:
            api_key = self.config.get('tmdb_api_key')
            if not api_key: self.log("❌ API Key de TMDb no configurada", "ERROR"); return []
            
            endpoint = f"/{content_type}/{tmdb_id}/images"; url = f"{self.tmdb_base_url}{endpoint}"
            params = { 'api_key': api_key, 'include_image_language': 'en,null' }; response = requests.get(url, params=params, timeout=15); response.raise_for_status()
            data = response.json(); downloaded_images = []
            
            for i, poster in enumerate(data.get('posters', [])[:3]):
                try:
                    file_path = poster.get('file_path'); 
                    if not file_path: continue
                    image_url = f"{self.tmdb_image_base}/w500{file_path}"; img_response = requests.get(image_url, timeout=20); img_response.raise_for_status()
                    filename = f"{tmdb_id}_poster_{i}.jpg"; save_path = self.images_cache / filename
                    with open(save_path, 'wb') as f: f.write(img_response.content)
                    downloaded_images.append(save_path); self.log(f"  📥 Poster {i+1} descargado"); time.sleep(0.2)
                except Exception as e: self.log(f"  ⚠️ Error descargando poster {i}: {e}", "WARNING")
            
            for i, backdrop in enumerate(data.get('backdrops', [])[:2]):
                try:
                    file_path = backdrop.get('file_path'); 
                    if not file_path: continue
                    image_url = f"{self.tmdb_image_base}/w780{file_path}"; img_response = requests.get(image_url, timeout=20); img_response.raise_for_status()
                    filename = f"{tmdb_id}_backdrop_{i}.jpg"; save_path = self.images_cache / filename
                    with open(save_path, 'wb') as f: f.write(img_response.content)
                    downloaded_images.append(save_path); self.log(f"  📥 Backdrop {i+1} descargado"); time.sleep(0.2)
                except Exception as e: self.log(f"  ⚠️ Error descargando backdrop {i}: {e}", "WARNING")
            
            return downloaded_images
            
        except Exception as e:
            self.log(f"❌ Error descargando imágenes de TMDb: {e}", "ERROR"); return []
    
    def generate_phash_from_image(self, image_path: Path) -> Optional[str]:
        """Generar pHash desde una imagen"""
        try:
            if not IMAGEHASH_AVAILABLE: self.log("❌ imagehash no disponible", "ERROR"); return None
            img = Image.open(image_path); phash = imagehash.phash(img, hash_size=8)
            return str(phash)
        except Exception as e:
            self.log(f"❌ Error generando pHash: {e}", "ERROR"); return None
    
    def generate_phash_from_video(self, video_path: Path, num_frames: int = 10) -> List[Tuple[str, int]]:
        """Generar múltiples pHashes desde un video"""
        try:
            if not IMAGEHASH_AVAILABLE: self.log("❌ imagehash no disponible", "ERROR"); return []
            cap = cv2.VideoCapture(str(video_path))
            if not cap.isOpened(): self.log(f"❌ No se pudo abrir video: {video_path}", "ERROR"); return []
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)); fps = cap.get(cv2.CAP_PROP_FPS)
            duration = total_frames / fps if fps > 0 else 0; hashes = []
            if duration < 10: num_frames = max(3, int(duration / 5))
            start_time = 10; end_time = max(start_time + 10, duration - 10)
            for i in range(num_frames):
                if self.should_stop: break
                while self.paused: time.sleep(1)
                progress = i / (num_frames - 1) if num_frames > 1 else 0.5
                frame_time = start_time + (progress * (end_time - start_time))
                frame_number = int(frame_time * fps)
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number); ret, frame = cap.read()
                if not ret: continue
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB); pil_image = Image.fromarray(frame_rgb)
                phash = imagehash.phash(pil_image, hash_size=8)
                hashes.append((str(phash), int(frame_time))); self.log(f"  🔍 Hash generado en {int(frame_time)}s: {phash}")
            cap.release(); return hashes
        except Exception as e:
            self.log(f"❌ Error generando pHash desde video: {e}", "ERROR"); return []
    
    def generate_audio_fingerprint(self, video_path: Path) -> Optional[Tuple[str, int]]:
        """Generar fingerprint de audio con Chromaprint"""
        try:
            if not CHROMAPRINT_AVAILABLE: self.log("❌ chromaprint no disponible", "ERROR"); return None
            import tempfile
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_audio: temp_audio_path = temp_audio.name
            cmd = ['ffmpeg', '-i', str(video_path), '-vn', '-ar', '16000', '-ac', '1', '-t', '120', '-y', temp_audio_path]
            result = subprocess.run(cmd, capture_output=True, timeout=60)
            if result.returncode != 0: self.log(f"⚠️ Error extrayendo audio: {result.stderr}", "WARNING"); return None
            duration, fingerprint = acoustid.fingerprint_file(temp_audio_path)
            Path(temp_audio_path).unlink()
            self.log(f"  🎵 Fingerprint de audio generado ({duration}s)"); return (fingerprint, duration)
        except Exception as e:
            self.log(f"❌ Error generando audio fingerprint: {e}", "ERROR"); return None
    
    def save_visual_hash(self, tmdb_id: int, hash_value: str, time_seconds: int = None,
                        source_type: str = "image", episode_id: int = None, resolution: str = None):
        """Guardar hash visual en la base de datos"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO visual_hashes (tmdb_id, episode_id, hash_type, hash_value, 
                                          time_seconds, source_type, resolution)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (tmdb_id, episode_id, 'PHASH', hash_value, time_seconds, source_type, resolution))
            conn.commit(); conn.close()
        except Exception as e: self.log(f"❌ Error guardando hash visual: {e}", "ERROR")
    
    def save_audio_hash(self, tmdb_id: int, fingerprint: str, duration: int,
                       source_type: str = "video", episode_id: int = None):
        """Guardar hash de audio en la base de datos"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO audio_hashes (tmdb_id, episode_id, fingerprint, 
                                         duration_seconds, source_type)
                VALUES (?, ?, ?, ?, ?)
            ''', (tmdb_id, episode_id, fingerprint, duration, source_type))
            conn.commit(); conn.close()
        except Exception as e: self.log(f"❌ Error guardando hash de audio: {e}", "ERROR")
    
    def process_content_images(self, tmdb_id: int, content_type: str, title: str, year: int):
        """Procesar hashes desde imágenes de TMDb"""
        try:
            if self.is_content_processed(tmdb_id, 'images'): self.log(f"⏭️ {title}: Imágenes ya procesadas", "INFO"); return True
            self.log(f"🖼️ Procesando imágenes: {title} ({year})")
            images = self.download_tmdb_images(tmdb_id, content_type); 
            if not images: self.log(f"⚠️ No se descargaron imágenes para: {title}", "WARNING"); return False
            hashes_generated = 0
            for img_path in images:
                if self.should_stop: return False
                while self.paused: time.sleep(1)
                phash = self.generate_phash_from_image(img_path)
                if phash:
                    resolution = "500x750" if 'poster' in img_path.name else "780x439"
                    self.save_visual_hash(tmdb_id=tmdb_id, hash_value=phash, source_type="tmdb_image", resolution=resolution)
                    hashes_generated += 1
                img_path.unlink()
            self.mark_content_processed(tmdb_id, content_type, title, year, 'images')
            self.log(f"✅ {title}: {hashes_generated} hashes de imágenes generados"); return True
        except Exception as e: self.log(f"❌ Error procesando imágenes de {title}: {e}", "ERROR"); return False
    
    def process_content_video(self, tmdb_id: int, content_type: str, title: str, year: int, youtube_manager):
        """Procesar hashes desde video (trailer)"""
        try:
            if self.is_content_processed(tmdb_id, 'video'): self.log(f"⏭️ {title}: Video ya procesado", "INFO"); return True
            self.log(f"🎬 Procesando video: {title} ({year})")
            trailer_path = youtube_manager.download_trailer_for_content(tmdb_id=str(tmdb_id), content_type=content_type, output_dir=self.videos_cache, title=title)
            if not trailer_path or not trailer_path.exists(): self.log(f"⚠️ No se pudo descargar trailer para: {title}", "WARNING"); return False
            
            visual_hashes = self.generate_phash_from_video(trailer_path, num_frames=15)
            for phash, time_sec in visual_hashes:
                if self.should_stop: break
                self.save_visual_hash(tmdb_id=tmdb_id, hash_value=phash, time_seconds=time_sec, source_type="youtube_trailer", resolution="video")
            self.log(f"  ✅ {len(visual_hashes)} hashes visuales generados desde video")
            
            if self.config.get('process_audio_hashes', True): self.process_content_audio(tmdb_id, content_type, title, year, trailer_path)
            
            self.mark_content_processed(tmdb_id, content_type, title, year, 'video'); trailer_path.unlink(); return True
        except Exception as e:
            self.log(f"❌ Error procesando video de {title}: {e}", "ERROR"); return False
    
    def process_content_audio(self, tmdb_id: int, content_type: str, title: str, year: int, video_path: Path = None):
        """Procesar hashes de audio"""
        try:
            if self.is_content_processed(tmdb_id, 'audio'): self.log(f"⏭️ {title}: Audio ya procesado", "INFO"); return True
            if not video_path or not video_path.exists(): self.log(f"⚠️ No hay video disponible para procesar audio: {title}", "WARNING"); return False
            self.log(f"🎵 Procesando audio: {title}")
            audio_result = self.generate_audio_fingerprint(video_path)
            if not audio_result: self.log(f"⚠️ No se pudo generar fingerprint de audio para: {title}", "WARNING"); return False
            fingerprint, duration = audio_result
            self.save_audio_hash(tmdb_id=tmdb_id, fingerprint=fingerprint, duration=duration, source_type="youtube_trailer")
            self.mark_content_processed(tmdb_id, content_type, title, year, 'audio')
            self.log(f"  ✅ Fingerprint de audio generado ({duration}s)"); return True
        except Exception as e:
            self.log(f"❌ Error procesando audio de {title}: {e}", "ERROR"); return False
    
    def pause_processing(self): self.paused = True; logging.info("⏸️ Procesamiento pausado")
    def resume_processing(self): self.paused = False; logging.info("▶️ Procesamiento reanudado")
    def stop_processing(self): self.should_stop = True; self.paused = False; logging.info("⏹️ Procesamiento detenido")
    
    # MODIFICADO: Implementa la lógica de acumulación
    def build_database_from_tmdb_popular(self, mode: str = "images", max_items: int = 1000):
        """
        Construir base de datos desde películas populares de TMDb
        
        Args:
            mode: 'images', 'video', 'both'
            max_items: Límite MÁXIMO total a alcanzar (incluye ya procesados)
        """
        try:
            # YouTubeManagerSimple se importa al inicio, no es necesario reimportar aquí
            youtube_manager = YouTubeManagerSimple(self.config, self.progress_callback)
            
            api_key = self.config.get('tmdb_api_key')
            if not api_key: self.log("❌ API Key de TMDb no configurada", "ERROR"); return
            
            self.log(f"🚀 Iniciando construcción de base de datos (modo: {mode})")
            self.log(f"📊 Objetivo MÁXIMO: {max_items} ítems de TMDb (incluye ya procesados)")
            
            stats = { 'processed': 0, 'skipped': 0, 'errors': 0 }
            self.should_stop = False; self.paused = False
            
            page = 1
            processed_count = 0
            
            while processed_count < max_items and not self.should_stop:
                try:
                    url = f"{self.tmdb_base_url}/movie/popular"
                    params = { 'api_key': api_key, 'language': 'es-ES', 'page': page }
                    
                    response = requests.get(url, params=params, timeout=15); response.raise_for_status()
                    data = response.json(); movies = data.get('results', [])
                    
                    if not movies: break
                    
                    for movie in movies:
                        try:
                            if processed_count >= max_items or self.should_stop: break
                            while self.paused: time.sleep(1)
                        
                            tmdb_id = movie.get('id'); title = movie.get('title', 'Unknown')
                            year = int(movie.get('release_date', '')[:4]) if movie.get('release_date') else 0
                        
                            self.log(f"\n{'='*60}"); self.log(f"📽️ [{processed_count+1}/{max_items}] {title} ({year})")
                            self.log(f"{'='*60}")
                        
                            images_done = self.is_content_processed(tmdb_id, 'images')
                            video_done = self.is_content_processed(tmdb_id, 'video')
                            
                            processed_item_success = False
                            
                            if mode in ['images', 'both'] and not images_done:
                                processed_item_success = self.process_content_images(tmdb_id, 'movie', title, year)
                            elif images_done and mode in ['images', 'both']:
                                self.log(f"⏭️ {title}: Imágenes ya hasheadas, saltando.")
                                stats['skipped'] += 1

                            if mode in ['video', 'both'] and not video_done and not self.should_stop:
                                processed_item_success = self.process_content_video(tmdb_id, 'movie', title, year, youtube_manager) or processed_item_success
                            elif video_done and mode in ['video', 'both']:
                                self.log(f"⏭️ {title}: Video/Audio ya hasheado, saltando.")
                                stats['skipped'] += 1
                        
                            if processed_item_success: stats['processed'] += 1
                            
                            processed_count += 1
                            time.sleep(1) # Pequeña pausa entre películas
                        
                        except Exception as e:
                            self.log(f"❌ Error procesando {movie.get('title', 'Unknown')}: {e}", "ERROR")
                            stats['errors'] += 1; processed_count += 1
                
                    page += 1; time.sleep(0.5) # Rate limiting entre páginas
                
                except Exception as e:
                    self.log(f"❌ Error obteniendo página {page}: {e}", "ERROR"); page += 1
        
            final_stats = self.get_database_stats()
            self.log("\n" + "="*60); self.log("✅ CONSTRUCCIÓN DE BASE DE DATOS COMPLETADA"); self.log("="*60)
            self.log(f"📊 Estadísticas de esta sesión:"); self.log(f"   • Procesados exitosamente: {stats['processed']}")
            self.log(f"   • Saltados (ya procesados): {stats['skipped']}"); self.log(f"   • Errores: {stats['errors']}")
            
        except Exception as e:
            self.log(f"❌ Error crítico en construcción de base de datos: {e}", "ERROR")
    
    def build_database_from_jellyfin(self, jellyfin_client, mode: str = "images", content_type: str = "movies", max_items: int = None):
        """Construir base de datos desde biblioteca de Jellyfin"""
        self.log("⚠️ build_database_from_jellyfin requiere ajuste manual de lógica incremental similar al método popular.", "WARNING")
        pass 

    def export_database_summary(self, output_path: Path = None):
        """Exportar resumen de la base de datos a JSON"""
        try:
            if not output_path: output_path = Path("data/database_summary.json")
            stats = self.get_database_stats()
            conn = sqlite3.connect(self.db_path); cursor = conn.cursor()
            cursor.execute('''
                SELECT tmdb_id, content_type, title, year, images_processed, video_processed, audio_processed
                FROM content_processed ORDER BY date_added DESC LIMIT 100
            ''')
            recent_content = []; 
            for row in cursor.fetchall(): recent_content.append({'tmdb_id': row[0], 'type': row[1], 'title': row[2], 'year': row[3], 'images': bool(row[4]), 'video': bool(row[5]), 'audio': bool(row[6])})
            conn.close()
            summary = {'generated_at': datetime.now().isoformat(), 'statistics': stats, 'recent_content': recent_content, 'database_path': str(self.db_path)}
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f: json.dump(summary, f, indent=2, ensure_ascii=False)
            self.log(f"✅ Resumen exportado a: {output_path}")
        except Exception as e: self.log(f"❌ Error exportando resumen: {e}", "ERROR")
    
    def estimate_processing_time(self, num_items: int, mode: str = "both") -> Dict:
        """Estimar tiempo y espacio de procesamiento"""
        time_per_image = 5; time_per_video = 45; space_per_video_mb = 50; db_space_mb = (num_items * 0.1)
        if mode == "images": total_time_seconds = num_items * time_per_image
        elif mode == "video": total_time_seconds = num_items * time_per_video
        else: total_time_seconds = num_items * (time_per_image + time_per_video)
        hours = int(total_time_seconds // 3600); minutes = int((total_time_seconds % 3600) // 60)
        return {
            'total_items': num_items, 'mode': mode, 'estimated_hours': hours, 'estimated_minutes': minutes,
            'total_seconds': int(total_time_seconds), 'database_size_mb': round(db_space_mb, 2),
            'temp_cache_mb': round(space_per_video_mb, 2), 'human_readable': f"{hours}h {minutes}m"
        }