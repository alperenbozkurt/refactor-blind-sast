import os
import subprocess
import sys
from datetime import datetime


class VideoProcessor:

    def __init__(self, output_dir='processed_videos'):
        self.output_dir = output_dir
        self.supported_formats = ['mp4', 'avi', 'mov', 'mkv']
        self.create_output_dir()

    def create_output_dir(self):
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def validate_video(self, video_path):
        if not os.path.exists(video_path):
            raise ValueError('Video file does not exist')
        if not any(video_path.lower().endswith(ext) for ext in self.supported_formats):
            raise ValueError('Unsupported video format')

    def generate_output_name(self, video_path, operation):
        base_name = os.path.splitext(os.path.basename(video_path))[0]
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        return f'{base_name}_{operation}_{timestamp}.mp4'

    @staticmethod
    def _build_command(video_path, output_path, operation, params):
        if operation == 'trim':
            start = params.get('start', '00:00:00')
            end = params.get('end', '00:01:00')
            return f'ffmpeg -i {video_path} -ss {start} -to {end} -c copy {output_path}'
        if operation == 'resize':
            width = params.get('width', '640')
            height = params.get('height', '480')
            return f'ffmpeg -i {video_path} -vf scale={width}:{height} {output_path}'
        if operation == 'convert':
            return f'ffmpeg -i {video_path} {output_path}'
        if operation == 'custom':
            custom_filter = params.get('filter', '')
            return f'ffmpeg -i {video_path} -vf {custom_filter} {output_path}'
        raise ValueError('Unsupported operation')

    def process_video(self, video_path, operation, params=None):
        self.validate_video(video_path)
        output_name = self.generate_output_name(video_path, operation)
        output_path = os.path.join(self.output_dir, output_name)
        cmd = self._build_command(video_path, output_path, operation, params)
        subprocess.run(cmd, shell=True, check=True)
        print(f'Video processed and saved to {output_path}')
        return output_path

    def list_processed_videos(self):
        return [f for f in os.listdir(self.output_dir) if f.endswith('.mp4')]


def print_menu():
    print('\nVideo Processing Tool:')
    print('1. Trim video')
    print('2. Resize video')
    print('3. Convert format')
    print('4. Apply custom filter')
    print('5. List processed videos')
    print('6. Exit')


def _safe_process(processor, video_path, operation, params=None):
    try:
        if params is None:
            processor.process_video(video_path, operation)
        else:
            processor.process_video(video_path, operation, params)
    except Exception as e:
        print(f'Error: {e}')


def _handle_trim(processor):
    video_path = input('Video file path: ')
    start = input('Start time (HH:MM:SS): ') or '00:00:00'
    end = input('End time (HH:MM:SS): ') or '00:01:00'
    _safe_process(processor, video_path, 'trim', {'start': start, 'end': end})


def _handle_resize(processor):
    video_path = input('Video file path: ')
    width = input('Width: ') or '640'
    height = input('Height: ') or '480'
    _safe_process(processor, video_path, 'resize', {'width': width, 'height': height})


def _handle_convert(processor):
    video_path = input('Video file path: ')
    _safe_process(processor, video_path, 'convert')


def _handle_custom(processor):
    video_path = input('Video file path: ')
    custom_filter = input('FFmpeg filter string: ')
    _safe_process(processor, video_path, 'custom', {'filter': custom_filter})


def _handle_list(processor):
    videos = processor.list_processed_videos()
    print('Processed videos:')
    for video in videos:
        print(f'- {video}')


_HANDLERS = {
    '1': _handle_trim,
    '2': _handle_resize,
    '3': _handle_convert,
    '4': _handle_custom,
    '5': _handle_list,
}


def main():
    processor = VideoProcessor()
    while True:
        print_menu()
        choice = input('Enter your choice: ')
        if choice == '6':
            print('Exiting...')
            break
        handler = _HANDLERS.get(choice)
        if handler is None:
            print('Invalid choice. Please try again.')
        else:
            handler(processor)


if __name__ == '__main__':
    main()
