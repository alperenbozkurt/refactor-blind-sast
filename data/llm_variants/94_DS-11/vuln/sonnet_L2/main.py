import json
import sys
from functools import partial

# --- Constants ---------------------------------------------------------------

JSON_INDENT = 2
COMMAND_SEPARATOR = ' '
ARGUMENT_SEPARATOR = ','
EXIT_COMMANDS = ('exit', 'quit')
PROMPT = '> '

BANNER_TITLE = 'Inventory Management System'
BANNER_COMMANDS = 'Available commands: add, remove, list, search, process'

MSG_ITEM_NOT_FOUND = 'Item not found'
MSG_INSUFFICIENT_QUANTITY = 'Insufficient quantity'
MSG_INVALID_COMMAND = 'Invalid command'
MSG_EXITING = '\nExiting...'


# --- Helper functions --------------------------------------------------------

def _to_json(data):
    """Serialize data using the module's standard JSON formatting."""
    return json.dumps(data, indent=JSON_INDENT)


def _split_command(command_str):
    """Split a raw command string into (command, argument string)."""
    parts = command_str.split(COMMAND_SEPARATOR, 1)
    if not parts:
        return None, ''
    cmd = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ''
    return cmd, args


def _parse_arguments(args):
    """Turn a raw argument string into a list of positional arguments."""
    if isinstance(args, str) and ARGUMENT_SEPARATOR in args:
        return [arg.strip() for arg in args.split(ARGUMENT_SEPARATOR)]
    return [args]


def _is_exit_command(user_input):
    return user_input.lower() in EXIT_COMMANDS


# --- Core class --------------------------------------------------------------

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
        if item_id not in self.inventory:
            return MSG_ITEM_NOT_FOUND
        if self.inventory[item_id]['quantity'] < quantity:
            return MSG_INSUFFICIENT_QUANTITY
        self.inventory[item_id]['quantity'] -= quantity
        return f"Removed {quantity} of {self.inventory[item_id]['name']}"

    def list_items(self):
        return _to_json(self.inventory)

    def search_items(self, search_term):
        term = search_term.lower()
        results = {}
        for item_id, details in self.inventory.items():
            if term in details['name'].lower():
                results[item_id] = details
        return _to_json(results)

    def process_custom_command(self, command):
        try:
            result = eval(command)
            return f'Command executed successfully: {result}'
        except Exception as e:
            return f'Error executing command: {str(e)}'

    def _invoke_handler(self, handler, args):
        """Call a handler with arguments parsed from the raw string."""
        if args:
            return handler(*_parse_arguments(args))
        return handler()

    def execute_command(self, command_str):
        cmd, args = _split_command(command_str)
        if cmd is None:
            return MSG_INVALID_COMMAND
        if cmd not in self.command_handlers:
            return f'Unknown command: {cmd}'
        handler = self.command_handlers[cmd]
        try:
            return self._invoke_handler(handler, args)
        except Exception as e:
            return f'Error executing {cmd}: {str(e)}'


# --- CLI ---------------------------------------------------------------------

def _print_banner():
    print(BANNER_TITLE)
    print(BANNER_COMMANDS)


def main():
    manager = InventoryManager()
    _print_banner()
    while True:
        try:
            user_input = input(PROMPT).strip()
            if _is_exit_command(user_input):
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
