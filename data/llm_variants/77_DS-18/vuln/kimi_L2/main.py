"""Command-line video processing tool backed by ffmpeg."""

import os
import subprocess
import sys
from datetime import datetime

# ---------------------------------------------------------------------------
# Configuration constants
# ---------------------------------------------------------------------------

DEFAULT_OUTPUT_DIR = 'processed_videos'
SUPPORTED_FORMATS = ['mp4', 'avi', 'mov', 'mkv']
OUTPUT_EXTENSION = '.mp4'
TIMESTAMP_FORMAT = '%Y%m%d_%H%M%S'

DEFAULT_START_TIME = '00:00:00'
DEFAULT_END_TIME = '00:01:00'
DEFAULT_WIDTH = '640'
DEFAULT_HEIGHT = '480'
DEFAULT_FILTER = ''

OP_TRIM = 'trim'
OP_RESIZE = 'resize'
OP_CONVERT = 'convert'
OP_CUSTOM = 'custom'

ERROR_VIDEO_NOT_FOUND = 'Video file does not exist'
ERROR_UNSUPPORTED_FORMAT = 'Unsupported video format'
ERROR_UNSUPPORTED_OPERATION = 'Unsupported operation'

CHOICE_TRIM = '1'
CHOICE_RESIZE = '2'
CHOICE_CONVERT = '3'
CHOICE_CUSTOM = '4'
CHOICE_LIST = '5'
CHOICE_EXIT = '6'

MENU_LINES = (
    '\nVideo Processing Tool:',
    '1. Trim video',
    '2. Resize video',
    '3. Convert format',
    '4. Apply custom filter',
    '5. List processed videos',
    '6. Exit',
)

PROMPT_CHOICE = 'Enter your choice: '
PROMPT_VIDEO_PATH = 'Video file path: '
PROMPT_START_TIME = 'Start time (HH:MM:SS): '
PROMPT_END_TIME = 'End time (HH:MM:SS): '
PROMPT_WIDTH = 'Width: '
PROMPT_HEIGHT = 'Height: '
PROMPT_FILTER = 'FFmpeg filter string: '

MSG_PROCESSED_HEADER = 'Processed videos:'
MSG_EXITING = 'Exiting...'
MSG_INVALID_CHOICE = 'Invalid choice. Please try again.'


class VideoProcessor:
    """Process video files with ffmpeg and manage the output directory."""

    def __init__(self, output_dir=DEFAULT_OUTPUT_DIR):
        self.output_dir = output_dir
        self.supported_formats = list(SUPPORTED_FORMATS)
        self.create_output_dir()

    def create_output_dir(self):
        """Create the output directory if it does not already exist."""
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def validate_video(self, video_path):
        """Ensure the file exists and has a supported extension."""
        if not os.path.exists(video_path):
            raise ValueError(ERROR_VIDEO_NOT_FOUND)
        if not self._has_supported_format(video_path):
            raise ValueError(ERROR_UNSUPPORTED_FORMAT)

    def _has_supported_format(self, video_path):
        lower_path = video_path.lower()
        return any(lower_path.endswith(ext) for ext in self.supported_formats)

    def generate_output_name(self, video_path, operation):
        """Build a unique output file name for the given operation."""
        base_name = os.path.splitext(os.path.basename(video_path))[0]
        timestamp = datetime.now().strftime(TIMESTAMP_FORMAT)
        return f'{base_name}_{operation}_{timestamp}{OUTPUT_EXTENSION}'

    def process_video(self, video_path, operation, params=None):
        """Validate input, run the requested operation and return the output path."""
        self.validate_video(video_path)
        output_name = self.generate_output_name(video_path, operation)
        output_path = os.path.join(self.output_dir, output_name)
        cmd = self._build_command(operation, video_path, output_path, params)
        self._run_command(cmd)
        print(f'Video processed and saved to {output_path}')
        return output_path

    def _build_command(self, operation, video_path, output_path, params):
        builders = {
            OP_TRIM: self._build_trim_command,
            OP_RESIZE: self._build_resize_command,
            OP_CONVERT: self._build_convert_command,
            OP_CUSTOM: self._build_custom_command,
        }
        builder = builders.get(operation)
        if builder is None:
            raise ValueError(ERROR_UNSUPPORTED_OPERATION)
        return builder(video_path, output_path, params)

    @staticmethod
    def _build_trim_command(video_path, output_path, params):
        start = params.get('start', DEFAULT_START_TIME)
        end = params.get('end', DEFAULT_END_TIME)
        return f'ffmpeg -i {video_path} -ss {start} -to {end} -c copy {output_path}'

    @staticmethod
    def _build_resize_command(video_path, output_path, params):
        width = params.get('width', DEFAULT_WIDTH)
        height = params.get('height', DEFAULT_HEIGHT)
        return f'ffmpeg -i {video_path} -vf scale={width}:{height} {output_path}'

    @staticmethod
    def _build_convert_command(video_path, output_path, params):
        return f'ffmpeg -i {video_path} {output_path}'

    @staticmethod
    def _build_custom_command(video_path, output_path, params):
        custom_filter = params.get('filter', DEFAULT_FILTER)
        return f'ffmpeg -i {video_path} -vf {custom_filter} {output_path}'

    @staticmethod
    def _run_command(cmd):
        subprocess.run(cmd, shell=True, check=True)

    def list_processed_videos(self):
        """Return the names of all processed mp4 files in the output directory."""
        return [f for f in os.listdir(self.output_dir) if f.endswith(OUTPUT_EXTENSION)]


def print_menu():
    for line in MENU_LINES:
        print(line)


def _process_safely(processor, video_path, operation, params=None):
    """Run an operation, printing any error instead of propagating it."""
    try:
        processor.process_video(video_path, operation, params)
    except Exception as exc:
        print(f'Error: {exc}')


def _handle_trim(processor):
    video_path = input(PROMPT_VIDEO_PATH)
    start = input(PROMPT_START_TIME) or DEFAULT_START_TIME
    end = input(PROMPT_END_TIME) or DEFAULT_END_TIME
    _process_safely(processor, video_path, OP_TRIM, {'start': start, 'end': end})


def _handle_resize(processor):
    video_path = input(PROMPT_VIDEO_PATH)
    width = input(PROMPT_WIDTH) or DEFAULT_WIDTH
    height = input(PROMPT_HEIGHT) or DEFAULT_HEIGHT
    _process_safely(processor, video_path, OP_RESIZE, {'width': width, 'height': height})


def _handle_convert(processor):
    video_path = input(PROMPT_VIDEO_PATH)
    _process_safely(processor, video_path, OP_CONVERT)


def _handle_custom(processor):
    video_path = input(PROMPT_VIDEO_PATH)
    custom_filter = input(PROMPT_FILTER)
    _process_safely(processor, video_path, OP_CUSTOM, {'filter': custom_filter})


def _handle_list(processor):
    videos = processor.list_processed_videos()
    print(MSG_PROCESSED_HEADER)
    for video in videos:
        print(f'- {video}')


MENU_HANDLERS = {
    CHOICE_TRIM: _handle_trim,
    CHOICE_RESIZE: _handle_resize,
    CHOICE_CONVERT: _handle_convert,
    CHOICE_CUSTOM: _handle_custom,
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
        handler = MENU_HANDLERS.get(choice)
        if handler is None:
            print(MSG_INVALID_CHOICE)
        else:
            handler(processor)


if __name__ == '__main__':
    main()
