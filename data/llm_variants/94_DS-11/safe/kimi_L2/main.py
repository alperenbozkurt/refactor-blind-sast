"""Inventory Management System.

An interactive inventory manager supporting add/remove/list/search
commands plus a restricted set of safe, read-only "custom" operations.
"""

import json
import sys
from functools import partial
from enum import Enum, auto

# ---------------------------------------------------------------------------
# Command vocabulary
# ---------------------------------------------------------------------------

CMD_ADD = 'add'
CMD_REMOVE = 'remove'
CMD_LIST = 'list'
CMD_SEARCH = 'search'
CMD_CUSTOM = 'custom'

OP_COUNT = 'count'
OP_TOTAL_ITEMS = 'total_items'

EXIT_COMMANDS = ('exit', 'quit')

# ---------------------------------------------------------------------------
# User-facing strings
# ---------------------------------------------------------------------------

MSG_QUANTITY_POSITIVE = 'Quantity must be positive'
MSG_QUANTITY_NOT_A_NUMBER = 'Quantity must be a number'
MSG_ITEM_NOT_FOUND = 'Item not found'
MSG_INSUFFICIENT_QUANTITY = 'Insufficient quantity'
MSG_INVALID_COMMAND = 'Invalid command'
MSG_EXITING = '\nExiting...'

BANNER_TITLE = 'Inventory Management System'
BANNER_COMMANDS = 'Available commands: ' + ', '.join(
    (CMD_ADD, CMD_REMOVE, CMD_LIST, CMD_SEARCH, CMD_CUSTOM)
)
BANNER_CUSTOM_OPS_PREFIX = 'Available custom operations: '
PROMPT = '> '

JSON_INDENT = 2


class CommandType(Enum):
    ADD = auto()
    REMOVE = auto()
    LIST = auto()
    SEARCH = auto()
    CUSTOM = auto()


def _format_available(names):
    """Join command/operation names for display in error messages."""
    return ', '.join(names)


class InventoryManager:
    """Holds the inventory and dispatches text commands to handlers."""

    def __init__(self):
        self.inventory = {}
        self.command_handlers = self._build_command_handlers()
        self.safe_operations = self._build_safe_operations()

    # -- internal construction helpers -------------------------------------

    def _build_command_handlers(self):
        return {
            CMD_ADD: (CommandType.ADD, self.add_item),
            CMD_REMOVE: (CommandType.REMOVE, self.remove_item),
            CMD_LIST: (CommandType.LIST, self.list_items),
            CMD_SEARCH: (CommandType.SEARCH, self.search_items),
            CMD_CUSTOM: (CommandType.CUSTOM, self.safe_custom_command),
        }

    def _build_safe_operations(self):
        return {
            OP_COUNT: lambda: len(self.inventory),
            OP_TOTAL_ITEMS: lambda: sum(
                item['quantity'] for item in self.inventory.values()
            ),
        }

    # -- shared validation helpers ------------------------------------------

    @staticmethod
    def _parse_quantity(quantity):
        """Convert *quantity* to a positive int.

        Returns a ``(value, error)`` pair; exactly one element is ``None``.
        """
        try:
            value = int(quantity)
        except ValueError:
            return None, MSG_QUANTITY_NOT_A_NUMBER
        if value <= 0:
            return None, MSG_QUANTITY_POSITIVE
        return value, None

    # -- command handlers ----------------------------------------------------

    def add_item(self, item_id, name, quantity):
        quantity, error = self._parse_quantity(quantity)
        if error is not None:
            return error
        if item_id in self.inventory:
            self.inventory[item_id]['quantity'] += quantity
        else:
            self.inventory[item_id] = {'name': name, 'quantity': quantity}
        return f'Added {quantity} of {name} (ID: {item_id})'

    def remove_item(self, item_id, quantity):
        quantity, error = self._parse_quantity(quantity)
        if error is not None:
            return error
        if item_id not in self.inventory:
            return MSG_ITEM_NOT_FOUND
        if self.inventory[item_id]['quantity'] < quantity:
            return MSG_INSUFFICIENT_QUANTITY
        self.inventory[item_id]['quantity'] -= quantity
        return f"Removed {quantity} of {self.inventory[item_id]['name']}"

    def list_items(self):
        return json.dumps(self.inventory, indent=JSON_INDENT)

    def search_items(self, search_term):
        needle = search_term.lower()
        results = {
            item_id: details
            for item_id, details in self.inventory.items()
            if needle in details['name'].lower()
        }
        return json.dumps(results, indent=JSON_INDENT)

    def safe_custom_command(self, operation):
        if operation not in self.safe_operations:
            available = _format_available(self.safe_operations)
            return f'Unknown operation: {operation}. Available: {available}'
        try:
            result = self.safe_operations[operation]()
            return f"Operation '{operation}' result: {result}"
        except Exception as e:
            return f'Error executing operation: {str(e)}'

    # -- command dispatch ----------------------------------------------------

    def execute_command(self, command_str):
        cmd, args = self._parse_command_line(command_str)
        if cmd is None:
            return MSG_INVALID_COMMAND
        if cmd not in self.command_handlers:
            available = _format_available(self.command_handlers)
            return f'Unknown command: {cmd}. Available: {available}'
        cmd_type, handler = self.command_handlers[cmd]
        try:
            return self._invoke_handler(cmd_type, handler, args)
        except Exception as e:
            return f'Error executing {cmd}: {str(e)}'

    @staticmethod
    def _parse_command_line(command_str):
        """Split *command_str* into a lower-cased command and raw args."""
        parts = command_str.split(' ', 1)
        if not parts:
            return None, ''
        args = parts[1] if len(parts) > 1 else ''
        return parts[0].lower(), args

    @staticmethod
    def _split_args(args):
        return [arg.strip() for arg in args.split(',')]

    def _invoke_handler(self, cmd_type, handler, args):
        if cmd_type == CommandType.CUSTOM:
            return handler(args)
        if args:
            if ',' in args:
                return handler(*self._split_args(args))
            return handler(args)
        return handler()


def _print_banner(manager):
    print(BANNER_TITLE)
    print(BANNER_COMMANDS)
    print(BANNER_CUSTOM_OPS_PREFIX + ', '.join(manager.safe_operations.keys()))


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
            print(MSG_EXITING)
            break
        except Exception as e:
            print(f'Error: {str(e)}')


if __name__ == '__main__':
    main()
