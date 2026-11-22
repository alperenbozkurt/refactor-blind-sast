"""Command-line video processing utility backed by FFmpeg."""

import argparse
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

# --- Configuration constants -------------------------------------------------
DEFAULT_OUTPUT_DIR = 'processed'
DEFAULT_THUMBNAIL_TIME = '00:00:01'

COMMAND_AUDIO = 'audio'
COMMAND_THUMBNAIL = 'thumbnail'
COMMAND_PROCESS = 'process'

_AUDIO_SUFFIX = 'audio'
_PROCESSED_SUFFIX = 'processed'
_THUMBNAIL_SUFFIX = 'thumbnail'
_THUMBNAIL_EXTENSION = '.jpg'

_FFMPEG_EXTRACT_AUDIO = "ffmpeg -i '{input}' -vn -acodec copy {output}"
_FFMPEG_CREATE_THUMBNAIL = "ffmpeg -ss {timestamp} -i '{input}' -vframes 1 -q:v 2 {output}"
_FFMPEG_PROCESS_VIDEO = "ffmpeg -i '{input}' -vf '{filters}' {output}"

_ERROR_INPUT_NOT_FOUND = 'Error: Input file {path} not found'
_ERROR_OPERATION_FAILED = 'Error {action}: {error}'


class VideoProcessor:
    """Process video files by delegating the heavy lifting to FFmpeg."""

    def __init__(self, output_dir: str = DEFAULT_OUTPUT_DIR):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

    def _generate_output_path(self, input_path: Path, suffix: str) -> Path:
        return self.output_dir / f'{input_path.stem}_{suffix}{input_path.suffix}'

    @staticmethod
    def _resolve_input(video_path: str) -> Optional[Path]:
        """Return the input path if it exists, otherwise report and return None."""
        input_path = Path(video_path)
        if not input_path.exists():
            print(_ERROR_INPUT_NOT_FOUND.format(path=video_path), file=sys.stderr)
            return None
        return input_path

    @staticmethod
    def _run_ffmpeg(command: str, action: str) -> bool:
        """Run an FFmpeg command, reporting failures to stderr."""
        try:
            subprocess.run(command, shell=True, check=True)
            return True
        except subprocess.CalledProcessError as error:
            print(_ERROR_OPERATION_FAILED.format(action=action, error=error),
                  file=sys.stderr)
            return False

    def extract_audio(self, video_path: str) -> Optional[str]:
        input_path = self._resolve_input(video_path)
        if input_path is None:
            return None
        output_path = self._generate_output_path(input_path, _AUDIO_SUFFIX)
        command = _FFMPEG_EXTRACT_AUDIO.format(input=video_path, output=output_path)
        if self._run_ffmpeg(command, 'extracting audio'):
            return str(output_path)
        return None

    def create_thumbnail(self, video_path: str, timestamp: str = DEFAULT_THUMBNAIL_TIME) -> Optional[str]:
        input_path = self._resolve_input(video_path)
        if input_path is None:
            return None
        output_path = self.output_dir / f'{input_path.stem}_{_THUMBNAIL_SUFFIX}{_THUMBNAIL_EXTENSION}'
        command = _FFMPEG_CREATE_THUMBNAIL.format(
            timestamp=timestamp, input=video_path, output=output_path
        )
        if self._run_ffmpeg(command, 'creating thumbnail'):
            return str(output_path)
        return None

    def process_video(self, video_path: str, operations: List[str]) -> bool:
        input_path = self._resolve_input(video_path)
        if input_path is None:
            return False
        output_path = self._generate_output_path(input_path, _PROCESSED_SUFFIX)
        filters = ','.join(operations)
        command = _FFMPEG_PROCESS_VIDEO.format(
            input=video_path, filters=filters, output=output_path
        )
        return self._run_ffmpeg(command, 'processing video')


def _build_argument_parser() -> argparse.ArgumentParser:
    """Construct the command-line argument parser."""
    parser = argparse.ArgumentParser(description='Video Processing Utility')
    subparsers = parser.add_subparsers(dest='command', required=True)

    audio_parser = subparsers.add_parser(COMMAND_AUDIO, help='Extract audio from video')
    audio_parser.add_argument('video_file', help='Path to video file')

    thumbnail_parser = subparsers.add_parser(COMMAND_THUMBNAIL, help='Create video thumbnail')
    thumbnail_parser.add_argument('video_file', help='Path to video file')
    thumbnail_parser.add_argument('--time', default=DEFAULT_THUMBNAIL_TIME,
                                  help='Timestamp for thumbnail')

    process_parser = subparsers.add_parser(COMMAND_PROCESS, help='Process video with filters')
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
    if processor.process_video(args.video_file, args.operations):
        print('Video processed successfully')


_COMMAND_HANDLERS = {
    COMMAND_AUDIO: _handle_audio,
    COMMAND_THUMBNAIL: _handle_thumbnail,
    COMMAND_PROCESS: _handle_process,
}


def main():
    args = _build_argument_parser().parse_args()
    processor = VideoProcessor()
    _COMMAND_HANDLERS[args.command](processor, args)


if __name__ == '__main__':
    main()
