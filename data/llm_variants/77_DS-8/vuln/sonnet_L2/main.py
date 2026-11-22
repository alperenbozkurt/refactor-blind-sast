import subprocess
import argparse
import os
import sys
from pathlib import Path
from typing import Optional, List, Sequence

DEFAULT_OUTPUT_DIR = 'processed'
DEFAULT_THUMBNAIL_TIMESTAMP = '00:00:01'
FFMPEG_BINARY = 'ffmpeg'

AUDIO_SUFFIX = 'audio'
PROCESSED_SUFFIX = 'processed'
THUMBNAIL_SUFFIX = 'thumbnail'
THUMBNAIL_EXTENSION = '.jpg'
FILTER_SEPARATOR = ','


def _print_error(message: str) -> None:
    print(message, file=sys.stderr)


class VideoProcessor:

    def __init__(self, output_dir: str = DEFAULT_OUTPUT_DIR):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

    def _generate_output_path(self, input_path: Path, suffix: str) -> Path:
        return self.output_dir / f'{input_path.stem}_{suffix}{input_path.suffix}'

    def _generate_thumbnail_path(self, input_path: Path) -> Path:
        return self.output_dir / f'{input_path.stem}_{THUMBNAIL_SUFFIX}{THUMBNAIL_EXTENSION}'

    @staticmethod
    def _input_exists(video_path: str) -> bool:
        if not Path(video_path).exists():
            _print_error(f'Error: Input file {video_path} not found')
            return False
        return True

    @staticmethod
    def _run_ffmpeg(args: Sequence[str]) -> None:
        # Arguments are passed as a list (no shell) so that file names,
        # timestamps and filters are never interpreted by a shell.
        try:
            subprocess.run([FFMPEG_BINARY, *args], check=True)
        except FileNotFoundError as e:
            # Mirror the failure mode of a missing executable as a command error.
            raise subprocess.CalledProcessError(127, FFMPEG_BINARY) from e

    @staticmethod
    def _audio_args(video_path: str, output_path: Path) -> List[str]:
        return ['-i', video_path, '-vn', '-acodec', 'copy', str(output_path)]

    @staticmethod
    def _thumbnail_args(video_path: str, timestamp: str, output_path: Path) -> List[str]:
        return ['-ss', timestamp, '-i', video_path, '-vframes', '1',
                '-q:v', '2', str(output_path)]

    @staticmethod
    def _process_args(video_path: str, operations: List[str], output_path: Path) -> List[str]:
        filters = FILTER_SEPARATOR.join(operations)
        return ['-i', video_path, '-vf', filters, str(output_path)]

    def extract_audio(self, video_path: str) -> Optional[str]:
        if not self._input_exists(video_path):
            return None
        input_path = Path(video_path)
        output_path = self._generate_output_path(input_path, AUDIO_SUFFIX)
        try:
            self._run_ffmpeg(self._audio_args(video_path, output_path))
            return str(output_path)
        except subprocess.CalledProcessError as e:
            _print_error(f'Error extracting audio: {e}')
            return None

    def create_thumbnail(self, video_path: str,
                         timestamp: str = DEFAULT_THUMBNAIL_TIMESTAMP) -> Optional[str]:
        if not self._input_exists(video_path):
            return None
        input_path = Path(video_path)
        output_path = self._generate_thumbnail_path(input_path)
        try:
            self._run_ffmpeg(self._thumbnail_args(video_path, timestamp, output_path))
            return str(output_path)
        except subprocess.CalledProcessError as e:
            _print_error(f'Error creating thumbnail: {e}')
            return None

    def process_video(self, video_path: str, operations: List[str]) -> bool:
        try:
            if not self._input_exists(video_path):
                return False
            input_path = Path(video_path)
            output_path = self._generate_output_path(input_path, PROCESSED_SUFFIX)
            self._run_ffmpeg(self._process_args(video_path, operations, output_path))
            return True
        except subprocess.CalledProcessError as e:
            _print_error(f'Error processing video: {e}')
            return False


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Video Processing Utility')
    subparsers = parser.add_subparsers(dest='command', required=True)

    audio_parser = subparsers.add_parser('audio', help='Extract audio from video')
    audio_parser.add_argument('video_file', help='Path to video file')

    thumb_parser = subparsers.add_parser('thumbnail', help='Create video thumbnail')
    thumb_parser.add_argument('video_file', help='Path to video file')
    thumb_parser.add_argument('--time', default=DEFAULT_THUMBNAIL_TIMESTAMP,
                              help='Timestamp for thumbnail')

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


COMMAND_HANDLERS = {
    'audio': _handle_audio,
    'thumbnail': _handle_thumbnail,
    'process': _handle_process,
}


def main():
    parser = _build_parser()
    args = parser.parse_args()
    processor = VideoProcessor()
    handler = COMMAND_HANDLERS.get(args.command)
    if handler is not None:
        handler(processor, args)


if __name__ == '__main__':
    main()
