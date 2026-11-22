"""Command-line inventory management system."""

import json
import sys
from functools import partial


class InventoryManager:
    """Manage an in-memory inventory and dispatch text-based commands."""

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
        """Add ``quantity`` units of an item, creating it if necessary."""
        if item_id in self.inventory:
            self.inventory[item_id]['quantity'] += quantity
        else:
            self.inventory[item_id] = {'name': name, 'quantity': quantity}
        return f'Added {quantity} of {name} (ID: {item_id})'

    def remove_item(self, item_id, quantity):
        """Remove ``quantity`` units of an item from the inventory."""
        if item_id not in self.inventory:
            return 'Item not found'
        if self.inventory[item_id]['quantity'] < quantity:
            return 'Insufficient quantity'
        self.inventory[item_id]['quantity'] -= quantity
        return f"Removed {quantity} of {self.inventory[item_id]['name']}"

    def list_items(self):
        """Return the full inventory as a pretty-printed JSON string."""
        return json.dumps(self.inventory, indent=2)

    def search_items(self, search_term):
        """Return, as JSON, the items whose name contains ``search_term``."""
        results = {
            item_id: details
            for item_id, details in self.inventory.items()
            if search_term.lower() in details['name'].lower()
        }
        return json.dumps(results, indent=2)

    def process_custom_command(self, command):
        """Execute a custom command and report its result."""
        try:
            result = eval(command)
            return f'Command executed successfully: {result}'
        except Exception as e:
            return f'Error executing command: {str(e)}'

    def execute_command(self, command_str):
        """Parse and run a text command, returning a response message."""
        parts = command_str.split(' ', 1)
        if not parts:
            return 'Invalid command'

        command = parts[0].lower()
        if command not in self.command_handlers:
            return f'Unknown command: {command}'

        args = parts[1] if len(parts) > 1 else ''
        handler = self.command_handlers[command]

        try:
            if not args:
                return handler()
            if isinstance(args, str) and ',' in args:
                arguments = [arg.strip() for arg in args.split(',')]
                return handler(*arguments)
            return handler(args)
        except Exception as e:
            return f'Error executing {command}: {str(e)}'


def main():
    """Run the interactive command-line interface."""
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
