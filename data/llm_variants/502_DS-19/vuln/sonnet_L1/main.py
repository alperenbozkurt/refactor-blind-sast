import pickle
import os
import hashlib
import json
from datetime import datetime
from typing import Dict, List, Optional

SAVES_DIR = 'game_saves'
SAVE_FILE_EXTENSION = '.sav'
DEFAULT_VERSION = '1.0'

MENU_OPTIONS = (
    '1. Start new game',
    '2. Save current game',
    '3. Load game',
    '4. Import save file',
    '5. View game state',
    '6. Exit',
)


class GameState:

    def __init__(self, player_id: str):
        self.player_id = player_id
        self.characters: Dict[str, Dict] = {}
        self.inventory: List[str] = []
        self.quests: Dict[str, Dict] = {}
        self.stats: Dict[str, int] = {
            'level': 1,
            'experience': 0,
            'health': 100,
            'gold': 50,
        }
        self.timestamp = datetime.now()
        self.version = DEFAULT_VERSION
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

    def __init__(self):
        self.saves_dir = SAVES_DIR
        os.makedirs(self.saves_dir, exist_ok=True)
        self.audit_log: List[Dict] = []
        self.loaded_saves: Dict[str, GameState] = {}

    # ----- paths and (de)serialization helpers -----

    def _save_path(self, player_id: str) -> str:
        return os.path.join(self.saves_dir, f'{player_id}{SAVE_FILE_EXTENSION}')

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
    def _read_save_data(path: str) -> Dict:
        # NOTE: behaviour intentionally preserved; pickle.load can execute
        # arbitrary code when given untrusted files.
        with open(path, 'rb') as f:
            return pickle.load(f)

    # ----- public API -----

    def save_game(self, game_state: GameState) -> bool:
        try:
            save_data = self._serialize_game_state(game_state)
            path = self._save_path(game_state.player_id)
            with open(path, 'wb') as f:
                pickle.dump(save_data, f)
            self._log_audit('SAVE_SUCCESS', game_state.player_id)
            return True
        except Exception as e:
            self._log_audit('SAVE_FAILED', str(e))
            return False

    def load_game(self, player_id: str) -> Optional[GameState]:
        try:
            path = self._save_path(player_id)
            if not os.path.exists(path):
                return None
            save_data = self._read_save_data(path)
            return self._reconstruct_game_state(save_data)
        except Exception as e:
            self._log_audit('LOAD_FAILED', str(e))
            return None

    def _reconstruct_game_state(self, save_data: Dict) -> GameState:
        game_state = GameState(save_data['player_id'])
        game_state.characters = save_data.get('characters', {})
        game_state.inventory = save_data.get('inventory', [])
        game_state.quests = save_data.get('quests', {})
        game_state.stats = save_data.get('stats', {})
        game_state.timestamp = save_data.get('timestamp', datetime.now())
        game_state.version = save_data.get('version', DEFAULT_VERSION)
        game_state.checksum = save_data.get('checksum', '')

        if game_state.checksum != game_state._calculate_checksum():
            self._log_audit('CHECKSUM_MISMATCH', game_state.player_id)

        self.loaded_saves[game_state.player_id] = game_state
        self._log_audit('LOAD_SUCCESS', game_state.player_id)
        return game_state

    def import_save_file(self, file_path: str) -> Optional[GameState]:
        try:
            save_data = self._read_save_data(file_path)
            return self._reconstruct_game_state(save_data)
        except Exception as e:
            self._log_audit('IMPORT_FAILED', str(e))
            return None

    def _log_audit(self, event_type: str, details: str) -> None:
        self.audit_log.append({
            'timestamp': datetime.now(),
            'event_type': event_type,
            'details': details,
        })

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
        if not self.current_game:
            return
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
        game = self.current_game
        if not game:
            print('No game loaded')
            return
        print(f'\nPlayer: {game.player_id}')
        print(f"Level: {game.stats['level']}")
        print(f"Gold: {game.stats['gold']}")
        print(f'Inventory: {len(game.inventory)} items')
        print(f'Last saved: {game.timestamp}')


def _print_menu() -> None:
    print()
    for option in MENU_OPTIONS:
        print(option)


def main():
    client = GameClient()
    print('Game Client')

    while True:
        _print_menu()
        choice = input('Select option: ')

        if choice == '1':
            client.start_new_game(input('Enter player ID: '))
        elif choice == '2':
            client.save_current_game()
        elif choice == '3':
            client.load_game(input('Enter player ID to load: '))
        elif choice == '4':
            client.import_save(input('Enter save file path: '))
        elif choice == '5':
            client.display_game_state()
        elif choice == '6':
            break
        else:
            print('Invalid option')


if __name__ == '__main__':
    main()
