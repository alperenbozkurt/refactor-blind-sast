import os
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

GAME_VERSION = '1.0'

DEFAULT_PLAYER_STATS: Dict[str, int] = {
    'level': 1,
    'experience': 0,
    'health': 100,
    'gold': 50,
}

DEFAULT_SAVES_DIR = 'game_saves'
SAVE_FILE_EXTENSION = '.sav'
FILE_ENCODING = 'utf-8'

REQUIRED_SAVE_FIELDS = ('player_id', 'stats', 'timestamp', 'checksum')

ERROR_INVALID_SAVE_FORMAT = 'Invalid save data format'
ERROR_MISSING_SAVE_FIELDS = 'Missing required fields in save data'
ERROR_CHECKSUM_FAILED = 'Checksum verification failed'

MENU_TITLE = 'Game Client'
MENU_OPTIONS = (
    '1. Start new game',
    '2. Save current game',
    '3. Load game',
    '4. Import save file',
    '5. View game state',
    '6. Exit',
)

CHOICE_START_NEW_GAME = '1'
CHOICE_SAVE_GAME = '2'
CHOICE_LOAD_GAME = '3'
CHOICE_IMPORT_SAVE = '4'
CHOICE_VIEW_STATE = '5'
CHOICE_EXIT = '6'

PROMPT_SELECT_OPTION = 'Select option: '
PROMPT_NEW_PLAYER_ID = 'Enter player ID: '
PROMPT_LOAD_PLAYER_ID = 'Enter player ID to load: '
PROMPT_SAVE_FILE_PATH = 'Enter save file path: '
MSG_INVALID_OPTION = 'Invalid option'


class AuditEventType:
    """Namespace for audit log event type identifiers."""

    SAVE_SUCCESS = 'SAVE_SUCCESS'
    SAVE_FAILED = 'SAVE_FAILED'
    LOAD_SUCCESS = 'LOAD_SUCCESS'
    LOAD_FAILED = 'LOAD_FAILED'
    CHECKSUM_MISMATCH = 'CHECKSUM_MISMATCH'
    IMPORT_FAILED = 'IMPORT_FAILED'


@dataclass(frozen=True)
class SaveManagerConfig:
    """File-storage configuration for the save manager."""

    saves_dir: str = DEFAULT_SAVES_DIR
    save_extension: str = SAVE_FILE_EXTENSION
    encoding: str = FILE_ENCODING


DEFAULT_SAVE_MANAGER_CONFIG = SaveManagerConfig()


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _now() -> datetime:
    return datetime.now()


def _initial_player_stats() -> Dict[str, int]:
    return dict(DEFAULT_PLAYER_STATS)


def _compute_checksum(player_id: str, stats: Dict[str, int], timestamp: datetime) -> str:
    data = f'{player_id}{stats}{timestamp}'
    return hashlib.sha256(data.encode()).hexdigest()


def _build_save_path(saves_dir: str, player_id: str, extension: str = SAVE_FILE_EXTENSION) -> str:
    return os.path.join(saves_dir, f'{player_id}{extension}')


def _read_json_file(path: str, encoding: str = FILE_ENCODING) -> Dict:
    with open(path, 'r', encoding=encoding) as f:
        return json.load(f)


def _write_json_file(path: str, data: Dict, encoding: str = FILE_ENCODING) -> None:
    with open(path, 'w', encoding=encoding) as f:
        json.dump(data, f)


def _make_audit_entry(event_type: str, details: str) -> Dict:
    return {'timestamp': _now(), 'event_type': event_type, 'details': details}


class GameState:

    def __init__(self, player_id: str):
        self.player_id = player_id
        self.characters: Dict[str, Dict] = {}
        self.inventory: List[str] = []
        self.quests: Dict[str, Dict] = {}
        self.stats: Dict[str, int] = _initial_player_stats()
        self.timestamp = _now()
        self.version = GAME_VERSION
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
        self.timestamp = _now()
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
        game_state.timestamp = datetime.fromisoformat(data.get('timestamp', _now().isoformat()))
        game_state.version = data.get('version', GAME_VERSION)
        game_state.checksum = data.get('checksum', '')
        return game_state


