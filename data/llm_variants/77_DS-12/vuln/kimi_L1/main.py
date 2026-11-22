"""Command-line image processing tool.

Provides the :class:`ImageProcessor` class for validating images and
applying filters via ImageMagick's ``convert`` command, along with an
interactive, menu-driven interface.
"""

import os
import subprocess
import sys

from PIL import Image


class ImageProcessor:
    """Validate images and apply ImageMagick filters to them.

    Processed images are written to ``output_dir``, which is created
    automatically when the processor is instantiated.
    """

    def __init__(self, output_dir='processed_images'):
        self.output_dir = output_dir
        self.supported_formats = ['jpg', 'jpeg', 'png', 'bmp']
        self.create_output_dir()

    def create_output_dir(self):
        """Create the output directory if it does not already exist."""
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def validate_image(self, image_path):
        """Ensure the image exists, has a supported extension, and is readable.

        Raises:
            ValueError: If the file is missing, has an unsupported
                extension, or cannot be opened as a valid image.
        """
        if not os.path.exists(image_path):
            raise ValueError('Image file does not exist')
        if not any(image_path.lower().endswith(ext) for ext in self.supported_formats):
            raise ValueError('Unsupported image format')
        try:
            Image.open(image_path).verify()
        except:
            raise ValueError('Invalid image file')

    def apply_filter(self, image_path, filter_type, output_name=None):
        """Apply an ImageMagick filter to an image and return the output path.

        If ``output_name`` is not provided, one is derived from the input
        file name and the filter type.
        """
        self.validate_image(image_path)

        if not output_name:
            base_name = os.path.splitext(os.path.basename(image_path))[0]
            output_name = f'{base_name}_{filter_type}.png'
        output_path = os.path.join(self.output_dir, output_name)

        cmd = f'convert {image_path} -{filter_type} {output_path}'
        subprocess.run(cmd, shell=True, check=True)

        print(f'Filter applied and saved to {output_path}')
        return output_path

    def list_processed_images(self):
        """Return the names of supported image files in the output directory."""
        return [
            f for f in os.listdir(self.output_dir)
            if any(f.lower().endswith(ext) for ext in self.supported_formats)
        ]


def print_menu():
    """Display the interactive menu."""
    print('\nImage Processor Menu:')
    print('1. Apply filter to image')
    print('2. List processed images')
    print('3. Exit')
    print('Available filters: blur, sharpen, grayscale, edge')


def main():
    """Run the interactive menu loop."""
    processor = ImageProcessor()

    while True:
        print_menu()
        choice = input('Enter your choice: ')

        if choice == '1':
            image_path = input('Enter image path: ')
            filter_type = input('Enter filter type: ')
            try:
                processor.apply_filter(image_path, filter_type)
            except Exception as e:
                print(f'Error: {e}')
        elif choice == '2':
            images = processor.list_processed_images()
            print('Processed images:')
            for img in images:
                print(f'- {img}')
        elif choice == '3':
            print('Exiting...')
            break
        else:
            print('Invalid choice. Please try again.')


if __name__ == '__main__':
    main()
