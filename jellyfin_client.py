"""
Cliente para interactuar con Jellyfin API
Obtiene información de la biblioteca y gestiona metadatos
"""

import requests
import json
import logging
from typing import Dict, List, Optional
from urllib.parse import urljoin

class JellyfinClient:
    def __init__(self, config, progress_callback=None):
        self.config = config
        self.progress_callback = progress_callback
        self.base_url = config.get("jellyfin_url", "http://10.10.1.111:8096/")
        self.api_key = config.get("jellyfin_api_key", "c07d422f84bc40579b5f918aa60ea97f")
        self.user_id = config.get("jellyfin_user_id", "POLUX")
        self.session = requests.Session()
        
        # Headers comunes
        self.session.headers.update({
            "X-Emby-Token": self.api_key,
            "Content-Type": "application/json"
        })
    
    def log_progress(self, message: str, level: str = "INFO"):
        """Enviar mensaje de progreso"""
        if self.progress_callback:
            self.progress_callback(message, level)
        logging.info(message)
    
    def test_connection(self) -> bool:
        """Probar conexión con Jellyfin"""
        try:
            if not self.base_url or not self.api_key:
                self.log_progress("URL o API key de Jellyfin no configurados", "ERROR")
                return False
            
            # Probar endpoint de sistema
            url = urljoin(self.base_url, "/System/Info")
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            server_name = data.get("ServerName", "Unknown")
            version = data.get("Version", "Unknown")
            
            self.log_progress(f"Conectado a Jellyfin: {server_name} v{version}")
            return True
            
        except Exception as e:
            self.log_progress(f"Error conectando a Jellyfin: {e}", "ERROR")
            return False
    
    def get_libraries(self) -> List[Dict]:
        """Obtener todas las bibliotecas de Jellyfin"""
        try:
            url = urljoin(self.base_url, f"/Users/{self.user_id}/Views")
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            libraries = []
            
            for item in data.get("Items", []):
                if item.get("CollectionType") in ["movies", "tvshows"]:
                    library_info = {
                        "id": item.get("Id"),
                        "name": item.get("Name"),
                        "type": item.get("CollectionType"),
                        "path": item.get("Path"),
                        "item_count": item.get("ChildCount", 0)
                    }
                    libraries.append(library_info)
            
            self.log_progress(f"Encontradas {len(libraries)} bibliotecas de medios")
            return libraries
            
        except Exception as e:
            self.log_progress(f"Error obteniendo bibliotecas: {e}", "ERROR")
            return []
    
    def get_movies_library(self) -> List[Dict]:
        """Obtener todas las películas de la biblioteca"""
        try:
            libraries = self.get_libraries()
            movies_library = None
            
            for lib in libraries:
                if lib["type"] == "movies":
                    movies_library = lib
                    break
            
            if not movies_library:
                self.log_progress("No se encontró biblioteca de películas", "ERROR")
                return []
            
            # Obtener elementos de la biblioteca
            url = urljoin(self.base_url, f"/Users/{self.user_id}/Items")
            params = {
                "ParentId": movies_library["id"],
                "IncludeItemTypes": "Movie",
                "Recursive": "true",
                "Fields": "ProviderIds,Genres,Studios,People,Overview,ProductionYear"
            }
            
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            movies = []
            
            for item in data.get("Items", []):
                movie_info = {
                    "id": item.get("Id"),
                    "name": item.get("Name"),
                    "original_title": item.get("OriginalTitle"),
                    "year": item.get("ProductionYear"),
                    "overview": item.get("Overview"),
                    "path": item.get("Path"),
                    "imdb_id": item.get("ProviderIds", {}).get("Imdb"),
                    "tmdb_id": item.get("ProviderIds", {}).get("Tmdb"),
                    "genres": [g.get("Name") for g in item.get("Genres", [])],
                    "studios": [s.get("Name") for s in item.get("Studios", [])],
                    "people": item.get("People", [])
                }
                movies.append(movie_info)
            
            self.log_progress(f"Obtenidas {len(movies)} películas de Jellyfin")
            return movies
            
        except Exception as e:
            self.log_progress(f"Error obteniendo películas: {e}", "ERROR")
            return []
    
    def get_series_library(self) -> List[Dict]:
        """Obtener todas las series de la biblioteca"""
        try:
            libraries = self.get_libraries()
            series_library = None
            
            for lib in libraries:
                if lib["type"] == "tvshows":
                    series_library = lib
                    break
            
            if not series_library:
                self.log_progress("No se encontró biblioteca de series", "ERROR")
                return []
            
            # Obtener series
            url = urljoin(self.base_url, f"/Users/{self.user_id}/Items")
            params = {
                "ParentId": series_library["id"],
                "IncludeItemTypes": "Series",
                "Recursive": "true",
                "Fields": "ProviderIds,Genres,Studios,People,Overview,ProductionYear"
            }
            
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            series = []
            
            for item in data.get("Items", []):
                series_info = {
                    "id": item.get("Id"),
                    "name": item.get("Name"),
                    "original_title": item.get("OriginalTitle"),
                    "year": item.get("ProductionYear"),
                    "overview": item.get("Overview"),
                    "path": item.get("Path"),
                    "imdb_id": item.get("ProviderIds", {}).get("Imdb"),
                    "tmdb_id": item.get("ProviderIds", {}).get("Tmdb"),
                    "tvdb_id": item.get("ProviderIds", {}).get("Tvdb"),
                    "genres": [g.get("Name") for g in item.get("Genres", [])],
                    "studios": [s.get("Name") for s in item.get("Studios", [])],
                    "people": item.get("People", [])
                }
                series.append(series_info)
            
            self.log_progress(f"Obtenidas {len(series)} series de Jellyfin")
            return series
            
        except Exception as e:
            self.log_progress(f"Error obteniendo series: {e}", "ERROR")
            return []
    
    def get_all_content(self) -> Dict[str, List]:
        """Obtener todo el contenido (películas y series)"""
        try:
            self.log_progress("Obteniendo contenido completo de Jellyfin...")
            
            movies = self.get_movies_library()
            series = self.get_series_library()
            
            return {
                "movies": movies,
                "series": series,
                "total_movies": len(movies),
                "total_series": len(series),
                "total_items": len(movies) + len(series)
            }
            
        except Exception as e:
            self.log_progress(f"Error obteniendo contenido: {e}", "ERROR")
            return {"movies": [], "series": [], "total_movies": 0, "total_series": 0, "total_items": 0}
    
    def get_missing_metadata_items(self) -> List[Dict]:
        """Encontrar elementos sin metadatos completos"""
        try:
            all_content = self.get_all_content()
            missing_metadata = []
            
            # Verificar películas
            for movie in all_content["movies"]:
                issues = []
                
                if not movie.get("tmdb_id"):
                    issues.append("Sin TMDB ID")
                if not movie.get("imdb_id"):
                    issues.append("Sin IMDB ID")
                if not movie.get("overview"):
                    issues.append("Sin descripción")
                if not movie.get("genres"):
                    issues.append("Sin géneros")
                if not movie.get("year"):
                    issues.append("Sin año")
                
                if issues:
                    missing_metadata.append({
                        "type": "movie",
                        "name": movie.get("name"),
                        "id": movie.get("id"),
                        "path": movie.get("path"),
                        "issues": issues
                    })
            
            # Verificar series
            for series in all_content["series"]:
                issues = []
                
                if not series.get("tmdb_id") and not series.get("tvdb_id"):
                    issues.append("Sin TMDB/TVDB ID")
                if not series.get("overview"):
                    issues.append("Sin descripción")
                if not series.get("genres"):
                    issues.append("Sin géneros")
                if not series.get("year"):
                    issues.append("Sin año")
                
                if issues:
                    missing_metadata.append({
                        "type": "series",
                        "name": series.get("name"),
                        "id": series.get("id"),
                        "path": series.get("path"),
                        "issues": issues
                    })
            
            self.log_progress(f"Encontrados {len(missing_metadata)} elementos con metadatos incompletos")
            return missing_metadata
            
        except Exception as e:
            self.log_progress(f"Error verificando metadatos: {e}", "ERROR")
            return []
    
    def trigger_library_scan(self, library_id: str = None) -> bool:
        """Disparar escaneo de biblioteca"""
        try:
            if library_id:
                url = urljoin(self.base_url, f"/Items/{library_id}/Refresh")
                params = {"Recursive": "true", "MetadataRefreshMode": "Default"}
            else:
                url = urljoin(self.base_url, "/Library/Refresh")
                params = {}
            
            response = self.session.post(url, params=params, timeout=10)
            response.raise_for_status()
            
            self.log_progress("Escaneo de biblioteca iniciado")
            return True
            
        except Exception as e:
            self.log_progress(f"Error iniciando escaneo: {e}", "ERROR")
            return False
    
    def get_actors_from_library(self) -> List[str]:
        """Obtener lista de actores únicos de la biblioteca"""
        try:
            all_content = self.get_all_content()
            actors = set()
            
            # Extraer actores de películas
            for movie in all_content["movies"]:
                for person in movie.get("people", []):
                    if person.get("Type") == "Actor":
                        actors.add(person.get("Name", ""))
            
            # Extraer actores de series
            for series in all_content["series"]:
                for person in series.get("people", []):
                    if person.get("Type") == "Actor":
                        actors.add(person.get("Name", ""))
            
            actors_list = sorted([actor for actor in actors if actor])
            self.log_progress(f"Encontrados {len(actors_list)} actores únicos en biblioteca")
            
            return actors_list
            
        except Exception as e:
            self.log_progress(f"Error obteniendo actores: {e}", "ERROR")
            return []
    
    def setup_jellyfin_connection(self, url: str, api_key: str, user_id: str) -> bool:
        """Configurar conexión a Jellyfin"""
        try:
            # Actualizar configuración
            self.base_url = url.rstrip('/')
            self.api_key = api_key
            self.user_id = user_id
            
            # Actualizar headers de sesión
            self.session.headers.update({
                "X-Emby-Token": self.api_key
            })
            
            # Guardar en configuración
            config_updates = {
                "jellyfin_url": self.base_url,
                "jellyfin_api_key": self.api_key,
                "jellyfin_user_id": self.user_id
            }
            
            self.config.update(config_updates)
            
            # Probar conexión
            if self.test_connection():
                self.log_progress("Configuración de Jellyfin guardada exitosamente")
                return True
            else:
                self.log_progress("Error en la configuración de Jellyfin", "ERROR")
                return False
                
        except Exception as e:
            self.log_progress(f"Error configurando Jellyfin: {e}", "ERROR")
            return False
