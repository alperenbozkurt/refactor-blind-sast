import os
import subprocess
import sys
from PIL import Image


class ImageProcessor:

    def __init__(self, output_dir='processed_images'):
        self.output_dir = output_dir
        self.supported_formats = ['jpg', 'jpeg', 'png', 'bmp']
        self.create_output_dir()

    def create_output_dir(self):
        os.makedirs(self.output_dir, exist_ok=True)

    def _has_supported_extension(self, path):
        lowered = path.lower()
        return any(lowered.endswith(ext) for ext in self.supported_formats)

    def validate_image(self, image_path):
        if not os.path.exists(image_path):
            raise ValueError('Image file does not exist')
        if not self._has_supported_extension(image_path):
            raise ValueError('Unsupported image format')
        try:
            with Image.open(image_path) as image:
                image.verify()
        except Exception:
            raise ValueError('Invalid image file')

    def apply_filter(self, image_path, filter_type, output_name=None):
        self.validate_image(image_path)
        if not output_name:
            base_name = os.path.splitext(os.path.basename(image_path))[0]
            output_name = f'{base_name}_{filter_type}.png'
        output_path = os.path.join(self.output_dir, output_name)
        # Pass arguments as a list (no shell) to avoid shell injection.
        cmd = ['convert', image_path, f'-{filter_type}', output_path]
        subprocess.run(cmd, check=True)
        print(f'Filter applied and saved to {output_path}')
        return output_path

    def list_processed_images(self):
        return [f for f in os.listdir(self.output_dir) if self._has_supported_extension(f)]


def print_menu():
    print('\nImage Processor Menu:')
    print('1. Apply filter to image')
    print('2. List processed images')
    print('3. Exit')
    print('Available filters: blur, sharpen, grayscale, edge')


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
        if choice == '1':
            _handle_apply_filter(processor)
        elif choice == '2':
            _handle_list_images(processor)
        elif choice == '3':
            print('Exiting...')
            break
        else:
            print('Invalid choice. Please try again.')


if __name__ == '__main__':
    main()
