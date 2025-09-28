"""
Analizador de videos con IA para VideoSort Pro - VERSION CON DEBUG DETALLADO
Incluye reconocimiento facial, OCR y análisis de contenido
"""

import cv2
import numpy as np
import pytesseract
import face_recognition
import re
import json
from pathlib import Path
import logging
from typing import Dict, List, Optional, Tuple

class VideoAnalyzer:
    def __init__(self, config):
        self.config = config
        self.actors_db = self.load_actors_database()
        
    def load_actors_database(self) -> Dict:
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
                
                logging.info(f"Base de datos de actores cargada: {len(actors_db)} actores")
                return actors_db
            else:
                logging.warning("Base de datos de actores no encontrada")
                return {}
        
        except Exception as e:
            logging.error(f"Error cargando base de datos de actores: {e}")
            return {}
    
    def is_problematic_filename(self, filename: str) -> bool:
        """Detectar archivos con nombres problemáticos que deberían ir a unknown"""
        name = Path(filename).stem.lower()
        
        # Patrones problemáticos
        problematic_patterns = [
            r'^[a-z]?\d+$',                    # Solo números o letra+números: f13796081992
            r'^[a-z]\d{8,}$',                  # Letra seguida de muchos números
            r'^tmp',                           # Archivos temporales
            r'^temp',                          # Archivos temporales
            r'^\d{8,}',                        # Solo números largos
            r'^[a-z]{1,2}\d{6,}$',            # 1-2 letras + 6+ números
            r'^sample',                        # Archivos de muestra
            r'^test',                          # Archivos de prueba
        ]
        
        # Verificar patrones problemáticos
        for pattern in problematic_patterns:
            if re.match(pattern, name):
                logging.debug(f"Archivo problemático detectado: {filename} (patrón: {pattern})")
                return True
        
        # Verificar si el nombre es muy corto (menos de 3 caracteres)
        if len(name) < 3:
            logging.debug(f"Archivo problemático: nombre muy corto ({len(name)} chars): {filename}")
            return True
        
        # Verificar si tiene muy pocos caracteres alfabéticos
        alpha_chars = len([c for c in name if c.isalpha()])
        if alpha_chars < 2:  # Menos de 2 letras
            logging.debug(f"Archivo problemático: muy pocas letras ({alpha_chars}): {filename}")
            return True
        
        return False
    
    def is_extra_content(self, filename: str) -> bool:
        """Detectar si el archivo es contenido adicional/extras"""
        name = filename.lower()
        
        # Patrones de contenido adicional
        extra_patterns = [
            r'featurette',
            r'behind.the.scene',
            r'making.of',
            r'documentary',
            r'interview',
            r'trailer',
            r'teaser',
            r'promo',
            r'extras?',
            r'special.feature',
            r'deleted.scene',
            r'gag.reel',
            r'bloopers?',
            r'commentary',
            r'making.off',
            r'detras.de.escena',
            r'entrevista',
            r'documental',
        ]
        
        # Verificar si contiene palabras clave de extras
        for pattern in extra_patterns:
            if re.search(pattern, name):
                logging.debug(f"Contenido extra detectado: {filename} (patrón: {pattern})")
                return True
        
        # Verificar rutas que indican extras
        path_indicators = [
            'featurettes',
            'extras',
            'special features',
            'behind the scenes',
            'documentaries',
            'interviews',
            'making of',
        ]
        
        for indicator in path_indicators:
            if indicator.replace(' ', '.') in name or indicator.replace(' ', '_') in name:
                logging.debug(f"Contenido extra por ruta: {filename} (indicador: {indicator})")
                return True
        
        return False
    
    def extract_series_from_path(self, filepath: str) -> Optional[str]:
        """Extraer nombre de serie desde la ruta del archivo"""
        path_parts = Path(filepath).parts
        logging.debug(f"Analizando ruta para extraer serie: {filepath}")
        
        # Buscar en las partes de la ruta información de serie
        for i, part in enumerate(path_parts):
            logging.debug(f"  Parte {i}: {part}")
            # Patrones que indican carpeta de serie
            series_patterns = [
                r'(.+?)\s*\(?(\d{4})\)?\s*Season\s*\d+',  # "Serie (2020) Season 1"
                r'(.+?)\s*[Ss]\d{2}',                      # "Serie S01"
                r'(.+?)\s*Season\s*\d+',                   # "Serie Season 1"
                r'(.+?)\s*Temporada\s*\d+',               # "Serie Temporada 1"
            ]
            
            for pattern in series_patterns:
                match = re.search(pattern, part, re.IGNORECASE)
                if match:
                    series_name = match.group(1).strip()
                    logging.debug(f"  Serie encontrada en ruta: {series_name}")
                    # Limpiar el nombre
                    clean_name, _ = self.clean_filename_for_search(series_name)
                    result = clean_name if clean_name else series_name
                    logging.debug(f"  Serie limpia: {result}")
                    return result
        
        logging.debug("  No se encontró serie en la ruta")
        return None
    
    def clean_filename_for_search(self, filename: str) -> Tuple[str, Optional[str]]:
        """Limpiar nombre de archivo para búsqueda mejorada"""
        logging.debug(f"Limpiando filename: {filename}")
        
        # Remover extensión
        name = Path(filename).stem
        logging.debug(f"  Sin extensión: {name}")
        
        # Remover caracteres especiales y patrones comunes
        patterns_to_remove = [
            r'\b(1080p|720p|480p|2160p|4K|HDRip|BRRip|DVDRip|WEBRip|HDTV)\b',
            r'\b(x264|x265|h264|h265|HEVC|AVC)\b',
            r'\b(BluRay|Blu-ray|DVD|WEB-DL|WEBRip)\b',
            r'\b(PROPER|REPACK|EXTENDED|UNCUT|DC|DIRECTORS?\.CUT)\b',
            r'\[(.*?)\]',  # Texto entre corchetes
            r'\{(.*?)\}',  # Texto entre llaves
        ]
        
        # Primero extraer año si existe
        year_match = re.search(r'\b(19|20)\d{2}\b', name)
        year = year_match.group(0) if year_match else None
        if year:
            logging.debug(f"  Año detectado: {year}")
        
        # Aplicar limpieza básica
        for pattern in patterns_to_remove:
            old_name = name
            name = re.sub(pattern, ' ', name, flags=re.IGNORECASE)
            if old_name != name:
                logging.debug(f"  Aplicado patrón {pattern}: {name}")
        
        # Remover información de episodios para obtener solo el nombre de la serie/película
        episode_patterns = [
            r'\s*[Ss]\d{1,2}\s*[Ee]\d{1,2}.*$',  # S01E01 y todo lo que sigue
            r'\s*\d{1,2}x\d{1,2}.*$',            # 1x01 y todo lo que sigue
            r'\s*[Ss]eason\s*\d+.*$',            # Season 1 y todo lo que sigue
            r'\s*[Tt]emporada\s*\d+.*$',         # Temporada 1 y todo lo que sigue
        ]
        
        for pattern in episode_patterns:
            old_name = name
            name = re.sub(pattern, '', name, flags=re.IGNORECASE)
            if old_name != name:
                logging.debug(f"  Removido episodio {pattern}: {name}")
        
        # Remover paréntesis vacíos o con contenido no relevante
        name = re.sub(r'\([^0-9]*\)', '', name)  # Remover paréntesis que no contengan años
        
        # Restaurar año si se encontró
        if year:
            name = f"{name} {year}"
            logging.debug(f"  Con año restaurado: {name}")
        
        # Limpieza final
        name = re.sub(r'[\.\-_]', ' ', name)  # Convertir puntos, guiones a espacios
        name = re.sub(r'\s+', ' ', name).strip()  # Múltiples espacios a uno solo
        
        # Verificar que no esté vacío después de la limpieza
        if not name or len(name.strip()) < 2:
            logging.debug(f"  Nombre vacío después de limpieza, usando original")
            # Si la limpieza dejó el nombre vacío, usar el original sin extensión
            name = Path(filename).stem
            name = re.sub(r'[\.\-_]', ' ', name)
            name = re.sub(r'\s+', ' ', name).strip()
        
        logging.debug(f"  Resultado final: '{name}', año: {year}")
        return name, year
    
    def extract_video_info(self, filename: str, filepath: str = None) -> Optional[Dict]:
        """Extraer información básica del nombre del archivo"""
        logging.debug(f"Extrayendo info de video: {filename}")
        
        # Primero verificar si el archivo es problemático/inválido
        if self.is_problematic_filename(filename):
            logging.debug(f"Archivo marcado como problemático: {filename}")
            return None
        
        # Verificar si es contenido adicional/extras
        if self.is_extra_content(filename):
            logging.debug(f"Archivo detectado como extra: {filename}")
            # Intentar extraer serie desde la ruta
            series_name = None
            if filepath:
                series_name = self.extract_series_from_path(filepath)
            
            if not series_name:
                # Fallback: usar el nombre del archivo
                clean_name, _ = self.clean_filename_for_search(filename)
                series_name = clean_name
            
            return {
                'type': 'extra',
                'title': series_name or 'Unknown Series',
                'extra_type': self.classify_extra_type(filename),
                'original_filename': filename,
                'search_title': series_name or 'Unknown'
            }
        
        # Detectar si es serie o película
        series_patterns = [
            r'[Ss]\d{1,2}\s*[Ee]\d{1,2}',  # S01 E01, S01E01
            r'\d{1,2}x\d{1,2}',            # 1x01
            r'[Tt]emporada\s*\d+',         # Temporada 1
            r'[Ee]pisode\s*\d+',           # Episode 1
            r'[Ss]eason\s*\d+',            # Season 1
        ]
        
        is_series = any(re.search(pattern, filename, re.IGNORECASE) for pattern in series_patterns)
        
        if is_series:
            logging.debug(f"Detectado como serie: {filename}")
            return self.extract_series_info(filename)
        else:
            logging.debug(f"Detectado como película: {filename}")
            return self.extract_movie_info(filename)
    
    def classify_extra_type(self, filename: str) -> str:
        """Clasificar el tipo de contenido adicional"""
        name = filename.lower()
        
        if any(word in name for word in ['featurette', 'making', 'behind']):
            return 'featurette'
        elif any(word in name for word in ['interview', 'entrevista']):
            return 'interview'
        elif any(word in name for word in ['documentary', 'documental']):
            return 'documentary'
        elif any(word in name for word in ['trailer', 'teaser', 'promo']):
            return 'trailer'
        elif any(word in name for word in ['deleted', 'scene']):
            return 'deleted_scene'
        elif any(word in name for word in ['gag', 'blooper']):
            return 'blooper'
        elif any(word in name for word in ['commentary']):
            return 'commentary'
        else:
            return 'extra'
    
    def extract_movie_info(self, filename: str) -> Dict:
        """Extraer información de película con limpieza mejorada"""
        clean_name, year = self.clean_filename_for_search(filename)
        
        return {
            'type': 'movie',
            'title': clean_name,
            'year': year,
            'original_filename': filename,
            'search_title': clean_name
        }
    
    def extract_series_info(self, filename: str) -> Optional[Dict]:
        """Extraer información de serie"""
        name = Path(filename).stem
        logging.debug(f"Extrayendo info de serie: {name}")
        
        patterns = [
            # Formato S01E01, S01 E01
            r'(.+?)\s*[Ss](\d{1,2})\s*[Ee](\d{1,2})',
            # Formato 1x01
            r'(.+?)\s*(\d{1,2})x(\d{1,2})',
            # Formato Temporada X Capitulo Y
            r'(.+?)\s*[Tt]emporada\s*(\d+).*?[Cc]apitulo\s*(\d+)',
            # Formato Season X Episode Y
            r'(.+?)\s*[Ss]eason\s*(\d+).*?[Ee]pisode\s*(\d+)',
        ]
        
        for i, pattern in enumerate(patterns):
            match = re.search(pattern, name, re.IGNORECASE)
            if match:
                series_name = match.group(1).strip()
                season = int(match.group(2))
                episode = int(match.group(3))
                
                logging.debug(f"  Patrón {i} coincide: serie='{series_name}', S{season:02d}E{episode:02d}")
                
                # Limpiar nombre de la serie
                clean_name, _ = self.clean_filename_for_search(series_name)
                
                # Verificar que el nombre de la serie no esté vacío después de limpiar
                if not clean_name or len(clean_name.strip()) < 2:
                    clean_name = series_name  # Usar el nombre original si la limpieza falla
                    logging.debug(f"  Usando nombre original tras fallo de limpieza: {clean_name}")
                
                return {
                    'type': 'series',
                    'title': clean_name,
                    'season': season,
                    'episode': episode,
                    'original_filename': filename,
                    'search_title': clean_name
                }
        
        logging.debug(f"  No se pudo extraer info de serie de: {name}")
        return None
    
    def detect_actors_in_frame(self, frame: np.ndarray) -> List[str]:
        """Detectar actores en un fotograma"""
        detected_actors = []
        
        if not self.actors_db:
            logging.debug("Sin base de datos de actores, saltando reconocimiento facial")
            return detected_actors
        
        try:
            logging.debug("Iniciando detección de actores en fotograma...")
            
            # Convertir BGR a RGB
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            logging.debug(f"Frame convertido a RGB: {rgb_frame.shape}")
            
            # Detectar caras
            face_locations = face_recognition.face_locations(rgb_frame)
            logging.debug(f"Caras detectadas: {len(face_locations)}")
            
            if not face_locations:
                return detected_actors
            
            face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)
            logging.debug(f"Encodings generados: {len(face_encodings)}")
            
            for i, face_encoding in enumerate(face_encodings):
                logging.debug(f"  Procesando cara {i+1}/{len(face_encodings)}")
                best_match = None
                best_distance = float('inf')
                
                # Comparar con base de datos de actores
                for actor_name, known_encodings in self.actors_db.items():
                    for j, known_encoding in enumerate(known_encodings):
                        distance = face_recognition.face_distance([known_encoding], face_encoding)[0]
                        
                        if distance < best_distance:
                            best_distance = distance
                            best_match = actor_name
                            logging.debug(f"    Mejor match hasta ahora: {actor_name} (distancia: {distance:.3f})")
                
                # Verificar si la distancia es aceptable
                tolerance = 1.0 - self.config.get('min_confidence', 0.7)
                logging.debug(f"  Tolerancia: {tolerance:.3f}, mejor distancia: {best_distance:.3f}")
                
                if best_match and best_distance < tolerance:
                    detected_actors.append(best_match)
                    logging.debug(f"  Actor confirmado: {best_match}")
                else:
                    logging.debug(f"  No hay match suficientemente bueno para cara {i+1}")
        
        except Exception as e:
            logging.error(f"Error en reconocimiento facial: {e}", exc_info=True)
        
        logging.debug(f"Actores detectados en total: {detected_actors}")
        return detected_actors
    
    def extract_text_from_frame(self, frame: np.ndarray) -> str:
        """Extraer texto de un fotograma usando OCR"""
        try:
            logging.debug("Iniciando extracción de texto con OCR...")
            
            # Convertir a escala de grises para mejor OCR
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            logging.debug(f"Frame convertido a escala de grises: {gray.shape}")
            
            # Mejorar contraste
            gray = cv2.convertScaleAbs(gray, alpha=1.5, beta=0)
            logging.debug("Contraste mejorado")
            
            # Extraer texto
            text = pytesseract.image_to_string(gray, lang='spa+eng')
            text = text.strip()
            
            if text:
                logging.debug(f"OCR detectó texto ({len(text)} chars): '{text[:100]}{'...' if len(text) > 100 else ''}'")
            else:
                logging.debug("OCR no detectó texto")
            
            return text
        
        except Exception as e:
            logging.error(f"Error en OCR: {e}", exc_info=True)
            return ""
    
    def analyze_video_with_ai(self, file_path: Path) -> Dict:
        """Análisis avanzado con IA (reconocimiento facial, OCR, etc.)"""
        logging.info(f"Iniciando análisis con IA de: {file_path.name}")
        
        analysis_result = {
            'detected_actors': [],
            'extracted_text': [],
            'studio_logos': [],
            'confidence_score': 0.0
        }
        
        try:
            # Verificar que el archivo existe
            if not file_path.exists():
                logging.error(f"Archivo no existe: {file_path}")
                return analysis_result
            
            # Capturar fotogramas
            logging.debug(f"Abriendo video: {file_path}")
            cap = cv2.VideoCapture(str(file_path))
            
            if not cap.isOpened():
                logging.error(f"No se pudo abrir el video: {file_path}")
                return analysis_result
            
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            duration = total_frames / fps if fps > 0 else 0
            
            logging.debug(f"Video info: {total_frames} frames, {fps:.2f} FPS, {duration:.2f}s")
            
            frames_to_capture = min(self.config.get('capture_frames', 30), total_frames)
            logging.info(f"Capturando {frames_to_capture} fotogramas de {total_frames} totales")
            
            if frames_to_capture == 0:
                logging.warning("No hay fotogramas para capturar")
                cap.release()
                return analysis_result
            
            for i in range(frames_to_capture):
                frame_pos = int((i / frames_to_capture) * total_frames)
                percentage = (frame_pos / total_frames) * 100
                
                logging.debug(f"Capturando fotograma {i+1}/{frames_to_capture} en posición {frame_pos} ({percentage:.1f}%)")
                
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_pos)
                ret, frame = cap.read()
                
                if not ret:
                    logging.warning(f"No se pudo leer fotograma en posición {frame_pos}")
                    continue
                
                logging.debug(f"Fotograma leído exitosamente: {frame.shape}")
                
                # Reconocimiento facial
                if self.config.get('detect_actors', True):
                    logging.debug("Ejecutando reconocimiento facial...")
                    actors = self.detect_actors_in_frame(frame)
                    if actors:
                        analysis_result['detected_actors'].extend(actors)
                        logging.info(f"Actores detectados en frame {i+1}: {actors}")
                
                # OCR para texto
                logging.debug("Ejecutando OCR...")
                text = self.extract_text_from_frame(frame)
                if text:
                    analysis_result['extracted_text'].append(text)
                    logging.info(f"Texto extraído en frame {i+1}: '{text[:50]}{'...' if len(text) > 50 else ''}'")
            
            cap.release()
            logging.debug("Video cerrado")
            
            # Calcular confianza basada en múltiples factores
            analysis_result['confidence_score'] = self.calculate_confidence_score(analysis_result)
            
            logging.info(f"Análisis completado. Actores: {len(set(analysis_result['detected_actors']))}, "
                        f"Textos: {len(analysis_result['extracted_text'])}, "
                        f"Confianza: {analysis_result['confidence_score']:.2f}")
            
        except Exception as e:
            logging.error(f"Error crítico en análisis de video: {e}", exc_info=True)
        
        return analysis_result
    
    def calculate_confidence_score(self, analysis_result: Dict) -> float:
        """Calcular puntuación de confianza del análisis"""
        score = 0.0
        
        # Puntos por actores detectados
        if analysis_result['detected_actors']:
            unique_actors = len(set(analysis_result['detected_actors']))
            score += min(0.4, unique_actors * 0.1)  # Max 0.4, 0.1 por actor
            logging.debug(f"Puntos por actores: {unique_actors} actores = {min(0.4, unique_actors * 0.1):.2f}")
        
        # Puntos por texto extraído
        if analysis_result['extracted_text']:
            text_count = len([t for t in analysis_result['extracted_text'] if len(t.strip()) > 10])
            score += min(0.3, text_count * 0.1)  # Max 0.3, 0.1 por texto útil
            logging.debug(f"Puntos por texto: {text_count} textos útiles = {min(0.3, text_count * 0.1):.2f}")
        
        # Puntos por logos de estudio
        if analysis_result['studio_logos']:
            score += 0.3
            logging.debug("Puntos por logos: 0.3")
        
        final_score = min(score, 1.0)
        logging.debug(f"Puntuación final de confianza: {final_score:.2f}")
        return final_score
    
    def perform_visual_analysis(self, video_path: Path) -> Optional[Dict]:
        """Realizar análisis visual de un video para extraer información"""
        logging.info(f"Iniciando análisis visual de: {video_path.name}")
        
        try:
            analysis_result = {
                'detected_text': '',
                'actors': [],
                'google_search_suggestion': '',
                'confidence': 0.0
            }
            
            # Verificar que el archivo existe
            if not video_path.exists():
                logging.error(f"Archivo no existe para análisis visual: {video_path}")
                return None
            
            # Capturar fotogramas estratégicos
            cap = cv2.VideoCapture(str(video_path))
            
            if not cap.isOpened():
                logging.error(f"No se pudo abrir video para análisis visual: {video_path}")
                return None
            
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            logging.debug(f"Total de frames para análisis visual: {total_frames}")
            
            if total_frames == 0:
                logging.warning("Video sin frames para análisis visual")
                cap.release()
                return None
            
            # Fotogramas estratégicos: inicio, 10%, 50%, 90%
            strategic_frames = [
                int(total_frames * 0.05),   # 5% - títulos iniciales
                int(total_frames * 0.1),    # 10% - créditos iniciales
                int(total_frames * 0.5),    # 50% - contenido principal
                int(total_frames * 0.9)     # 90% - créditos finales
            ]
            
            logging.info(f"Analizando fotogramas estratégicos: {strategic_frames}")
            
            all_text = []
            detected_actors = []
            
            for i, frame_pos in enumerate(strategic_frames):
                try:
                    percentage = (frame_pos / total_frames) * 100
                    logging.debug(f"Procesando fotograma estratégico {i+1}/4 en posición {frame_pos} ({percentage:.1f}%)")
                    
                    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_pos)
                    ret, frame = cap.read()
                    
                    if not ret:
                        logging.warning(f"No se pudo leer fotograma estratégico en posición {frame_pos}")
                        continue
                    
                    # OCR para texto
                    logging.debug("Extrayendo texto del fotograma estratégico...")
                    text = self.extract_text_from_frame(frame)
                    if text and len(text.strip()) > 3:
                        all_text.append(text.strip())
                        logging.info(f"Texto útil extraído: '{text[:50]}{'...' if len(text) > 50 else ''}'")
                    
                    # Reconocimiento facial
                    if self.actors_db:
                        logging.debug("Analizando actores en fotograma estratégico...")
                        actors = self.detect_actors_in_frame(frame)
                        if actors:
                            detected_actors.extend(actors)
                            logging.info(f"Actores detectados: {actors}")
                
                except Exception as e:
                    logging.error(f"Error procesando fotograma estratégico {i+1}: {e}")
                    continue
            
            cap.release()
            
            # Procesar texto extraído
            if all_text:
                combined_text = ' '.join(all_text)
                analysis_result['detected_text'] = combined_text
                logging.info(f"Texto combinado ({len(combined_text)} chars): '{combined_text[:100]}{'...' if len(combined_text) > 100 else ''}'")
                
                # Generar sugerencia de búsqueda
                search_suggestion = self.generate_search_suggestion(combined_text)
                analysis_result['google_search_suggestion'] = search_suggestion
                if search_suggestion:
                    logging.info(f"Sugerencia de búsqueda generada: '{search_suggestion}'")
            else:
                logging.warning("No se extrajo texto útil del análisis visual")
            
            # Procesar actores detectados
            if detected_actors:
                unique_actors = list(set(detected_actors))
                analysis_result['actors'] = unique_actors
                logging.info(f"Actores únicos detectados: {unique_actors}")
                
                # Si hay actores conocidos, usar para mejorar búsqueda
                if not analysis_result['google_search_suggestion'] and unique_actors:
                    main_actor = max(set(detected_actors), key=detected_actors.count)
                    analysis_result['google_search_suggestion'] = f"película {main_actor}"
                    logging.info(f"Sugerencia basada en actor principal: '{analysis_result['google_search_suggestion']}'")
            else:
                logging.warning("No se detectaron actores en el análisis visual")
            
            # Calcular confianza
            confidence = 0.0
            if analysis_result['detected_text']:
                confidence += 0.5
                logging.debug("Puntos por texto detectado: +0.5")
            if analysis_result['actors']:
                confidence += 0.3
                logging.debug("Puntos por actores detectados: +0.3")
            if analysis_result['google_search_suggestion']:
                confidence += 0.2
                logging.debug("Puntos por sugerencia de búsqueda: +0.2")
            
            analysis_result['confidence'] = confidence
            logging.info(f"Confianza final del análisis visual: {confidence:.2f}")
            
            if confidence > 0.3:
                logging.info("Análisis visual exitoso (confianza > 0.3)")
                return analysis_result
            else:
                logging.warning(f"Análisis visual fallido (confianza {confidence:.2f} <= 0.3)")
                return None
            
        except Exception as e:
            logging.error(f"Error crítico en análisis visual: {e}", exc_info=True)
            return None
    
    def generate_search_suggestion(self, text: str) -> str:
        """Generar sugerencia de búsqueda basada en texto extraído"""
        logging.debug(f"Generando sugerencia de búsqueda para texto ({len(text)} chars)")
        
        try:
            # Limpiar el texto
            text = re.sub(r'[^\w\s]', ' ', text)
            words = text.split()
            logging.debug(f"Palabras después de limpieza: {len(words)}")
            
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
            
            logging.debug(f"Palabras significativas encontradas: {len(significant_words)}")
            
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
                        logging.debug(f"Patrón de título encontrado: '{best_match}'")
                        return best_match
            
            # Si no hay patrones claros, usar palabras más significativas
            if significant_words:
                # Tomar las primeras 2-3 palabras más largas
                sorted_words = sorted(significant_words, key=len, reverse=True)
                search_terms = sorted_words[:3]
                
                if search_terms:
                    result = ' '.join(search_terms)
                    logging.debug(f"Sugerencia basada en palabras clave: '{result}'")
                    return result
            
            logging.debug("No se pudo generar sugerencia de búsqueda")
            return ''
            
        except Exception as e:
            logging.error(f"Error generando sugerencia de búsqueda: {e}")
            return ''
    
    def extract_possible_titles_from_text(self, text: str) -> List[str]:
        """Extraer posibles títulos de películas del texto OCR"""
        logging.debug(f"Extrayendo posibles títulos de texto ({len(text)} chars)")
        possible_titles = []
        
        try:
            # Patrones para encontrar títulos
            title_patterns = [
                r'\b([A-Z][a-z]+(?: [A-Z][a-z]+){1,3})\b',  # Títulos en formato título (2-4 palabras)
                r'\b([A-Z]{3,}(?: [A-Z]{3,})*)\b',          # Títulos en mayúsculas
                r'"([^"]{5,30})"',                           # Texto entre comillas
                r"'([^']{5,30})'",                           # Texto entre comillas simples
            ]
            
            for i, pattern in enumerate(title_patterns):
                matches = re.findall(pattern, text)
                logging.debug(f"Patrón {i+1} encontró {len(matches)} coincidencias")
                
                for match in matches:
                    if isinstance(match, tuple):
                        match = match[0]
                    
                    # Filtrar matches válidos
                    if (len(match) > 4 and 
                        len(match) < 50 and 
                        not match.lower() in ['presents', 'production', 'entertainment', 'pictures']):
                        possible_titles.append(match.strip())
                        logging.debug(f"Título candidato: '{match.strip()}'")
            
            # Remover duplicados manteniendo orden
            seen = set()
            unique_titles = []
            for title in possible_titles:
                if title.lower() not in seen:
                    seen.add(title.lower())
                    unique_titles.append(title)
            
            logging.debug(f"Títulos únicos extraídos: {len(unique_titles)}")
            return unique_titles[:5]  # Máximo 5 intentos
            
        except Exception as e:
            logging.error(f"Error extrayendo títulos: {e}")
            return []