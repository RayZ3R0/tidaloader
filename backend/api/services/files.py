from pathlib import Path
import shutil
import aiohttp
from api.utils.logging import log_info, log_success, log_warning
from api.settings import DOWNLOAD_DIR

def sanitize_path_component(name: str) -> str:
    if not name:
        return "Unknown"
    
    invalid_chars = r'<>:"/\\|?*'
    for char in invalid_chars:
        name = name.replace(char, '_')
    
    name = name.strip('. ')
    
    if len(name) > 200:
        name = name[:200].strip()
    
    return name or "Unknown"

async def organize_file_by_metadata(temp_filepath: Path, metadata: dict, template: str = "{Artist}/{Album}/{TrackNumber} - {Title}", group_compilations: bool = True) -> Path:
    try:
        artist = metadata.get('album_artist') or metadata.get('artist', 'Unknown Artist')
        album = metadata.get('album', 'Unknown Album')
        title = metadata.get('title', temp_filepath.stem)
        track_number = metadata.get('track_number')
        file_ext = metadata.get('file_ext')
        if not file_ext:
            file_ext = temp_filepath.suffix or '.flac'
        file_ext = file_ext if file_ext.startswith('.') else f".{file_ext}"
        
        s_artist = sanitize_path_component(artist)
        s_album = sanitize_path_component(album)
        s_title = sanitize_path_component(title)
        
        is_compilation = artist.lower() in ['various artists', 'various'] or metadata.get('compilation')
        
        track_str = str(track_number).zfill(2) if track_number else "00"
        
        template_artist = s_artist
        template_album = s_album
        
        if group_compilations and is_compilation:
            template_artist = "Compilations"
            if not template_album.startswith("VA - "):
                template_album = f"VA - {template_album}"

        template_vars = {
            "Artist": template_artist,
            "AlbumArtist": s_artist,
            "TrackArtist": sanitize_path_component(metadata.get('artist', artist)),
            "Album": template_album,
            "Title": s_title,
            "TrackNumber": track_str,
            "Year": str(metadata.get('date', '')).split('-')[0] if metadata.get('date') else "Unknown Year"
        }
        
        try:
            clean_template = template.lstrip('/')
            relative_path_str = clean_template.format(**template_vars)
        except KeyError as e:
            log_warning(f"Invalid template key: {e}. Falling back to default.")
            relative_path_str = f"{s_artist}/{s_album}/{track_str} - {s_title}"
            
        if not relative_path_str.endswith(file_ext):
            relative_path_str += file_ext
            
        final_path = DOWNLOAD_DIR / relative_path_str
        final_dir = final_path.parent
        
        final_dir.mkdir(parents=True, exist_ok=True)
        
        if final_path.exists():
            log_warning(f"File already exists at: {final_path}")
            if temp_filepath.exists() and temp_filepath != final_path:
                try:
                    temp_filepath.unlink()
                    temp_lrc = temp_filepath.with_suffix('.lrc')
                    if temp_lrc.exists():
                        temp_lrc.unlink()
                    temp_txt = temp_filepath.with_suffix('.txt')
                    if temp_txt.exists():
                        temp_txt.unlink()
                except Exception:
                    pass
            return final_path
        
        if temp_filepath != final_path:
            shutil.move(str(temp_filepath), str(final_path))
            log_success(f"Organized to: {relative_path_str}")
            
            temp_lrc_path = temp_filepath.with_suffix('.lrc')
            if temp_lrc_path.exists():
                final_lrc_path = final_path.with_suffix('.lrc')
                shutil.move(str(temp_lrc_path), str(final_lrc_path))
                log_success("Moved .lrc file to organized location")
            
            temp_txt_path = temp_filepath.with_suffix('.txt')
            if temp_txt_path.exists():
                final_txt_path = final_path.with_suffix('.txt')
                shutil.move(str(temp_txt_path), str(final_txt_path))
                log_success("Moved .txt file to organized location")
        
        if metadata.get('synced_lyrics') and metadata.get('target_format') != 'opus':
            lrc_path = final_path.with_suffix('.lrc')
            try:
                with open(lrc_path, 'w', encoding='utf-8') as f:
                    f.write(metadata['synced_lyrics'])
                log_success("Saved synced lyrics to .lrc file")
            except Exception as e:
                log_warning(f"Failed to save .lrc file: {e}")
        
        elif metadata.get('plain_lyrics') and metadata.get('target_format') != 'opus':
            txt_path = final_path.with_suffix('.txt')
            try:
                with open(txt_path, 'w', encoding='utf-8') as f:
                    f.write(metadata['plain_lyrics'])
                log_success("Saved plain lyrics to .txt file")
            except Exception as e:
                log_warning(f"Failed to save .txt file: {e}")
        
        if metadata.get('target_format') == 'opus' and metadata.get('cover_url'):
            cover_path = final_dir / 'cover.jpg'
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(metadata['cover_url']) as response:
                        if response.status == 200:
                            image_data = await response.read()
                            with open(cover_path, 'wb') as f:
                                 f.write(image_data)
                            log_success("Saved cover art to cover.jpg")
            except Exception as e:
                log_warning(f"Failed to save cover art: {e}")
        
        return final_path
        
    except Exception as e:
        log_warning(f"Failed to organize file: {e}")
        import traceback
        traceback.print_exc()
        return temp_filepath
