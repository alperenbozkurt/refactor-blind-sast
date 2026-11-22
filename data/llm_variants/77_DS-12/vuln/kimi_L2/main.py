"""Interactive command-line tool for applying ImageMagick filters to images."""

import os
import subprocess

from PIL import Image

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_OUTPUT_DIR = 'processed_images'
SUPPORTED_FORMATS = ['jpg', 'jpeg', 'png', 'bmp']
AVAILABLE_FILTERS = ['blur', 'sharpen', 'grayscale', 'edge']

CONVERT_COMMAND_TEMPLATE = 'convert {image_path} -{filter_type} {output_path}'

CHOICE_APPLY_FILTER = '1'
CHOICE_LIST_IMAGES = '2'
CHOICE_EXIT = '3'

PROMPT_CHOICE = 'Enter your choice: '
PROMPT_IMAGE_PATH = 'Enter image path: '
PROMPT_FILTER_TYPE = 'Enter filter type: '


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _has_supported_extension(filename, extensions):
    """Return True if *filename* ends with one of *extensions* (case-insensitive)."""
    return any(filename.lower().endswith(ext) for ext in extensions)


def _default_output_name(image_path, filter_type):
    """Build the default output file name for a filtered image."""
    base_name = os.path.splitext(os.path.basename(image_path))[0]
    return f'{base_name}_{filter_type}.png'


def _build_convert_command(image_path, filter_type, output_path):
    """Build the ImageMagick command used to apply a filter."""
    return CONVERT_COMMAND_TEMPLATE.format(
        image_path=image_path,
        filter_type=filter_type,
        output_path=output_path,
    )


# ---------------------------------------------------------------------------
# Core processing
# ---------------------------------------------------------------------------

class ImageProcessor:
    """Validate images, apply filters via ImageMagick and track processed files."""

    def __init__(self, output_dir=DEFAULT_OUTPUT_DIR):
        self.output_dir = output_dir
        self.supported_formats = list(SUPPORTED_FORMATS)
        self.create_output_dir()

    def create_output_dir(self):
        """Create the output directory if it does not exist yet."""
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def validate_image(self, image_path):
        """Raise ValueError unless *image_path* is a readable, supported image."""
        if not os.path.exists(image_path):
            raise ValueError('Image file does not exist')
        if not _has_supported_extension(image_path, self.supported_formats):
            raise ValueError('Unsupported image format')
        try:
            Image.open(image_path).verify()
        except Exception:
            raise ValueError('Invalid image file')

    def apply_filter(self, image_path, filter_type, output_name=None):
        """Apply *filter_type* to *image_path* and save it in the output directory."""
        self.validate_image(image_path)
        if not output_name:
            output_name = _default_output_name(image_path, filter_type)
        output_path = os.path.join(self.output_dir, output_name)
        cmd = _build_convert_command(image_path, filter_type, output_path)
        subprocess.run(cmd, shell=True, check=True)
        print(f'Filter applied and saved to {output_path}')
        return output_path

    def list_processed_images(self):
        """Return the names of supported image files in the output directory."""
        return [
            name
            for name in os.listdir(self.output_dir)
            if _has_supported_extension(name, self.supported_formats)
        ]


# ---------------------------------------------------------------------------
# Command-line interface
# ---------------------------------------------------------------------------

def print_menu():
    """Print the main menu."""
    print('\nImage Processor Menu:')
    print(f'{CHOICE_APPLY_FILTER}. Apply filter to image')
    print(f'{CHOICE_LIST_IMAGES}. List processed images')
    print(f'{CHOICE_EXIT}. Exit')
    print(f'Available filters: {", ".join(AVAILABLE_FILTERS)}')


def _apply_filter_interactive(processor):
    """Prompt for input and apply a filter, reporting any error."""
    image_path = input(PROMPT_IMAGE_PATH)
    filter_type = input(PROMPT_FILTER_TYPE)
    try:
        processor.apply_filter(image_path, filter_type)
    except Exception as e:
        print(f'Error: {e}')


def _list_images_interactive(processor):
    """Print all currently processed images."""
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
            _apply_filter_interactive(processor)
        elif choice == CHOICE_LIST_IMAGES:
            _list_images_interactive(processor)
        elif choice == CHOICE_EXIT:
            print('Exiting...')
            break
        else:
            print('Invalid choice. Please try again.')


if __name__ == '__main__':
    main()
