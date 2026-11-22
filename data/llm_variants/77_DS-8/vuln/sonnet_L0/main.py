import subprocess
import argparse
import os
import sys
from pathlib import Path
from typing import Optional, List


class VideoProcessor:

    def __init__(self, output_dir: str = 'processed'):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

    def _generate_output_path(self, input_path: Path, suffix: str) -> Path:
        return self.output_dir / f'{input_path.stem}_{suffix}{input_path.suffix}'

    @staticmethod
    def _input_exists(video_path: str) -> Optional[Path]:
        input_path = Path(video_path)
        if not input_path.exists():
            print(f'Error: Input file {video_path} not found', file=sys.stderr)
            return None
        return input_path

    @staticmethod
    def _run_ffmpeg(args: List[str], error_label: str) -> bool:
        # Arguments are passed as a list (no shell) to avoid quoting/injection issues.
        try:
            subprocess.run(['ffmpeg', *args], check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            print(f'Error {error_label}: {e}', file=sys.stderr)
            return False

    def extract_audio(self, video_path: str) -> Optional[str]:
        input_path = self._input_exists(video_path)
        if input_path is None:
            return None
        output_path = self._generate_output_path(input_path, 'audio')
        args = ['-i', video_path, '-vn', '-acodec', 'copy', str(output_path)]
        if self._run_ffmpeg(args, 'extracting audio'):
            return str(output_path)
        return None

    def create_thumbnail(self, video_path: str, timestamp: str = '00:00:01') -> Optional[str]:
        input_path = self._input_exists(video_path)
        if input_path is None:
            return None
        output_path = self.output_dir / f'{input_path.stem}_thumbnail.jpg'
        args = ['-ss', timestamp, '-i', video_path,
                '-vframes', '1', '-q:v', '2', str(output_path)]
        if self._run_ffmpeg(args, 'creating thumbnail'):
            return str(output_path)
        return None

    def process_video(self, video_path: str, operations: List[str]) -> bool:
        input_path = self._input_exists(video_path)
        if input_path is None:
            return False
        output_path = self._generate_output_path(input_path, 'processed')
        args = ['-i', video_path, '-vf', ','.join(operations), str(output_path)]
        return self._run_ffmpeg(args, 'processing video')


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
