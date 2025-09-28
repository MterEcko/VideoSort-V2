"""
Organizador de archivos para VideoSort Pro
Maneja el movimiento y organización de archivos según estructura Jellyfin
"""

import re
import shutil
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Callable

class FileOrganizer:
    def __init__(self, config):
        self.config = config
        
    def create_jellyfin_structure(self, video_info: Dict, dest_base_path: Path) -> Optional[Path]:
        """Crear estructura de carpetas según convenciones de Jellyfin"""
        try:
            if video_info['type'] == 'movie':
                # Estructura para películas: Movies/Título (Año)/
                title = video_info['title']
                year = video_info.get('year', '')
                
                if year:
                    folder_name = f"{title} ({year})"
                else:
                    folder_name = title
                
                # Limpiar caracteres no válidos
                folder_name = re.sub(r'[<>:"/\\|?*]', '', folder_name)
                movie_folder = dest_base_path / folder_name
                movie_folder.mkdir(parents=True, exist_ok=True)
                
                return movie_folder
            
            elif video_info['type'] == 'series':
                # Estructura para series: Shows/Serie/Season XX/
                title = video_info['title']
                season = video_info['season']
                
                # Limpiar caracteres no válidos
                clean_title = re.sub(r'[<>:"/\\|?*]', '', title)
                
                series_folder = dest_base_path / clean_title
                season_folder = series_folder / f"Season {season:02d}"
                season_folder.mkdir(parents=True, exist_ok=True)
                
                return season_folder
            
            elif video_info['type'] == 'extra':
                # Estructura para extras: Shows/Serie/Specials/ o Shows/Serie/Season XX/Extras/
                title = video_info['title']
                extra_type = video_info.get('extra_type', 'extra')
                
                # Limpiar caracteres no válidos
                clean_title = re.sub(r'[<>:"/\\|?*]', '', title)
                
                series_folder = dest_base_path / clean_title
                
                # Crear carpeta de extras según el tipo
                if extra_type in ['featurette', 'documentary', 'interview']:
                    extras_folder = series_folder / "Specials"
                else:
                    extras_folder = series_folder / "Extras"
                
                extras_folder.mkdir(parents=True, exist_ok=True)
                return extras_folder
        
        except Exception as e:
            logging.error(f"Error creando estructura: {e}")
            return None
    
    def generate_jellyfin_filename(self, video_info: Dict, original_filename: str) -> str:
        """Generar nombre de archivo según convenciones de Jellyfin"""
        extension = Path(original_filename).suffix
        
        if video_info['type'] == 'movie':
            title = video_info['title']
            year = video_info.get('year', '')
            
            if year:
                filename = f"{title} ({year}){extension}"
            else:
                filename = f"{title}{extension}"
        
        elif video_info['type'] == 'series':
            title = video_info['title']
            season = video_info['season']
            episode = video_info['episode']
            
            filename = f"{title} - S{season:02d}E{episode:02d}{extension}"
        
        elif video_info['type'] == 'extra':
            # Para extras, mantener el nombre original pero limpio
            title = video_info['title']
            original_name = Path(original_filename).stem
            
            # Limpiar el nombre original de patrones problemáticos
            clean_original = re.sub(r'[<>:"/\\|?*]', '', original_name)
            
            # Si el nombre original es descriptivo, usarlo
            if len(clean_original) > 5:
                filename = f"{clean_original}{extension}"
            else:
                # Fallback al título de la serie + tipo de extra
                extra_type = video_info.get('extra_type', 'Extra')
                filename = f"{title} - {extra_type.title()}{extension}"
        
        else:
            filename = original_filename
        
        # Limpiar caracteres no válidos
        filename = re.sub(r'[<>:"/\\|?*]', '', filename)
        return filename
    
    def create_nfo_file(self, video_info: Dict, video_file_path: Path):
        """Crear archivo NFO para Jellyfin con metadatos"""
        try:
            nfo_path = video_file_path.with_suffix('.nfo')
            
            # Crear contenido NFO básico
            if video_info['type'] == 'movie':
                nfo_content = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<movie>
    <title>{video_info['title']}</title>
    <originaltitle>{video_info.get('original_title', video_info['title'])}</originaltitle>
    <year>{video_info.get('year', '')}</year>
    <plot>{video_info.get('overview', '')}</plot>
    <tmdbid>{video_info.get('tmdb_id', '')}</tmdbid>
    <id>{video_info.get('tmdb_id', '')}</id>
    <uniqueid type="tmdb">{video_info.get('tmdb_id', '')}</uniqueid>
