"""Video processing command-line utility built on top of FFmpeg.

Provides the :class:`VideoProcessor` class for programmatic use and a small
``argparse``-based command-line interface via :func:`main`.
"""

import argparse
import os  # noqa: F401 -- kept to preserve the original module namespace
import shlex  # noqa: F401 -- kept to preserve the original module namespace
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

# ---------------------------------------------------------------------------
# Named constants
# ---------------------------------------------------------------------------

FFMPEG_EXECUTABLE = "ffmpeg"

DEFAULT_OUTPUT_DIR = "processed"
DEFAULT_THUMBNAIL_TIMESTAMP = "00:00:01"

AUDIO_SUFFIX = "audio"
PROCESSED_SUFFIX = "processed"
THUMBNAIL_SUFFIX = "thumbnail"
THUMBNAIL_EXTENSION = ".jpg"

THUMBNAIL_FRAME_COUNT = "1"
THUMBNAIL_JPEG_QUALITY = "2"

TIMESTAMP_SEPARATOR = ":"
TIMESTAMP_COMPONENT_COUNT = 3
MAX_MINUTE_OR_SECOND = 59

ALLOWED_OPERATION_CHARACTERS = frozenset(
    ("=", ":", ",", "-", "_", " ", "'", '"')
)

COMMAND_AUDIO = "audio"
COMMAND_THUMBNAIL = "thumbnail"
COMMAND_PROCESS = "process"

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def _print_error(message: str) -> None:
    """Write ``message`` to standard error."""
    print(message, file=sys.stderr)


def _resolve_input_path(video_path: str) -> Optional[Path]:
    """Return the input path if it exists, otherwise report and return None."""
    input_path = Path(video_path)
    if not input_path.exists():
        _print_error(f"Error: Input file {video_path} not found")
        return None
    return input_path


def _run_ffmpeg(arguments: List[str]) -> None:
    """Run FFmpeg with ``arguments``, capturing output and raising on failure."""
    command = [FFMPEG_EXECUTABLE, *arguments]
    subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def _decode_ffmpeg_error(error: subprocess.CalledProcessError) -> str:
    """Extract the captured standard error text from a failed FFmpeg run."""
    return error.stderr.decode()


def _parse_timestamp(timestamp: str) -> Optional[List[int]]:
    """Split an ``HH:MM:SS`` timestamp into integers, or return None if invalid."""
    try:
        parts = list(map(int, timestamp.split(TIMESTAMP_SEPARATOR)))
    except ValueError:
        return None
    if len(parts) != TIMESTAMP_COMPONENT_COUNT:
        return None
    return parts


def _timestamp_parts_in_range(parts: List[int]) -> bool:
    """Check that hours are non-negative and minutes/seconds are within 0-59."""
    hours, minutes, seconds = parts
    return (
        hours >= 0
        and 0 <= minutes <= MAX_MINUTE_OR_SECOND
        and 0 <= seconds <= MAX_MINUTE_OR_SECOND
    )


def _is_allowed_operation(operation: str) -> bool:
    """Check that a filter operation contains only safe characters."""
    return all(
        character.isalnum() or character in ALLOWED_OPERATION_CHARACTERS
        for character in operation
    )


# ---------------------------------------------------------------------------
# Core processor
# ---------------------------------------------------------------------------


