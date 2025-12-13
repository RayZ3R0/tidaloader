from pathlib import Path
import asyncio
import aiohttp
import traceback

from api.state import active_downloads
from download_state import download_state_manager
from api.utils.logging import log_error, log_info, log_step, log_success, log_warning
from api.services.audio import transcode_to_mp3, transcode_to_opus, write_metadata_tags
from api.services.files import organize_file_by_metadata
from api.services.beets import run_beets_import
from api.services.lyrics import embed_lyrics_with_ffmpeg
from queue_manager import queue_manager

async def download_file_async(
    track_id: int, 
    stream_url: str, 
    filepath: Path, 
    filename: str, 
    metadata: dict = None,
    organization_template: str = "{Artist}/{Album}/{TrackNumber} - {Title}",
    group_compilations: bool = True,
    run_beets: bool = False,
    embed_lyrics: bool = False
):
    processed_path = filepath
    try:
        log_step("3/4", f"Downloading {filename}...")
        
        if track_id not in active_downloads:
            active_downloads[track_id] = {'progress': 0, 'status': 'downloading'}
        
        download_state_manager.set_downloading(track_id, 0, metadata)
        
        async with aiohttp.ClientSession() as session:
            async with session.get(stream_url, timeout=aiohttp.ClientTimeout(total=300)) as response:
                if response.status != 200:
                    error_msg = f"HTTP {response.status}"
                    log_error(f"Download failed: {error_msg}")
                    if track_id in active_downloads:
                        active_downloads[track_id] = {'progress': 0, 'status': 'failed'}
                        download_state_manager.set_failed(track_id, error_msg, metadata)
                        await asyncio.sleep(5)
                        del active_downloads[track_id]
                    return
                
                total_size = int(response.headers.get('content-length', 0))
                downloaded = 0
                
                # Ensure the directory exists
                filepath.parent.mkdir(parents=True, exist_ok=True)
                
                with open(filepath, 'wb') as f:
                    async for chunk in response.content.iter_chunked(8192):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            
                            if total_size > 0:
                                progress = int((downloaded / total_size) * 100)
                                active_downloads[track_id] = {
                                    'progress': progress,
                                    'status': 'downloading'
                                }
                                download_state_manager.update_progress(track_id, progress)
                                # Update queue manager for frontend sync
                                queue_manager.update_active_progress(track_id, progress, 'downloading')
                            
                            await asyncio.sleep(0.01)
        
        if metadata:
            if metadata.get('target_format') == 'mp3':
                bitrate = metadata.get('bitrate_kbps', 256)
                mp3_path = filepath.with_suffix('.mp3')
                log_step("3.5/4", f"Transcoding to MP3 ({bitrate} kbps)...")
                active_downloads[track_id] = {
                    'progress': 95,
                    'status': 'transcoding'
                }
                download_state_manager.update_progress(track_id, 95)
                await transcode_to_mp3(filepath, mp3_path, bitrate)
                processed_path = mp3_path
                metadata['file_ext'] = '.mp3'
                try:
                    filepath.unlink()
                except FileNotFoundError:
                    pass
                except Exception as exc:
                    log_warning(f"Failed to remove intermediate file: {exc}")
            elif metadata.get('target_format') == 'opus':
                bitrate = metadata.get('bitrate_kbps', 192)
                opus_path = filepath.with_suffix('.opus')
                log_step("3.5/4", f"Transcoding to Opus ({bitrate} kbps)...")
                active_downloads[track_id] = {
                    'progress': 95,
                    'status': 'transcoding'
                }
                download_state_manager.update_progress(track_id, 95)
                await transcode_to_opus(filepath, opus_path, bitrate)
                processed_path = opus_path
                metadata['file_ext'] = '.opus'
                try:
                    filepath.unlink()
                except FileNotFoundError:
                    pass
                except Exception as exc:
                    log_warning(f"Failed to remove intermediate file: {exc}")
            else:
                processed_path = filepath
                metadata.setdefault('file_ext', filepath.suffix)
        
        if metadata:
            log_step("4/4", "Writing metadata tags...")
            await write_metadata_tags(processed_path, metadata)
            
            if embed_lyrics:
                await embed_lyrics_with_ffmpeg(processed_path, metadata)
        
        # Organize file
        log_step("4/4", "Organizing file...")
        final_path = await organize_file_by_metadata(
            processed_path, 
            metadata,
            template=organization_template,
            group_compilations=group_compilations
        )
        
        # Run beets import if requested
        if run_beets:
            await run_beets_import(final_path)
            
        # Update state to completed - store the final path for fast file existence checks
        if metadata is None:
            metadata = {}
        metadata['final_path'] = str(final_path)
        download_state_manager.set_completed(track_id, final_path.name, metadata)
        
        file_size_mb = final_path.stat().st_size / 1024 / 1024
        display_name = final_path.name if final_path else filename
        log_success(f"Downloaded: {display_name} ({file_size_mb:.2f} MB)")
        log_info(f"Location: {final_path}")
        
        # Invalidate library cache so the new file/tags appear immediately
        try:
             from api.services.library import library_service
             library_service.invalidate_cache()
        except Exception as e:
             log_warning(f"Failed to invalidate library cache: {e}")

        print(f"{'='*60}\n")
        
        await asyncio.sleep(5)
        
        if track_id in active_downloads:
            del active_downloads[track_id]
        
    except Exception as e:
        log_error(f"Download error: {e}")
        traceback.print_exc()
        
        if track_id in active_downloads:
            active_downloads[track_id] = {'progress': 0, 'status': 'failed'}
            download_state_manager.set_failed(track_id, str(e), metadata)
            await asyncio.sleep(5)
            del active_downloads[track_id]
        
        if filepath.exists():
            try:
                filepath.unlink()
                log_info(f"Cleaned up partial file: {filename}")
            except Exception:
                pass
        
        if processed_path and processed_path != filepath and processed_path.exists():
            try:
                processed_path.unlink()
                log_info(f"Cleaned up partial file: {processed_path.name}")
            except Exception:
                pass