</movie>"""
            
            elif video_info['type'] == 'series':
                nfo_content = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<episodedetails>
    <title>{video_info['title']}</title>
    <season>{video_info.get('season', '')}</season>
    <episode>{video_info.get('episode', '')}</episode>
    <plot>{video_info.get('overview', '')}</plot>
    <tmdbid>{video_info.get('tmdb_id', '')}</tmdbid>
    <uniqueid type="tmdb">{video_info.get('tmdb_id', '')}</uniqueid>
</episodedetails>"""
            
            else:
                return
            
            with open(nfo_path, 'w', encoding='utf-8') as f:
                f.write(nfo_content)
            
            logging.info(f"Archivo NFO creado: {nfo_path.name}")
            
        except Exception as e:
            logging.error(f"Error creando archivo NFO: {e}")
    
    def create_analysis_file(self, analysis_result: Dict, video_file_path: Path):
        """Crear archivo con información del análisis visual"""
        try:
            analysis_file_path = video_file_path.with_suffix('.analysis.txt')
            
            content = f"""ANÁLISIS VISUAL - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
{'='*60}

Archivo: {video_file_path.name}
Confianza del análisis: {analysis_result.get('confidence_score', 0):.2f}

TEXTO DETECTADO:
{analysis_result.get('detected_text', 'No se detectó texto')}

ACTORES DETECTADOS:
{', '.join(analysis_result.get('detected_actors', [])) if analysis_result.get('detected_actors') else 'No se detectaron actores conocidos'}

SUGERENCIA DE BÚSQUEDA:
{analysis_result.get('google_search_suggestion', 'No se generó sugerencia')}

NOTA: Este archivo contiene información extraída automáticamente del video
usando reconocimiento óptico de caracteres (OCR) y reconocimiento facial.
"""
            
            with open(analysis_file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            logging.info(f"Archivo de análisis creado: {analysis_file_path.name}")
            
        except Exception as e:
            logging.error(f"Error creando archivo de análisis: {e}")
    
    def process_videos(self, paths: Dict[str, Path], options: Dict, tmdb_client, video_analyzer, progress_bar, log_callback):
        """Procesar y organizar todos los videos"""
        stats = {
            'movies_processed': 0,
            'series_processed': 0,
            'unknown_files': 0,
            'errors': 0,
            'skipped_low_confidence': 0,
            'visual_analysis_used': 0,
            'alternative_search_success': 0,
            'actors_detected': set(),
            'processing_time': datetime.now()
        }
        
        try:
            source_path = paths['source']
            movies_dest = paths['movies']
            series_dest = paths['series']
            unknown_dest = paths.get('unknown') or source_path / "Unknown"
            
            # Crear carpetas destino
            movies_dest.mkdir(parents=True, exist_ok=True)
            series_dest.mkdir(parents=True, exist_ok=True)
            unknown_dest.mkdir(parents=True, exist_ok=True)
            
            video_extensions = set(self.config.get('video_extensions', []))
            
            # Encontrar todos los videos
            videos_found = []
            for file_path in source_path.rglob('*'):
                if file_path.is_file() and file_path.suffix.lower() in video_extensions:
                    videos_found.append(file_path)
            
            log_callback(f"Procesando {len(videos_found)} archivos de video...")
            
            # Configurar barra de progreso
            progress_bar.configure(mode='determinate', maximum=len(videos_found))
            
            for i, video_path in enumerate(videos_found):
                try:
                    progress_bar['value'] = i + 1
                    
                    log_callback(f"Procesando: {video_path.name}")
                    
                    # Extraer información básica
                    video_info = video_analyzer.extract_video_info(video_path.name)
                    
                    if not video_info:
                        log_callback(f"No se pudo extraer información de: {video_path.name}", "WARNING")
                        if options['move_files']:
                            dest_file = unknown_dest / video_path.name
                            shutil.move(str(video_path), str(dest_file))
                            log_callback(f"Movido a desconocidos: {video_path.name}")
                        stats['unknown_files'] += 1
                        continue
                    
                    # Análisis visual si está habilitado
                    analysis_result = None
                    needs_visual_analysis = (
                        len(video_info['title'].split()) < 2 or 
                        not video_info.get('year') or
                        any(char in video_info['title'].lower() for char in ['~', 'tmp', 'temp'])
                    )
                    
                    if needs_visual_analysis and (options['use_facial_recognition'] or options['use_ocr']):
                        log_callback(f"Realizando análisis visual de: {video_path.name}")
                        analysis_result = video_analyzer.perform_visual_analysis(video_path)
                        
                        if analysis_result:
                            stats['visual_analysis_used'] += 1
                            log_callback(f"Análisis visual completado (confianza: {analysis_result['confidence']:.2f})")
                            
                            if analysis_result.get('actors'):
                                stats['actors_detected'].update(analysis_result['actors'])
                                log_callback(f"Actores detectados: {', '.join(analysis_result['actors'])}")
                    
                    # Consultar TMDB
                    tmdb_info = None
                    if options['use_tmdb']:
                        if video_info['type'] == 'series':
                            tmdb_info = tmdb_client.search_tv_show(
                                video_info['search_title'],
                                options.get('tmdb_min_score', 0.8)
                            )
                        else:
                            tmdb_info = tmdb_client.search_movie(
                                video_info['search_title'], 
                                video_info.get('year'),
                                options.get('tmdb_min_score', 0.8)
                            )
                        
                        # Si TMDB falla y hay análisis visual, intentar búsqueda alternativa
                        if not tmdb_info and analysis_result:
                            log_callback("TMDB falló, intentando búsqueda alternativa...")
                            tmdb_info = self.enhanced_search_with_visual_data(
                                video_info, analysis_result, tmdb_client, options
                            )
                            
                            if tmdb_info and not tmdb_info.get('needs_manual_review'):
                                stats['alternative_search_success'] += 1
                                log_callback("Búsqueda alternativa exitosa!")
                        
                        if tmdb_info and not tmdb_info.get('needs_manual_review'):
                            video_info.update(tmdb_info)
                            similarity = tmdb_info.get('similarity_score', 1.0)
                            log_callback(f"Información TMDB: '{tmdb_info['title']}' (similitud: {similarity:.2f})")
                        elif not tmdb_info:
                            log_callback(f"No se encontró información en TMDB para: {video_info['title']}", "WARNING")
                    
                    # Decidir si procesar el archivo
                    should_process = True
                    
                    if options['strict_matching']:
                        if options['use_tmdb'] and not tmdb_info:
                            log_callback(f"Saltando (sin metadatos): {video_path.name}", "WARNING")
                            stats['skipped_low_confidence'] += 1
                            should_process = False
                        elif tmdb_info and tmdb_info.get('similarity_score', 0) < options.get('tmdb_min_score', 0.8):
                            log_callback(f"Saltando (baja similitud): {video_path.name}", "WARNING")
                            stats['skipped_low_confidence'] += 1
                            should_process = False
                    
                    if not should_process:
                        if options['move_files']:
                            dest_file = unknown_dest / video_path.name
                            shutil.move(str(video_path), str(dest_file))
                            log_callback(f"Movido a desconocidos: {video_path.name}")
                        stats['unknown_files'] += 1
                        continue
                    
                    # Usar información visual como fallback para el naming
                    if not tmdb_info and analysis_result and analysis_result.get('google_search_suggestion'):
                        video_info['title'] = analysis_result['google_search_suggestion']
                        log_callback(f"Usando título del análisis visual: {video_info['title']}")
                    
                    # Determinar carpeta destino
                    if video_info['type'] == 'movie':
                        dest_folder = self.create_jellyfin_structure(video_info, movies_dest)
                        stats['movies_processed'] += 1
                    elif video_info['type'] == 'series':
                        dest_folder = self.create_jellyfin_structure(video_info, series_dest)
                        stats['series_processed'] += 1
                    else:
                        dest_folder = unknown_dest
                        stats['unknown_files'] += 1
                    
                    if not dest_folder:
                        log_callback(f"Error creando carpeta para: {video_path.name}", "ERROR")
                        stats['errors'] += 1
                        continue
                    
                    # Generar nombre del archivo final
                    new_filename = self.generate_jellyfin_filename(video_info, video_path.name)
                    dest_file = dest_folder / new_filename
                    
                    # Mover archivo si está habilitado
                    if options['move_files']:
                        # Verificar si el archivo ya existe
                        if dest_file.exists():
                            log_callback(f"Archivo ya existe: {dest_file}", "WARNING")
                            counter = 1
                            while dest_file.exists():
                                name_without_ext = dest_file.stem
                                ext = dest_file.suffix
                                dest_file = dest_folder / f"{name_without_ext} ({counter}){ext}"
                                counter += 1
                        
                        # Mover archivo
                        shutil.move(str(video_path), str(dest_file))
                        log_callback(f"Movido: {video_path.name} -> {dest_file}")
                    else:
                        log_callback(f"Análisis: {video_path.name} -> {dest_file}")
                    
                    # Crear archivo NFO para Jellyfin
                    if tmdb_info and tmdb_info.get('tmdb_id') and not tmdb_info.get('needs_manual_review'):
                        self.create_nfo_file(video_info, dest_file)
                    
                    # Crear archivo de información adicional si se usó análisis visual
                    if analysis_result:
                        self.create_analysis_file(analysis_result, dest_file)
                    
                except Exception as e:
                    log_callback(f"Error procesando {video_path.name}: {str(e)}", "ERROR")
                    stats['errors'] += 1
            
            # Calcular tiempo de procesamiento
            processing_time = datetime.now() - stats['processing_time']
            stats['processing_time'] = str(processing_time).split('.')[0]  # Remover microsegundos
            
            log_callback("Procesamiento completado!")
            
        except Exception as e:
            log_callback(f"Error crítico durante el procesamiento: {str(e)}", "ERROR")
            stats['errors'] += 1
        
        return stats
    
    def enhanced_search_with_visual_data(self, video_info: Dict, visual_analysis: Dict, tmdb_client, options: Dict):
        """Búsqueda mejorada usando datos visuales cuando TMDB falla"""
        try:
            if not visual_analysis:
                return None
            
            # Intentar búsquedas alternativas
            search_attempts = []
            
            # 1. Usar sugerencia de búsqueda visual
            if visual_analysis.get('google_search_suggestion'):
                search_attempts.append(visual_analysis['google_search_suggestion'])
            
            # 2. Usar actores detectados
            if visual_analysis.get('actors'):
                main_actor = visual_analysis['actors'][0]
                search_attempts.append(f"movie {main_actor}")
                search_attempts.append(f"film {main_actor}")
            
            # 3. Usar texto extraído directamente
            if visual_analysis.get('detected_text'):
                possible_titles = self.extract_possible_titles_from_text(visual_analysis['detected_text'])
                search_attempts.extend(possible_titles)
            
            # Intentar cada búsqueda
            for search_query in search_attempts:
                if len(search_query.strip()) < 3:
                    continue
                
                logging.info(f"Búsqueda alternativa: '{search_query}'")
                
                # Intentar en TMDB con el nuevo query
                if video_info['type'] == 'series':
                    tmdb_result = tmdb_client.search_tv_show(search_query, 0.5)
                else:
                    tmdb_result = tmdb_client.search_movie(search_query, None, 0.5)
                
                if tmdb_result and tmdb_result.get('similarity_score', 0) > 0.5:
                    logging.info(f"Encontrado con búsqueda alternativa: {tmdb_result['title']}")
                    return tmdb_result
            
            # Si no encuentra nada, generar información básica
            fallback_info = {
                'title': visual_analysis.get('google_search_suggestion', video_info.get('title', 'Unknown')),
                'search_suggestion': visual_analysis.get('google_search_suggestion'),
                'detected_actors': visual_analysis.get('actors', []),
                'confidence_score': visual_analysis.get('confidence', 0),
                'needs_manual_review': True
            }
            
            return fallback_info
            
        except Exception as e:
            logging.error(f"Error en búsqueda mejorada: {e}")
            return None
    
    def extract_possible_titles_from_text(self, text: str) -> List[str]:
        """Extraer posibles títulos de películas del texto OCR"""
        possible_titles = []
        
        try:
            # Patrones para encontrar títulos
            title_patterns = [
                r'\b([A-Z][a-z]+(?: [A-Z][a-z]+){1,3})\b',  # Títulos en formato título (2-4 palabras)
                r'\b([A-Z]{3,}(?: [A-Z]{3,})*)\b',          # Títulos en mayúsculas
                r'"([^"]{5,30})"',                           # Texto entre comillas
                r"'([^']{5,30})'",                           # Texto entre comillas simples
            ]
            
            for pattern in title_patterns:
                matches = re.findall(pattern, text)
                for match in matches:
                    if isinstance(match, tuple):
                        match = match[0]
                    
                    # Filtrar matches válidos
                    if (len(match) > 4 and 
                        len(match) < 50 and 
                        not match.lower() in ['presents', 'production', 'entertainment', 'pictures']):
                        possible_titles.append(match.strip())
            
            # Remover duplicados manteniendo orden
            seen = set()
            unique_titles = []
            for title in possible_titles:
                if title.lower() not in seen:
                    seen.add(title.lower())
                    unique_titles.append(title)
            
            return unique_titles[:5]  # Máximo 5 intentos
            
        except Exception:
            return []