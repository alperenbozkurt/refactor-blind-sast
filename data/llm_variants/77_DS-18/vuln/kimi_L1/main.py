"""Command-line tool for processing videos with FFmpeg."""

import os
import subprocess
import sys
from datetime import datetime


class VideoProcessor:
    """Process videos with FFmpeg and store the results in an output directory."""

    def __init__(self, output_dir='processed_videos'):
        self.output_dir = output_dir
        self.supported_formats = ['mp4', 'avi', 'mov', 'mkv']
        self.create_output_dir()

    def create_output_dir(self):
        """Create the output directory if it does not already exist."""
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def validate_video(self, video_path):
        """Raise ValueError if the video file is missing or has an unsupported format."""
        if not os.path.exists(video_path):
            raise ValueError('Video file does not exist')

        has_supported_extension = any(
            video_path.lower().endswith(extension)
            for extension in self.supported_formats
        )
        if not has_supported_extension:
            raise ValueError('Unsupported video format')

    def generate_output_name(self, video_path, operation):
        """Return a timestamped output file name for the given operation."""
        base_name = os.path.splitext(os.path.basename(video_path))[0]
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        return f'{base_name}_{operation}_{timestamp}.mp4'

    def process_video(self, video_path, operation, params=None):
        """Run the requested FFmpeg operation and return the output path."""
        self.validate_video(video_path)
        output_name = self.generate_output_name(video_path, operation)
        output_path = os.path.join(self.output_dir, output_name)

        command_builders = {
            'trim': lambda: (
                f'ffmpeg -i {video_path} '
                f'-ss {params.get("start", "00:00:00")} '
                f'-to {params.get("end", "00:01:00")} '
                f'-c copy {output_path}'
            ),
            'resize': lambda: (
                f'ffmpeg -i {video_path} '
                f'-vf scale={params.get("width", "640")}:{params.get("height", "480")} '
                f'{output_path}'
            ),
            'convert': lambda: f'ffmpeg -i {video_path} {output_path}',
            'custom': lambda: (
                f'ffmpeg -i {video_path} '
                f'-vf {params.get("filter", "")} '
                f'{output_path}'
            ),
        }

        if operation not in command_builders:
            raise ValueError('Unsupported operation')

        cmd = command_builders[operation]()
        subprocess.run(cmd, shell=True, check=True)
        print(f'Video processed and saved to {output_path}')
        return output_path

    def list_processed_videos(self):
        """Return the names of all .mp4 files in the output directory."""
        return [
            filename
            for filename in os.listdir(self.output_dir)
            if filename.endswith('.mp4')
        ]


def print_menu():
    """Print the main menu of the command-line interface."""
    print('\nVideo Processing Tool:')
    print('1. Trim video')
    print('2. Resize video')
    print('3. Convert format')
    print('4. Apply custom filter')
    print('5. List processed videos')
    print('6. Exit')


def main():
    """Run the interactive video processing menu loop."""
    processor = VideoProcessor()

    def process_with_error_report(video_path, operation, params=None):
        try:
            processor.process_video(video_path, operation, params)
        except Exception as e:
            print(f'Error: {e}')

    def handle_trim():
        video_path = input('Video file path: ')
        start = input('Start time (HH:MM:SS): ') or '00:00:00'
        end = input('End time (HH:MM:SS): ') or '00:01:00'
        process_with_error_report(
            video_path, 'trim', {'start': start, 'end': end}
        )

    def handle_resize():
        video_path = input('Video file path: ')
        width = input('Width: ') or '640'
        height = input('Height: ') or '480'
        process_with_error_report(
            video_path, 'resize', {'width': width, 'height': height}
        )

    def handle_convert():
        video_path = input('Video file path: ')
        process_with_error_report(video_path, 'convert')

    def handle_custom_filter():
        video_path = input('Video file path: ')
        custom_filter = input('FFmpeg filter string: ')
        process_with_error_report(
            video_path, 'custom', {'filter': custom_filter}
        )

    def handle_list_processed_videos():
        videos = processor.list_processed_videos()
        print('Processed videos:')
        for video in videos:
            print(f'- {video}')

    menu_actions = {
        '1': handle_trim,
        '2': handle_resize,
        '3': handle_convert,
        '4': handle_custom_filter,
        '5': handle_list_processed_videos,
    }

    while True:
        print_menu()
        choice = input('Enter your choice: ')

        if choice == '6':
            print('Exiting...')
            break

        action = menu_actions.get(choice)
        if action is None:
            print('Invalid choice. Please try again.')
        else:
            action()


if __name__ == '__main__':
    main()
