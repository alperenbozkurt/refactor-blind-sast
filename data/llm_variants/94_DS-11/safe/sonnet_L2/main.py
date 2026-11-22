import json
import sys
from functools import partial
from enum import Enum, auto

JSON_INDENT = 2
COMMAND_SEPARATOR = ' '
ARGUMENT_SEPARATOR = ','
EXIT_COMMANDS = ('exit', 'quit')
PROMPT = '> '

MSG_QUANTITY_POSITIVE = 'Quantity must be positive'
MSG_QUANTITY_NUMBER = 'Quantity must be a number'
MSG_ITEM_NOT_FOUND = 'Item not found'
MSG_INSUFFICIENT_QUANTITY = 'Insufficient quantity'
MSG_INVALID_COMMAND = 'Invalid command'


class CommandType(Enum):
    ADD = auto()
    REMOVE = auto()
    LIST = auto()
    SEARCH = auto()
    CUSTOM = auto()


class _InvalidQuantity(Exception):
    """Internal signal carrying a user-facing message for a bad quantity."""


def _parse_positive_quantity(raw_quantity):
    """Convert raw_quantity to a positive int or raise _InvalidQuantity."""
    try:
        quantity = int(raw_quantity)
    except ValueError:
        raise _InvalidQuantity(MSG_QUANTITY_NUMBER)
    if quantity <= 0:
        raise _InvalidQuantity(MSG_QUANTITY_POSITIVE)
    return quantity


def _split_command(command_str):
    """Split a raw command string into (lowercased command, argument string)."""
    parts = command_str.split(COMMAND_SEPARATOR, 1)
    if not parts:
        return None, ''
    cmd = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ''
    return cmd, args


def _split_arguments(args):
    """Split a comma separated argument string into stripped values."""
    return [arg.strip() for arg in args.split(ARGUMENT_SEPARATOR)]


class InventoryManager:

    def __init__(self):
        self.inventory = {}
        self.command_handlers = self._build_command_handlers()
        self.safe_operations = self._build_safe_operations()

    # ------------------------------------------------------------------
    # Construction helpers
    # ------------------------------------------------------------------
    def _build_command_handlers(self):
        return {
            'add': (CommandType.ADD, self.add_item),
            'remove': (CommandType.REMOVE, self.remove_item),
            'list': (CommandType.LIST, self.list_items),
            'search': (CommandType.SEARCH, self.search_items),
            'custom': (CommandType.CUSTOM, self.safe_custom_command),
        }

    def _build_safe_operations(self):
        return {
            'count': self._count_items,
            'total_items': self._total_quantity,
        }

    def _count_items(self):
        return len(self.inventory)

    def _total_quantity(self):
        return sum((item['quantity'] for item in self.inventory.values()))

    # ------------------------------------------------------------------
    # Inventory operations
    # ------------------------------------------------------------------
    def add_item(self, item_id, name, quantity):
        try:
            quantity = _parse_positive_quantity(quantity)
        except _InvalidQuantity as error:
            return str(error)
        if item_id in self.inventory:
            self.inventory[item_id]['quantity'] += quantity
        else:
            self.inventory[item_id] = {'name': name, 'quantity': quantity}
        return f'Added {quantity} of {name} (ID: {item_id})'

    def remove_item(self, item_id, quantity):
        try:
            quantity = _parse_positive_quantity(quantity)
        except _InvalidQuantity as error:
            return str(error)
        if item_id not in self.inventory:
            return MSG_ITEM_NOT_FOUND
        if self.inventory[item_id]['quantity'] < quantity:
            return MSG_INSUFFICIENT_QUANTITY
        self.inventory[item_id]['quantity'] -= quantity
        return f"Removed {quantity} of {self.inventory[item_id]['name']}"

    def list_items(self):
        return self._to_json(self.inventory)

    def search_items(self, search_term):
        term = search_term.lower()
        results = {}
        for (item_id, details) in self.inventory.items():
            if term in details['name'].lower():
                results[item_id] = details
        return self._to_json(results)

    @staticmethod
    def _to_json(data):
        return json.dumps(data, indent=JSON_INDENT)

    # ------------------------------------------------------------------
    # Custom operations
    # ------------------------------------------------------------------
    def safe_custom_command(self, operation):
        if operation not in self.safe_operations:
            return f"Unknown operation: {operation}. Available: {', '.join(self.safe_operations.keys())}"
        try:
            result = self.safe_operations[operation]()
            return f"Operation '{operation}' result: {result}"
        except Exception as e:
            return f'Error executing operation: {str(e)}'

    # ------------------------------------------------------------------
    # Command dispatch
    # ------------------------------------------------------------------
    @staticmethod
    def _invoke_handler(cmd_type, handler, args):
        if cmd_type == CommandType.CUSTOM:
            return handler(args)
        if args:
            if ARGUMENT_SEPARATOR in args:
                return handler(*_split_arguments(args))
            return handler(args)
        return handler()

    def execute_command(self, command_str):
        cmd, args = _split_command(command_str)
        if cmd is None:
            return MSG_INVALID_COMMAND
        if cmd not in self.command_handlers:
            return f"Unknown command: {cmd}. Available: {', '.join(self.command_handlers.keys())}"
        (cmd_type, handler) = self.command_handlers[cmd]
        try:
            return self._invoke_handler(cmd_type, handler, args)
        except Exception as e:
            return f'Error executing {cmd}: {str(e)}'


def _print_banner(manager):
    print('Inventory Management System')
    print('Available commands: add, remove, list, search, custom')
    print('Available custom operations: ' + ', '.join(manager.safe_operations.keys()))


def main():
    manager = InventoryManager()
    _print_banner(manager)
    while True:
        try:
            user_input = input(PROMPT).strip()
            if user_input.lower() in EXIT_COMMANDS:
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
