"""
Gestor de configuración para VideoSort Pro
"""

import json
from pathlib import Path
import logging

class ConfigManager:
    def __init__(self):
        self.default_config = {
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
            "min_tmdb_score": 0.8,
            "require_metadata": True,
            # Nuevas configuraciones para rutas y funcionalidades avanzadas
            "last_source_folder": "",
            "last_movies_folder": "",
            "last_series_folder": "",
            "last_unknown_folder": "",
            # Configuración de YouTube OAuth
            "youtube_client_id": "",
            "youtube_client_secret": "",
            "youtube_refresh_token": "",
            # Configuración de Jellyfin
            "jellyfin_url": "",
            "jellyfin_api_key": "",
            "jellyfin_user_id": "",
            # Configuración de análisis de audio
            "whisper_model": "base",  # tiny, base, small, medium, large
            "audio_language": "es",
            "enable_audio_analysis": True,
            "enable_subtitle_search": True,
            "opensubtitles_user_agent": "VideoSortPro v2.0",
            # Configuración de conversión de video
            "enable_video_conversion": True,
            "target_video_codec": "h264",
            "target_audio_codec": "aac",
            "max_video_bitrate": "2M",
            "video_quality_preset": "medium",  # ultrafast, fast, medium, slow, veryslow
        }
        self.config = self.load_config()
    
    def load_config(self):
        """Cargar configuración desde archivo JSON"""
        config = self.default_config.copy()
        
        try:
            config_path = Path("config/config.json")
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    loaded_config = json.load(f)
                    config.update(loaded_config)
                    
        except Exception as e:
            logging.error(f"Error cargando configuración: {e}")
        
        return config
    
    def save_config(self, config_updates=None):
        """Guardar configuración a archivo JSON"""
        try:
            if config_updates:
                self.config.update(config_updates)
            
            config_dir = Path("config")
            config_dir.mkdir(exist_ok=True)
            
            config_path = config_dir / "config.json"
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
            
            return True
            
        except Exception as e:
            logging.error(f"Error guardando configuración: {e}")
            return False
    
    def save_last_folders(self, source, movies, series, unknown):
        """Guardar las últimas carpetas seleccionadas"""
        folder_updates = {
            "last_source_folder": source,
            "last_movies_folder": movies,
            "last_series_folder": series,
            "last_unknown_folder": unknown
        }
        return self.save_config(folder_updates)
    
    def get_last_folders(self):
        """Obtener las últimas carpetas seleccionadas"""
        return {
            "source": self.config.get("last_source_folder", ""),
            "movies": self.config.get("last_movies_folder", ""),
            "series": self.config.get("last_series_folder", ""),
            "unknown": self.config.get("last_unknown_folder", "")
        }
    
    def get(self, key, default=None):
        """Obtener valor de configuración"""
        return self.config.get(key, default)
    
    def set(self, key, value):
        """Establecer valor de configuración"""
        self.config[key] = value
    
    def update(self, updates):
        """Actualizar múltiples valores de configuración"""
        self.config.update(updates)