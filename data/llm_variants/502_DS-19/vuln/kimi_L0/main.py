import hashlib
import json
import os
import pickle
from datetime import datetime
from typing import Dict, List, Optional


class GameState:
    """Represents the complete state of a single player's game."""

    DEFAULT_VERSION = '1.0'
    DEFAULT_STATS = {'level': 1, 'experience': 0, 'health': 100, 'gold': 50}

    def __init__(self, player_id: str):
        self.player_id = player_id
        self.characters: Dict[str, Dict] = {}
        self.inventory: List[str] = []
        self.quests: Dict[str, Dict] = {}
        self.stats: Dict[str, int] = self.DEFAULT_STATS.copy()
        self.timestamp = datetime.now()
        self.version = self.DEFAULT_VERSION
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
    """Persists game states to disk and keeps an audit log of operations."""

    SAVES_DIR = 'game_saves'
    SAVE_EXTENSION = '.sav'

    def __init__(self):
        self.saves_dir = self.SAVES_DIR
        os.makedirs(self.saves_dir, exist_ok=True)
        self.audit_log: List[Dict] = []
        self.loaded_saves: Dict[str, GameState] = {}

    def save_game(self, game_state: GameState) -> bool:
        try:
            save_data = {
                'player_id': game_state.player_id,
                'characters': game_state.characters,
                'inventory': game_state.inventory,
                'quests': game_state.quests,
                'stats': game_state.stats,
                'timestamp': game_state.timestamp,
                'version': game_state.version,
                'checksum': game_state.checksum,
            }
            with open(self._save_path(game_state.player_id), 'wb') as f:
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
            with open(path, 'rb') as f:
                save_data = pickle.load(f)
            return self._reconstruct_game_state(save_data)
        except Exception as e:
            self._log_audit('LOAD_FAILED', str(e))
            return None

    def import_save_file(self, file_path: str) -> Optional[GameState]:
        try:
            with open(file_path, 'rb') as f:
                save_data = pickle.load(f)
            return self._reconstruct_game_state(save_data)
        except Exception as e:
            self._log_audit('IMPORT_FAILED', str(e))
            return None

    def get_recent_audit_logs(self, count: int = 5) -> List[Dict]:
        return self.audit_log[-count:]

    def _save_path(self, player_id: str) -> str:
        filename = f'{player_id}{self.SAVE_EXTENSION}'
        return os.path.join(self.saves_dir, filename)

    def _reconstruct_game_state(self, save_data: Dict) -> GameState:
        game_state = GameState(save_data['player_id'])
        game_state.characters = save_data.get('characters', {})
        game_state.inventory = save_data.get('inventory', [])
        game_state.quests = save_data.get('quests', {})
        game_state.stats = save_data.get('stats', {})
        game_state.timestamp = save_data.get('timestamp', datetime.now())
        game_state.version = save_data.get('version', GameState.DEFAULT_VERSION)
        game_state.checksum = save_data.get('checksum', '')
        if game_state.checksum != game_state._calculate_checksum():
            self._log_audit('CHECKSUM_MISMATCH', game_state.player_id)
        self.loaded_saves[game_state.player_id] = game_state
        self._log_audit('LOAD_SUCCESS', game_state.player_id)
        return game_state

    def _log_audit(self, event_type: str, details: str) -> None:
        self.audit_log.append({
            'timestamp': datetime.now(),
            'event_type': event_type,
            'details': details,
        })


class GameClient:
    """Command-line front end that coordinates game state and persistence."""

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


MENU = (
    '\n1. Start new game\n'
    '2. Save current game\n'
    '3. Load game\n'
    '4. Import save file\n'
    '5. View game state\n'
    '6. Exit'
)


def main():
    client = GameClient()
    print('Game Client')
    while True:
        print(MENU)
        choice = input('Select option: ')
        if choice == '1':
            player_id = input('Enter player ID: ')
            client.start_new_game(player_id)
        elif choice == '2':
            client.save_current_game()
        elif choice == '3':
            player_id = input('Enter player ID to load: ')
            client.load_game(player_id)
        elif choice == '4':
            file_path = input('Enter save file path: ')
            client.import_save(file_path)
        elif choice == '5':
            client.display_game_state()
        elif choice == '6':
            break
        else:
            print('Invalid option')


if __name__ == '__main__':
    main()
