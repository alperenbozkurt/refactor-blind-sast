import subprocess
import argparse
import os
import sys
import shlex
from pathlib import Path
from typing import Optional, List

FFMPEG_BINARY = 'ffmpeg'
DEFAULT_OUTPUT_DIR = 'processed'
DEFAULT_THUMBNAIL_TIMESTAMP = '00:00:01'
THUMBNAIL_EXTENSION = '.jpg'

AUDIO_SUFFIX = 'audio'
THUMBNAIL_SUFFIX = 'thumbnail'
PROCESSED_SUFFIX = 'processed'

TIMESTAMP_SEPARATOR = ':'
TIMESTAMP_PART_COUNT = 3
MAX_MINUTES_SECONDS = 59

ALLOWED_OPERATION_PUNCTUATION = frozenset(['=', ':', ',', '-', '_', ' ', "'", '"'])
FILTER_SEPARATOR = ','


def _print_error(message: str) -> None:
    print(message, file=sys.stderr)


def _is_safe_operation(operation: str) -> bool:
    return all(c.isalnum() or c in ALLOWED_OPERATION_PUNCTUATION for c in operation)


def _run_ffmpeg(args: List[str]) -> None:
    """Run ffmpeg with the given arguments, raising CalledProcessError on failure."""
    cmd = [FFMPEG_BINARY, *args]
    subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


class VideoProcessor:

    def __init__(self, output_dir: str=DEFAULT_OUTPUT_DIR):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _generate_output_path(self, input_path: Path, suffix: str) -> Path:
        return self.output_dir / f'{input_path.stem}_{suffix}{input_path.suffix}'

    def _generate_thumbnail_path(self, input_path: Path) -> Path:
        return self.output_dir / f'{input_path.stem}_{THUMBNAIL_SUFFIX}{THUMBNAIL_EXTENSION}'

    def _validate_timestamp(self, timestamp: str) -> bool:
        try:
            parts = list(map(int, timestamp.split(TIMESTAMP_SEPARATOR)))
        except ValueError:
            return False
        if len(parts) != TIMESTAMP_PART_COUNT:
            return False
        hours, minutes, seconds = parts
        if hours < 0:
            return False
        if not 0 <= minutes <= MAX_MINUTES_SECONDS:
            return False
        if not 0 <= seconds <= MAX_MINUTES_SECONDS:
            return False
        return True

    def _input_exists(self, input_path: Path, video_path: str) -> bool:
        if not input_path.exists():
            _print_error(f'Error: Input file {video_path} not found')
            return False
        return True

    def _filter_operations(self, operations: List[str]) -> List[str]:
        valid_operations = []
        for op in operations:
            if _is_safe_operation(op):
                valid_operations.append(op)
            else:
                _print_error(f'Warning: Skipping potentially issue operation: {op}')
        return valid_operations

    # ------------------------------------------------------------------
    # Public operations
    # ------------------------------------------------------------------
    def extract_audio(self, video_path: str) -> Optional[str]:
        input_path = Path(video_path)
        if not self._input_exists(input_path, video_path):
            return None
        output_path = self._generate_output_path(input_path, AUDIO_SUFFIX)
        try:
            _run_ffmpeg(['-i', str(input_path), '-vn', '-acodec', 'copy', str(output_path)])
            return str(output_path)
        except subprocess.CalledProcessError as e:
            _print_error(f'Error extracting audio: {e.stderr.decode()}')
            return None

    def create_thumbnail(self, video_path: str, timestamp: str=DEFAULT_THUMBNAIL_TIMESTAMP) -> Optional[str]:
        input_path = Path(video_path)
        if not self._input_exists(input_path, video_path):
            return None
        if not self._validate_timestamp(timestamp):
            _print_error(f'Error: Invalid timestamp format {timestamp}')
            return None
        output_path = self._generate_thumbnail_path(input_path)
        try:
            _run_ffmpeg([
                '-ss', timestamp,
                '-i', str(input_path),
                '-vframes', '1',
                '-q:v', '2',
                str(output_path),
            ])
            return str(output_path)
        except subprocess.CalledProcessError as e:
            _print_error(f'Error creating thumbnail: {e.stderr.decode()}')
            return None

    def process_video(self, video_path: str, operations: List[str]) -> bool:
        try:
            input_path = Path(video_path)
            if not self._input_exists(input_path, video_path):
                return False
            valid_operations = self._filter_operations(operations)
            if not valid_operations:
                _print_error('Error: No valid operations provided')
                return False
            output_path = self._generate_output_path(input_path, PROCESSED_SUFFIX)
            _run_ffmpeg([
                '-i', str(input_path),
                '-vf', FILTER_SEPARATOR.join(valid_operations),
                str(output_path),
            ])
            return True
        except subprocess.CalledProcessError as e:
            _print_error(f'Error processing video: {e.stderr.decode()}')
            return False


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Video Processing Utility')
    subparsers = parser.add_subparsers(dest='command', required=True)

    audio_parser = subparsers.add_parser('audio', help='Extract audio from video')
    audio_parser.add_argument('video_file', help='Path to video file')

    thumb_parser = subparsers.add_parser('thumbnail', help='Create video thumbnail')
    thumb_parser.add_argument('video_file', help='Path to video file')
    thumb_parser.add_argument('--time', default=DEFAULT_THUMBNAIL_TIMESTAMP, help='Timestamp for thumbnail')

    process_parser = subparsers.add_parser('process', help='Process video with filters')
    process_parser.add_argument('video_file', help='Path to video file')
    process_parser.add_argument('operations', nargs='+', help='FFmpeg filter operations')
    return parser


def _handle_audio(processor: VideoProcessor, args: argparse.Namespace) -> None:
    result = processor.extract_audio(args.video_file)
    if result:
        print(f'Audio extracted to: {result}')


def _handle_thumbnail(processor: VideoProcessor, args: argparse.Namespace) -> None:
    result = processor.create_thumbnail(args.video_file, args.time)
    if result:
        print(f'Thumbnail created at: {result}')


def _handle_process(processor: VideoProcessor, args: argparse.Namespace) -> None:
    success = processor.process_video(args.video_file, args.operations)
    if success:
        print('Video processed successfully')


_COMMAND_HANDLERS = {
    'audio': _handle_audio,
    'thumbnail': _handle_thumbnail,
    'process': _handle_process,
}


def main():
    parser = _build_parser()
    args = parser.parse_args()
    processor = VideoProcessor()
    handler = _COMMAND_HANDLERS.get(args.command)
    if handler is not None:
        handler(processor, args)


if __name__ == '__main__':
    main()
