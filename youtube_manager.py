"""
Gestor de YouTube con OAuth para descargar trailers
Incluye autenticación con Google y descarga de videos
"""

import os
import json
import subprocess
import logging
import requests
from pathlib import Path
from typing import Optional, Dict, List
import webbrowser
import threading
import time
from urllib.parse import urlencode, parse_qs, urlparse

class YouTubeManager:
    def __init__(self, config_manager, progress_callback=None):
        self.config_manager = config_manager
        self.progress_callback = progress_callback
        self.access_token = None
        self.is_authenticated = False
        
        # YouTube OAuth endpoints
        self.auth_url = "https://accounts.google.com/o/oauth2/auth"
        self.token_url = "https://oauth2.googleapis.com/token"
        self.youtube_api_url = "https://www.googleapis.com/youtube/v3"
        
        # Scopes necesarios para YouTube
        self.scopes = [
            "https://www.googleapis.com/auth/youtube.readonly"
        ]
        
        # Cliente OAuth público para aplicaciones nativas
        self.client_id = "your_client_id_here.apps.googleusercontent.com"
        self.client_secret = "your_client_secret_here"
        self.redirect_uri = "http://localhost:8080/oauth/callback"
    
    def log_progress(self, message: str, level: str = "INFO"):
        """Enviar mensaje de progreso"""
        if self.progress_callback:
            self.progress_callback(message, level)
        logging.info(message)
    
    def setup_oauth_credentials(self, client_id: str, client_secret: str):
        """Configurar credenciales OAuth"""
        self.client_id = client_id
        self.client_secret = client_secret
        
        # Guardar en configuración
        self.config_manager.set("youtube_client_id", client_id)
        self.config_manager.set("youtube_client_secret", client_secret)
        self.config_manager.save_config()
        
        self.log_progress("Credenciales OAuth configuradas")
    
    def get_auth_url(self) -> str:
        """Generar URL de autenticación"""
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scope": " ".join(self.scopes),
            "response_type": "code",
            "access_type": "offline",
            "prompt": "consent"
        }
        
        return f"{self.auth_url}?{urlencode(params)}"
    
    def start_oauth_flow(self):
        """Iniciar flujo de autenticación OAuth"""
        try:
            auth_url = self.get_auth_url()
            self.log_progress("Iniciando autenticación con Google...")
            self.log_progress(f"Abriendo navegador: {auth_url}")
            
            # Abrir navegador
            webbrowser.open(auth_url)
            
            # Iniciar servidor local para recibir callback
            self.start_callback_server()
            
        except Exception as e:
            self.log_progress(f"Error iniciando OAuth: {e}", "ERROR")
    
    def start_callback_server(self):
        """Iniciar servidor simple para recibir callback OAuth"""
        import socket
        import urllib.parse
        
        try:
            # Crear socket servidor
            server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_socket.bind(('localhost', 8080))
            server_socket.listen(1)
            
            self.log_progress("Esperando autorización... (revisa tu navegador)")
            
            # Esperar conexión
            client_socket, address = server_socket.accept()
            
            # Leer request
            request = client_socket.recv(1024).decode('utf-8')
            
            # Extraer código de autorización
            if "GET /oauth/callback" in request:
                # Parsear URL para obtener código
                lines = request.split('\n')
                get_line = lines[0]
                url_part = get_line.split(' ')[1]
                
                if '?code=' in url_part:
                    parsed = urlparse(f"http://localhost:8080{url_part}")
                    query_params = parse_qs(parsed.query)
                    auth_code = query_params.get('code', [None])[0]
                    
                    if auth_code:
                        # Enviar respuesta al navegador
                        response = """HTTP/1.1 200 OK
Content-Type: text/html

<html>
<body>
<h2>Autenticación exitosa!</h2>
<p>Puedes cerrar esta ventana y volver a VideoSort Pro.</p>
</body>
</html>
"""
                        client_socket.send(response.encode())
                        client_socket.close()
                        server_socket.close()
                        
                        # Intercambiar código por tokens
                        self.exchange_code_for_tokens(auth_code)
                        return
            
            # Si llegamos aquí, algo salió mal
            error_response = """HTTP/1.1 400 Bad Request
Content-Type: text/html

<html>
<body>
<h2>Error en autenticación</h2>
<p>No se pudo obtener el código de autorización.</p>
</body>
</html>
"""
            client_socket.send(error_response.encode())
            client_socket.close()
            server_socket.close()
            
        except Exception as e:
            self.log_progress(f"Error en servidor callback: {e}", "ERROR")
    
    def exchange_code_for_tokens(self, auth_code: str):
        """Intercambiar código de autorización por tokens"""
        try:
            data = {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "code": auth_code,
                "grant_type": "authorization_code",
                "redirect_uri": self.redirect_uri
            }
            
            response = requests.post(self.token_url, data=data)
            response.raise_for_status()
            
            tokens = response.json()
            
            self.access_token = tokens.get("access_token")
            refresh_token = tokens.get("refresh_token")
            
            if refresh_token:
                # Guardar refresh token para uso futuro
                self.config_manager.set("youtube_refresh_token", refresh_token)
                self.config_manager.save_config()
            
            self.is_authenticated = True
            self.log_progress("Autenticación exitosa con YouTube!")
            
        except Exception as e:
            self.log_progress(f"Error intercambiando tokens: {e}", "ERROR")
    
    def refresh_access_token(self):
        """Renovar access token usando refresh token"""
        try:
            refresh_token = self.config_manager.get("youtube_refresh_token")
            if not refresh_token:
                self.log_progress("No hay refresh token disponible", "ERROR")
                return False
            
            data = {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token"
            }
            
            response = requests.post(self.token_url, data=data)
            response.raise_for_status()
            
            tokens = response.json()
            self.access_token = tokens.get("access_token")
            self.is_authenticated = True
            
            self.log_progress("Token renovado exitosamente")
            return True
            
        except Exception as e:
            self.log_progress(f"Error renovando token: {e}", "ERROR")
            return False
    
    def search_trailer(self, movie_title: str, year: str = None) -> Optional[str]:
        """Buscar trailer en YouTube"""
        try:
            if not self.is_authenticated:
                if not self.refresh_access_token():
                    self.log_progress("No autenticado con YouTube", "ERROR")
                    return None
            
            # Construir query de búsqueda
            query = f"{movie_title} trailer"
            if year:
                query += f" {year}"
            
            # Parámetros de búsqueda
            params = {
                "part": "snippet",
                "q": query,
                "type": "video",
                "maxResults": 5,
                "order": "relevance"
            }
            
            headers = {
                "Authorization": f"Bearer {self.access_token}"
            }
            
            response = requests.get(
                f"{self.youtube_api_url}/search",
                params=params,
                headers=headers
            )
            response.raise_for_status()
            
            data = response.json()
            
            # Buscar el mejor resultado
            for item in data.get("items", []):
                title = item["snippet"]["title"].lower()
                if "trailer" in title and "official" in title:
                    video_id = item["id"]["videoId"]
                    video_url = f"https://www.youtube.com/watch?v={video_id}"
                    self.log_progress(f"Trailer encontrado: {item['snippet']['title']}")
                    return video_url
            
            # Si no hay trailer oficial, tomar el primero
            if data.get("items"):
                video_id = data["items"][0]["id"]["videoId"]
                video_url = f"https://www.youtube.com/watch?v={video_id}"
                self.log_progress(f"Video encontrado: {data['items'][0]['snippet']['title']}")
                return video_url
            
            self.log_progress(f"No se encontró trailer para: {movie_title}")
            return None
            
        except Exception as e:
            self.log_progress(f"Error buscando trailer: {e}", "ERROR")
            return None
    
    def download_video(self, video_url: str, output_path: Path, quality: str = "480p") -> bool:
        """Descargar video usando yt-dlp"""
        try:
            # Verificar que yt-dlp esté instalado
            try:
                subprocess.run(["yt-dlp", "--version"], 
                              capture_output=True, check=True)
            except (subprocess.CalledProcessError, FileNotFoundError):
                self.log_progress("yt-dlp no está instalado. Instálalo con: pip install yt-dlp", "ERROR")
                return False
            
            # Configurar opciones de descarga
            cmd = [
                "yt-dlp",
                "--format", f"best[height<={quality[:-1]}]",  # 480p -> 480
                "--output", str(output_path / "%(title)s.%(ext)s"),
                "--no-playlist",
                video_url
            ]
            
            self.log_progress(f"Descargando: {video_url}")
            
            # Ejecutar descarga
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                self.log_progress("Descarga completada exitosamente")
                return True
            else:
                self.log_progress(f"Error en descarga: {result.stderr}", "ERROR")
                return False
                
        except Exception as e:
            self.log_progress(f"Error descargando video: {e}", "ERROR")
            return False
    
    def get_trailer_from_tmdb(self, tmdb_id: str, tmdb_client) -> Optional[str]:
        """Obtener URL de trailer desde TMDB"""
        try:
            # Obtener videos de la película desde TMDB
            videos_url = f"https://api.themoviedb.org/3/movie/{tmdb_id}/videos"
            params = {
                "api_key": tmdb_client.api_key,
                "language": "en-US"
            }
            
            response = requests.get(videos_url, params=params)
            response.raise_for_status()
            
            data = response.json()
            
            # Buscar trailer en YouTube
            for video in data.get("results", []):
                if (video.get("site") == "YouTube" and 
                    video.get("type") == "Trailer"):
                    video_key = video.get("key")
                    if video_key:
                        youtube_url = f"https://www.youtube.com/watch?v={video_key}"
                        self.log_progress(f"Trailer TMDB encontrado: {video.get('name', 'Unknown')}")
                        return youtube_url
            
            self.log_progress(f"No se encontró trailer en TMDB para ID: {tmdb_id}")
            return None
            
        except Exception as e:
            self.log_progress(f"Error obteniendo trailer de TMDB: {e}", "ERROR")
            return None
    
    def download_trailer_for_movie(self, movie_info: Dict, output_dir: Path, tmdb_client=None) -> Optional[Path]:
        """Pipeline completo: buscar y descargar trailer para una película"""
        try:
            movie_title = movie_info.get("title", "")
            year = movie_info.get("year", "")
            tmdb_id = movie_info.get("tmdb_id")
            
            self.log_progress(f"Buscando trailer para: {movie_title} ({year})")
            
            trailer_url = None
            
            # Método 1: Usar TMDB si tenemos ID
            if tmdb_id and tmdb_client:
                trailer_url = self.get_trailer_from_tmdb(tmdb_id, tmdb_client)
            
            # Método 2: Buscar en YouTube si no encontramos en TMDB
            if not trailer_url:
                trailer_url = self.search_trailer(movie_title, year)
            
            if not trailer_url:
                self.log_progress(f"No se encontró trailer para: {movie_title}", "WARNING")
                return None
            
            # Descargar video
            temp_dir = output_dir / "temp_trailers"
            temp_dir.mkdir(exist_ok=True)
            
            if self.download_video(trailer_url, temp_dir):
                # Buscar archivo descargado
                downloaded_files = list(temp_dir.glob("*"))
                if downloaded_files:
                    return downloaded_files[0]  # Retornar primer archivo encontrado
            
            return None
            
        except Exception as e:
            self.log_progress(f"Error en pipeline de descarga: {e}", "ERROR")
            return None
    
    def cleanup_temp_files(self, temp_dir: Path):
        """Limpiar archivos temporales"""
        try:
            if temp_dir.exists():
                for file in temp_dir.iterdir():
                    if file.is_file():
                        file.unlink()
                        self.log_progress(f"Archivo temporal eliminado: {file.name}")
                
                temp_dir.rmdir()
                self.log_progress("Limpieza de archivos temporales completada")
                
        except Exception as e:
            self.log_progress(f"Error limpiando archivos temporales: {e}", "ERROR")
