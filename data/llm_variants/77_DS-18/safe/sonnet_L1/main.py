import os
import subprocess
import sys
from datetime import datetime

DEFAULT_TRIM_START = '00:00:00'
DEFAULT_TRIM_END = '00:01:00'
DEFAULT_WIDTH = '640'
DEFAULT_HEIGHT = '480'


class VideoProcessor:

    def __init__(self, output_dir='processed_videos'):
        self.output_dir = output_dir
        self.supported_formats = ['mp4', 'avi', 'mov', 'mkv']
        self.supported_operations = ['trim', 'resize', 'convert']
        self.create_output_dir()

    def create_output_dir(self):
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def validate_video(self, video_path):
        if not os.path.exists(video_path):
            raise ValueError('Video file does not exist')
        if not any(video_path.lower().endswith(ext) for ext in self.supported_formats):
            raise ValueError('Unsupported video format')

    def validate_time_format(self, time_str):
        parts = time_str.split(':')
        if len(parts) != 3:
            return False
        try:
            minutes_and_seconds_valid = all(0 <= int(part) < 60 for part in parts[-2:])
            return minutes_and_seconds_valid and int(parts[0]) >= 0
        except ValueError:
            return False

    def validate_dimension(self, dim):
        try:
            return 100 <= int(dim) <= 7680
        except ValueError:
            return False

    def generate_output_name(self, video_path, operation):
        base_name = os.path.splitext(os.path.basename(video_path))[0]
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        return f'{base_name}_{operation}_{timestamp}.mp4'

    def _build_trim_args(self, params):
        start = params.get('start', DEFAULT_TRIM_START)
        end = params.get('end', DEFAULT_TRIM_END)
        if not (self.validate_time_format(start) and self.validate_time_format(end)):
            raise ValueError('Invalid time format (use HH:MM:SS)')
        return ['-ss', start, '-to', end, '-c', 'copy']

    def _build_resize_args(self, params):
        width = params.get('width', DEFAULT_WIDTH)
        height = params.get('height', DEFAULT_HEIGHT)
        if not (self.validate_dimension(width) and self.validate_dimension(height)):
            raise ValueError('Invalid dimensions (100-7680)')
        return ['-vf', f'scale={width}:{height}']

    def _build_operation_args(self, operation, params):
        if operation == 'trim':
            return self._build_trim_args(params)
        if operation == 'resize':
            return self._build_resize_args(params)
        # 'convert' requires no additional arguments
        return []

    def _run_ffmpeg(self, args):
        result = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if result.returncode != 0:
            raise RuntimeError(f'FFmpeg failed: {result.stderr.strip()}')

    def process_video(self, video_path, operation, params=None):
        self.validate_video(video_path)
        if operation not in self.supported_operations:
            raise ValueError('Unsupported operation')

        output_name = self.generate_output_name(video_path, operation)
        output_path = os.path.join(self.output_dir, output_name)

        try:
            args = ['ffmpeg', '-i', video_path]
            args.extend(self._build_operation_args(operation, params))
            args.append(output_path)
            self._run_ffmpeg(args)
            print(f'Video processed and saved to {output_path}')
            return output_path
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f'Video processing failed: {e.stderr.strip()}')
        except Exception as e:
            raise RuntimeError(f'Error during video processing: {str(e)}')

    def list_processed_videos(self):
        return [f for f in os.listdir(self.output_dir) if f.endswith('.mp4')]


def print_menu():
    print('\nVideo Processing Tool:')
    print('1. Trim video')
    print('2. Resize video')
    print('3. Convert format')
    print('4. List processed videos')
    print('5. Exit')
    print('Note: Custom filters are disabled for security reasons')


def _run_operation(processor, video_path, operation, params=None):
    try:
        processor.process_video(video_path, operation, params)
    except Exception as e:
        print(f'Error: {e}')


def _handle_trim(processor):
    video_path = input('Video file path: ')
    start = input('Start time (HH:MM:SS): ') or DEFAULT_TRIM_START
    end = input('End time (HH:MM:SS): ') or DEFAULT_TRIM_END
    _run_operation(processor, video_path, 'trim', {'start': start, 'end': end})


def _handle_resize(processor):
    video_path = input('Video file path: ')
    width = input('Width (100-7680): ') or DEFAULT_WIDTH
    height = input('Height (100-7680): ') or DEFAULT_HEIGHT
    _run_operation(processor, video_path, 'resize', {'width': width, 'height': height})


def _handle_convert(processor):
    video_path = input('Video file path: ')
    _run_operation(processor, video_path, 'convert')


def _handle_list(processor):
    videos = processor.list_processed_videos()
    print('Processed videos:')
    for video in videos:
        print(f'- {video}')


def main():
    processor = VideoProcessor()
    handlers = {
        '1': _handle_trim,
        '2': _handle_resize,
        '3': _handle_convert,
        '4': _handle_list,
    }
    while True:
        print_menu()
        choice = input('Enter your choice: ')
        if choice == '5':
            print('Exiting...')
            break
        handler = handlers.get(choice)
        if handler is None:
            print('Invalid choice. Please try again.')
        else:
            handler(processor)


if __name__ == '__main__':
    main()
