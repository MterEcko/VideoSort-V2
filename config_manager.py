"""
Gestor de configuración para VideoSort Pro
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional

class ConfigManager:
    def __init__(self, config_file: str = "config/config.json"):
        self.config_file = Path(config_file)
        self.config = {}
        self.load_config()
    
    def load_config(self):
        """Cargar configuración desde archivo"""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    self.config = json.load(f)
                logging.info(f"Configuración cargada desde: {self.config_file}")
            else:
                # Configuración por defecto
                self.config = {
                    "tmdb_api_key": "f98a4a1f467421762760132e1b91df58",
                    "thetvdb_api_key": "",
                    "video_extensions": [".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".m4v"],
                    "max_processes": 4,
                    "capture_frames": 30,
                    "min_confidence": 0.7,
                    "min_tmdb_score": 0.8,
                    "detect_actors": True,
                    "detect_studios": True,
                    "analyze_audio": False,
                    "jellyfin_naming": True,
                    "jellyfin_url": "",
                    "jellyfin_api_key": "",
                    "jellyfin_user_id": "",
                    "whisper_model": "base",
                    "audio_language": "es",
                    "target_video_codec": "h264",
                    "video_quality_preset": "medium",
                    "max_video_bitrate": "2M",
                    "enable_video_conversion": False,
                    "youtube_client_id": "",
                    "youtube_client_secret": "",
                    "youtube_refresh_token": ""
                }
                self.save_config()
                logging.info("Configuración por defecto creada")
        except Exception as e:
            logging.error(f"Error cargando configuración: {e}")
            self.config = {}
    
    def save_config(self, updates: Optional[Dict] = None) -> bool:
        """Guardar configuración a archivo"""
        try:
            if updates:
                self.config.update(updates)
            
            # Crear directorio si no existe
            self.config_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
            
            logging.info(f"Configuración guardada en: {self.config_file}")
            return True
        except Exception as e:
            logging.error(f"Error guardando configuración: {e}")
            return False
    
    def get(self, key: str, default: Any = None) -> Any:
        """Obtener valor de configuración"""
        return self.config.get(key, default)
    
    def set(self, key: str, value: Any):
        """Establecer valor de configuración"""
        self.config[key] = value
    
    def update(self, updates: Dict):
        """Actualizar múltiples valores"""
        self.config.update(updates)
    
    def get_last_folders(self) -> Dict[str, str]:
        """Obtener últimas carpetas utilizadas"""
        return {
            "source": self.get("last_source_folder", ""),
            "movies": self.get("last_movies_folder", ""),
            "series": self.get("last_series_folder", ""),
            "unknown": self.get("last_unknown_folder", "")
        }
    
    def save_last_folders(self, source: str, movies: str, series: str, unknown: str):
        """Guardar últimas carpetas utilizadas"""
        updates = {
            "last_source_folder": source,
            "last_movies_folder": movies,
            "last_series_folder": series,
            "last_unknown_folder": unknown
        }
        self.save_config(updates)