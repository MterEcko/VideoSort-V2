"""
Analizador de audio para VideoSort Pro
Incluye transcripción con Whisper y búsqueda en bases de datos de subtítulos
"""

import os
import re
import json
import requests
import tempfile
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import logging
from difflib import SequenceMatcher
import time

try:
    import whisper
    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False
    logging.warning("Whisper no está instalado. Instálalo con: pip install openai-whisper")

class AudioAnalyzer:
    def __init__(self, config, progress_callback=None):
        self.config = config
        self.progress_callback = progress_callback
        self.whisper_model = None
        self.opensubtitles_base_url = "https://api.opensubtitles.com/api/v1"
        
        # NO cargar modelo Whisper automáticamente en __init__
        # Se cargará cuando se necesite para evitar problemas de inicialización
    
    def log_progress(self, message: str, level: str = "INFO"):
        """Enviar mensaje de progreso"""
        if self.progress_callback:
            try:
                self.progress_callback(message, level)
            except (AttributeError, TypeError):
                # Si el callback no está listo, usar logging
                logging.info(message)
        else:
            logging.info(message)
    
    def load_whisper_model(self):
        """Cargar modelo Whisper"""
        if not WHISPER_AVAILABLE:
            self.log_progress("Whisper no está disponible", "WARNING")
            return False
            
        try:
            model_name = self.config.get("whisper_model", "base")
            self.log_progress(f"Cargando modelo Whisper: {model_name}")
            self.whisper_model = whisper.load_model(model_name)
            self.log_progress("Modelo Whisper cargado exitosamente")
            return True
        except Exception as e:
            self.log_progress(f"Error cargando modelo Whisper: {e}", "ERROR")
            return False
    
    def extract_audio_segment(self, video_path: Path, start_time: int, duration: int, output_path: Path) -> bool:
        """Extraer segmento de audio usando ffmpeg"""
        try:
            cmd = [
                "ffmpeg",
                "-i", str(video_path),
                "-ss", str(start_time),
                "-t", str(duration),
                "-vn",  # Sin video
                "-acodec", "pcm_s16le",  # Audio sin compresión
                "-ar", "16000",  # Sample rate 16kHz (óptimo para Whisper)
                "-ac", "1",  # Mono
                "-y",  # Sobrescribir archivo
                str(output_path)
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                self.log_progress(f"Audio extraído: {start_time}s-{start_time + duration}s")
                return True
            else:
                self.log_progress(f"Error extrayendo audio: {result.stderr}", "ERROR")
                return False
                
        except Exception as e:
            self.log_progress(f"Error en extracción de audio: {e}", "ERROR")
            return False
    
    def transcribe_audio(self, audio_path: Path, language: str = "es") -> Optional[Dict]:
        """Transcribir audio usando Whisper"""
        try:
            # Cargar modelo si no está cargado
            if not self.whisper_model:
                if not self.load_whisper_model():
                    self.log_progress("Modelo Whisper no disponible", "ERROR")
                    return None
            
            self.log_progress(f"Transcribiendo audio: {audio_path.name}")
            
            # Transcribir con Whisper
            result = self.whisper_model.transcribe(
                str(audio_path),
                language=language,
                task="transcribe",
                word_timestamps=True
            )
            
            self.log_progress(f"Transcripción completada: {len(result['text'])} caracteres")
            
            return {
                "text": result["text"],
                "segments": result.get("segments", []),
                "language": result.get("language", language)
            }
            
        except Exception as e:
            self.log_progress(f"Error en transcripción: {e}", "ERROR")
            return None
    
    def analyze_video_audio(self, video_path: Path, num_segments: int = 6) -> List[Dict]:
        """Analizar audio completo de video en segmentos"""
        try:
            self.log_progress(f"Iniciando análisis de audio: {video_path.name}")
            
            # Obtener duración del video
            duration = self.get_video_duration(video_path)
            if not duration:
                return []
            
            self.log_progress(f"Duración del video: {duration}s")
            
            # Calcular segmentos estratégicos
            segment_duration = 30  # 30 segundos por segmento
            segments_info = []
            
            # Distribuir segmentos a lo largo del video
            for i in range(num_segments):
                start_time = int((i / num_segments) * duration)
                # Asegurar que no excedamos la duración
                if start_time + segment_duration > duration:
                    segment_duration = duration - start_time
                
                if segment_duration > 5:  # Mínimo 5 segundos
                    segments_info.append({
                        "start": start_time,
                        "duration": segment_duration,
                        "position": f"{(i / num_segments) * 100:.1f}%"
                    })
            
            transcriptions = []
            
            # Procesar cada segmento
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                
                for i, segment in enumerate(segments_info):
                    try:
                        self.log_progress(f"Procesando segmento {i+1}/{len(segments_info)} ({segment['position']})")
                        
                        # Extraer audio del segmento
                        audio_file = temp_path / f"segment_{i}.wav"
                        
                        if self.extract_audio_segment(
                            video_path, 
                            segment["start"], 
                            segment["duration"], 
                            audio_file
                        ):
                            # Transcribir segmento
                            transcription = self.transcribe_audio(
                                audio_file, 
                                self.config.get("audio_language", "es")
                            )
                            
                            if transcription:
                                transcriptions.append({
                                    "segment_index": i,
                                    "start_time": segment["start"],
                                    "duration": segment["duration"],
                                    "position": segment["position"],
                                    "text": transcription["text"],
                                    "segments": transcription.get("segments", []),
                                    "language": transcription.get("language", "unknown")
                                })
                                
                                self.log_progress(f"Segmento {i+1} transcrito: '{transcription['text'][:50]}...'")
                    
                    except Exception as e:
                        self.log_progress(f"Error procesando segmento {i+1}: {e}", "ERROR")
                        continue
            
            self.log_progress(f"Análisis de audio completado: {len(transcriptions)} segmentos transcritos")
            return transcriptions
            
        except Exception as e:
            self.log_progress(f"Error en análisis de audio: {e}", "ERROR")
            return []
    
    def get_video_duration(self, video_path: Path) -> Optional[int]:
        """Obtener duración del video en segundos"""
        try:
            cmd = [
                "ffprobe",
                "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                str(video_path)
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                data = json.loads(result.stdout)
                duration = float(data["format"]["duration"])
                return int(duration)
            else:
                self.log_progress(f"Error obteniendo duración: {result.stderr}", "ERROR")
                return None
                
        except Exception as e:
            self.log_progress(f"Error en ffprobe: {e}", "ERROR")
            return None
    
    def search_opensubtitles(self, query: str, max_results: int = 10) -> List[Dict]:
        """Buscar en OpenSubtitles usando texto"""
        try:
            self.log_progress(f"Buscando en OpenSubtitles: '{query[:50]}...'")
            
            # OpenSubtitles API v1 search
            headers = {
                "User-Agent": self.config.get("opensubtitles_user_agent", "VideoSortPro v2.0"),
                "Content-Type": "application/json"
            }
            
            # Buscar por query de texto
            params = {
                "query": query,
                "languages": "es,en",
                "moviehash_match": "include",
                "machine_translated": "exclude"
            }
            
            response = requests.get(
                f"{self.opensubtitles_base_url}/subtitles",
                params=params,
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                results = data.get("data", [])
                
                self.log_progress(f"OpenSubtitles encontró {len(results)} resultados")
                
                # Procesar resultados
                processed_results = []
                for subtitle in results[:max_results]:
                    attributes = subtitle.get("attributes", {})
                    
                    movie_info = {
                        "title": attributes.get("feature_details", {}).get("title", ""),
                        "year": attributes.get("feature_details", {}).get("year", ""),
                        "imdb_id": attributes.get("feature_details", {}).get("imdb_id", ""),
                        "subtitle_id": subtitle.get("id", ""),
                        "language": attributes.get("language", ""),
                        "download_count": attributes.get("download_count", 0),
                        "rating": attributes.get("ratings", 0),
                        "files": attributes.get("files", [])
                    }
                    processed_results.append(movie_info)
                
                return processed_results
            else:
                self.log_progress(f"Error API OpenSubtitles: {response.status_code}", "ERROR")
                return []
                
        except Exception as e:
            self.log_progress(f"Error buscando en OpenSubtitles: {e}", "ERROR")
            return []
    
    def download_subtitle_content(self, subtitle_id: str) -> Optional[str]:
        """Descargar contenido de subtítulo desde OpenSubtitles"""
        try:
            headers = {
                "User-Agent": self.config.get("opensubtitles_user_agent", "VideoSortPro v2.0")
            }
            
            # Obtener link de descarga
            response = requests.get(
                f"{self.opensubtitles_base_url}/download",
                params={"file_id": subtitle_id},
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                download_link = data.get("link")
                
                if download_link:
                    # Descargar contenido del subtítulo
                    subtitle_response = requests.get(download_link, timeout=15)
                    if subtitle_response.status_code == 200:
                        return subtitle_response.text
            
            return None
            
        except Exception as e:
            self.log_progress(f"Error descargando subtítulo: {e}", "ERROR")
            return None
    
    def calculate_text_similarity(self, text1: str, text2: str) -> float:
        """Calcular similitud entre dos textos"""
        try:
            # Limpiar textos
            clean_text1 = self.clean_text_for_comparison(text1)
            clean_text2 = self.clean_text_for_comparison(text2)
            
            # Usar SequenceMatcher para calcular similitud
            similarity = SequenceMatcher(None, clean_text1, clean_text2).ratio()
            
            return similarity
            
        except Exception as e:
            logging.error(f"Error calculando similitud: {e}")
            return 0.0
    
    def clean_text_for_comparison(self, text: str) -> str:
        """Limpiar texto para comparación"""
        # Convertir a minúsculas
        text = text.lower()
        
        # Remover caracteres especiales y números
        text = re.sub(r'[^\w\s]', ' ', text)
        text = re.sub(r'\d+', '', text)
        
        # Remover palabras muy comunes
        stop_words = {
            'el', 'la', 'de', 'que', 'y', 'a', 'en', 'un', 'es', 'se', 'no', 'te', 'lo', 'le',
            'da', 'su', 'por', 'son', 'con', 'para', 'como', 'las', 'del', 'los', 'una', 'pero',
            'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'
        }
        
        words = text.split()
        filtered_words = [word for word in words if word not in stop_words and len(word) > 2]
        
        return ' '.join(filtered_words)
    
    def find_movie_by_audio_analysis(self, transcriptions: List[Dict]) -> Optional[Dict]:
        """Encontrar película usando análisis de audio y subtítulos"""
        try:
            if not transcriptions:
                return None
            
            # Combinar todos los textos transcritos
            all_text = ' '.join([t['text'] for t in transcriptions if t.get('text')])
            
            if len(all_text.strip()) < 10:
                self.log_progress("Texto transcrito insuficiente para búsqueda", "WARNING")
                return None
            
            self.log_progress(f"Texto combinado para búsqueda: {len(all_text)} caracteres")
            
            # Extraer frases distintivas (más de 5 palabras)
            sentences = re.split(r'[.!?]+', all_text)
            distinctive_phrases = []
            
            for sentence in sentences:
                words = sentence.strip().split()
                if len(words) >= 5 and len(words) <= 15:
                    distinctive_phrases.append(sentence.strip())
            
            if not distinctive_phrases:
                self.log_progress("No se encontraron frases distintivas", "WARNING")
                return None
            
            # Buscar las mejores frases en OpenSubtitles
            best_matches = []
            
            for phrase in distinctive_phrases[:5]:  # Máximo 5 frases
                try:
                    results = self.search_opensubtitles(phrase, max_results=3)
                    
                    for result in results:
                        # Calcular puntuación de coincidencia
                        title = result.get('title', '')
                        year = result.get('year', '')
                        download_count = result.get('download_count', 0)
                        rating = result.get('rating', 0)
                        
                        # Puntuación basada en popularidad y calidad
                        score = (download_count * 0.5) + (rating * 0.3)
                        
                        best_matches.append({
                            'title': title,
                            'year': year,
                            'imdb_id': result.get('imdb_id'),
                            'score': score,
                            'matched_phrase': phrase,
                            'subtitle_info': result
                        })
                    
                    time.sleep(1)  # Rate limiting
                    
                except Exception as e:
                    self.log_progress(f"Error buscando frase '{phrase[:30]}...': {e}", "ERROR")
                    continue
            
            if not best_matches:
                return None
            
            # Encontrar el mejor resultado
            best_matches.sort(key=lambda x: x['score'], reverse=True)
            
            # Verificar si hay consenso en los resultados
            title_counts = {}
            for match in best_matches[:10]:  # Top 10 resultados
                title_key = f"{match['title']} ({match['year']})"
                if title_key not in title_counts:
                    title_counts[title_key] = {'count': 0, 'data': match}
                title_counts[title_key]['count'] += 1
            
            # Encontrar título más frecuente
            most_common = max(title_counts.values(), key=lambda x: x['count'])
            
            if most_common['count'] >= 2:  # Al menos 2 coincidencias
                result = most_common['data']
                self.log_progress(f"Película identificada por audio: {result['title']} ({result['year']})")
                self.log_progress(f"Confianza: {most_common['count']} coincidencias de {len(distinctive_phrases)} frases")
                
                return {
                    'title': result['title'],
                    'year': result['year'],
                    'imdb_id': result['imdb_id'],
                    'confidence_score': min(0.9, most_common['count'] / len(distinctive_phrases)),
                    'method': 'audio_analysis',
                    'matched_phrases': most_common['count'],
                    'total_phrases': len(distinctive_phrases)
                }
            
            return None
            
        except Exception as e:
            self.log_progress(f"Error en búsqueda por análisis de audio: {e}", "ERROR")
            return None
    
    def analyze_video_for_identification(self, video_path: Path) -> Optional[Dict]:
        """Pipeline completo de análisis de audio para identificación"""
        try:
            if not WHISPER_AVAILABLE:
                self.log_progress("Whisper no disponible para análisis de audio", "WARNING")
                return None
            
            self.log_progress(f"Iniciando identificación por audio: {video_path.name}")
            
            # Analizar audio del video
            transcriptions = self.analyze_video_audio(video_path, num_segments=8)
            
            if not transcriptions:
                self.log_progress("No se pudo transcribir audio del video", "WARNING")
                return None
            
            # Buscar película usando transcripciones
            result = self.find_movie_by_audio_analysis(transcriptions)
            
            if result:
                self.log_progress(f"Identificación por audio exitosa: {result['title']}")
                return result
            else:
                self.log_progress("No se pudo identificar película por análisis de audio", "WARNING")
                return None
                
        except Exception as e:
            self.log_progress(f"Error en pipeline de identificación por audio: {e}", "ERROR")
            return None