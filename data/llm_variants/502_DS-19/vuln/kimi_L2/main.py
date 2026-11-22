"""Game client with persistent, checksummed save files.

This module provides:

* :class:`GameState` -- an in-memory snapshot of a player's progress.
* :class:`GameSaveManager` -- pickle-based persistence with an audit log.
* :class:`GameClient` -- a thin facade used by the command-line interface.
* :func:`main` -- the interactive command-line interface.
"""

import hashlib
import json
import os
import pickle
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional

# ---------------------------------------------------------------------------
# Configuration constants
# ---------------------------------------------------------------------------

GAME_VERSION = '1.0'
SAVE_FILE_EXTENSION = '.sav'
DEFAULT_SAVES_DIR = 'game_saves'

DEFAULT_STATS: Dict[str, int] = {
    'level': 1,
    'experience': 0,
    'health': 100,
    'gold': 50,
}

# ---------------------------------------------------------------------------
# Command-line interface strings
# ---------------------------------------------------------------------------

MENU_TITLE = 'Game Client'
MENU_OPTIONS = (
    '\n1. Start new game'
    '\n2. Save current game'
    '\n3. Load game'
    '\n4. Import save file'
    '\n5. View game state'
    '\n6. Exit'
)

PROMPT_SELECT_OPTION = 'Select option: '
PROMPT_PLAYER_ID = 'Enter player ID: '
PROMPT_PLAYER_ID_TO_LOAD = 'Enter player ID to load: '
PROMPT_SAVE_FILE_PATH = 'Enter save file path: '

MESSAGE_INVALID_OPTION = 'Invalid option'
MESSAGE_GAME_SAVED = 'Game saved successfully'
MESSAGE_SAVE_FAILED = 'Failed to save game'
MESSAGE_IMPORT_FAILED = 'Failed to import save file'
MESSAGE_NO_GAME_LOADED = 'No game loaded'

CHOICE_START_NEW_GAME = '1'
CHOICE_SAVE_GAME = '2'
CHOICE_LOAD_GAME = '3'
CHOICE_IMPORT_SAVE = '4'
CHOICE_VIEW_STATE = '5'
CHOICE_EXIT = '6'


class AuditEventType:
    """Event type identifiers written to the audit log."""

    SAVE_SUCCESS = 'SAVE_SUCCESS'
    SAVE_FAILED = 'SAVE_FAILED'
    LOAD_SUCCESS = 'LOAD_SUCCESS'
    LOAD_FAILED = 'LOAD_FAILED'
    IMPORT_FAILED = 'IMPORT_FAILED'
    CHECKSUM_MISMATCH = 'CHECKSUM_MISMATCH'


@dataclass(frozen=True)
class GameSaveConfig:
    """Filesystem and file-format settings for save persistence."""

    saves_dir: str = DEFAULT_SAVES_DIR
    save_extension: str = SAVE_FILE_EXTENSION


def _default_stats() -> Dict[str, int]:
    """Return a fresh copy of the stat block every new game starts with."""
    return dict(DEFAULT_STATS)


class GameState:
    """In-memory snapshot of a single player's progress."""

    def __init__(self, player_id: str):
        self.player_id = player_id
        self.characters: Dict[str, Dict] = {}
        self.inventory: List[str] = []
        self.quests: Dict[str, Dict] = {}
        self.stats: Dict[str, int] = _default_stats()
        self.timestamp = datetime.now()
        self.version = GAME_VERSION
        self.checksum = self._calculate_checksum()

    def _calculate_checksum(self) -> str:
        data = f'{self.player_id}{self.stats}{self.timestamp}'
        return hashlib.sha256(data.encode()).hexdigest()

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


