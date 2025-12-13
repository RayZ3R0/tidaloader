# Tidaloader

A full-stack web application for downloading high-quality music from Tidal with intelligent playlist generation via ListenBrainz/Troi integration. Features automatic metadata tagging, lyrics fetching, and organized file management.

Heavily inspired from https://github.com/uimaxbai/tidal-ui and using https://github.com/sachinsenal0x64/hifi

> [!IMPORTANT]
>
> # Project Terms

- We do not encourage piracy. This project is made purely for educational and personal use.
  If you somehow download copyrighted content, you are solely responsible for complying with the relevant laws in your country.

- The Tidaloader Project assumes no responsibility for any misuse or legal violations arising from the use of this project.

- This project does not claim ownership of any music or audio content. All rights remain with their respective copyright holders. Users are **encouraged** to support artists and rights owners by maintaining a valid Tidal subscription. Tidaloader serves solely as a downloading interface for personal, non-commercial use.

## Screenshots

<p align="center">
  <img src="https://i.imgur.com/as8iNqV.png" width="45%" alt="Album Page">
  <img src="https://i.imgur.com/5mtKF52.png" width="45%" alt="Artist Page">
</p>
<p align="center">
  <img src="https://i.imgur.com/JrBzovz.png" width="90%" alt="Download Management">
</p>

## Key Features

- **Multi-Format Support**:
  - **FLAC**: Hi-Res (24-bit/192kHz) & Lossless (16-bit/44.1kHz)
  - **Opus**: High-efficiency 192kbps VBR
  - **MP3**: 320kbps / 128kbps (Transcoded)
  - **AAC**: 320kbps / 96kbps
- **Smart Playlists**: Generate "Daily Jams" using ListenBrainz history + Troi.
- **Rich Metadata**: Auto-tagging with MusicBrainz IDs, Artist/Album organization, and embedded covers.
- **Intelligent Library**: Strict ID-based album matching prevents duplicates. Artist covers are automatically fetched and cached for a beautiful, persistent browsing experience.
- **Lyrics**: Synced (`.lrc`) and plain text lyrics via LrcLib.
- **Queue Management**: Concurrent downloads, auto-retry, and persistence.
- **Resilience**: Automatic rotation of Tidal API tokens and endpoints.

## Quick Start (Docker)

The recommended way to run Tidaloader.

1.  Create a `docker-compose.yml`:

    ```yaml
    version: '3.8'
    services:
      tidaloader:
        image: ghcr.io/rayz3r0/tidaloader:latest
        container_name: tidaloader
        ports:
          - "8001:8001"
        environment:
          - MUSIC_DIR=/music
          - AUTH_USERNAME=admin
          - AUTH_PASSWORD=changeme
          - MAX_CONCURRENT_DOWNLOADS=3
          - QUEUE_AUTO_PROCESS=true
        volumes:
          - ./music:/music
        restart: unless-stopped
    ```

2.  Run the container:
    ```bash
    docker-compose up -d
    ```

3.  Open `http://localhost:8001`.

## Configuration Options

Configure these in your `docker-compose.yml` or `.env` file.

| Variable | Description | Default |
|----------|-------------|---------|
| `MUSIC_DIR` | Internal container path for downloads | `/music` |
| `AUTH_USERNAME` | Web UI Username | `admin` |
| `AUTH_PASSWORD` | Web UI Password | `changeme` |
| `MAX_CONCURRENT_DOWNLOADS` | Max parallel downloads | `3` |
| `QUEUE_AUTO_PROCESS` | Start queue automatically on boot | `true` |
| `MUSIC_DIR_HOST` | (Docker) Host directory to map | `./music` |

## Audio Quality Guide

| Quality Setting | Details | Format |
|-----------------|---------|--------|
| `HI_RES` | Source quality (up to 24-bit/192kHz) | FLAC |
| `LOSSLESS` | CD quality (16-bit/44.1kHz) | FLAC |
| `HIGH` | Standard High (320kbps) | AAC |
| `LOW` | Data Saver (96kbps) | AAC |
| `MP3_320`/`256` | Transcoded High Quality | MP3 |
| `OPUS_192` | Transcoded High Efficiency | Opus |

## Manual Installation

<details>
<summary><strong>Windows</strong></summary>

1.  **Clone**: `git clone https://github.com/RayZ3R0/tidaloader.git`
2.  **Backend**:
    ```powershell
    cd backend
    python -m venv venv; .\venv\Scripts\Activate.ps1
    pip install -r requirements.txt
    cp .env.example .env  # Edit .env with your settings
    ```
3.  **Frontend**:
    ```powershell
    cd ..\frontend
    npm install; npm run build
    ```
4.  **Run**: `cd ..\backend; .\start.ps1`
</details>

<details>
<summary><strong>Linux</strong></summary>

1.  **Clone**: `git clone https://github.com/RayZ3R0/tidaloader.git`
2.  **Backend**:
    ```bash
    cd backend
    python3 -m venv venv; source venv/bin/activate
    pip install -r requirements.txt
    cp .env.example .env  # Edit .env
    ```
3.  **Frontend**:
    ```bash
    cd ../frontend
    npm install; npm run build
    ```
4.  **Run**: `python -m uvicorn api.main:app --host 0.0.0.0 --port 8001`
</details>

<details>
<summary><strong>Android (Termux)</strong></summary>

1.  Install Termux (F-Droid).
2.  Run Setup:
    ```bash
    curl -O https://raw.githubusercontent.com/RayZ3R0/tidaloader/main/backend/termux-setup.sh
    bash termux-setup.sh
    ```
3.  Start: `./start-service.sh`
</details>

## Development

*   **Backend**: `uvicorn api.main:app --reload` (Port 8001)
*   **Frontend**: `npm run dev` (Port 5173)

## Credits

Inspired by [tidal-ui](https://github.com/uimaxbai/tidal-ui). Playlist generation by ListenBrainz Troi.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

> **Disclaimer**: This project is for educational purposes only. The developers do not endorse piracy and are not responsible for how this software is used. Please support artists by purchasing their music.
