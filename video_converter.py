"""
Conversor de video usando ffmpeg
Optimiza videos para compatibilidad con Jellyfin
"""

import subprocess
import json
import logging
from pathlib import Path
from typing import Dict, Optional, Tuple, List
import shutil

class VideoConverter:
    def __init__(self, config, progress_callback=None):
        self.config = config
        self.progress_callback = progress_callback
        
        # Codecs soportados por Jellyfin
        self.jellyfin_video_codecs = ["h264", "h265", "hevc", "av1", "vp9"]
        self.jellyfin_audio_codecs = ["aac", "ac3", "eac3", "mp3", "flac"]
        self.jellyfin_containers = [".mp4", ".mkv", ".avi", ".webm"]
    
    def log_progress(self, message: str, level: str = "INFO"):
        """Enviar mensaje de progreso"""
        if self.progress_callback:
            self.progress_callback(message, level)
        logging.info(message)
    
    def check_ffmpeg_available(self) -> bool:
        """Verificar si ffmpeg está disponible"""
        try:
            result = subprocess.run(["ffmpeg", "-version"], 
                                  capture_output=True, text=True)
            return result.returncode == 0
        except FileNotFoundError:
            return False
    
    def get_video_info(self, video_path: Path) -> Optional[Dict]:
        """Obtener información detallada del video"""
        try:
            cmd = [
                "ffprobe",
                "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                "-show_streams",
                str(video_path)
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                data = json.loads(result.stdout)
                
                video_info = {
                    "format": data.get("format", {}),
                    "video_streams": [],
                    "audio_streams": [],
                    "subtitle_streams": []
                }
                
                # Analizar streams
                for stream in data.get("streams", []):
                    codec_type = stream.get("codec_type")
                    
                    if codec_type == "video":
                        video_info["video_streams"].append({
                            "codec_name": stream.get("codec_name"),
                            "width": stream.get("width"),
                            "height": stream.get("height"),
                            "bit_rate": stream.get("bit_rate"),
                            "duration": stream.get("duration"),
                            "fps": eval(stream.get("r_frame_rate", "0/1")),
                            "pix_fmt": stream.get("pix_fmt")
                        })
                    
                    elif codec_type == "audio":
                        video_info["audio_streams"].append({
                            "codec_name": stream.get("codec_name"),
                            "channels": stream.get("channels"),
                            "sample_rate": stream.get("sample_rate"),
                            "bit_rate": stream.get("bit_rate"),
                            "language": stream.get("tags", {}).get("language", "unknown")
                        })
                    
                    elif codec_type == "subtitle":
                        video_info["subtitle_streams"].append({
                            "codec_name": stream.get("codec_name"),
                            "language": stream.get("tags", {}).get("language", "unknown")
                        })
                
                return video_info
            else:
                self.log_progress(f"Error obteniendo info de video: {result.stderr}", "ERROR")
                return None
                
        except Exception as e:
            self.log_progress(f"Error analizando video: {e}", "ERROR")
            return None
    
    def needs_conversion(self, video_info: Dict) -> Tuple[bool, List[str]]:
        """Determinar si el video necesita conversión"""
        conversion_reasons = []
        
        try:
            # Verificar formato del contenedor
            format_name = video_info.get("format", {}).get("format_name", "")
            file_extension = Path(video_info.get("format", {}).get("filename", "")).suffix.lower()
            
            if file_extension not in self.jellyfin_containers:
                conversion_reasons.append(f"Contenedor no compatible: {file_extension}")
            
            # Verificar streams de video
            video_streams = video_info.get("video_streams", [])
            if video_streams:
                video_codec = video_streams[0].get("codec_name", "").lower()
                if video_codec not in self.jellyfin_video_codecs:
                    conversion_reasons.append(f"Codec de video no compatible: {video_codec}")
                
                # Verificar resolución excesiva
                width = video_streams[0].get("width", 0)
                height = video_streams[0].get("height", 0)
                if width > 1920 or height > 1080:
                    conversion_reasons.append(f"Resolución muy alta: {width}x{height}")
            
            # Verificar streams de audio
            audio_streams = video_info.get("audio_streams", [])
            if audio_streams:
                audio_codec = audio_streams[0].get("codec_name", "").lower()
                if audio_codec not in self.jellyfin_audio_codecs:
                    conversion_reasons.append(f"Codec de audio no compatible: {audio_codec}")
            
            needs_conversion = len(conversion_reasons) > 0
            return needs_conversion, conversion_reasons
            
        except Exception as e:
            self.log_progress(f"Error evaluando necesidad de conversión: {e}", "ERROR")
            return False, []
    
    def build_ffmpeg_command(self, input_path: Path, output_path: Path, 
                           video_info: Dict, conversion_reasons: List[str]) -> List[str]:
        """Construir comando ffmpeg optimizado"""
        cmd = ["ffmpeg", "-i", str(input_path)]
        
        # Configuración de video
        target_video_codec = self.config.get("target_video_codec", "h264")
        video_quality = self.config.get("video_quality_preset", "medium")
        max_bitrate = self.config.get("max_video_bitrate", "2M")
        
        # Mapear streams
        cmd.extend(["-map", "0:v:0"])  # Primer stream de video
        cmd.extend(["-map", "0:a:0"])  # Primer stream de audio
        
        # Configuración de video
        video_streams = video_info.get("video_streams", [])
        if video_streams:
            width = video_streams[0].get("width", 0)
            height = video_streams[0].get("height", 0)
            
            # Escalar si es necesario (máximo 1080p)
            if width > 1920 or height > 1080:
                cmd.extend(["-vf", "scale=1920:1080:force_original_aspect_ratio=decrease"])
            
            # Codec de video
            if target_video_codec == "h265" or target_video_codec == "hevc":
                cmd.extend(["-c:v", "libx265"])
                cmd.extend(["-preset", video_quality])
                cmd.extend(["-crf", "23"])
            else:  # h264 por defecto
                cmd.extend(["-c:v", "libx264"])
                cmd.extend(["-preset", video_quality])
                cmd.extend(["-crf", "23"])
            
            # Bitrate máximo
            cmd.extend(["-maxrate", max_bitrate])
            cmd.extend(["-bufsize", f"{int(max_bitrate[:-1]) * 2}M"])
        
        # Configuración de audio
        target_audio_codec = self.config.get("target_audio_codec", "aac")
        audio_streams = video_info.get("audio_streams", [])
        
        if audio_streams:
            channels = audio_streams[0].get("channels", 2)
            
            if target_audio_codec == "aac":
                cmd.extend(["-c:a", "aac"])
                cmd.extend(["-b:a", "128k" if channels <= 2 else "256k"])
            else:
                cmd.extend(["-c:a", "copy"])  # Copiar audio original
        
        # Copiar subtítulos si existen
        subtitle_streams = video_info.get("subtitle_streams", [])
        if subtitle_streams:
            cmd.extend(["-c:s", "copy"])
        
        # Configuraciones adicionales
        cmd.extend(["-y"])  # Sobrescribir archivo de salida
        cmd.append(str(output_path))
        
        return cmd
    
    def convert_video(self, input_path: Path, output_path: Path, 
                     progress_callback=None) -> bool:
        """Convertir video con ffmpeg"""
        try:
            # Obtener información del video
            video_info = self.get_video_info(input_path)
            if not video_info:
                return False
            
            # Verificar si necesita conversión
            needs_conv, reasons = self.needs_conversion(video_info)
            if not needs_conv:
                self.log_progress(f"Video no necesita conversión: {input_path.name}")
                return True
            
            self.log_progress(f"Convirtiendo video: {input_path.name}")
            self.log_progress(f"Razones: {', '.join(reasons)}")
            
            # Construir comando ffmpeg
            cmd = self.build_ffmpeg_command(input_path, output_path, video_info, reasons)
            
            # Ejecutar conversión
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True
            )
            
            # Monitorear progreso si es posible
            duration = None
            if video_info.get("format", {}).get("duration"):
                duration = float(video_info["format"]["duration"])
            
            while True:
                output = process.stderr.readline()
                if output == '' and process.poll() is not None:
                    break
                
                if output and duration:
                    # Buscar tiempo actual en la salida de ffmpeg
                    if "time=" in output:
                        try:
                            time_str = output.split("time=")[1].split()[0]
                            current_time = self.parse_time_to_seconds(time_str)
                            progress = (current_time / duration) * 100
                            
                            if progress_callback:
                                progress_callback(min(99, progress))
                            
                        except Exception:
                            pass
            
            # Verificar resultado
            return_code = process.poll()
            
            if return_code == 0:
                self.log_progress(f"Conversión exitosa: {output_path.name}")
                return True
            else:
                error_output = process.stderr.read()
                self.log_progress(f"Error en conversión: {error_output}", "ERROR")
                return False
                
        except Exception as e:
            self.log_progress(f"Error durante conversión: {e}", "ERROR")
            return False
    
    def parse_time_to_seconds(self, time_str: str) -> float:
        """Convertir tiempo HH:MM:SS.ms a segundos"""
        try:
            parts = time_str.split(":")
            hours = float(parts[0])
            minutes = float(parts[1])
            seconds = float(parts[2])
            return hours * 3600 + minutes * 60 + seconds
        except Exception:
            return 0.0
    
    def verify_video_integrity(self, video_path: Path) -> bool:
        """Verificar integridad del video"""
        try:
            cmd = [
                "ffmpeg",
                "-v", "error",
                "-i", str(video_path),
                "-f", "null",
                "-"
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            
            if result.returncode == 0:
                self.log_progress(f"Video íntegro: {video_path.name}")
                return True
            else:
                self.log_progress(f"Video corrupto: {video_path.name}", "ERROR")
                self.log_progress(f"Error: {result.stderr}", "ERROR")
                return False
                
        except subprocess.TimeoutExpired:
            self.log_progress(f"Timeout verificando video: {video_path.name}", "WARNING")
            return False
        except Exception as e:
            self.log_progress(f"Error verificando integridad: {e}", "ERROR")
            return False
    
    def convert_video_with_backup(self, video_path: Path) -> bool:
        """Convertir video manteniendo backup del original"""
        try:
            # Crear nombre para archivo convertido
            output_path = video_path.with_suffix(".converted.mp4")
            backup_path = video_path.with_suffix(f"{video_path.suffix}.backup")
            
            # Verificar que no sea necesaria la conversión
            video_info = self.get_video_info(video_path)
            if not video_info:
                return False
            
            needs_conv, reasons = self.needs_conversion(video_info)
            if not needs_conv:
                self.log_progress(f"Video ya es compatible: {video_path.name}")
                return True
            
            # Convertir video
            success = self.convert_video(video_path, output_path)
            
            if success:
                # Verificar integridad del video convertido
                if self.verify_video_integrity(output_path):
                    # Crear backup del original
                    shutil.move(str(video_path), str(backup_path))
                    
                    # Mover video convertido al lugar original
                    shutil.move(str(output_path), str(video_path))
                    
                    self.log_progress(f"Conversión completada: {video_path.name}")
                    self.log_progress(f"Backup creado: {backup_path.name}")
                    
                    return True
                else:
                    # Eliminar archivo convertido corrupto
                    if output_path.exists():
                        output_path.unlink()
                    self.log_progress(f"Video convertido corrupto, manteniendo original", "ERROR")
                    return False
            else:
                # Limpiar archivo de salida si existe
                if output_path.exists():
                    output_path.unlink()
                return False
                
        except Exception as e:
            self.log_progress(f"Error en conversión con backup: {e}", "ERROR")
            return False
    
    def batch_convert_videos(self, video_paths: List[Path], 
                           progress_callback=None) -> Dict[str, int]:
        """Convertir múltiples videos en lote"""
        stats = {
            "total": len(video_paths),
            "converted": 0,
            "skipped": 0,
            "failed": 0
        }
        
        try:
            for i, video_path in enumerate(video_paths):
                try:
                    if progress_callback:
                        overall_progress = (i / len(video_paths)) * 100
                        progress_callback(overall_progress, f"Procesando: {video_path.name}")
                    
                    self.log_progress(f"Procesando video {i+1}/{len(video_paths)}: {video_path.name}")
                    
                    # Verificar que el archivo existe
                    if not video_path.exists():
                        self.log_progress(f"Archivo no encontrado: {video_path}", "ERROR")
                        stats["failed"] += 1
                        continue
                    
                    # Verificar información del video
                    video_info = self.get_video_info(video_path)
                    if not video_info:
                        self.log_progress(f"No se pudo analizar: {video_path.name}", "ERROR")
                        stats["failed"] += 1
                        continue
                    
                    # Verificar si necesita conversión
                    needs_conv, reasons = self.needs_conversion(video_info)
                    
                    if not needs_conv:
                        self.log_progress(f"No necesita conversión: {video_path.name}")
                        stats["skipped"] += 1
                        continue
                    
                    # Convertir video
                    if self.convert_video_with_backup(video_path):
                        stats["converted"] += 1
                    else:
                        stats["failed"] += 1
                        
                except Exception as e:
                    self.log_progress(f"Error procesando {video_path.name}: {e}", "ERROR")
                    stats["failed"] += 1
            
            self.log_progress(f"Conversión en lote completada:")
            self.log_progress(f"  Total: {stats['total']}")
            self.log_progress(f"  Convertidos: {stats['converted']}")
            self.log_progress(f"  Omitidos: {stats['skipped']}")
            self.log_progress(f"  Fallidos: {stats['failed']}")
            
            return stats
            
        except Exception as e:
            self.log_progress(f"Error en conversión en lote: {e}", "ERROR")
            return stats