class GameSaveManager:

    def __init__(self):
        self._config = DEFAULT_SAVE_MANAGER_CONFIG
        self.saves_dir = self._config.saves_dir
        os.makedirs(self.saves_dir, exist_ok=True)
        self.audit_log: List[Dict] = []
        self.loaded_saves: Dict[str, GameState] = {}

    def save_game(self, game_state: GameState) -> bool:
        try:
            path = self._get_save_path(game_state.player_id)
            _write_json_file(path, game_state.to_dict(), self._config.encoding)
            self._log_audit(AuditEventType.SAVE_SUCCESS, game_state.player_id)
            return True
        except Exception as e:
            self._log_audit(AuditEventType.SAVE_FAILED, str(e))
            return False

    def load_game(self, player_id: str) -> Optional[GameState]:
        try:
            path = self._get_save_path(player_id)
            if not os.path.exists(path):
                return None
            save_data = _read_json_file(path, self._config.encoding)
            return self._validate_and_reconstruct(save_data)
        except Exception as e:
            self._log_audit(AuditEventType.LOAD_FAILED, str(e))
            return None

    def _get_save_path(self, player_id: str) -> str:
        return _build_save_path(self.saves_dir, player_id, self._config.save_extension)

    def _validate_and_reconstruct(self, save_data: Dict) -> Optional[GameState]:
        self._validate_save_data(save_data)
        game_state = GameState.from_dict(save_data)
        self._verify_checksum(game_state)
        self.loaded_saves[game_state.player_id] = game_state
        self._log_audit(AuditEventType.LOAD_SUCCESS, game_state.player_id)
        return game_state

    @staticmethod
    def _validate_save_data(save_data: Dict) -> None:
        if not isinstance(save_data, dict):
            raise ValueError(ERROR_INVALID_SAVE_FORMAT)
        if not all((field in save_data for field in REQUIRED_SAVE_FIELDS)):
            raise ValueError(ERROR_MISSING_SAVE_FIELDS)

    def _verify_checksum(self, game_state: GameState) -> None:
        if game_state.checksum != game_state._calculate_checksum():
            self._log_audit(AuditEventType.CHECKSUM_MISMATCH, game_state.player_id)
            raise ValueError(ERROR_CHECKSUM_FAILED)

    def import_save_file(self, file_path: str) -> Optional[GameState]:
        try:
            save_data = _read_json_file(file_path, self._config.encoding)
            return self._validate_and_reconstruct(save_data)
        except Exception as e:
            self._log_audit(AuditEventType.IMPORT_FAILED, str(e))
            return None

    def _log_audit(self, event_type: str, details: str) -> None:
        self.audit_log.append(_make_audit_entry(event_type, details))

    def get_recent_audit_logs(self, count: int=5) -> List[Dict]:
        return self.audit_log[-count:]


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
            self._print_game_state(self.current_game)
        else:
            print('No game loaded')

    @staticmethod
    def _print_game_state(game_state: GameState) -> None:
        print(f'\nPlayer: {game_state.player_id}')
        print(f"Level: {game_state.stats['level']}")
        print(f"Gold: {game_state.stats['gold']}")
        print(f'Inventory: {len(game_state.inventory)} items')
        print(f'Last saved: {game_state.timestamp}')


def _print_menu() -> None:
    print()
    for option in MENU_OPTIONS:
        print(option)


def _handle_menu_choice(client: GameClient, choice: str) -> bool:
    """Dispatch a single menu choice; returns False when the client should exit."""
    if choice == CHOICE_START_NEW_GAME:
        client.start_new_game(input(PROMPT_NEW_PLAYER_ID))
    elif choice == CHOICE_SAVE_GAME:
        client.save_current_game()
    elif choice == CHOICE_LOAD_GAME:
        client.load_game(input(PROMPT_LOAD_PLAYER_ID))
    elif choice == CHOICE_IMPORT_SAVE:
        client.import_save(input(PROMPT_SAVE_FILE_PATH))
    elif choice == CHOICE_VIEW_STATE:
        client.display_game_state()
    elif choice == CHOICE_EXIT:
        return False
    else:
        print(MSG_INVALID_OPTION)
    return True


def main():
    client = GameClient()
    print(MENU_TITLE)
    while True:
        _print_menu()
        choice = input(PROMPT_SELECT_OPTION)
        if not _handle_menu_choice(client, choice):
            break


if __name__ == '__main__':
    main()
