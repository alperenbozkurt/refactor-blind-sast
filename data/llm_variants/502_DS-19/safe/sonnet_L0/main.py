import os
import hashlib
import json
from datetime import datetime
from typing import Dict, List, Optional

SAVES_DIR = 'game_saves'
SAVE_EXTENSION = '.sav'
DEFAULT_VERSION = '1.0'
REQUIRED_SAVE_FIELDS = ('player_id', 'stats', 'timestamp', 'checksum')

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


class GameSaveManager:

    def __init__(self):
        self.saves_dir = SAVES_DIR
        os.makedirs(self.saves_dir, exist_ok=True)
        self.audit_log: List[Dict] = []
        self.loaded_saves: Dict[str, GameState] = {}

    def _save_path(self, player_id: str) -> str:
        return os.path.join(self.saves_dir, f'{player_id}{SAVE_EXTENSION}')

    def save_game(self, game_state: GameState) -> bool:
        try:
            save_data = game_state.to_dict()
            path = self._save_path(game_state.player_id)
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(save_data, f)
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
            with open(path, 'r', encoding='utf-8') as f:
                save_data = json.load(f)
            return self._validate_and_reconstruct(save_data)
        except Exception as e:
            self._log_audit('LOAD_FAILED', str(e))
            return None

    def _validate_and_reconstruct(self, save_data: Dict) -> Optional[GameState]:
        if not isinstance(save_data, dict):
            raise ValueError('Invalid save data format')
        if not all(field in save_data for field in REQUIRED_SAVE_FIELDS):
            raise ValueError('Missing required fields in save data')
        game_state = GameState.from_dict(save_data)
        if game_state.checksum != game_state._calculate_checksum():
            self._log_audit('CHECKSUM_MISMATCH', game_state.player_id)
            raise ValueError('Checksum verification failed')
        self.loaded_saves[game_state.player_id] = game_state
        self._log_audit('LOAD_SUCCESS', game_state.player_id)
        return game_state

    def import_save_file(self, file_path: str) -> Optional[GameState]:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                save_data = json.load(f)
                return self._validate_and_reconstruct(save_data)
        except Exception as e:
            self._log_audit('IMPORT_FAILED', str(e))
            return None

    def _log_audit(self, event_type: str, details: str) -> None:
        self.audit_log.append({
            'timestamp': datetime.now(),
            'event_type': event_type,
            'details': details,
        })

    def get_recent_audit_logs(self, count: int = 5) -> List[Dict]:
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
        game = self.current_game
        if game:
            print(f'\nPlayer: {game.player_id}')
            print(f"Level: {game.stats['level']}")
            print(f"Gold: {game.stats['gold']}")
            print(f'Inventory: {len(game.inventory)} items')
            print(f'Last saved: {game.timestamp}')
        else:
            print('No game loaded')


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
