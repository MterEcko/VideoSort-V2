"""
Cliente para interactuar con The Movie Database (TMDB) API
"""

import requests
import time
import logging
from typing import Dict, Optional

class TMDBClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.themoviedb.org/3"
        self.session = requests.Session()
        
    def calculate_title_similarity(self, title1: str, title2: str) -> float:
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
    
    def search_movie(self, title: str, year: Optional[str] = None, min_score: float = 0.8) -> Optional[Dict]:
        """Buscar película en TMDB"""
        if not self.api_key:
            logging.warning("API Key de TMDB no configurada")
            return None
        
        try:
            endpoint = "/search/movie"
            params = {
                'api_key': self.api_key,
                'query': title,
                'language': 'es-ES'
            }
            
            if year:
                params['year'] = year
            
            logging.info(f"Buscando película en TMDB: '{title}' (año: {year})")
            
            response = self.session.get(f"{self.base_url}{endpoint}", params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            if not data.get('results'):
                logging.warning(f"No se encontraron resultados en TMDB para: {title}")
                return None
            
            # Buscar el mejor match
            best_match = None
            best_score = 0
            
            for result in data['results'][:5]:  # Revisar los primeros 5 resultados
                result_title = result.get('title', '')
                result_original_title = result.get('original_title', '')
                result_year = result.get('release_date', '')[:4] if result.get('release_date') else ''
                
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
            if best_score < min_score:
                logging.warning(f"Similitud muy baja ({best_score:.2f} < {min_score:.2f}) para: {title}")
                return None
            
            if best_match:
                result_info = {
                    'title': best_match.get('title'),
                    'original_title': best_match.get('original_title'),
                    'year': best_match.get('release_date', '')[:4] if best_match.get('release_date') else '',
                    'overview': best_match.get('overview'),
                    'tmdb_id': best_match.get('id'),
                    'similarity_score': best_score,
                    'poster_path': best_match.get('poster_path'),
                    'backdrop_path': best_match.get('backdrop_path')
                }
                
                logging.info(f"Encontrado en TMDB: '{result_info['title']}' (similitud: {best_score:.2f})")
                return result_info
        
        except Exception as e:
            logging.error(f"Error consultando TMDB: {e}")
        
        return None
    
    def search_tv_show(self, title: str, min_score: float = 0.8) -> Optional[Dict]:
        """Buscar serie de TV en TMDB"""
        if not self.api_key:
            logging.warning("API Key de TMDB no configurada")
            return None
        
        try:
            endpoint = "/search/tv"
            params = {
                'api_key': self.api_key,
                'query': title,
                'language': 'es-ES'
            }
            
            logging.info(f"Buscando serie en TMDB: '{title}'")
            
            response = self.session.get(f"{self.base_url}{endpoint}", params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            if not data.get('results'):
                logging.warning(f"No se encontraron resultados en TMDB para: {title}")
                return None
            
            # Buscar el mejor match
            best_match = None
            best_score = 0
            
            for result in data['results'][:5]:
                result_title = result.get('name', '')
                result_original_title = result.get('original_name', '')
                
                # Calcular similitud con el título
                title_similarity = self.calculate_title_similarity(title, result_title)
                original_title_similarity = self.calculate_title_similarity(title, result_original_title)
                
                # Usar la mejor similitud
                similarity = max(title_similarity, original_title_similarity)
                
                if similarity > best_score:
                    best_score = similarity
                    best_match = result
            
            # Verificar si la similitud es suficiente
            if best_score < min_score:
                logging.warning(f"Similitud muy baja ({best_score:.2f} < {min_score:.2f}) para: {title}")
                return None
            
            if best_match:
                result_info = {
                    'title': best_match.get('name'),
                    'original_title': best_match.get('original_name'),
                    'year': best_match.get('first_air_date', '')[:4] if best_match.get('first_air_date') else '',
                    'overview': best_match.get('overview'),
                    'tmdb_id': best_match.get('id'),
                    'similarity_score': best_score,
                    'poster_path': best_match.get('poster_path'),
                    'backdrop_path': best_match.get('backdrop_path')
                }
                
                logging.info(f"Encontrada serie en TMDB: '{result_info['title']}' (similitud: {best_score:.2f})")
                return result_info
        
        except Exception as e:
            logging.error(f"Error consultando TMDB: {e}")
        
        return None
    
    def test_connection(self) -> bool:
        """Probar conexión con TMDB API"""
        if not self.api_key:
            return False
        
        try:
            params = {
                'api_key': self.api_key,
                'query': 'Toy Story'
            }
            
            response = self.session.get(f"{self.base_url}/search/movie", params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            return bool(data.get('results'))
        
        except Exception as e:
            logging.error(f"Error probando conexión TMDB: {e}")
            return False
    
    def get_popular_actors(self, num_pages: int = 5) -> list:
        """Obtener actores populares desde TMDB"""
        if not self.api_key:
            return []
        
        popular_actors = []
        
        try:
            for page in range(1, min(num_pages + 1, 6)):  # Máximo 5 páginas
                params = {
                    'api_key': self.api_key,
                    'page': page
                }
                
                response = self.session.get(f"{self.base_url}/person/popular", params=params, timeout=10)
                response.raise_for_status()
                
                data = response.json()
                for person in data.get('results', []):
                    if person.get('profile_path'):  # Solo actores con foto
                        popular_actors.append({
                            'name': person['name'],
                            'id': person['id'],
                            'profile_path': person['profile_path'],
                            'known_for': [item.get('title', item.get('name', '')) for item in person.get('known_for', [])]
                        })
                
                time.sleep(0.3)  # Evitar rate limiting
        
        except Exception as e:
            logging.error(f"Error obteniendo actores populares: {e}")
        
        return popular_actors
    
    def get_person_images(self, person_id: int) -> list:
        """Obtener imágenes de una persona"""
        if not self.api_key:
            return []
        
        try:
            params = {'api_key': self.api_key}
            response = self.session.get(f"{self.base_url}/person/{person_id}/images", params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            return data.get('profiles', [])
        
        except Exception as e:
            logging.error(f"Error obteniendo imágenes de persona: {e}")
            return []
    
    def search_person(self, name: str) -> Optional[Dict]:
        """Buscar persona en TMDB"""
        if not self.api_key:
            return None
        
        try:
            params = {
                'api_key': self.api_key,
                'query': name
            }
            
            response = self.session.get(f"{self.base_url}/search/person", params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            if data.get('results'):
                return data['results'][0]
            
        except Exception as e:
            logging.error(f"Error buscando persona: {e}")
        
        return None