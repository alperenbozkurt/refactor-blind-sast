"""Interactive command-line tool for trimming, resizing and converting videos.

This module wraps FFmpeg behind the :class:`VideoProcessor` class and exposes
a simple text menu through :func:`main`.
"""

import os
import subprocess
import sys
from datetime import datetime

# --- Processor configuration ------------------------------------------------

DEFAULT_OUTPUT_DIR = 'processed_videos'
SUPPORTED_FORMATS = ('mp4', 'avi', 'mov', 'mkv')
SUPPORTED_OPERATIONS = ('trim', 'resize', 'convert')

OPERATION_TRIM = 'trim'
OPERATION_RESIZE = 'resize'
OPERATION_CONVERT = 'convert'

FFMPEG_EXECUTABLE = 'ffmpeg'
OUTPUT_EXTENSION = '.mp4'
TIMESTAMP_FORMAT = '%Y%m%d_%H%M%S'

TIME_SEPARATOR = ':'
TIME_PARTS_COUNT = 3
MAX_TIME_COMPONENT = 60

DEFAULT_TRIM_START = '00:00:00'
DEFAULT_TRIM_END = '00:01:00'
DEFAULT_WIDTH = '640'
DEFAULT_HEIGHT = '480'
MIN_DIMENSION = 100
MAX_DIMENSION = 7680

# --- User-facing messages -----------------------------------------------------

ERROR_VIDEO_NOT_FOUND = 'Video file does not exist'
ERROR_UNSUPPORTED_FORMAT = 'Unsupported video format'
ERROR_UNSUPPORTED_OPERATION = 'Unsupported operation'
ERROR_INVALID_TIME = 'Invalid time format (use HH:MM:SS)'
ERROR_INVALID_DIMENSIONS = 'Invalid dimensions (100-7680)'

CHOICE_TRIM = '1'
CHOICE_RESIZE = '2'
CHOICE_CONVERT = '3'
CHOICE_LIST = '4'
CHOICE_EXIT = '5'

MENU_LINES = (
    '\nVideo Processing Tool:',
    '1. Trim video',
    '2. Resize video',
    '3. Convert format',
    '4. List processed videos',
    '5. Exit',
    'Note: Custom filters are disabled for security reasons',
)

PROMPT_CHOICE = 'Enter your choice: '
PROMPT_VIDEO_PATH = 'Video file path: '
PROMPT_START_TIME = 'Start time (HH:MM:SS): '
PROMPT_END_TIME = 'End time (HH:MM:SS): '
PROMPT_WIDTH = 'Width (100-7680): '
PROMPT_HEIGHT = 'Height (100-7680): '

MSG_EXITING = 'Exiting...'
MSG_INVALID_CHOICE = 'Invalid choice. Please try again.'
MSG_PROCESSED_HEADER = 'Processed videos:'


# --- Small validation / execution helpers -------------------------------------


def _has_supported_extension(video_path, extensions):
    """Return True if ``video_path`` ends with one of ``extensions``."""
    return any(video_path.lower().endswith(ext) for ext in extensions)


def _is_valid_time_component(part):
    """Return True if ``part`` is an integer in the range [0, 60)."""
    return 0 <= int(part) < MAX_TIME_COMPONENT


def _run_ffmpeg(args):
    """Run FFmpeg with ``args`` and raise RuntimeError on a non-zero exit."""
    result = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        raise RuntimeError(f'FFmpeg failed: {result.stderr.strip()}')