class VideoProcessor:
    """Process video files with FFmpeg, writing results to an output directory."""

    def __init__(self, output_dir: str = DEFAULT_OUTPUT_DIR):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

    def _generate_output_path(self, input_path: Path, suffix: str) -> Path:
        return self.output_dir / f"{input_path.stem}_{suffix}{input_path.suffix}"

    def _generate_thumbnail_path(self, input_path: Path) -> Path:
        filename = f"{input_path.stem}_{THUMBNAIL_SUFFIX}{THUMBNAIL_EXTENSION}"
        return self.output_dir / filename

    def _validate_timestamp(self, timestamp: str) -> bool:
        parts = _parse_timestamp(timestamp)
        if parts is None:
            return False
        return _timestamp_parts_in_range(parts)

    @staticmethod
    def _filter_valid_operations(operations: List[str]) -> List[str]:
        valid_operations = []
        for operation in operations:
            if _is_allowed_operation(operation):
                valid_operations.append(operation)
            else:
                _print_error(
                    f"Warning: Skipping potentially issue operation: {operation}"
                )
        return valid_operations

    def extract_audio(self, video_path: str) -> Optional[str]:
        input_path = _resolve_input_path(video_path)
        if input_path is None:
            return None
        output_path = self._generate_output_path(input_path, AUDIO_SUFFIX)
        try:
            _run_ffmpeg([
                "-i", str(input_path),
                "-vn",
                "-acodec", "copy",
                str(output_path),
            ])
            return str(output_path)
        except subprocess.CalledProcessError as error:
            _print_error(f"Error extracting audio: {_decode_ffmpeg_error(error)}")
            return None

    def create_thumbnail(self, video_path: str, timestamp: str = DEFAULT_THUMBNAIL_TIMESTAMP) -> Optional[str]:
        input_path = _resolve_input_path(video_path)
        if input_path is None:
            return None
        if not self._validate_timestamp(timestamp):
            _print_error(f"Error: Invalid timestamp format {timestamp}")
            return None
        output_path = self._generate_thumbnail_path(input_path)
        try:
            _run_ffmpeg([
                "-ss", timestamp,
                "-i", str(input_path),
                "-vframes", THUMBNAIL_FRAME_COUNT,
                "-q:v", THUMBNAIL_JPEG_QUALITY,
                str(output_path),
            ])
            return str(output_path)
        except subprocess.CalledProcessError as error:
            _print_error(f"Error creating thumbnail: {_decode_ffmpeg_error(error)}")
            return None

    def process_video(self, video_path: str, operations: List[str]) -> bool:
        try:
            input_path = _resolve_input_path(video_path)
            if input_path is None:
                return False
            valid_operations = self._filter_valid_operations(operations)
            if not valid_operations:
                _print_error("Error: No valid operations provided")
                return False
            output_path = self._generate_output_path(input_path, PROCESSED_SUFFIX)
            _run_ffmpeg([
                "-i", str(input_path),
                "-vf", ",".join(valid_operations),
                str(output_path),
            ])
            return True
        except subprocess.CalledProcessError as error:
            _print_error(f"Error processing video: {_decode_ffmpeg_error(error)}")
            return False


# ---------------------------------------------------------------------------
# Command-line interface
# ---------------------------------------------------------------------------


def _build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Video Processing Utility")
    subparsers = parser.add_subparsers(dest="command", required=True)

    audio_parser = subparsers.add_parser(COMMAND_AUDIO, help="Extract audio from video")
    audio_parser.add_argument("video_file", help="Path to video file")

    thumbnail_parser = subparsers.add_parser(COMMAND_THUMBNAIL, help="Create video thumbnail")
    thumbnail_parser.add_argument("video_file", help="Path to video file")
    thumbnail_parser.add_argument(
        "--time",
        default=DEFAULT_THUMBNAIL_TIMESTAMP,
        help="Timestamp for thumbnail",
    )

    process_parser = subparsers.add_parser(COMMAND_PROCESS, help="Process video with filters")
    process_parser.add_argument("video_file", help="Path to video file")
    process_parser.add_argument("operations", nargs="+", help="FFmpeg filter operations")

    return parser


def main():
    args = _build_argument_parser().parse_args()
    processor = VideoProcessor()

    if args.command == COMMAND_AUDIO:
        result = processor.extract_audio(args.video_file)
        if result:
            print(f"Audio extracted to: {result}")
    elif args.command == COMMAND_THUMBNAIL:
        result = processor.create_thumbnail(args.video_file, args.time)
        if result:
            print(f"Thumbnail created at: {result}")
    elif args.command == COMMAND_PROCESS:
        success = processor.process_video(args.video_file, args.operations)
        if success:
            print("Video processed successfully")


if __name__ == "__main__":
    main()
