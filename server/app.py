import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from threading import Thread
from queue import Queue

from flask import Flask, jsonify, request
from flask_cors import CORS

import localstorage.client
from models.audio import AudioBook
from models.tonie import Tonie
from toniecloud.client import TonieCloud

import yt_dlp
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, TIT2, TPE1, TALB, APIC
from time import sleep
import yt_dlp
from pathlib import Path
from flask import Flask, jsonify, request
from pathlib import Path
from re import sub

logging.basicConfig(level=logging.DEBUG, stream=sys.stderr)
logger = logging.getLogger(__name__)

DEBUG = True

app = Flask(__name__)
app.config.from_object(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

tonie_cloud_api = TonieCloud(os.environ.get("TONIE_AUDIO_MATCH_USER"), os.environ.get("TONIE_AUDIO_MATCH_PASS"))

# Task queues
upload_queue = Queue()
transcoding_status = {}

# Media library
media_library = {"audiobooks": []}
creative_tonies = []

### Utility Functions
def refresh_media_library():
    """Refresh the media library in a background thread."""
    global media_library
    audiobooks = []
    try:
        for album in localstorage.client.audiobooks(Path("assets/audiobooks")):
            audiobook = AudioBook.from_path(album)
            if audiobook:
                audiobooks.append(audiobook)
    except Exception as e:
        logger.error(f"Error refreshing media library: {e}")
    media_library["audiobooks"] = audiobooks
    logger.info("Media library refreshed.")

def worker_process_uploads():
    """Worker function to process uploads."""
    while True:
        item = upload_queue.get()
        if item is None:
            break
        tonie_id, audiobook_id = item
        try:
            transcoding_status[audiobook_id] = "Uploading"
            upload = Upload.from_ids(tonie=tonie_id, audiobook=audiobook_id)
            status = tonie_cloud_api.put_album_on_tonie(upload.audiobook, upload.tonie)
            transcoding_status[audiobook_id] = "Completed" if status else "Failed"
        except Exception as e:
            logger.error(f"Error uploading: {e}")
            transcoding_status[audiobook_id] = "Error"
        finally:
            upload_queue.task_done()

upload_worker = Thread(target=worker_process_uploads, daemon=True)
upload_worker.start()

### Endpoints
@app.route("/refresh-library", methods=["POST"])
def refresh_library():
    """Trigger a library refresh."""
    Thread(target=refresh_media_library, daemon=True).start()
    return jsonify({"status": "success", "message": "Media library refresh started."})

@app.route("/audiobooks", methods=["GET"])
def all_audiobooks():
    """Fetch the current media library."""
    audiobooks = [
        {
            "id": album.id,
            "artist": album.artist,
            "title": album.album,
            "disc": album.album_no,
            "cover_uri": str(album.cover_relative) if album.cover else None,
        }
        for album in media_library["audiobooks"]
    ]
    
    return jsonify({"status": "success", "audiobooks": audiobooks})

    
    
@app.route("/ping", methods=["GET"])
def ping_pong():
    return jsonify("pong!")


@app.route("/creativetonies", methods=["GET"])
def all_creativetonies():
    """Fetch the list of creative Tonies."""
    global creative_tonies
    try:
        creative_tonies = tonie_cloud_api.creativetonies()
    except Exception as e:
        logger.error(f"Error refreshing Tonies: {e}")
    return jsonify({"status": "success", "creativetonies": creative_tonies})
        
@app.route("/download-audiobook", methods=["POST"])
def download_audiobook():
    """
    Accepts a JSON payload with a YouTube URL and optional metadata,
    downloads the audio, saves it in a directory named after the album,
    and updates metadata based on the provided information.
    Supports embedding a cover image into the MP3 file.
    """
    body = request.json
    
    # Required parameters
    video_url = body.get("url")
    if not video_url:
        return jsonify({"status": "failure", "message": "No URL provided"}), 400

    # Optional metadata parameters
    title = body.get("title", "Unknown Title")
    artist = body.get("artist", "Unknown Artist")
    album = body.get("album", "Unknown Album")
    cover_path = body.get("cover_path")  # Optional path to the cover image

    try:
        # Directory for audiobooks, with subdirectory for the album
        base_dir = Path("assets/audiobooks")
        album_dir = base_dir / album
        album_dir.mkdir(parents=True, exist_ok=True)

        # Filepath for the downloaded file
        downloaded_file = album_dir / f"{title}.mp3"
        logger.debug(f"Expected download path: {downloaded_file}")

        # Download options for yt_dlp
        ydl_opts = {
            'quiet': True,
            'noplaylist': True,
            'format': 'bestaudio/best',
            'outtmpl': str(album_dir / sanitize_filename(f"{title}.%(ext)s")),
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
        }

        # Download the audio file
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=True)
            logger.debug(f"Extracted info: {info}")
            # Match the downloaded file
            actual_file = Path(ydl.prepare_filename(info)).with_suffix(".mp3")
            logger.debug(f"Actual downloaded file: {actual_file}")

        # Verify the file exists
        if not actual_file.exists():
            raise FileNotFoundError(f"Downloaded file not found: {actual_file}")

        # Set metadata for the downloaded file
        metadata = {"title": title, "artist": artist, "album": album}
        update_mp3_metadata(actual_file, metadata, cover_path)

        return jsonify({
            "status": "success",
            "message": f"Downloaded and saved: {actual_file}",
            "file": str(actual_file),
            "metadata": metadata,
        }), 201

    except Exception as e:
        logger.error(f"Error refreshing Tonies: {e}")
    return jsonify({"status": "success", "creativetonies": creative_tonies})

