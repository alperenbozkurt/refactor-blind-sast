import subprocess
import argparse
import os
import sys
from pathlib import Path
from typing import Optional, List


class VideoProcessor:
    """Wrapper around ffmpeg for common video operations."""

    def __init__(self, output_dir: str = 'processed'):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

    def _generate_output_path(self, input_path: Path, suffix: str) -> Path:
        return self.output_dir / f'{input_path.stem}_{suffix}{input_path.suffix}'

    @staticmethod
    def _input_exists(video_path: str) -> bool:
        """Return True if the input file exists, otherwise report the error."""
        if Path(video_path).exists():
            return True
        print(f'Error: Input file {video_path} not found', file=sys.stderr)
        return False

    @staticmethod
    def _run_command(cmd: str, error_context: str) -> bool:
        """Run a shell command, reporting failures. Returns True on success."""
        try:
            subprocess.run(cmd, shell=True, check=True)
            return True
        except subprocess.CalledProcessError as e:
            print(f'Error {error_context}: {e}', file=sys.stderr)
            return False

    def extract_audio(self, video_path: str) -> Optional[str]:
        if not self._input_exists(video_path):
            return None

        output_path = self._generate_output_path(Path(video_path), 'audio')
        cmd = f"ffmpeg -i '{video_path}' -vn -acodec copy {output_path}"

        if self._run_command(cmd, 'extracting audio'):
            return str(output_path)
        return None

    def create_thumbnail(self, video_path: str, timestamp: str = '00:00:01') -> Optional[str]:
        if not self._input_exists(video_path):
            return None

        output_path = self.output_dir / f'{Path(video_path).stem}_thumbnail.jpg'
        cmd = f"ffmpeg -ss {timestamp} -i '{video_path}' -vframes 1 -q:v 2 {output_path}"

        if self._run_command(cmd, 'creating thumbnail'):
            return str(output_path)
        return None

    def process_video(self, video_path: str, operations: List[str]) -> bool:
        if not self._input_exists(video_path):
            return False

        output_path = self._generate_output_path(Path(video_path), 'processed')
        ffmpeg_filters = ','.join(operations)
        cmd = f"ffmpeg -i '{video_path}' -vf '{ffmpeg_filters}' {output_path}"

        return self._run_command(cmd, 'processing video')


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
        success = processor.process_video(args.video_file, args.operations)
        if success:
            print('Video processed successfully')


if __name__ == '__main__':
    main()
