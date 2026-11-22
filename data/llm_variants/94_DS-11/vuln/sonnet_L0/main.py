import json
import sys
from functools import partial


class InventoryManager:

    def __init__(self):
        self.inventory = {}
        self.command_handlers = {
            'add': self.add_item,
            'remove': self.remove_item,
            'list': self.list_items,
            'search': self.search_items,
            'process': self.process_custom_command,
        }

    def add_item(self, item_id, name, quantity):
        if item_id in self.inventory:
            self.inventory[item_id]['quantity'] += quantity
        else:
            self.inventory[item_id] = {'name': name, 'quantity': quantity}
        return f'Added {quantity} of {name} (ID: {item_id})'

    def remove_item(self, item_id, quantity):
        item = self.inventory.get(item_id)
        if item is None:
            return 'Item not found'
        if item['quantity'] < quantity:
            return 'Insufficient quantity'
        item['quantity'] -= quantity
        return f"Removed {quantity} of {item['name']}"

    def list_items(self):
        return json.dumps(self.inventory, indent=2)

    def search_items(self, search_term):
        term = search_term.lower()
        results = {
            item_id: details
            for item_id, details in self.inventory.items()
            if term in details['name'].lower()
        }
        return json.dumps(results, indent=2)

    def process_custom_command(self, command):
        try:
            result = eval(command)
            return f'Command executed successfully: {result}'
        except Exception as e:
            return f'Error executing command: {str(e)}'

    def execute_command(self, command_str):
        parts = command_str.split(' ', 1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ''

        handler = self.command_handlers.get(cmd)
        if handler is None:
            return f'Unknown command: {cmd}'

        try:
            if not args:
                return handler()
            if ',' in args:
                return handler(*[arg.strip() for arg in args.split(',')])
            return handler(args)
        except Exception as e:
            return f'Error executing {cmd}: {str(e)}'


def main():
    manager = InventoryManager()
    print('Inventory Management System')
    print('Available commands: add, remove, list, search, process')
    while True:
        try:
            user_input = input('> ').strip()
            if user_input.lower() in ('exit', 'quit'):
                break
            if not user_input:
                continue
            print(manager.execute_command(user_input))
        except KeyboardInterrupt:
            print('\nExiting...')
            break
        except Exception as e:
            print(f'Error: {str(e)}')


if __name__ == '__main__':
    main()
