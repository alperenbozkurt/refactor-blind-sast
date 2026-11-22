import json
import hashlib
import datetime
from typing import Any, Dict, List, Optional


# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #

DEFAULT_ACCOUNT_BALANCE = 1000.0
REQUIRED_TRANSACTION_FIELDS = ('sender', 'recipient', 'amount')
DEFAULT_AUDIT_ENTRIES = 5
FILE_ENCODING = 'utf-8'
STATE_JSON_INDENT = 2

# Audit event types
EVENT_BATCH_LOAD_FAILURE = 'BATCH_LOAD_FAILURE'
EVENT_TRANSACTION_QUEUED = 'TRANSACTION_QUEUED'
EVENT_TRANSACTION_REJECTED = 'TRANSACTION_REJECTED'
EVENT_TRANSACTION_PROCESSED = 'TRANSACTION_PROCESSED'
EVENT_TRANSACTION_FAILED = 'TRANSACTION_FAILED'
EVENT_STATE_LOAD_ERROR = 'STATE_LOAD_ERROR'

# Menu options
MENU_PROCESS_FILE = '1'
MENU_SHOW_BALANCES = '2'
MENU_SHOW_AUDIT_LOG = '3'
MENU_EXIT = '4'


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _parse_timestamp(timestamp_str: Any) -> datetime.datetime:
    """Parse an ISO timestamp, defaulting to 'now' when none is supplied."""
    if timestamp_str:
        try:
            return datetime.datetime.fromisoformat(timestamp_str)
        except ValueError:
            raise ValueError('Invalid timestamp format')
    return datetime.datetime.now()


def _decode_batch(batch_data: bytes) -> List[Dict]:
    """Decode raw batch bytes into a list of transaction dictionaries."""
    try:
        transactions = json.loads(batch_data.decode(FILE_ENCODING))
    except json.JSONDecodeError as e:
        raise ValueError(f'Invalid JSON format: {str(e)}')
    if not isinstance(transactions, list):
        raise ValueError('Transaction batch must be a list')
    return transactions


def _transaction_from_batch_entry(tx_data: Any) -> 'Transaction':
    """Build a Transaction from an untrusted batch entry."""
    if not isinstance(tx_data, dict):
        raise ValueError('Transaction must be a dictionary')
    if not all((field in tx_data for field in REQUIRED_TRANSACTION_FIELDS)):
        raise ValueError('Missing required transaction fields')
    timestamp = _parse_timestamp(tx_data.get('timestamp'))
    tx = Transaction(
        sender=str(tx_data['sender']),
        recipient=str(tx_data['recipient']),
        amount=float(tx_data['amount']),
        timestamp=timestamp,
    )
    if 'signature' in tx_data:
        tx.signature = str(tx_data['signature'])
    return tx


def _transaction_from_state(tx_data: Dict) -> 'Transaction':
    """Rebuild a Transaction from its persisted dictionary form."""
    tx = Transaction(
        sender=tx_data['sender'],
        recipient=tx_data['recipient'],
        amount=tx_data['amount'],
        timestamp=datetime.datetime.fromisoformat(tx_data['timestamp']),
    )
    tx.transaction_id = tx_data['transaction_id']
    tx.signature = tx_data.get('signature')
    return tx


def _serialize_audit_entry(entry: Dict) -> Dict:
    return {
        'timestamp': entry['timestamp'].isoformat(),
        'event_type': entry['event_type'],
        'details': entry['details'],
    }


def _deserialize_audit_entry(entry: Dict) -> Dict:
    return {
        'timestamp': datetime.datetime.fromisoformat(entry['timestamp']),
        'event_type': entry['event_type'],
        'details': entry['details'],
    }


# --------------------------------------------------------------------------- #
# Domain classes
# --------------------------------------------------------------------------- #

class Transaction:

    def __init__(self, sender: str, recipient: str, amount: float, timestamp: datetime.datetime):
        self.sender = sender
        self.recipient = recipient
        self.amount = amount
        self.timestamp = timestamp
        self.transaction_id = self._generate_id()
        self.signature: Optional[str] = None

    def _generate_id(self) -> str:
        data = f'{self.sender}{self.recipient}{self.amount}{self.timestamp}'
        return hashlib.sha256(data.encode()).hexdigest()

    def to_dict(self) -> Dict:
        return {
            'sender': self.sender,
            'recipient': self.recipient,
            'amount': self.amount,
            'timestamp': self.timestamp.isoformat(),
            'transaction_id': self.transaction_id,
            'signature': self.signature,
        }


