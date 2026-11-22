import os
import hashlib
import json
from datetime import datetime
from typing import Callable, Dict, List, Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SAVES_DIR_NAME = 'game_saves'
SAVE_FILE_EXTENSION = '.sav'
SAVE_FILE_ENCODING = 'utf-8'
DEFAULT_VERSION = '1.0'
DEFAULT_AUDIT_LOG_COUNT = 5

DEFAULT_STATS: Dict[str, int] = {
    'level': 1,
    'experience': 0,
    'health': 100,
    'gold': 50,
}

REQUIRED_SAVE_FIELDS = ('player_id', 'stats', 'timestamp', 'checksum')

# Audit event types
EVENT_SAVE_SUCCESS = 'SAVE_SUCCESS'
EVENT_SAVE_FAILED = 'SAVE_FAILED'
EVENT_LOAD_SUCCESS = 'LOAD_SUCCESS'
EVENT_LOAD_FAILED = 'LOAD_FAILED'
EVENT_IMPORT_FAILED = 'IMPORT_FAILED'
EVENT_CHECKSUM_MISMATCH = 'CHECKSUM_MISMATCH'

# Menu options
MENU_START_NEW = '1'
MENU_SAVE = '2'
MENU_LOAD = '3'
MENU_IMPORT = '4'
MENU_VIEW = '5'
MENU_EXIT = '6'

