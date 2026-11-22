"""Command-line video processing utility built on top of FFmpeg."""

import argparse
import os
import shlex
import subprocess
import sys
from pathlib import Path
from typing import List, Optional


class VideoProcessor:
    """Extract audio, create thumbnails, and apply filters to videos via FFmpeg."""

    # Non-alphanumeric characters permitted in filter operations.
    _ALLOWED_OPERATION_CHARS = frozenset(('=', ':', ',', '-', '_', ' ', "'", '"'))

    def __init__(self, output_dir: str = 'processed'):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

    def _generate_output_path(self, input_path: Path, suffix: str) -> Path:
        return self.output_dir / f'{input_path.stem}_{suffix}{input_path.suffix}'

    def _validate_timestamp(self, timestamp: str) -> bool:
        try:
            hours, minutes, seconds = map(int, timestamp.split(':'))
        except ValueError:
            return False
        return hours >= 0 and 0 <= minutes <= 59 and 0 <= seconds <= 59

    def _validate_input_path(self, video_path: str) -> Optional[Path]:
        """Return the resolved input path, or None after reporting it missing."""
        input_path = Path(video_path)
        if not input_path.exists():
            print(f'Error: Input file {video_path} not found', file=sys.stderr)
            return None
        return input_path

    def _is_operation_allowed(self, operation: str) -> bool:
        """Return True only if every character of the operation is allowed."""
        return all(
            char.isalnum() or char in self._ALLOWED_OPERATION_CHARS
            for char in operation
        )

    def _run_ffmpeg(self, cmd: List[str], action: str) -> bool:
        """Run an FFmpeg command, reporting failures to stderr."""
        try:
            subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            return True
        except subprocess.CalledProcessError as e:
            print(f'Error {action}: {e.stderr.decode()}', file=sys.stderr)
            return False

    def extract_audio(self, video_path: str) -> Optional[str]:
        input_path = self._validate_input_path(video_path)
        if input_path is None:
            return None
        output_path = self._generate_output_path(input_path, 'audio')
        cmd = [
            'ffmpeg', '-i', str(input_path),
            '-vn', '-acodec', 'copy',
            str(output_path),
        ]
        if self._run_ffmpeg(cmd, 'extracting audio'):
            return str(output_path)
        return None

    def create_thumbnail(self, video_path: str, timestamp: str = '00:00:01') -> Optional[str]:
        input_path = self._validate_input_path(video_path)
        if input_path is None:
            return None
        if not self._validate_timestamp(timestamp):
            print(f'Error: Invalid timestamp format {timestamp}', file=sys.stderr)
            return None
        output_path = self.output_dir / f'{input_path.stem}_thumbnail.jpg'
        cmd = [
            'ffmpeg', '-ss', timestamp, '-i', str(input_path),
            '-vframes', '1', '-q:v', '2',
            str(output_path),
        ]
        if self._run_ffmpeg(cmd, 'creating thumbnail'):
            return str(output_path)
        return None

    def process_video(self, video_path: str, operations: List[str]) -> bool:
        input_path = self._validate_input_path(video_path)
        if input_path is None:
            return False
        valid_operations = []
        for operation in operations:
            if self._is_operation_allowed(operation):
                valid_operations.append(operation)
            else:
                print(
                    f'Warning: Skipping potentially issue operation: {operation}',
                    file=sys.stderr,
                )
        if not valid_operations:
            print('Error: No valid operations provided', file=sys.stderr)
            return False
        output_path = self._generate_output_path(input_path, 'processed')
        cmd = [
            'ffmpeg', '-i', str(input_path),
            '-vf', ','.join(valid_operations),
            str(output_path),
        ]
        return self._run_ffmpeg(cmd, 'processing video')


def main():
    parser = argparse.ArgumentParser(description='Video Processing Utility')
    subparsers = parser.add_subparsers(dest='command', required=True)

    audio_parser = subparsers.add_parser('audio', help='Extract audio from video')
    audio_parser.add_argument('video_file', help='Path to video file')

    thumb_parser = subparsers.add_parser('thumbnail', help='Create video thumbnail')
    thumb_parser.add_argument('video_file', help='Path to video file')
    thumb_parser.add_argument('--time', default='00:00:01', help='Timestamp for thumbnail')

    process_parser = subparsers.add_parser('process', help='Process video with filters')
    process_parser.add_argument('video_file', help='Path to video file')
    process_parser.add_argument('operations', nargs='+', help='FFmpeg filter operations')

    args = parser.parse_args()
    processor = VideoProcessor()

    if args.command == 'audio':
        result = processor.extract_audio(args.video_file)
        if result:
            print(f'Audio extracted to: {result}')
    elif args.command == 'thumbnail':
        result = processor.create_thumbnail(args.video_file, args.time)
        if result:
            print(f'Thumbnail created at: {result}')
    elif args.command == 'process':
        success = processor.process_video(args.video_file, args.operations)
        if success:
            print('Video processed successfully')


if __name__ == '__main__':
    main()