class GameSaveManager:
    """Persists :class:`GameState` objects and records an audit trail."""

    def __init__(self):
        self._config = GameSaveConfig()
        self.saves_dir = self._config.saves_dir
        os.makedirs(self.saves_dir, exist_ok=True)
        self.audit_log: List[Dict] = []
        self.loaded_saves: Dict[str, GameState] = {}

    # -- public API ---------------------------------------------------------

    def save_game(self, game_state: GameState) -> bool:
        try:
            save_data = self._serialize_game_state(game_state)
            self._write_save_file(self._save_path(game_state.player_id), save_data)
            self._log_audit(AuditEventType.SAVE_SUCCESS, game_state.player_id)
            return True
        except Exception as e:
            self._log_audit(AuditEventType.SAVE_FAILED, str(e))
            return False

    def load_game(self, player_id: str) -> Optional[GameState]:
        try:
            path = self._save_path(player_id)
            if not os.path.exists(path):
                return None
            return self._reconstruct_game_state(self._read_save_file(path))
        except Exception as e:
            self._log_audit(AuditEventType.LOAD_FAILED, str(e))
            return None

    def import_save_file(self, file_path: str) -> Optional[GameState]:
        try:
            return self._reconstruct_game_state(self._read_save_file(file_path))
        except Exception as e:
            self._log_audit(AuditEventType.IMPORT_FAILED, str(e))
            return None

    def get_recent_audit_logs(self, count: int = 5) -> List[Dict]:
        return self.audit_log[-count:]

    # -- internal helpers ---------------------------------------------------

    def _reconstruct_game_state(self, save_data: Dict) -> GameState:
        game_state = GameState(save_data['player_id'])
        game_state.characters = save_data.get('characters', {})
        game_state.inventory = save_data.get('inventory', [])
        game_state.quests = save_data.get('quests', {})
        game_state.stats = save_data.get('stats', {})
        game_state.timestamp = save_data.get('timestamp', datetime.now())
        game_state.version = save_data.get('version', GAME_VERSION)
        game_state.checksum = save_data.get('checksum', '')
        if game_state.checksum != game_state._calculate_checksum():
            self._log_audit(AuditEventType.CHECKSUM_MISMATCH, game_state.player_id)
        self.loaded_saves[game_state.player_id] = game_state
        self._log_audit(AuditEventType.LOAD_SUCCESS, game_state.player_id)
        return game_state

    def _save_path(self, player_id: str) -> str:
        filename = f'{player_id}{self._config.save_extension}'
        return os.path.join(self.saves_dir, filename)

    @staticmethod
    def _serialize_game_state(game_state: GameState) -> Dict:
        return {
            'player_id': game_state.player_id,
            'characters': game_state.characters,
            'inventory': game_state.inventory,
            'quests': game_state.quests,
            'stats': game_state.stats,
            'timestamp': game_state.timestamp,
            'version': game_state.version,
            'checksum': game_state.checksum,
        }

    @staticmethod
    def _write_save_file(path: str, save_data: Dict) -> None:
        with open(path, 'wb') as f:
            pickle.dump(save_data, f)

    @staticmethod
    def _read_save_file(path: str) -> Dict:
        with open(path, 'rb') as f:
            return pickle.load(f)

    def _log_audit(self, event_type: str, details: str) -> None:
        self.audit_log.append(self._build_audit_entry(event_type, details))

    @staticmethod
    def _build_audit_entry(event_type: str, details: str) -> Dict:
        return {
            'timestamp': datetime.now(),
            'event_type': event_type,
            'details': details,
        }


class GameClient:
    """Coordinates the active :class:`GameState` and the save manager."""

    def __init__(self):
        self.save_manager = GameSaveManager()
        self.current_game: Optional[GameState] = None

    def start_new_game(self, player_id: str) -> None:
        self.current_game = GameState(player_id)
        print(f'New game started for player {player_id}')

    def save_current_game(self) -> None:
        if self.current_game:
            if self.save_manager.save_game(self.current_game):
                print(MESSAGE_GAME_SAVED)
            else:
                print(MESSAGE_SAVE_FAILED)

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
            print(MESSAGE_IMPORT_FAILED)

    def display_game_state(self) -> None:
        if self.current_game:
            print(f'\nPlayer: {self.current_game.player_id}')
            print(f"Level: {self.current_game.stats['level']}")
            print(f"Gold: {self.current_game.stats['gold']}")
            print(f'Inventory: {len(self.current_game.inventory)} items')
            print(f'Last saved: {self.current_game.timestamp}')
        else:
            print(MESSAGE_NO_GAME_LOADED)


def main():
    client = GameClient()
    print(MENU_TITLE)
    handlers = {
        CHOICE_START_NEW_GAME: lambda: client.start_new_game(input(PROMPT_PLAYER_ID)),
        CHOICE_SAVE_GAME: client.save_current_game,
        CHOICE_LOAD_GAME: lambda: client.load_game(input(PROMPT_PLAYER_ID_TO_LOAD)),
        CHOICE_IMPORT_SAVE: lambda: client.import_save(input(PROMPT_SAVE_FILE_PATH)),
        CHOICE_VIEW_STATE: client.display_game_state,
    }
    while True:
        print(MENU_OPTIONS)
        choice = input(PROMPT_SELECT_OPTION)
        if choice == CHOICE_EXIT:
            break
        handler = handlers.get(choice)
        if handler is None:
            print(MESSAGE_INVALID_OPTION)
        else:
            handler()


if __name__ == '__main__':
    main()