@app.route("/upload", methods=["POST"])
def upload_album_to_tonie():
    """Queue an upload task."""
    body = request.json
    tonie_id = body.get("tonie_id")
    audiobook_id = body.get("audiobook_id")
    if not tonie_id or not audiobook_id:
        return jsonify({"status": "failure", "message": "Missing 'tonie_id' or 'audiobook_id'"}), 400
    upload_queue.put((tonie_id, audiobook_id))
    transcoding_status[audiobook_id] = "Queued"
    return jsonify({"status": "success", "message": "Upload queued."}), 202

@app.route("/upload-status/<audiobook_id>", methods=["GET"])
def upload_status(audiobook_id):
    """Fetch the upload/transcoding status of a specific audiobook."""
    status = transcoding_status.get(audiobook_id, "Unknown")
    return jsonify({"status": status})

def sanitize_filename(filename):
    return sub(r'[<>:"/\\|?*]', '', filename)

def update_mp3_metadata(file_path: Path, metadata: dict, cover_path: str = None):
    """
    Updates the metadata of an MP3 file using mutagen.
    Adds a cover image if provided, or uses a default cover if available.
    """
    default_cover = "assets/covers/default_cover.jpg"
    try:
        # Load the MP3 file and access existing ID3 tags
        audio = MP3(file_path, ID3=ID3)
    except Exception as e:
        logger.error(f"Error loading ID3 tags for {file_path}: {e}")
        return

    # Update or add metadata fields
    audio.tags["TIT2"] = TIT2(encoding=3, text=metadata.get("title", "Unknown Title"))  # Title
    audio.tags["TPE1"] = TPE1(encoding=3, text=metadata.get("artist", "Unknown Artist"))  # Artist
    audio.tags["TALB"] = TALB(encoding=3, text=metadata.get("album", "Unknown Album"))  # Album

    # Add or update cover art if provided
    cover_to_use = cover_path if cover_path and Path(cover_path).exists() else default_cover
    if Path(cover_to_use).exists():
        with open(cover_to_use, "rb") as img:
            audio.tags["APIC"] = APIC(
                encoding=3,
                mime="image/jpeg" if cover_to_use.endswith(".jpg") else "image/png",
                type=3,
                desc="Cover",
                data=img.read(),
            )
        logger.info(f"Added cover from {cover_to_use} to {file_path}")
    else:
        logger.warning(f"No valid cover found for {file_path}. Skipping cover update.")

    # Save changes
    try:
        audio.save()
        logger.info(f"Updated metadata for {file_path}: {metadata}")
    except Exception as e:
        logger.error(f"Failed to save metadata for {file_path}: {e}")


@app.route("/upload-cover", methods=["POST"])
def upload_cover():
    if "cover" not in request.files:
        return jsonify({"status": "failure", "message": "No cover file provided"}), 400

    cover = request.files["cover"]
    cover_dir = Path("assets/covers")
    cover_dir.mkdir(parents=True, exist_ok=True)

    cover_path = cover_dir / cover.filename
    cover.save(cover_path)

    return jsonify({"status": "success", "cover_path": str(cover_path)}), 201



### Helper Functions
@dataclass
class Upload:
    tonie: Tonie
    audiobook: AudioBook

    @classmethod
    def from_ids(cls, tonie: str, audiobook: str) -> "Upload":
        return cls(
            next(filter(lambda t: t.id == tonie, creative_tonies), None),
            next(filter(lambda a: a.id == audiobook, media_library["audiobooks"]), None),
        )

### Auto-refresh Tonies
def refresh_creative_tonies():
    while True:
        try:
            global creative_tonies
            creative_tonies = tonie_cloud_api.creativetonies()
        except Exception as e:
            logger.error(f"Error refreshing Tonies: {e}")
        sleep(300)  # Refresh every 5 minutes

tonie_worker = Thread(target=refresh_creative_tonies, daemon=True)
tonie_worker.start()

### Run Server
if __name__ == "__main__":
    refresh_media_library()  # Initial load
    app.run(host="0.0.0.0")
