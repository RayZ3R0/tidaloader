from pathlib import Path
from api.utils.logging import log_info, log_success, log_warning, log_step
import asyncio
import shutil
from lyrics_client import lyrics_client

async def fetch_and_store_lyrics(filepath: Path, metadata: dict, audio_file=None):
    if metadata.get('title') and metadata.get('artist'):
        try:
            log_info("Fetching lyrics...")
            lyrics_result = await lyrics_client.get_lyrics(
                track_name=metadata['title'],
                artist_name=metadata['artist'],
                album_name=metadata.get('album'),
                duration=metadata.get('duration')
            )
            
            if lyrics_result:
                if lyrics_result.synced_lyrics:
                    metadata['synced_lyrics'] = lyrics_result.synced_lyrics
                    log_success("Synced lyrics found (will save to .lrc)")
                elif lyrics_result.plain_lyrics:
                    metadata['plain_lyrics'] = lyrics_result.plain_lyrics
                    log_success("Plain lyrics found (will save to .txt)")
                
        except Exception as e:
            log_warning(f"Failed to fetch lyrics: {e}")
        
        if audio_file and metadata.get('synced_lyrics'):
            try:
                lyrics_text = metadata['synced_lyrics']
                
                for i, line in enumerate(lyrics_text.split('\n')):
                    if line.strip():
                        audio_file[f'LYRICS_LINE_{i+1}'] = line.strip()
                
                log_success(f"Embedded {len(lyrics_text.splitlines())} lines of lyrics")
            except Exception as e:
                log_warning(f"Failed to embed lyrics: {e}")

async def embed_lyrics_with_ffmpeg(filepath: Path, metadata: dict):
    """Embed lyrics into the audio file using FFmpeg"""
    try:
        import subprocess
        

        try:
            subprocess.run(["ffmpeg", "-version"], check=True, capture_output=True)
        except (FileNotFoundError, subprocess.CalledProcessError):
            log_warning("FFmpeg not found. Skipping lyrics embedding.")
            return

        lyrics = metadata.get('synced_lyrics') or metadata.get('plain_lyrics')
        if not lyrics:
            log_info("No lyrics found to embed.")
            return

        log_step("3.8/4", f"Embedding lyrics with FFmpeg...")
        

        lyrics_path = filepath.with_suffix('.lyrics.txt')
        with open(lyrics_path, 'w', encoding='utf-8') as f:
            f.write(lyrics)
            
        output_path = filepath.with_suffix('.temp' + filepath.suffix)
        

        cmd = [
            "ffmpeg", "-y", "-i", str(filepath),
            "-map", "0", "-c", "copy",
            "-metadata", f"LYRICS={lyrics}",
            str(output_path)
        ]
        

        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        
        if process.returncode == 0:

            shutil.move(str(output_path), str(filepath))
            log_success("Lyrics embedded with FFmpeg")
        else:
            log_warning(f"FFmpeg lyrics embedding failed: {stderr.decode()}")
            if output_path.exists():
                output_path.unlink()
                

        if lyrics_path.exists():
            lyrics_path.unlink()
            
    except Exception as e:
        log_warning(f"Failed to embed lyrics with FFmpeg: {e}")
        import traceback
        traceback.print_exc()
