import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path

from flask import Flask, jsonify, request
from flask_cors import CORS

import localstorage.client

# configuration
from models.audio import AudioBook
from models.tonie import Tonie
from toniecloud.client import TonieCloud

import yt_dlp
from mutagen.easyid3 import EasyID3
from mutagen.id3 import ID3, TIT2, TPE1, TALB, APIC
from mutagen.mp3 import MP3
from pathlib import Path

import eyed3
from eyed3.id3.frames import ImageFrame
from flask import Flask, jsonify, request
from pathlib import Path

from re import sub

logging.basicConfig(level=logging.DEBUG, stream=sys.stderr)
logger = logging.getLogger(__name__)

DEBUG = True

# instantiate the app
app = Flask(__name__)
app.config.from_object(__name__)

# enable CORS
CORS(app, resources={r"/*": {"origins": "*"}})

tonie_cloud_api = TonieCloud(os.environ.get("TONIE_AUDIO_MATCH_USER"), os.environ.get("TONIE_AUDIO_MATCH_PASS"))


def audiobooks():
    audiobooks = localstorage.client.audiobooks(Path("assets/audiobooks"))
    logger.debug("Discovered audiobook paths: %s", audiobooks)
    for album in audiobooks:
        audiobook = AudioBook.from_path(album)
        if audiobook:
            yield audiobook


audio_books_models = list(audiobooks())
audio_books = [
    {
        "id": album.id,
        "artist": album.artist,
        "title": album.album,
        "disc": album.album_no,
        "cover_uri": str(album.cover_relative) if album.cover else None,
    }
    for album in audio_books_models
]

creative_tonies = tonie_cloud_api.creativetonies()


@app.route("/ping", methods=["GET"])
def ping_pong():
    return jsonify("pong!")


@app.route("/audiobooks", methods=["GET"])
def all_audiobooks():
    return jsonify({"status": "success", "audiobooks": audio_books,})


@app.route("/creativetonies", methods=["GET"])
def all_creativetonies():
    return jsonify({"status": "success", "creativetonies": creative_tonies,})

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
        logger.error(f"Error downloading audiobook: {e}")
        return jsonify({"status": "failure", "message": str(e)}), 500
    
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

@dataclass
class Upload:
    tonie: Tonie
    audiobook: AudioBook

    @classmethod
    def from_ids(cls, tonie: str, audiobook: str) -> "Upload":
        return cls(
            next(filter(lambda t: t.id == tonie, creative_tonies), None),
            next(filter(lambda a: a.id == audiobook, audio_books_models), None),
        )


@app.route("/upload", methods=["POST"])
def upload_album_to_tonie():
    body = request.json
    upload = Upload.from_ids(tonie=body["tonie_id"], audiobook=body["audiobook_id"])
    logger.debug(f"Created upload object: {upload}")

    status = tonie_cloud_api.put_album_on_tonie(upload.audiobook, upload.tonie)
    return jsonify({"status": "success" if status else "failure", "upload_id": str(upload)}), 201


if __name__ == "__main__":
    app.run(host="0.0.0.0")
