import json
import sys
from functools import partial

_JSON_INDENT = 2
_COMMAND_SEPARATOR = ' '
_ARGUMENT_SEPARATOR = ','
_NAME_KEY = 'name'
_QUANTITY_KEY = 'quantity'

_INVALID_COMMAND_MESSAGE = 'Invalid command'
_ITEM_NOT_FOUND_MESSAGE = 'Item not found'
_INSUFFICIENT_QUANTITY_MESSAGE = 'Insufficient quantity'
_PROCESS_SUCCESS_PREFIX = 'Command executed successfully: '
_PROCESS_ERROR_PREFIX = 'Error executing command: '


class _ConsoleConfig:
    PROMPT = '> '
    BANNER = 'Inventory Management System'
    COMMANDS_HINT = 'Available commands: add, remove, list, search, process'
    EXIT_COMMANDS = ('exit', 'quit')
    INTERRUPT_MESSAGE = '\nExiting...'
    ERROR_PREFIX = 'Error: '


_CONSOLE_CONFIG = _ConsoleConfig()


def _serialize_inventory(data):
    return json.dumps(data, indent=_JSON_INDENT)


class InventoryManager:

    def __init__(self):
        self.inventory = {}
        self.command_handlers = {'add': self.add_item, 'remove': self.remove_item, 'list': self.list_items, 'search': self.search_items, 'process': self.process_custom_command}

    @staticmethod
    def _parse_command(command_str):
        parts = command_str.split(_COMMAND_SEPARATOR, 1)
        if not parts:
            return None
        return parts[0].lower(), parts[1] if len(parts) > 1 else ''

    @staticmethod
    def _has_multiple_arguments(args):
        return isinstance(args, str) and _ARGUMENT_SEPARATOR in args

    @staticmethod
    def _split_arguments(args):
        return [arg.strip() for arg in args.split(_ARGUMENT_SEPARATOR)]

    @staticmethod
    def _matches_search_term(details, search_term):
        return search_term.lower() in details[_NAME_KEY].lower()

    def add_item(self, item_id, name, quantity):
        if item_id in self.inventory:
            self.inventory[item_id][_QUANTITY_KEY] += quantity
        else:
            self.inventory[item_id] = {_NAME_KEY: name, _QUANTITY_KEY: quantity}
        return f'Added {quantity} of {name} (ID: {item_id})'

    def remove_item(self, item_id, quantity):
        if item_id not in self.inventory:
            return _ITEM_NOT_FOUND_MESSAGE
        if self.inventory[item_id][_QUANTITY_KEY] < quantity:
            return _INSUFFICIENT_QUANTITY_MESSAGE
        self.inventory[item_id][_QUANTITY_KEY] -= quantity
        return f"Removed {quantity} of {self.inventory[item_id][_NAME_KEY]}"

    def list_items(self):
        return _serialize_inventory(self.inventory)

    def search_items(self, search_term):
        results = {item_id: details for (item_id, details) in self.inventory.items() if self._matches_search_term(details, search_term)}
        return _serialize_inventory(results)

    def process_custom_command(self, command):
        try:
            result = eval(command)
            return f'{_PROCESS_SUCCESS_PREFIX}{result}'
        except Exception as e:
            return f'{_PROCESS_ERROR_PREFIX}{str(e)}'

    def execute_command(self, command_str):
        parsed_command = self._parse_command(command_str)
        if parsed_command is None:
            return _INVALID_COMMAND_MESSAGE
        (cmd, args) = parsed_command
        if cmd not in self.command_handlers:
            return f'Unknown command: {cmd}'
        handler = self.command_handlers[cmd]
        try:
            if args:
                if self._has_multiple_arguments(args):
                    return handler(*self._split_arguments(args))
                return handler(args)
            return handler()
        except Exception as e:
            return f'Error executing {cmd}: {str(e)}'


def main():
    manager = InventoryManager()
    print(_CONSOLE_CONFIG.BANNER)
    print(_CONSOLE_CONFIG.COMMANDS_HINT)
    while True:
        try:
            user_input = input(_CONSOLE_CONFIG.PROMPT).strip()
            if user_input.lower() in _CONSOLE_CONFIG.EXIT_COMMANDS:
                break
            if not user_input:
                continue
            response = manager.execute_command(user_input)
            print(response)
        except KeyboardInterrupt:
            print(_CONSOLE_CONFIG.INTERRUPT_MESSAGE)
            break
        except Exception as e:
            print(f'{_CONSOLE_CONFIG.ERROR_PREFIX}{str(e)}')


if __name__ == '__main__':
    main()
