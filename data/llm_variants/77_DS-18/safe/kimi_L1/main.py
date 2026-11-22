"""Simple command-line tool for trimming, resizing and converting videos.

All heavy lifting is delegated to FFmpeg; this module only validates the
user's input, builds the corresponding FFmpeg command and runs it.
"""

import os
import subprocess
import sys
from datetime import datetime


class VideoProcessor:
    """Validate user input and run FFmpeg commands on video files."""

    SUPPORTED_FORMATS = ('mp4', 'avi', 'mov', 'mkv')
    SUPPORTED_OPERATIONS = ('trim', 'resize', 'convert')

    def __init__(self, output_dir='processed_videos'):
        self.output_dir = output_dir
        self.supported_formats = list(self.SUPPORTED_FORMATS)
        self.supported_operations = list(self.SUPPORTED_OPERATIONS)
        self.create_output_dir()

    def create_output_dir(self):
        """Create the output directory if it does not exist yet."""
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def validate_video(self, video_path):
        """Raise ValueError if the file is missing or has an unsupported format."""
        if not os.path.exists(video_path):
            raise ValueError('Video file does not exist')
        if not video_path.lower().endswith(tuple(self.supported_formats)):
            raise ValueError('Unsupported video format')

    def validate_time_format(self, time_str):
        """Return True if time_str is a valid HH:MM:SS timestamp."""
        parts = time_str.split(':')
        if len(parts) != 3:
            return False
        try:
            hours, minutes, seconds = map(int, parts)
        except ValueError:
            return False
        return hours >= 0 and 0 <= minutes < 60 and 0 <= seconds < 60

    def validate_dimension(self, dim):
        """Return True if dim is an integer between 100 and 7680 inclusive."""
        try:
            return 100 <= int(dim) <= 7680
        except ValueError:
            return False

    def generate_output_name(self, video_path, operation):
        """Build a timestamped .mp4 output name for the given operation."""
        base_name = os.path.splitext(os.path.basename(video_path))[0]
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        return f'{base_name}_{operation}_{timestamp}.mp4'

    def _build_ffmpeg_command(self, video_path, operation, params):
        """Assemble the FFmpeg argument list for the requested operation."""
        args = ['ffmpeg', '-i', video_path]
        if operation == 'trim':
            start = params.get('start', '00:00:00')
            end = params.get('end', '00:01:00')
            if not (self.validate_time_format(start) and self.validate_time_format(end)):
                raise ValueError('Invalid time format (use HH:MM:SS)')
            args.extend(['-ss', start, '-to', end, '-c', 'copy'])
        elif operation == 'resize':
            width = params.get('width', '640')
            height = params.get('height', '480')
            if not (self.validate_dimension(width) and self.validate_dimension(height)):
                raise ValueError('Invalid dimensions (100-7680)')
            args.extend(['-vf', f'scale={width}:{height}'])
        # 'convert' needs no extra arguments; the .mp4 output name suffices.
        return args

    def process_video(self, video_path, operation, params=None):
        """Process video_path with the given operation and return the output path."""
        self.validate_video(video_path)
        if operation not in self.supported_operations:
            raise ValueError('Unsupported operation')

        output_name = self.generate_output_name(video_path, operation)
        output_path = os.path.join(self.output_dir, output_name)

        try:
            args = self._build_ffmpeg_command(video_path, operation, params)
            args.append(output_path)
            result = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if result.returncode != 0:
                raise RuntimeError(f'FFmpeg failed: {result.stderr.strip()}')
            print(f'Video processed and saved to {output_path}')
            return output_path
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f'Video processing failed: {e.stderr.strip()}')
        except Exception as e:
            raise RuntimeError(f'Error during video processing: {str(e)}')

    def list_processed_videos(self):
        """Return the names of all .mp4 files in the output directory."""
        return [f for f in os.listdir(self.output_dir) if f.endswith('.mp4')]


def print_menu():
    """Print the main menu."""
    print(
        '\nVideo Processing Tool:\n'
        '1. Trim video\n'
        '2. Resize video\n'
        '3. Convert format\n'
        '4. List processed videos\n'
        '5. Exit\n'
        'Note: Custom filters are disabled for security reasons'
    )


def main():
    """Run the interactive command-line interface."""
    processor = VideoProcessor()
    while True:
        print_menu()
        choice = input('Enter your choice: ')

        if choice == '1':
            video_path = input('Video file path: ')
            start = input('Start time (HH:MM:SS): ') or '00:00:00'
            end = input('End time (HH:MM:SS): ') or '00:01:00'
            operation, params = 'trim', {'start': start, 'end': end}
        elif choice == '2':
            video_path = input('Video file path: ')
            width = input('Width (100-7680): ') or '640'
            height = input('Height (100-7680): ') or '480'
            operation, params = 'resize', {'width': width, 'height': height}
        elif choice == '3':
            video_path = input('Video file path: ')
            operation, params = 'convert', None
        elif choice == '4':
            videos = processor.list_processed_videos()
            print('Processed videos:')
            for video in videos:
                print(f'- {video}')
            continue
        elif choice == '5':
            print('Exiting...')
            break
        else:
            print('Invalid choice. Please try again.')
            continue

        try:
            processor.process_video(video_path, operation, params)
        except Exception as e:
            print(f'Error: {e}')


if __name__ == '__main__':
    main()