class TransactionProcessor:

    def __init__(self):
        self.pending_transactions: List[Transaction] = []
        self.processed_transactions: Dict[str, Transaction] = {}
        self.account_balances: Dict[str, float] = {}
        self.audit_log: List[Dict] = []

    # ---- batch loading ---------------------------------------------------- #

    def load_transaction_batch(self, batch_data: bytes) -> bool:
        try:
            transactions = _decode_batch(batch_data)
            return self._process_batch(transactions)
        except Exception as e:
            self._log_audit(EVENT_BATCH_LOAD_FAILURE, str(e))
            return False

    def _process_batch(self, transactions: List[Dict]) -> bool:
        for tx_data in transactions:
            try:
                tx = _transaction_from_batch_entry(tx_data)
                self._validate_transaction(tx)
                self.pending_transactions.append(tx)
                self._log_audit(EVENT_TRANSACTION_QUEUED, tx.transaction_id)
            except Exception as e:
                self._log_audit(EVENT_TRANSACTION_REJECTED, str(e))
        return True

    # ---- validation ------------------------------------------------------- #

    def _ensure_account(self, account_id: str) -> None:
        if account_id not in self.account_balances:
            self.account_balances[account_id] = DEFAULT_ACCOUNT_BALANCE

    def _validate_transaction(self, tx: Transaction) -> None:
        if tx.amount <= 0:
            raise ValueError('Invalid transaction amount')
        if not isinstance(tx.sender, str) or not tx.sender:
            raise ValueError('Invalid sender')
        if not isinstance(tx.recipient, str) or not tx.recipient:
            raise ValueError('Invalid recipient')
        self._ensure_account(tx.sender)
        self._ensure_account(tx.recipient)
        if self.account_balances[tx.sender] < tx.amount:
            raise ValueError('Insufficient funds')

    # ---- processing ------------------------------------------------------- #

    def _apply_transaction(self, tx: Transaction) -> None:
        self.account_balances[tx.sender] -= tx.amount
        self.account_balances[tx.recipient] += tx.amount
        self.processed_transactions[tx.transaction_id] = tx

    def process_pending_transactions(self) -> None:
        for tx in self.pending_transactions:
            try:
                self._apply_transaction(tx)
                self._log_audit(EVENT_TRANSACTION_PROCESSED, tx.transaction_id)
            except Exception as e:
                self._log_audit(EVENT_TRANSACTION_FAILED, str(e))
        self.pending_transactions.clear()

    # ---- auditing / queries ----------------------------------------------- #

    def _log_audit(self, event_type: str, details: str) -> None:
        self.audit_log.append({
            'timestamp': datetime.datetime.now(),
            'event_type': event_type,
            'details': details,
        })

    def get_balance(self, account_id: str) -> float:
        return self.account_balances.get(account_id, 0.0)

    # ---- persistence ------------------------------------------------------ #

    def save_state(self, file_path: str) -> None:
        state = {
            'processed_transactions': {
                tx_id: tx.to_dict() for (tx_id, tx) in self.processed_transactions.items()
            },
            'account_balances': self.account_balances,
            'audit_log': [_serialize_audit_entry(entry) for entry in self.audit_log],
        }
        with open(file_path, 'w', encoding=FILE_ENCODING) as f:
            json.dump(state, f, indent=STATE_JSON_INDENT)

    def _restore_transactions(self, serialized: Dict[str, Dict]) -> None:
        self.processed_transactions = {}
        for (tx_id, tx_data) in serialized.items():
            try:
                self.processed_transactions[tx_id] = _transaction_from_state(tx_data)
            except Exception as e:
                self._log_audit(
                    EVENT_STATE_LOAD_ERROR,
                    f'Failed to load transaction {tx_id}: {str(e)}',
                )

    def _restore_audit_log(self, serialized: List[Dict]) -> None:
        self.audit_log = []
        for entry in serialized:
            try:
                self.audit_log.append(_deserialize_audit_entry(entry))
            except Exception as e:
                self._log_audit(
                    EVENT_STATE_LOAD_ERROR,
                    f'Failed to load audit entry: {str(e)}',
                )

    def load_state(self, file_path: str) -> None:
        with open(file_path, 'r', encoding=FILE_ENCODING) as f:
            state = json.load(f)
            self._restore_transactions(state['processed_transactions'])
            self.account_balances = state['account_balances']
            self._restore_audit_log(state['audit_log'])


class FinancialSystem:

    def __init__(self):
        self.processor = TransactionProcessor()

    def process_transaction_file(self, file_path: str) -> None:
        try:
            with open(file_path, 'rb') as f:
                data = f.read()
                if self.processor.load_transaction_batch(data):
                    self.processor.process_pending_transactions()
                    print('Transactions processed successfully')
                else:
                    print('Failed to process transactions')
        except Exception as e:
            print(f'Error processing file: {str(e)}')

    def print_balances(self) -> None:
        print('\nAccount Balances:')
        for (account, balance) in self.processor.account_balances.items():
            print(f'{account}: {balance:.2f}')

    def print_audit_log(self, num_entries: int = DEFAULT_AUDIT_ENTRIES) -> None:
        print(f'\nLast {num_entries} audit entries:')
        for entry in self.processor.audit_log[-num_entries:]:
            print(f"{entry['timestamp']} - {entry['event_type']}: {entry['details']}")


# --------------------------------------------------------------------------- #
# Command-line interface
# --------------------------------------------------------------------------- #

def _print_menu() -> None:
    print('\n1. Process transaction file')
    print('2. Show account balances')
    print('3. Show audit log')
    print('4. Exit')


def _handle_process_file(system: FinancialSystem) -> None:
    file_path = input('Enter transaction file path: ').strip()
    if not file_path:
        print('Error: File path cannot be empty')
        return
    system.process_transaction_file(file_path)


def main():
    system = FinancialSystem()
    print('Financial Transaction System')
    while True:
        _print_menu()
        choice = input('Select option: ').strip()
        if choice == MENU_PROCESS_FILE:
            _handle_process_file(system)
        elif choice == MENU_SHOW_BALANCES:
            system.print_balances()
        elif choice == MENU_SHOW_AUDIT_LOG:
            system.print_audit_log()
        elif choice == MENU_EXIT:
            break
        else:
            print('Invalid option')


if __name__ == '__main__':
    main()
