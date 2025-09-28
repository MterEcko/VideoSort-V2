"""
Gestor de actores para descarga y entrenamiento de reconocimiento facial
"""

import json
import time
import requests
import face_recognition
import numpy as np
from pathlib import Path
from PIL import Image
import logging
from typing import Dict, List, Optional, Callable

class ActorsManager:
    def __init__(self, tmdb_client, progress_callback: Optional[Callable] = None):
        self.tmdb_client = tmdb_client
        self.progress_callback = progress_callback
        self.actors_dir = Path("data/actors")
        self.actors_dir.mkdir(parents=True, exist_ok=True)
        
    def log_progress(self, message: str, level: str = "INFO"):
        """Enviar mensaje de progreso"""
        if self.progress_callback:
            self.progress_callback(message, level)
        else:
            logging.info(message)
    
    def download_popular_actors(self, num_actors: int = 30, photos_per_actor: int = 3) -> bool:
        """Descargar imágenes de actores populares desde TMDB"""
        try:
            self.log_progress(f"Iniciando descarga de {num_actors} actores populares ({photos_per_actor} fotos por actor)...")
            
            # Obtener actores populares desde TMDB
            self.log_progress("Obteniendo lista de actores populares desde TMDB...")
            
            popular_actors = []
            
            # Obtener actores populares de múltiples páginas
            for page in range(1, min(6, (num_actors // 20) + 2)):  # Máximo 5 páginas
                try:
                    params = {
                        'api_key': self.tmdb_client.api_key,
                        'page': page
                    }
                    
                    response = requests.get(f"{self.tmdb_client.base_url}/person/popular", params=params, timeout=10)
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
                    self.log_progress(f"Error obteniendo página {page}: {str(e)}", "ERROR")
            
            self.log_progress(f"Obtenidos {len(popular_actors)} actores de TMDB")
            
            # Descargar fotos para cada actor
            for i, actor in enumerate(popular_actors):
                try:
                    actor_name = actor['name']
                    self.log_progress(f"Descargando: {actor_name} ({i+1}/{len(popular_actors)})")
                    
                    # Crear carpeta del actor
                    actor_folder = self.actors_dir / actor_name.replace(" ", "_")
                    actor_folder.mkdir(exist_ok=True)
                    
                    # Descargar foto principal
                    profile_url = f"https://image.tmdb.org/t/p/w500{actor['profile_path']}"
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
                            images_data = self.tmdb_client.get_person_images(actor['id'])
                            
                            for j, profile in enumerate(images_data[:photos_per_actor-1]):
                                try:
                                    additional_url = f"https://image.tmdb.org/t/p/w500{profile['file_path']}"
                                    additional_response = requests.get(additional_url, timeout=15)
                                    additional_response.raise_for_status()
                                    
                                    additional_path = actor_folder / f"photo_{j+2}.jpg"
                                    with open(additional_path, 'wb') as f:
                                        f.write(additional_response.content)
                                    
                                    photos_downloaded += 1
                                    time.sleep(0.2)
                                    
                                except Exception as e:
                                    self.log_progress(f"Error descargando foto adicional {j+2} de {actor_name}: {str(e)}", "WARNING")
                        
                        except Exception as e:
                            self.log_progress(f"Error obteniendo fotos adicionales de {actor_name}: {str(e)}", "WARNING")
                    
                    self.log_progress(f"✅ {actor_name}: {photos_downloaded} fotos descargadas")
                    time.sleep(0.5)  # Evitar rate limiting
                    
                except Exception as e:
                    self.log_progress(f"Error descargando {actor.get('name', 'desconocido')}: {str(e)}", "ERROR")
            
            self.log_progress("Descarga de actores completada!")
            self.log_progress(f"Total descargado: {len(popular_actors)} actores")
            return True
            
        except Exception as e:
            self.log_progress(f"Error en descarga masiva: {str(e)}", "ERROR")
            return False
    
    def download_specific_actor(self, actor_name: str) -> bool:
        """Descargar actor específico"""
        try:
            self.log_progress(f"Descargando actor: {actor_name}")
            
            # Buscar en TMDB
            actor_data = self.tmdb_client.search_person(actor_name)
            
            if not actor_data:
                self.log_progress(f"Actor no encontrado: {actor_name}", "ERROR")
                return False
            
            profile_path = actor_data.get('profile_path')
            
            if not profile_path:
                self.log_progress(f"Sin imagen disponible para: {actor_data['name']}", "ERROR")
                return False
            
            # Descargar imagen
            image_url = f"https://image.tmdb.org/t/p/w500{profile_path}"
            img_response = requests.get(image_url, timeout=15)
            img_response.raise_for_status()
            
            # Guardar imagen
            actor_folder = self.actors_dir / actor_data['name'].replace(" ", "_")
            actor_folder.mkdir(exist_ok=True)
            
            image_path = actor_folder / "profile.jpg"
            with open(image_path, 'wb') as f:
                f.write(img_response.content)
            
            self.log_progress(f"Actor descargado: {actor_data['name']}")
            return True
            
        except Exception as e:
            self.log_progress(f"Error descargando actor: {str(e)}", "ERROR")
            return False
    
    def train_face_recognition_model(self) -> bool:
        """Entrenar modelo de reconocimiento facial"""
        try:
            self.log_progress("Iniciando entrenamiento del modelo...")
            
            if not self.actors_dir.exists():
                self.log_progress("Carpeta de actores no existe. Descarga actores primero.", "ERROR")
                return False
            
            actors_db = {}
            total_actors = 0
            successful_encodings = 0
            
            # Procesar cada actor
            actor_folders = list(self.actors_dir.iterdir())
            for i, actor_folder in enumerate(actor_folders):
                if not actor_folder.is_dir():
                    continue
                
                actor_name = actor_folder.name.replace("_", " ")
                self.log_progress(f"Procesando: {actor_name} ({i+1}/{len(actor_folders)})")
                
                # Buscar imágenes en la carpeta del actor
                image_files = list(actor_folder.glob("*.jpg")) + list(actor_folder.glob("*.png"))
                
                if not image_files:
                    self.log_progress(f"Sin imágenes para: {actor_name}", "WARNING")
                    continue
                
                encodings = []
                
                for image_file in image_files:
                    try:
                        # Cargar imagen
                        image = face_recognition.load_image_file(str(image_file))
                        
                        # Detectar caras
                        face_locations = face_recognition.face_locations(image)
                        
                        if not face_locations:
                            self.log_progress(f"Sin caras detectadas en: {image_file.name}", "WARNING")
                            continue
                        
                        # Obtener encodings
                        face_encodings = face_recognition.face_encodings(image, face_locations)
                        
                        if face_encodings:
                            encodings.extend(face_encodings)
                            self.log_progress(f"Encoding generado para: {actor_name}")
                        
                    except Exception as e:
                        self.log_progress(f"Error procesando {image_file.name}: {str(e)}", "ERROR")
                
                if encodings:
                    # Convertir a lista para JSON
                    actors_db[actor_name] = [encoding.tolist() for encoding in encodings]
                    successful_encodings += len(encodings)
                    total_actors += 1
                    self.log_progress(f"✅ {actor_name}: {len(encodings)} encodings")
                else:
                    self.log_progress(f"Sin encodings válidos para: {actor_name}", "ERROR")
            
            # Guardar base de datos
            if actors_db:
                db_path = Path("data/actors_db.json")
                with open(db_path, 'w', encoding='utf-8') as f:
                    json.dump(actors_db, f, indent=2, ensure_ascii=False)
                
                self.log_progress("Modelo entrenado exitosamente!")
                self.log_progress("Estadísticas:")
                self.log_progress(f"   - Actores procesados: {total_actors}")
                self.log_progress(f"   - Encodings generados: {successful_encodings}")
                self.log_progress(f"   - Base de datos guardada en: {db_path}")
                
                return True
            else:
                self.log_progress("No se generaron encodings válidos", "ERROR")
                return False
                
        except Exception as e:
            self.log_progress(f"Error en entrenamiento: {str(e)}", "ERROR")
            return False
    
    def get_database_info(self) -> Dict:
        """Obtener información de la base de datos actual"""
        try:
            actors_db_path = Path("data/actors_db.json")
            if not actors_db_path.exists():
                return {'actors': 0, 'encodings': 0, 'actors_list': []}
            
            with open(actors_db_path, 'r', encoding='utf-8') as f:
                actors_data = json.load(f)
            
            total_encodings = sum(len(encodings) for encodings in actors_data.values())
            
            return {
                'actors': len(actors_data),
                'encodings': total_encodings,
                'actors_list': list(actors_data.keys())
            }
            
        except Exception as e:
            logging.error(f"Error obteniendo información de BD: {e}")
            return {'actors': 0, 'encodings': 0, 'actors_list': []}