import subprocess
import argparse
import os
import sys
import shlex
from pathlib import Path
from typing import Optional, List

ALLOWED_OPERATION_SYMBOLS = ('=', ':', ',', '-', '_', ' ', "'", '"')


def _print_error(message: str) -> None:
    print(message, file=sys.stderr)


class VideoProcessor:

    def __init__(self, output_dir: str = 'processed'):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _generate_output_path(self, input_path: Path, suffix: str) -> Path:
        return self.output_dir / f'{input_path.stem}_{suffix}{input_path.suffix}'

    def _validate_timestamp(self, timestamp: str) -> bool:
        """Return True if timestamp is of the form H:M:S with valid ranges."""
        try:
            parts = list(map(int, timestamp.split(':')))
        except ValueError:
            return False
        if len(parts) != 3:
            return False
        hours, minutes, seconds = parts
        if hours < 0:
            return False
        if not 0 <= minutes <= 59:
            return False
        if not 0 <= seconds <= 59:
            return False
        return True

    @staticmethod
    def _is_safe_operation(operation: str) -> bool:
        return all(
            c.isalnum() or c in ALLOWED_OPERATION_SYMBOLS
            for c in operation
        )

    @staticmethod
    def _input_exists(input_path: Path, video_path: str) -> bool:
        if input_path.exists():
            return True
        _print_error(f'Error: Input file {video_path} not found')
        return False

    @staticmethod
    def _run_ffmpeg(cmd: List[str]) -> None:
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    # ------------------------------------------------------------------
    # Public operations
    # ------------------------------------------------------------------
    def extract_audio(self, video_path: str) -> Optional[str]:
        input_path = Path(video_path)
        if not self._input_exists(input_path, video_path):
            return None
        output_path = self._generate_output_path(input_path, 'audio')
        try:
            cmd = ['ffmpeg', '-i', str(input_path), '-vn', '-acodec', 'copy', str(output_path)]
            self._run_ffmpeg(cmd)
            return str(output_path)
        except subprocess.CalledProcessError as e:
            _print_error(f'Error extracting audio: {e.stderr.decode()}')
            return None

    def create_thumbnail(self, video_path: str, timestamp: str = '00:00:01') -> Optional[str]:
        input_path = Path(video_path)
        if not self._input_exists(input_path, video_path):
            return None
        if not self._validate_timestamp(timestamp):
            _print_error(f'Error: Invalid timestamp format {timestamp}')
            return None
        output_path = self.output_dir / f'{input_path.stem}_thumbnail.jpg'
        try:
            cmd = [
                'ffmpeg', '-ss', timestamp, '-i', str(input_path),
                '-vframes', '1', '-q:v', '2', str(output_path),
            ]
            self._run_ffmpeg(cmd)
            return str(output_path)
        except subprocess.CalledProcessError as e:
            _print_error(f'Error creating thumbnail: {e.stderr.decode()}')
            return None

    def process_video(self, video_path: str, operations: List[str]) -> bool:
        try:
            input_path = Path(video_path)
            if not self._input_exists(input_path, video_path):
                return False

            valid_operations = []
            for op in operations:
                if self._is_safe_operation(op):
                    valid_operations.append(op)
                else:
                    _print_error(f'Warning: Skipping potentially issue operation: {op}')

            if not valid_operations:
                _print_error('Error: No valid operations provided')
                return False

            output_path = self._generate_output_path(input_path, 'processed')
            cmd = [
                'ffmpeg', '-i', str(input_path),
                '-vf', ','.join(valid_operations),
                str(output_path),
            ]
            self._run_ffmpeg(cmd)
            return True
        except subprocess.CalledProcessError as e:
            _print_error(f'Error processing video: {e.stderr.decode()}')
            return False


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