MENU_LINES = (
    '\n1. Start new game',
    '2. Save current game',
    '3. Load game',
    '4. Import save file',
    '5. View game state',
    '6. Exit',
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _default_stats() -> Dict[str, int]:
    """Return a fresh copy of the default player stats."""
    return dict(DEFAULT_STATS)


def _save_filename(player_id: str) -> str:
    """Return the save file name for a player."""
    return f'{player_id}{SAVE_FILE_EXTENSION}'


def _compute_checksum(player_id: str, stats: Dict, timestamp: datetime) -> str:
    """Compute the SHA-256 checksum for the given state components."""
    data = f'{player_id}{stats}{timestamp}'
    return hashlib.sha256(data.encode()).hexdigest()


def _read_json_file(path: str) -> object:
    """Read and decode a JSON file."""
    with open(path, 'r', encoding=SAVE_FILE_ENCODING) as f:
        return json.load(f)


def _write_json_file(path: str, data: Dict) -> None:
    """Encode and write data to a JSON file."""
    with open(path, 'w', encoding=SAVE_FILE_ENCODING) as f:
        json.dump(data, f)


# ---------------------------------------------------------------------------
# Domain model
# ---------------------------------------------------------------------------

class GameState:

    def __init__(self, player_id: str):
        self.player_id = player_id
        self.characters: Dict[str, Dict] = {}
        self.inventory: List[str] = []
        self.quests: Dict[str, Dict] = {}
        self.stats: Dict[str, int] = _default_stats()
        self.timestamp = datetime.now()
        self.version = DEFAULT_VERSION
        self.checksum = self._calculate_checksum()

    def _calculate_checksum(self) -> str:
        return _compute_checksum(self.player_id, self.stats, self.timestamp)

    def add_item(self, item_id: str) -> None:
        self.inventory.append(item_id)
        self._update_state()

    def complete_quest(self, quest_id: str) -> None:
        if quest_id in self.quests:
            self.quests[quest_id]['completed'] = True
            self._update_state()

    def _update_state(self) -> None:
        self.timestamp = datetime.now()
        self.checksum = self._calculate_checksum()

    def to_dict(self) -> Dict:
        return {
            'player_id': self.player_id,
            'characters': self.characters,
            'inventory': self.inventory,
            'quests': self.quests,
            'stats': self.stats,
            'timestamp': self.timestamp.isoformat(),
            'version': self.version,
            'checksum': self.checksum,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'GameState':
        game_state = cls(data['player_id'])
        game_state.characters = data.get('characters', {})
        game_state.inventory = data.get('inventory', [])
        game_state.quests = data.get('quests', {})
        game_state.stats = data.get('stats', {})
        game_state.timestamp = datetime.fromisoformat(
            data.get('timestamp', datetime.now().isoformat())
        )
        game_state.version = data.get('version', DEFAULT_VERSION)
        game_state.checksum = data.get('checksum', '')
        return game_state


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

class GameSaveManager:

    def __init__(self):
        self.saves_dir = SAVES_DIR_NAME
        os.makedirs(self.saves_dir, exist_ok=True)
        self.audit_log: List[Dict] = []
        self.loaded_saves: Dict[str, GameState] = {}

    def _save_path(self, player_id: str) -> str:
        return os.path.join(self.saves_dir, _save_filename(player_id))

    def save_game(self, game_state: GameState) -> bool:
        try:
            save_data = game_state.to_dict()
            path = self._save_path(game_state.player_id)
            _write_json_file(path, save_data)
            self._log_audit(EVENT_SAVE_SUCCESS, game_state.player_id)
            return True
        except Exception as e:
            self._log_audit(EVENT_SAVE_FAILED, str(e))
            return False

    def load_game(self, player_id: str) -> Optional[GameState]:
        try:
            path = self._save_path(player_id)
            if not os.path.exists(path):
                return None
            save_data = _read_json_file(path)
            return self._validate_and_reconstruct(save_data)
        except Exception as e:
            self._log_audit(EVENT_LOAD_FAILED, str(e))
            return None

    @staticmethod
    def _validate_save_data(save_data: object) -> None:
        if not isinstance(save_data, dict):
            raise ValueError('Invalid save data format')
        if not all((field in save_data for field in REQUIRED_SAVE_FIELDS)):
            raise ValueError('Missing required fields in save data')

    def _validate_and_reconstruct(self, save_data: Dict) -> Optional[GameState]:
        self._validate_save_data(save_data)
        game_state = GameState.from_dict(save_data)
        if game_state.checksum != game_state._calculate_checksum():
            self._log_audit(EVENT_CHECKSUM_MISMATCH, game_state.player_id)
            raise ValueError('Checksum verification failed')
        self.loaded_saves[game_state.player_id] = game_state
        self._log_audit(EVENT_LOAD_SUCCESS, game_state.player_id)
        return game_state

    def import_save_file(self, file_path: str) -> Optional[GameState]:
        try:
            save_data = _read_json_file(file_path)
            return self._validate_and_reconstruct(save_data)
        except Exception as e:
            self._log_audit(EVENT_IMPORT_FAILED, str(e))
            return None

    def _log_audit(self, event_type: str, details: str) -> None:
        self.audit_log.append({
            'timestamp': datetime.now(),
            'event_type': event_type,
            'details': details,
        })

    def get_recent_audit_logs(self, count: int = DEFAULT_AUDIT_LOG_COUNT) -> List[Dict]:
        return self.audit_log[-count:]


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

class GameClient:

    def __init__(self):
        self.save_manager = GameSaveManager()
        self.current_game: Optional[GameState] = None

    def start_new_game(self, player_id: str) -> None:
        self.current_game = GameState(player_id)
        print(f'New game started for player {player_id}')

    def save_current_game(self) -> None:
        if self.current_game:
            if self.save_manager.save_game(self.current_game):
                print('Game saved successfully')
            else:
                print('Failed to save game')

    def load_game(self, player_id: str) -> None:
        game_state = self.save_manager.load_game(player_id)
        if game_state:
            self.current_game = game_state
            print(f'Loaded game for player {player_id}')
        else:
            print(f'No save found for player {player_id}')

    def import_save(self, file_path: str) -> None:
        game_state = self.save_manager.import_save_file(file_path)
        if game_state:
            self.current_game = game_state
            print(f'Imported save for player {game_state.player_id}')
        else:
            print('Failed to import save file')

    def display_game_state(self) -> None:
        if self.current_game:
            print(f'\nPlayer: {self.current_game.player_id}')
            print(f"Level: {self.current_game.stats['level']}")
            print(f"Gold: {self.current_game.stats['gold']}")
            print(f'Inventory: {len(self.current_game.inventory)} items')
            print(f'Last saved: {self.current_game.timestamp}')
        else:
            print('No game loaded')


# ---------------------------------------------------------------------------
# Command-line interface
# ---------------------------------------------------------------------------

def _print_menu() -> None:
    for line in MENU_LINES:
        print(line)


def _handle_start_new(client: GameClient) -> None:
    player_id = input('Enter player ID: ')
    client.start_new_game(player_id)


def _handle_save(client: GameClient) -> None:
    client.save_current_game()


def _handle_load(client: GameClient) -> None:
    player_id = input('Enter player ID to load: ')
    client.load_game(player_id)


def _handle_import(client: GameClient) -> None:
    file_path = input('Enter save file path: ')
    client.import_save(file_path)


def _handle_view(client: GameClient) -> None:
    client.display_game_state()


_MENU_HANDLERS: Dict[str, Callable[[GameClient], None]] = {
    MENU_START_NEW: _handle_start_new,
    MENU_SAVE: _handle_save,
    MENU_LOAD: _handle_load,
    MENU_IMPORT: _handle_import,
    MENU_VIEW: _handle_view,
}


def main():
    client = GameClient()
    print('Game Client')
    while True:
        _print_menu()
        choice = input('Select option: ')
        if choice == MENU_EXIT:
            break
        handler = _MENU_HANDLERS.get(choice)
        if handler is None:
            print('Invalid option')
        else:
            handler(client)


if __name__ == '__main__':
    main()
