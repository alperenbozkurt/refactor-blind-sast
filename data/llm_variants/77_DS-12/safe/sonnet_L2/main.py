import os
import subprocess
import sys
from PIL import Image

DEFAULT_OUTPUT_DIR = 'processed_images'
SUPPORTED_FORMATS = ('jpg', 'jpeg', 'png', 'bmp')
SUPPORTED_FILTERS = ('blur', 'sharpen', 'grayscale', 'edge')
OUTPUT_EXTENSION = 'png'
CONVERT_COMMAND = 'convert'

MENU_APPLY_FILTER = '1'
MENU_LIST_IMAGES = '2'
MENU_EXIT = '3'


def _has_supported_extension(file_name, formats):
    """Return True if the file name ends with one of the given extensions."""
    lowered = file_name.lower()
    return any(lowered.endswith(ext) for ext in formats)


def _default_output_name(image_path, filter_type):
    base_name = os.path.splitext(os.path.basename(image_path))[0]
    return f'{base_name}_{filter_type}.{OUTPUT_EXTENSION}'


def _build_convert_command(image_path, filter_type, output_path):
    return [CONVERT_COMMAND, image_path, f'-{filter_type}', output_path]


class ImageProcessor:

    def __init__(self, output_dir=DEFAULT_OUTPUT_DIR):
        self.output_dir = output_dir
        self.supported_formats = list(SUPPORTED_FORMATS)
        self.supported_filters = list(SUPPORTED_FILTERS)
        self.create_output_dir()

    def create_output_dir(self):
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def validate_image(self, image_path):
        if not os.path.exists(image_path):
            raise ValueError('Image file does not exist')
        if not _has_supported_extension(image_path, self.supported_formats):
            raise ValueError('Unsupported image format')
        try:
            Image.open(image_path).verify()
        except:
            raise ValueError('Invalid image file')

    def _validate_filter(self, filter_type):
        if filter_type not in self.supported_filters:
            raise ValueError(
                f"Unsupported filter type. Supported filters: {', '.join(self.supported_filters)}"
            )

    def _run_convert(self, image_path, filter_type, output_path):
        subprocess.run(
            _build_convert_command(image_path, filter_type, output_path),
            check=True,
            stderr=subprocess.PIPE,
        )

    def apply_filter(self, image_path, filter_type, output_name=None):
        self.validate_image(image_path)
        self._validate_filter(filter_type)
        if not output_name:
            output_name = _default_output_name(image_path, filter_type)
        output_path = os.path.join(self.output_dir, output_name)
        try:
            self._run_convert(image_path, filter_type, output_path)
            print(f'Filter applied and saved to {output_path}')
            return output_path
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f'Failed to apply filter: {e.stderr.decode().strip()}')
        except Exception as e:
            raise RuntimeError(f'Error during image processing: {str(e)}')

    def list_processed_images(self):
        return [
            f for f in os.listdir(self.output_dir)
            if _has_supported_extension(f, self.supported_formats)
        ]


def print_menu():
    print('\nImage Processor Menu:')
    print('1. Apply filter to image')
    print('2. List processed images')
    print('3. Exit')
    print(f"Available filters: {', '.join(ImageProcessor().supported_filters)}")


def _handle_apply_filter(processor):
    image_path = input('Enter image path: ')
    filter_type = input('Enter filter type: ')
    try:
        processor.apply_filter(image_path, filter_type)
    except Exception as e:
        print(f'Error: {e}')


def _handle_list_images(processor):
    images = processor.list_processed_images()
    print('Processed images:')
    for img in images:
        print(f'- {img}')


def main():
    processor = ImageProcessor()
    while True:
        print_menu()
        choice = input('Enter your choice: ')
        if choice == MENU_APPLY_FILTER:
            _handle_apply_filter(processor)
        elif choice == MENU_LIST_IMAGES:
            _handle_list_images(processor)
        elif choice == MENU_EXIT:
            print('Exiting...')
            break
        else:
            print('Invalid choice. Please try again.')


if __name__ == '__main__':
    main()