class VideoProcessor:
    """Validate videos and run FFmpeg operations on them."""

    def __init__(self, output_dir=DEFAULT_OUTPUT_DIR):
        self.output_dir = output_dir
        self.supported_formats = list(SUPPORTED_FORMATS)
        self.supported_operations = list(SUPPORTED_OPERATIONS)
        self.create_output_dir()

    def create_output_dir(self):
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def validate_video(self, video_path):
        if not os.path.exists(video_path):
            raise ValueError(ERROR_VIDEO_NOT_FOUND)
        if not _has_supported_extension(video_path, self.supported_formats):
            raise ValueError(ERROR_UNSUPPORTED_FORMAT)

    def validate_time_format(self, time_str):
        parts = time_str.split(TIME_SEPARATOR)
        if len(parts) != TIME_PARTS_COUNT:
            return False
        try:
            return all(_is_valid_time_component(part) for part in parts[-2:]) and int(parts[0]) >= 0
        except ValueError:
            return False

    def validate_dimension(self, dim):
        try:
            return MIN_DIMENSION <= int(dim) <= MAX_DIMENSION
        except ValueError:
            return False

    def generate_output_name(self, video_path, operation):
        base_name = os.path.splitext(os.path.basename(video_path))[0]
        timestamp = datetime.now().strftime(TIMESTAMP_FORMAT)
        return f'{base_name}_{operation}_{timestamp}{OUTPUT_EXTENSION}'

    def process_video(self, video_path, operation, params=None):
        self.validate_video(video_path)
        if operation not in self.supported_operations:
            raise ValueError(ERROR_UNSUPPORTED_OPERATION)
        output_name = self.generate_output_name(video_path, operation)
        output_path = os.path.join(self.output_dir, output_name)
        try:
            args = self._build_ffmpeg_args(video_path, operation, params, output_path)
            _run_ffmpeg(args)
            print(f'Video processed and saved to {output_path}')
            return output_path
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f'Video processing failed: {e.stderr.strip()}')
        except Exception as e:
            raise RuntimeError(f'Error during video processing: {str(e)}')

    def list_processed_videos(self):
        return [f for f in os.listdir(self.output_dir) if f.endswith(OUTPUT_EXTENSION)]

    def _build_ffmpeg_args(self, video_path, operation, params, output_path):
        args = [FFMPEG_EXECUTABLE, '-i', video_path]
        if operation == OPERATION_TRIM:
            args.extend(self._build_trim_args(params))
        elif operation == OPERATION_RESIZE:
            args.extend(self._build_resize_args(params))
        args.append(output_path)
        return args

    def _build_trim_args(self, params):
        start = params.get('start', DEFAULT_TRIM_START)
        end = params.get('end', DEFAULT_TRIM_END)
        if not (self.validate_time_format(start) and self.validate_time_format(end)):
            raise ValueError(ERROR_INVALID_TIME)
        return ['-ss', start, '-to', end, '-c', 'copy']

    def _build_resize_args(self, params):
        width = params.get('width', DEFAULT_WIDTH)
        height = params.get('height', DEFAULT_HEIGHT)
        if not (self.validate_dimension(width) and self.validate_dimension(height)):
            raise ValueError(ERROR_INVALID_DIMENSIONS)
        return ['-vf', f'scale={width}:{height}']


# --- Command-line interface ---------------------------------------------------


def print_menu():
    for line in MENU_LINES:
        print(line)


def _process_and_report(processor, video_path, operation, params=None):
    try:
        processor.process_video(video_path, operation, params)
    except Exception as e:
        print(f'Error: {e}')


def _handle_trim(processor):
    video_path = input(PROMPT_VIDEO_PATH)
    start = input(PROMPT_START_TIME) or DEFAULT_TRIM_START
    end = input(PROMPT_END_TIME) or DEFAULT_TRIM_END
    _process_and_report(processor, video_path, OPERATION_TRIM, {'start': start, 'end': end})


def _handle_resize(processor):
    video_path = input(PROMPT_VIDEO_PATH)
    width = input(PROMPT_WIDTH) or DEFAULT_WIDTH
    height = input(PROMPT_HEIGHT) or DEFAULT_HEIGHT
    _process_and_report(processor, video_path, OPERATION_RESIZE, {'width': width, 'height': height})


def _handle_convert(processor):
    video_path = input(PROMPT_VIDEO_PATH)
    _process_and_report(processor, video_path, OPERATION_CONVERT)


def _handle_list(processor):
    videos = processor.list_processed_videos()
    print(MSG_PROCESSED_HEADER)
    for video in videos:
        print(f'- {video}')


_MENU_HANDLERS = {
    CHOICE_TRIM: _handle_trim,
    CHOICE_RESIZE: _handle_resize,
    CHOICE_CONVERT: _handle_convert,
    CHOICE_LIST: _handle_list,
}


def main():
    processor = VideoProcessor()
    while True:
        print_menu()
        choice = input(PROMPT_CHOICE)
        if choice == CHOICE_EXIT:
            print(MSG_EXITING)
            break
        handler = _MENU_HANDLERS.get(choice)
        if handler is None:
            print(MSG_INVALID_CHOICE)
        else:
            handler(processor)


if __name__ == '__main__':
    main()
