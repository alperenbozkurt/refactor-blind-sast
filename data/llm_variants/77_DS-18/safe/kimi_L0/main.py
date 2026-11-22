import os
import subprocess
import sys
from datetime import datetime


class VideoProcessor:
    """Process video files with ffmpeg (trim, resize, convert)."""

    def __init__(self, output_dir='processed_videos'):
        self.output_dir = output_dir
        self.supported_formats = ['mp4', 'avi', 'mov', 'mkv']
        self.supported_operations = ['trim', 'resize', 'convert']
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
            hours, minutes, seconds = (int(part) for part in parts)
        except ValueError:
            return False
        return hours >= 0 and 0 <= minutes < 60 and 0 <= seconds < 60

    def validate_dimension(self, dim):
        """Return True if dim is an integer within the allowed range."""
        try:
            return 100 <= int(dim) <= 7680
        except ValueError:
            return False

    def generate_output_name(self, video_path, operation):
        """Build a timestamped output file name for the given operation."""
        base_name = os.path.splitext(os.path.basename(video_path))[0]
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        return f'{base_name}_{operation}_{timestamp}.mp4'

    def process_video(self, video_path, operation, params=None):
        """Run the requested operation and return the output file path."""
        self.validate_video(video_path)
        if operation not in self.supported_operations:
            raise ValueError('Unsupported operation')
        output_name = self.generate_output_name(video_path, operation)
        output_path = os.path.join(self.output_dir, output_name)
        try:
            args = self._build_ffmpeg_args(video_path, operation, params, output_path)
            result = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if result.returncode != 0:
                raise RuntimeError(f'FFmpeg failed: {result.stderr.strip()}')
            print(f'Video processed and saved to {output_path}')
            return output_path
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f'Video processing failed: {e.stderr.strip()}')
        except Exception as e:
            raise RuntimeError(f'Error during video processing: {str(e)}')

    def _build_ffmpeg_args(self, video_path, operation, params, output_path):
        args = ['ffmpeg', '-i', video_path]
        if operation == 'trim':
            args.extend(self._trim_args(params))
        elif operation == 'resize':
            args.extend(self._resize_args(params))
        # 'convert' needs no extra flags; the .mp4 output extension sets the format.
        args.append(output_path)
        return args

    def _trim_args(self, params):
        start = params.get('start', '00:00:00')
        end = params.get('end', '00:01:00')
        if not (self.validate_time_format(start) and self.validate_time_format(end)):
            raise ValueError('Invalid time format (use HH:MM:SS)')
        return ['-ss', start, '-to', end, '-c', 'copy']

    def _resize_args(self, params):
        width = params.get('width', '640')
        height = params.get('height', '480')
        if not (self.validate_dimension(width) and self.validate_dimension(height)):
            raise ValueError('Invalid dimensions (100-7680)')
        return ['-vf', f'scale={width}:{height}']

    def list_processed_videos(self):
        """Return the names of all .mp4 files in the output directory."""
        return [f for f in os.listdir(self.output_dir) if f.endswith('.mp4')]


def print_menu():
    print(
        '\nVideo Processing Tool:'
        '\n1. Trim video'
        '\n2. Resize video'
        '\n3. Convert format'
        '\n4. List processed videos'
        '\n5. Exit'
        '\nNote: Custom filters are disabled for security reasons'
    )


def main():
    processor = VideoProcessor()

    def process_safely(video_path, operation, params=None):
        try:
            processor.process_video(video_path, operation, params)
        except Exception as e:
            print(f'Error: {e}')

    def handle_trim():
        video_path = input('Video file path: ')
        start = input('Start time (HH:MM:SS): ') or '00:00:00'
        end = input('End time (HH:MM:SS): ') or '00:01:00'
        process_safely(video_path, 'trim', {'start': start, 'end': end})

    def handle_resize():
        video_path = input('Video file path: ')
        width = input('Width (100-7680): ') or '640'
        height = input('Height (100-7680): ') or '480'
        process_safely(video_path, 'resize', {'width': width, 'height': height})

    def handle_convert():
        video_path = input('Video file path: ')
        process_safely(video_path, 'convert')

    def handle_list():
        videos = processor.list_processed_videos()
        print('Processed videos:')
        for video in videos:
            print(f'- {video}')

    actions = {
        '1': handle_trim,
        '2': handle_resize,
        '3': handle_convert,
        '4': handle_list,
    }

    while True:
        print_menu()
        choice = input('Enter your choice: ')
        if choice == '5':
            print('Exiting...')
            break
        action = actions.get(choice)
        if action is None:
            print('Invalid choice. Please try again.')
        else:
            action()


if __name__ == '__main__':
    main()
