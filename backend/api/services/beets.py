from pathlib import Path
import asyncio
import os
import sys
from api.utils.logging import log_info, log_success, log_warning, log_step

async def run_beets_import(path: Path):
    """Run beets import on the downloaded file/directory"""
    try:
        import subprocess
        
        # Determine beet executable path
        beet_cmd = "beet"
        
        # Check if beet is in the same directory as python executable (common in venvs)
        python_dir = os.path.dirname(sys.executable)
        potential_beet = os.path.join(python_dir, "beet")
        if os.path.exists(potential_beet):
            beet_cmd = potential_beet
        elif os.path.exists(potential_beet + ".exe"):
            beet_cmd = potential_beet + ".exe"
            
        # Check if beet is installed/runnable
        try:
            subprocess.run([beet_cmd, "version"], check=True, capture_output=True)
        except (FileNotFoundError, subprocess.CalledProcessError):
            log_warning(f"Beets not found (tried '{beet_cmd}'). Skipping import.")
            return

        log_step("4/4", f"Running beets import on {path.name}...")
        
        use_custom_config = False
        custom_config_path = Path("tidaloader_beets.yaml").resolve()
        
        try:
            result = subprocess.run([beet_cmd, "config", "-p"], capture_output=True, text=True)
            config_path = result.stdout.strip()
            
            if result.returncode != 0 or not config_path or not os.path.exists(config_path):
                log_info("No existing Beets config found. Using auto-generated configuration.")
                use_custom_config = True
            else:
                log_info(f"Using existing Beets config at: {config_path}")
                
        except Exception as e:
            log_warning(f"Error checking Beets config: {e}. Defaulting to auto-generated config.")
            use_custom_config = True
            
        if use_custom_config:
            config_content = """
directory: /tmp # Dummy, we don't move files
original_date: no
plugins: chroma fetchart embedart lastgenre
import:
    write: yes
    copy: no
    move: no
    autotag: yes
    timid: no
    resume: ask
    incremental: no
    quiet_fallback: skip
    log: beets_import.log
chroma:
    auto: yes
fetchart:
    auto: yes
embedart:
    auto: yes
lastgenre:
    auto: yes
    source: artist
musicbrainz:
    genres: yes
    match:
        strong_rec_thresh: 0.10
        distance_weights:
            missing_tracks: 0.0
            unmatched_tracks: 0.0
"""
            with open(custom_config_path, "w") as f:
                f.write(config_content)
            log_info("Generated/Updated custom Beets configuration.")

        log_step("4/4", f"Running beets import on {path.name}...")
        
        cmd = [beet_cmd, "-c", str(custom_config_path), "import", "-q", "-s", str(path)]
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        
        stdout_str = stdout.decode()
        stderr_str = stderr.decode()
        
        if process.returncode == 0:
            log_success("Beets import completed successfully")
            print(f"Beets Output:\n{stdout_str}")
            if stderr_str:
                print(f"Beets Errors/Warnings:\n{stderr_str}")
        else:
            log_warning(f"Beets import failed: {stderr_str}")
            print(f"Beets Output:\n{stdout_str}")
            
    except Exception as e:
        log_warning(f"Failed to run beets import: {e}")
