import os
import subprocess
import sys
from datetime import datetime

# --- Constants ---------------------------------------------------------------

DEFAULT_OUTPUT_DIR = 'processed_videos'
SUPPORTED_FORMATS = ['mp4', 'avi', 'mov', 'mkv']
OUTPUT_EXTENSION = '.mp4'
TIMESTAMP_FORMAT = '%Y%m%d_%H%M%S'

DEFAULT_TRIM_START = '00:00:00'
DEFAULT_TRIM_END = '00:01:00'
DEFAULT_WIDTH = '640'
DEFAULT_HEIGHT = '480'
DEFAULT_FILTER = ''

OP_TRIM = 'trim'
OP_RESIZE = 'resize'
OP_CONVERT = 'convert'
OP_CUSTOM = 'custom'

MENU_LINES = (
    '\nVideo Processing Tool:',
    '1. Trim video',
    '2. Resize video',
    '3. Convert format',
    '4. Apply custom filter',
    '5. List processed videos',
    '6. Exit',
)


# --- FFmpeg command builders -------------------------------------------------

def _build_trim_command(video_path, output_path, params):
    start = params.get('start', DEFAULT_TRIM_START)
    end = params.get('end', DEFAULT_TRIM_END)
    return f'ffmpeg -i {video_path} -ss {start} -to {end} -c copy {output_path}'


def _build_resize_command(video_path, output_path, params):
    width = params.get('width', DEFAULT_WIDTH)
    height = params.get('height', DEFAULT_HEIGHT)
    return f'ffmpeg -i {video_path} -vf scale={width}:{height} {output_path}'


def _build_convert_command(video_path, output_path, params):
    return f'ffmpeg -i {video_path} {output_path}'


def _build_custom_command(video_path, output_path, params):
    custom_filter = params.get('filter', DEFAULT_FILTER)
    return f'ffmpeg -i {video_path} -vf {custom_filter} {output_path}'


COMMAND_BUILDERS = {
    OP_TRIM: _build_trim_command,
    OP_RESIZE: _build_resize_command,
    OP_CONVERT: _build_convert_command,
    OP_CUSTOM: _build_custom_command,
}


# --- Core processor ----------------------------------------------------------

class VideoProcessor:

    def __init__(self, output_dir=DEFAULT_OUTPUT_DIR):
        self.output_dir = output_dir
        self.supported_formats = list(SUPPORTED_FORMATS)
        self.create_output_dir()

    def create_output_dir(self):
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def validate_video(self, video_path):
        if not os.path.exists(video_path):
            raise ValueError('Video file does not exist')
        if not any((video_path.lower().endswith(ext) for ext in self.supported_formats)):
            raise ValueError('Unsupported video format')

    def generate_output_name(self, video_path, operation):
        base_name = os.path.splitext(os.path.basename(video_path))[0]
        timestamp = datetime.now().strftime(TIMESTAMP_FORMAT)
        return f'{base_name}_{operation}_{timestamp}{OUTPUT_EXTENSION}'

    def _build_command(self, video_path, output_path, operation, params):
        builder = COMMAND_BUILDERS.get(operation)
        if builder is None:
            raise ValueError('Unsupported operation')
        return builder(video_path, output_path, params)

    def process_video(self, video_path, operation, params=None):
        self.validate_video(video_path)
        output_name = self.generate_output_name(video_path, operation)
        output_path = os.path.join(self.output_dir, output_name)
        cmd = self._build_command(video_path, output_path, operation, params)
        subprocess.run(cmd, shell=True, check=True)
        print(f'Video processed and saved to {output_path}')
        return output_path

    def list_processed_videos(self):
        return [f for f in os.listdir(self.output_dir) if f.endswith(OUTPUT_EXTENSION)]


# --- CLI ---------------------------------------------------------------------

def print_menu():
    for line in MENU_LINES:
        print(line)


def _run_operation(processor, video_path, operation, params=None):
    try:
        processor.process_video(video_path, operation, params)
    except Exception as e:
        print(f'Error: {e}')


def _handle_trim(processor):
    video_path = input('Video file path: ')
    start = input('Start time (HH:MM:SS): ') or DEFAULT_TRIM_START
    end = input('End time (HH:MM:SS): ') or DEFAULT_TRIM_END
    _run_operation(processor, video_path, OP_TRIM, {'start': start, 'end': end})


def _handle_resize(processor):
    video_path = input('Video file path: ')
    width = input('Width: ') or DEFAULT_WIDTH
    height = input('Height: ') or DEFAULT_HEIGHT
    _run_operation(processor, video_path, OP_RESIZE, {'width': width, 'height': height})


def _handle_convert(processor):
    video_path = input('Video file path: ')
    _run_operation(processor, video_path, OP_CONVERT)


def _handle_custom(processor):
    video_path = input('Video file path: ')
    custom_filter = input('FFmpeg filter string: ')
    _run_operation(processor, video_path, OP_CUSTOM, {'filter': custom_filter})


def _handle_list(processor):
    videos = processor.list_processed_videos()
    print('Processed videos:')
    for video in videos:
        print(f'- {video}')


MENU_HANDLERS = {
    '1': _handle_trim,
    '2': _handle_resize,
    '3': _handle_convert,
    '4': _handle_custom,
    '5': _handle_list,
}
EXIT_CHOICE = '6'


def main():
    processor = VideoProcessor()
    while True:
        print_menu()
        choice = input('Enter your choice: ')
        if choice == EXIT_CHOICE:
            print('Exiting...')
            break
        handler = MENU_HANDLERS.get(choice)
        if handler is None:
            print('Invalid choice. Please try again.')
        else:
            handler(processor)


if __name__ == '__main__':
    main()
