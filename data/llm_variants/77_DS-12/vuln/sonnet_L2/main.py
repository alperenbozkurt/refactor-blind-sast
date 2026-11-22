import os
import subprocess
import sys
from PIL import Image

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #
DEFAULT_OUTPUT_DIR = 'processed_images'
DEFAULT_SUPPORTED_FORMATS = ('jpg', 'jpeg', 'png', 'bmp')
OUTPUT_EXTENSION = 'png'

AVAILABLE_FILTERS_TEXT = 'Available filters: blur, sharpen, grayscale, edge'

CHOICE_APPLY_FILTER = '1'
CHOICE_LIST_IMAGES = '2'
CHOICE_EXIT = '3'

MENU_LINES = (
    '\nImage Processor Menu:',
    '1. Apply filter to image',
    '2. List processed images',
    '3. Exit',
    AVAILABLE_FILTERS_TEXT,
)

PROMPT_CHOICE = 'Enter your choice: '
PROMPT_IMAGE_PATH = 'Enter image path: '
PROMPT_FILTER_TYPE = 'Enter filter type: '

ERR_NOT_FOUND = 'Image file does not exist'
ERR_UNSUPPORTED = 'Unsupported image format'
ERR_INVALID = 'Invalid image file'


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _has_supported_extension(file_name, supported_formats):
    """Return True if file_name ends with one of the supported extensions."""
    lowered = file_name.lower()
    return any((lowered.endswith(ext) for ext in supported_formats))


def _default_output_name(image_path, filter_type):
    """Build the default output file name for a filtered image."""
    base_name = os.path.splitext(os.path.basename(image_path))[0]
    return f'{base_name}_{filter_type}.{OUTPUT_EXTENSION}'


def _build_convert_command(image_path, filter_type, output_path):
    """Build the ImageMagick command line (kept identical to the original)."""
    return f'convert {image_path} -{filter_type} {output_path}'


# --------------------------------------------------------------------------- #
# Core class
# --------------------------------------------------------------------------- #
class ImageProcessor:

    def __init__(self, output_dir=DEFAULT_OUTPUT_DIR):
        self.output_dir = output_dir
        self.supported_formats = list(DEFAULT_SUPPORTED_FORMATS)
        self.create_output_dir()

    def create_output_dir(self):
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def _has_supported_format(self, file_name):
        return _has_supported_extension(file_name, self.supported_formats)

    def validate_image(self, image_path):
        if not os.path.exists(image_path):
            raise ValueError(ERR_NOT_FOUND)
        if not self._has_supported_format(image_path):
            raise ValueError(ERR_UNSUPPORTED)
        try:
            Image.open(image_path).verify()
        except:
            raise ValueError(ERR_INVALID)

    def apply_filter(self, image_path, filter_type, output_name=None):
        self.validate_image(image_path)
        if not output_name:
            output_name = _default_output_name(image_path, filter_type)
        output_path = os.path.join(self.output_dir, output_name)
        cmd = _build_convert_command(image_path, filter_type, output_path)
        subprocess.run(cmd, shell=True, check=True)
        print(f'Filter applied and saved to {output_path}')
        return output_path

    def list_processed_images(self):
        return [f for f in os.listdir(self.output_dir) if self._has_supported_format(f)]


# --------------------------------------------------------------------------- #
# Command-line interface
# --------------------------------------------------------------------------- #
def print_menu():
    for line in MENU_LINES:
        print(line)


def _handle_apply_filter(processor):
    image_path = input(PROMPT_IMAGE_PATH)
    filter_type = input(PROMPT_FILTER_TYPE)
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
        choice = input(PROMPT_CHOICE)
        if choice == CHOICE_APPLY_FILTER:
            _handle_apply_filter(processor)
        elif choice == CHOICE_LIST_IMAGES:
            _handle_list_images(processor)
        elif choice == CHOICE_EXIT:
            print('Exiting...')
            break
        else:
            print('Invalid choice. Please try again.')


if __name__ == '__main__':
    main()
