"""
Cliente de YouTube simplificado para la construcción de la base de datos.
Utiliza yt-dlp para descargar trailers sin requerir autenticación OAuth.
"""

import subprocess
import logging
from pathlib import Path
from typing import Optional, Dict, Any
import requests
import time
import re
import threading

class YouTubeManagerSimple:
    def __init__(self, config, progress_callback=None):
        self.config = config
        self.progress_callback = progress_callback
        self.tmdb_base_url = "https://api.themoviedb.org/3"

    def log_progress(self, message: str, level: str = "INFO"):
        """Logging con callback."""
        if self.progress_callback:
            self.progress_callback(message, level)
        logging.info(message)

    def check_ytdlp_available(self) -> bool:
        """Verificar si yt-dlp está disponible en el PATH."""
        try:
            subprocess.run(["yt-dlp", "--version"], capture_output=True, check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    def get_trailer_url(self, tmdb_id: str, content_type: str = "movie") -> Optional[str]:
        """Obtener URL del trailer principal desde TMDB (YouTube Key)."""
        try:
            api_key = self.config.get('tmdb_api_key')
            if not api_key: self.log_progress("❌ API Key de TMDb no configurada.", "ERROR"); return None
            
            endpoint = f"/{content_type}/{tmdb_id}/videos"; url = f"{self.tmdb_base_url}{endpoint}"
            params = { 'api_key': api_key, 'language': 'en-US' }
            response = requests.get(url, params=params, timeout=10); response.raise_for_status()
            data = response.json()
            
            for video in data.get("results", []):
                if (video.get("site") == "YouTube" and video.get("type") in ["Trailer", "Teaser"]):
                    # Priorizar trailer oficial
                    if "official" in video.get("name", "").lower(): return f"https://www.youtube.com/watch?v={video.get('key')}"
                    
            # Fallback al primer resultado
            for video in data.get("results", []):
                 if video.get("site") == "YouTube" and video.get("type") in ["Trailer", "Teaser"]:
                    return f"https://www.youtube.com/watch/v={video.get('key')}"
            
            self.log_progress(f"⚠️ No se encontró URL de trailer para TMDb ID {tmdb_id}.", "WARNING"); return None
            
        except Exception as e:
            self.log_progress(f"❌ Error obteniendo trailer de TMDB ID {tmdb_id}: {e}", "ERROR"); return None
            
    def download_video(self, video_url: str, output_path: Path, quality: str = "480p") -> Optional[Path]:
        """Descargar video usando yt-dlp, con login a través de cookies del navegador."""
        try:
            if not self.check_ytdlp_available():
                self.log_progress("❌ yt-dlp no está instalado. Instalación requerida.", "ERROR"); return None
            
            output_template = Path(output_path.parent) / f"{output_path.stem}.%(ext)s"
            quality_num = int(re.search(r'\d+', quality).group(0))
            
            # Crear la carpeta de caché si no existe
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            cmd = [
                "yt-dlp",
                "--format", f"bestvideo[height<={quality_num}]+bestaudio/best[height<={quality_num}]", 
                "--output", str(output_template),
                "--no-playlist",
                "--max-filesize", "100M",
                # Solución para el login: Usar cookies del navegador (Chrome)
                "--cookies-from-browser", "chrome:default",
                "--no-check-certificate", 
                video_url
            ]
            
            self.log_progress(f"  ⬇️ Descargando trailer (usando cookies): {video_url}")
            
            # Ejecutar yt-dlp
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
            
            if result.returncode == 0:
                downloaded_files = list(output_path.parent.glob(f"{output_path.stem}.*"))
                if downloaded_files: return downloaded_files[0]
            else:
                self.log_progress(f"  ❌ Error de descarga (yt-dlp): {result.stderr.splitlines()[-1]}", "ERROR")
                self.log_progress("    Asegúrate de tener sesión iniciada en YouTube en Chrome.", "WARNING")
                
            return None
                
        except Exception as e:
            self.log_progress(f"❌ Error crítico descargando trailer: {e}", "ERROR"); return None
            
    def download_trailer_for_content(self, tmdb_id: str, content_type: str, output_dir: Path, title: str) -> Optional[Path]:
        """Pipeline: obtener URL y descargar trailer."""
        video_url = self.get_trailer_url(tmdb_id, content_type)
        if not video_url: return None
        clean_title = re.sub(r'[^\w\s-]', '', title).strip().replace(' ', '_')
        output_file_stem = output_dir / f"{tmdb_id}_{clean_title}_trailer"
        
        quality = self.config.get("youtube_quality", "480p")
        
        trailer_path = self.download_video(video_url, output_file_stem, quality)
        return trailer_path