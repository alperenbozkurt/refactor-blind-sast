import subprocess
import argparse
import os
import sys
import shlex
from pathlib import Path
from typing import Optional, List

_ALLOWED_OPERATION_PUNCTUATION = frozenset(['=', ':', ',', '-', '_', ' ', "'", '"'])


def _print_error(message: str) -> None:
    print(message, file=sys.stderr)


def _is_safe_operation(operation: str) -> bool:
    return all(c.isalnum() or c in _ALLOWED_OPERATION_PUNCTUATION for c in operation)


class VideoProcessor:

    def __init__(self, output_dir: str='processed'):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

    def _generate_output_path(self, input_path: Path, suffix: str) -> Path:
        return self.output_dir / f'{input_path.stem}_{suffix}{input_path.suffix}'

    def _validate_timestamp(self, timestamp: str) -> bool:
        try:
            parts = list(map(int, timestamp.split(':')))
        except ValueError:
            return False
        if len(parts) != 3:
            return False
        hours, minutes, seconds = parts
        return hours >= 0 and 0 <= minutes <= 59 and 0 <= seconds <= 59

    def _check_input(self, video_path: str) -> Optional[Path]:
        input_path = Path(video_path)
        if not input_path.exists():
            _print_error(f'Error: Input file {video_path} not found')
            return None
        return input_path

    def _run_ffmpeg(self, cmd: List[str], action: str) -> bool:
        try:
            subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            return True
        except subprocess.CalledProcessError as e:
            _print_error(f'Error {action}: {e.stderr.decode()}')
            return False

    def extract_audio(self, video_path: str) -> Optional[str]:
        input_path = self._check_input(video_path)
        if input_path is None:
            return None
        output_path = self._generate_output_path(input_path, 'audio')
        cmd = ['ffmpeg', '-i', str(input_path), '-vn', '-acodec', 'copy', str(output_path)]
        if self._run_ffmpeg(cmd, 'extracting audio'):
            return str(output_path)
        return None

    def create_thumbnail(self, video_path: str, timestamp: str='00:00:01') -> Optional[str]:
        input_path = self._check_input(video_path)
        if input_path is None:
            return None
        if not self._validate_timestamp(timestamp):
            _print_error(f'Error: Invalid timestamp format {timestamp}')
            return None
        output_path = self.output_dir / f'{input_path.stem}_thumbnail.jpg'
        cmd = ['ffmpeg', '-ss', timestamp, '-i', str(input_path), '-vframes', '1', '-q:v', '2', str(output_path)]
        if self._run_ffmpeg(cmd, 'creating thumbnail'):
            return str(output_path)
        return None

    def process_video(self, video_path: str, operations: List[str]) -> bool:
        input_path = self._check_input(video_path)
        if input_path is None:
            return False
        valid_operations = []
        for op in operations:
            if _is_safe_operation(op):
                valid_operations.append(op)
            else:
                _print_error(f'Warning: Skipping potentially issue operation: {op}')
        if not valid_operations:
            _print_error('Error: No valid operations provided')
            return False
        output_path = self._generate_output_path(input_path, 'processed')
        cmd = ['ffmpeg', '-i', str(input_path), '-vf', ','.join(valid_operations), str(output_path)]
        return self._run_ffmpeg(cmd, 'processing video')


def _build_parser() -> argparse.ArgumentParser:
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
    return parser


def main():
    args = _build_parser().parse_args()
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
        if processor.process_video(args.video_file, args.operations):
            print('Video processed successfully')


if __name__ == '__main__':
    main()
