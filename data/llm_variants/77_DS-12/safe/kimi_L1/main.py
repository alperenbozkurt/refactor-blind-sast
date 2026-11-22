"""Interactive command-line tool for applying filters to images.

Filters are applied with ImageMagick's ``convert`` command and the
results are stored in a dedicated output directory.
"""

import os
import subprocess
import sys

from PIL import Image


class ImageProcessor:
    """Validate images, apply filters and list processed results."""

    def __init__(self, output_dir='processed_images'):
        self.output_dir = output_dir
        self.supported_formats = ['jpg', 'jpeg', 'png', 'bmp']
        self.supported_filters = ['blur', 'sharpen', 'grayscale', 'edge']
        self.create_output_dir()

    def create_output_dir(self):
        """Create the output directory if it does not exist yet."""
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def _is_supported_image(self, filename):
        """Return True if *filename* ends with a supported extension."""
        return any(
            filename.lower().endswith(extension)
            for extension in self.supported_formats
        )

    def validate_image(self, image_path):
        """Check that *image_path* exists, is supported and is valid."""
        if not os.path.exists(image_path):
            raise ValueError('Image file does not exist')
        if not self._is_supported_image(image_path):
            raise ValueError('Unsupported image format')
        try:
            Image.open(image_path).verify()
        except:
            raise ValueError('Invalid image file')

    def apply_filter(self, image_path, filter_type, output_name=None):
        """Apply *filter_type* to *image_path* and return the output path."""
        self.validate_image(image_path)
        if filter_type not in self.supported_filters:
            raise ValueError(
                'Unsupported filter type. Supported filters: '
                f"{', '.join(self.supported_filters)}"
            )
        if not output_name:
            base_name = os.path.splitext(os.path.basename(image_path))[0]
            output_name = f'{base_name}_{filter_type}.png'
        output_path = os.path.join(self.output_dir, output_name)
        try:
            subprocess.run(
                ['convert', image_path, f'-{filter_type}', output_path],
                check=True,
                stderr=subprocess.PIPE,
            )
            print(f'Filter applied and saved to {output_path}')
            return output_path
        except subprocess.CalledProcessError as error:
            raise RuntimeError(
                f'Failed to apply filter: {error.stderr.decode().strip()}'
            )
        except Exception as error:
            raise RuntimeError(f'Error during image processing: {str(error)}')

    def list_processed_images(self):
        """Return the supported image files found in the output directory."""
        return [
            filename
            for filename in os.listdir(self.output_dir)
            if self._is_supported_image(filename)
        ]


def print_menu():
    """Display the menu options and the available filters."""
    print('\nImage Processor Menu:')
    print('1. Apply filter to image')
    print('2. List processed images')
    print('3. Exit')
    print(f"Available filters: {', '.join(ImageProcessor().supported_filters)}")


def main():
    """Run the interactive image processor menu loop."""
    processor = ImageProcessor()
    while True:
        print_menu()
        choice = input('Enter your choice: ')
        if choice == '1':
            image_path = input('Enter image path: ')
            filter_type = input('Enter filter type: ')
            try:
                processor.apply_filter(image_path, filter_type)
            except Exception as error:
                print(f'Error: {error}')
        elif choice == '2':
            images = processor.list_processed_images()
            print('Processed images:')
            for image in images:
                print(f'- {image}')
        elif choice == '3':
            print('Exiting...')
            break
        else:
            print('Invalid choice. Please try again.')


if __name__ == '__main__':
    main()
