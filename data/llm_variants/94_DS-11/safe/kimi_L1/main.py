"""Inventory management system with an interactive command-line interface."""

import json
import sys
from enum import Enum, auto
from functools import partial


class CommandType(Enum):
    """Supported command categories used for dispatching user input."""

    ADD = auto()
    REMOVE = auto()
    LIST = auto()
    SEARCH = auto()
    CUSTOM = auto()


class InventoryManager:
    """In-memory inventory store with text-based command dispatch."""

    def __init__(self):
        self.inventory = {}
        self.command_handlers = {
            'add': (CommandType.ADD, self.add_item),
            'remove': (CommandType.REMOVE, self.remove_item),
            'list': (CommandType.LIST, self.list_items),
            'search': (CommandType.SEARCH, self.search_items),
            'custom': (CommandType.CUSTOM, self.safe_custom_command),
        }
        self.safe_operations = {
            'count': lambda: len(self.inventory),
            'total_items': lambda: sum(
                item['quantity'] for item in self.inventory.values()
            ),
        }

    def add_item(self, item_id, name, quantity):
        """Add ``quantity`` units of an item, creating it if necessary."""
        quantity, error = self._parse_quantity(quantity)
        if error is not None:
            return error
        if item_id in self.inventory:
            self.inventory[item_id]['quantity'] += quantity
        else:
            self.inventory[item_id] = {'name': name, 'quantity': quantity}
        return f'Added {quantity} of {name} (ID: {item_id})'

    def remove_item(self, item_id, quantity):
        """Remove ``quantity`` units of an existing item."""
        quantity, error = self._parse_quantity(quantity)
        if error is not None:
            return error
        if item_id not in self.inventory:
            return 'Item not found'
        if self.inventory[item_id]['quantity'] < quantity:
            return 'Insufficient quantity'
        self.inventory[item_id]['quantity'] -= quantity
        return f"Removed {quantity} of {self.inventory[item_id]['name']}"

    def list_items(self):
        """Return the full inventory as a formatted JSON string."""
        return json.dumps(self.inventory, indent=2)

    def search_items(self, search_term):
        """Return items whose name contains ``search_term`` as JSON."""
        results = {
            item_id: details
            for item_id, details in self.inventory.items()
            if search_term.lower() in details['name'].lower()
        }
        return json.dumps(results, indent=2)

    def safe_custom_command(self, operation):
        """Run a whitelisted read-only operation by name."""
        if operation not in self.safe_operations:
            available = ', '.join(self.safe_operations.keys())
            return f'Unknown operation: {operation}. Available: {available}'
        try:
            result = self.safe_operations[operation]()
            return f"Operation '{operation}' result: {result}"
        except Exception as e:
            return f'Error executing operation: {str(e)}'

    def execute_command(self, command_str):
        """Parse and execute a raw command line, returning a message."""
        parts = command_str.split(' ', 1)
        if not parts:
            return 'Invalid command'
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ''
        if cmd not in self.command_handlers:
            available = ', '.join(self.command_handlers.keys())
            return f'Unknown command: {cmd}. Available: {available}'
        cmd_type, handler = self.command_handlers[cmd]
        return self._invoke_handler(cmd, cmd_type, handler, args)

    @staticmethod
    def _parse_quantity(quantity):
        """Return ``(value, None)`` on success, else ``(None, message)``."""
        try:
            value = int(quantity)
        except ValueError:
            return None, 'Quantity must be a number'
        if value <= 0:
            return None, 'Quantity must be positive'
        return value, None

    def _invoke_handler(self, cmd, cmd_type, handler, args):
        """Call ``handler`` with arguments derived from ``args``."""
        try:
            if cmd_type == CommandType.CUSTOM:
                return handler(args)
            if not args:
                return handler()
            if ',' in args:
                return handler(*[arg.strip() for arg in args.split(',')])
            return handler(args)
        except Exception as e:
            return f'Error executing {cmd}: {str(e)}'


def main():
    """Run the interactive read-eval-print loop."""
    manager = InventoryManager()
    print('Inventory Management System')
    print('Available commands: add, remove, list, search, custom')
    print(
        'Available custom operations: '
        + ', '.join(manager.safe_operations.keys())
    )
    while True:
        try:
            user_input = input('> ').strip()
            if user_input.lower() in ['exit', 'quit']:
                break
            if not user_input:
                continue
            response = manager.execute_command(user_input)
            print(response)
        except KeyboardInterrupt:
            print('\nExiting...')
            break
        except Exception as e:
            print(f'Error: {str(e)}')


if __name__ == '__main__':
    main()
