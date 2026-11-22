import json
import sys
from functools import partial
from enum import Enum, auto


class CommandType(Enum):
    ADD = auto()
    REMOVE = auto()
    LIST = auto()
    SEARCH = auto()
    CUSTOM = auto()


class InventoryManager:
    ERR_NOT_POSITIVE = 'Quantity must be positive'
    ERR_NOT_NUMBER = 'Quantity must be a number'

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
            'total_items': lambda: sum(item['quantity'] for item in self.inventory.values()),
        }

    def _parse_quantity(self, quantity):
        """Return (quantity, error_message); error_message is None on success."""
        try:
            quantity = int(quantity)
        except ValueError:
            return None, self.ERR_NOT_NUMBER
        if quantity <= 0:
            return None, self.ERR_NOT_POSITIVE
        return quantity, None

    def add_item(self, item_id, name, quantity):
        quantity, error = self._parse_quantity(quantity)
        if error:
            return error
        if item_id in self.inventory:
            self.inventory[item_id]['quantity'] += quantity
        else:
            self.inventory[item_id] = {'name': name, 'quantity': quantity}
        return f'Added {quantity} of {name} (ID: {item_id})'

    def remove_item(self, item_id, quantity):
        quantity, error = self._parse_quantity(quantity)
        if error:
            return error
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

    def safe_custom_command(self, operation):
        if operation not in self.safe_operations:
            available = ', '.join(self.safe_operations.keys())
            return f"Unknown operation: {operation}. Available: {available}"
        try:
            result = self.safe_operations[operation]()
            return f"Operation '{operation}' result: {result}"
        except Exception as e:
            return f'Error executing operation: {str(e)}'

    def execute_command(self, command_str):
        parts = command_str.split(' ', 1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ''
        if cmd not in self.command_handlers:
            available = ', '.join(self.command_handlers.keys())
            return f"Unknown command: {cmd}. Available: {available}"
        cmd_type, handler = self.command_handlers[cmd]
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
    manager = InventoryManager()
    print('Inventory Management System')
    print('Available commands: add, remove, list, search, custom')
    print('Available custom operations: ' + ', '.join(manager.safe_operations.keys()))
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
