import imghdr
import logging
from dataclasses import dataclass
from hashlib import sha512
from io import BytesIO
from pathlib import Path
from typing import List, ClassVar, Optional

from tinytag import TinyTag

from localstorage.client import audiofiles, metadata

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AudioTrack:
    album: str
    title: str
    track: int
    file: Path


@dataclass(frozen=True)
class AudioBook:
    covers: ClassVar[Path] = Path("assets/covers")

    id: str
    album: str
    album_no: int
    artist: str
    cover: Optional[Path]
    tracks: List[AudioTrack]

    @property
    def cover_relative(self) -> Optional[Path]:
        if not self.cover:
            return

        try:
            relative_path = str(self.cover.relative_to(self.covers))
            logger.debug(f"Generated relative cover path: {relative_path}")
            return relative_path
        except ValueError:
            logger.error(f"Cover path {self.cover} is not relative to {self.covers}")
            return None

    @classmethod
    def from_path(cls, album: Path) -> Optional["AudioBook"]:
        tracks_files = audiofiles(album)
        if not tracks_files:
            logger.error("Album without tracks or no tracks with expected extension: %s", album)
            return None

        tracks: List[AudioTrack] = []

        for file in tracks_files:
            tags = metadata(file)
            tracks.append(AudioTrack(album=tags.album, title=tags.title, track=tags.track, file=file))

        if not len({track.album for track in tracks}) == 1:
            print("WARNING De-normalized album title.")

        tags_first = metadata(tracks[0].file)

        album_id = cls.path_hash(album)
        cover_path = cls.cover_path_for(album_id)
        cover_path = cls.persist_cover(cover_path, TinyTag.get(str(tracks[0].file), image=True).get_image())

        return cls(
            id=album_id,
            album=tracks[0].album,
            album_no=tags_first.disc,
            artist=tags_first.artist,
            cover=cover_path,
            tracks=tracks,
        )

    @staticmethod
    def path_hash(path: Path) -> str:
        return sha512(str(path).encode("utf-8")).hexdigest()

    @classmethod
    def cover_path_for(cls, id: str) -> Path:
        return cls.covers.joinpath(id)
    
    @staticmethod
    def persist_cover(file: Path, image: Optional[bytes]) -> Optional[Path]:
        if not image:
            logger.warning("No image data to persist.")
            return None

        image_stream = BytesIO(image)
        image_type = imghdr.what(image_stream)

        if not image_type:
            logger.error("Could not determine image type for file: %s", file)
            return None

        # Ensure the parent directory exists
        file = file.with_suffix(f".{image_type}")
        file.parent.mkdir(parents=True, exist_ok=True)

        with file.open("wb") as ch:
            ch.write(image)

        logger.info(f"Cover saved at: {file}")
        return file
