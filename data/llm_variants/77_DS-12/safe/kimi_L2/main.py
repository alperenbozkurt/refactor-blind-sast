import os
import subprocess
import sys
from PIL import Image

_DEFAULT_OUTPUT_DIR = 'processed_images'
_SUPPORTED_FORMATS = ('jpg', 'jpeg', 'png', 'bmp')
_SUPPORTED_FILTERS = ('blur', 'sharpen', 'grayscale', 'edge')
_CONVERT_EXECUTABLE = 'convert'

_CHOICE_APPLY_FILTER = '1'
_CHOICE_LIST_PROCESSED = '2'
_CHOICE_EXIT = '3'


def _ensure_directory(path):
    if not os.path.exists(path):
        os.makedirs(path)


def _has_supported_extension(path, extensions):
    return any(path.lower().endswith(extension) for extension in extensions)


def _default_output_name(image_path, filter_type):
    base_name = os.path.splitext(os.path.basename(image_path))[0]
    return f'{base_name}_{filter_type}.png'


def _run_image_filter(image_path, filter_type, output_path):
    command = [_CONVERT_EXECUTABLE, image_path, f'-{filter_type}', output_path]
    subprocess.run(command, check=True, stderr=subprocess.PIPE)


class ImageProcessor:

    def __init__(self, output_dir=_DEFAULT_OUTPUT_DIR):
        self.output_dir = output_dir
        self.supported_formats = list(_SUPPORTED_FORMATS)
        self.supported_filters = list(_SUPPORTED_FILTERS)
        self.create_output_dir()

    def create_output_dir(self):
        _ensure_directory(self.output_dir)

    def validate_image(self, image_path):
        if not os.path.exists(image_path):
            raise ValueError('Image file does not exist')
        if not _has_supported_extension(image_path, self.supported_formats):
            raise ValueError('Unsupported image format')
        try:
            Image.open(image_path).verify()
        except:
            raise ValueError('Invalid image file')

    def apply_filter(self, image_path, filter_type, output_name=None):
        self.validate_image(image_path)
        if filter_type not in self.supported_filters:
            raise ValueError(f"Unsupported filter type. Supported filters: {', '.join(self.supported_filters)}")
        if not output_name:
            output_name = _default_output_name(image_path, filter_type)
        output_path = os.path.join(self.output_dir, output_name)
        try:
            _run_image_filter(image_path, filter_type, output_path)
            print(f'Filter applied and saved to {output_path}')
            return output_path
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f'Failed to apply filter: {e.stderr.decode().strip()}')
        except Exception as e:
            raise RuntimeError(f'Error during image processing: {str(e)}')

    def list_processed_images(self):
        return [f for f in os.listdir(self.output_dir) if _has_supported_extension(f, self.supported_formats)]


def print_menu():
    print('\nImage Processor Menu:')
    print('1. Apply filter to image')
    print('2. List processed images')
    print('3. Exit')
    print(f"Available filters: {', '.join(ImageProcessor().supported_filters)}")


def main():
    processor = ImageProcessor()
    while True:
        print_menu()
        choice = input('Enter your choice: ')
        if choice == _CHOICE_APPLY_FILTER:
            image_path = input('Enter image path: ')
            filter_type = input('Enter filter type: ')
            try:
                processor.apply_filter(image_path, filter_type)
            except Exception as e:
                print(f'Error: {e}')
        elif choice == _CHOICE_LIST_PROCESSED:
            images = processor.list_processed_images()
            print('Processed images:')
            for img in images:
                print(f'- {img}')
        elif choice == _CHOICE_EXIT:
            print('Exiting...')
            break
        else:
            print('Invalid choice. Please try again.')


if __name__ == '__main__':
    main()
