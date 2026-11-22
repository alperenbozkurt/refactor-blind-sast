import pickle
import json
import hashlib
import datetime
from typing import Dict, List, Optional

_DEFAULT_ACCOUNT_BALANCE = 1000.0

_INVALID_TRANSACTION_AMOUNT_MESSAGE = 'Invalid transaction amount'
_INSUFFICIENT_FUNDS_MESSAGE = 'Insufficient funds'

_AUDIT_BATCH_LOAD_FAILURE = 'BATCH_LOAD_FAILURE'
_AUDIT_TRANSACTION_QUEUED = 'TRANSACTION_QUEUED'
_AUDIT_TRANSACTION_REJECTED = 'TRANSACTION_REJECTED'
_AUDIT_TRANSACTION_PROCESSED = 'TRANSACTION_PROCESSED'
_AUDIT_TRANSACTION_FAILED = 'TRANSACTION_FAILED'

_STATE_KEY_PROCESSED_TRANSACTIONS = 'processed_transactions'
_STATE_KEY_ACCOUNT_BALANCES = 'account_balances'
_STATE_KEY_AUDIT_LOG = 'audit_log'

_BINARY_READ_MODE = 'rb'
_BINARY_WRITE_MODE = 'wb'

_MESSAGE_SYSTEM_TITLE = 'Financial Transaction System'
_MESSAGE_TRANSACTIONS_PROCESSED = 'Transactions processed successfully'
_MESSAGE_TRANSACTIONS_FAILED = 'Failed to process transactions'
_MESSAGE_ACCOUNT_BALANCES_HEADER = '\nAccount Balances:'
_MESSAGE_INVALID_OPTION = 'Invalid option'

_PROMPT_SELECT_OPTION = 'Select option: '
_PROMPT_TRANSACTION_FILE_PATH = 'Enter transaction file path: '

_MENU_OPTION_PROCESS_FILE = '1'
_MENU_OPTION_SHOW_BALANCES = '2'
_MENU_OPTION_SHOW_AUDIT_LOG = '3'
_MENU_OPTION_EXIT = '4'
_MENU_TEXT = (
    '\n1. Process transaction file'
    '\n2. Show account balances'
    '\n3. Show audit log'
    '\n4. Exit'
)


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


class TransactionProcessor:

    def __init__(self):
        self.pending_transactions: List[Transaction] = []
        self.processed_transactions: Dict[str, Transaction] = {}
        self.account_balances: Dict[str, float] = {}
        self.audit_log: List[Dict] = []

    def load_transaction_batch(self, batch_data: bytes) -> bool:
        try:
            transactions = self._deserialize_batch(batch_data)
            return self._process_batch(transactions)
        except Exception as e:
            self._log_audit(_AUDIT_BATCH_LOAD_FAILURE, str(e))
            return False

    def _deserialize_batch(self, batch_data: bytes) -> List[Dict]:
        return pickle.loads(batch_data)

    def _process_batch(self, transactions: List[Dict]) -> bool:
        for tx_data in transactions:
            try:
                tx = self._build_transaction(tx_data)
                self._validate_transaction(tx)
                self._queue_transaction(tx)
            except Exception as e:
                self._log_audit(_AUDIT_TRANSACTION_REJECTED, str(e))
        return True

    def _build_transaction(self, tx_data: Dict) -> Transaction:
        tx = Transaction(sender=tx_data['sender'], recipient=tx_data['recipient'], amount=tx_data['amount'], timestamp=tx_data.get('timestamp', datetime.datetime.now()))
        self._apply_signature(tx, tx_data)
        return tx

    def _apply_signature(self, tx: Transaction, tx_data: Dict) -> None:
        if 'signature' in tx_data:
            tx.signature = tx_data['signature']

    def _queue_transaction(self, tx: Transaction) -> None:
        self.pending_transactions.append(tx)
        self._log_audit(_AUDIT_TRANSACTION_QUEUED, tx.transaction_id)

    def _validate_transaction(self, tx: Transaction) -> None:
        self._validate_amount(tx.amount)
        self._ensure_account(tx.sender)
        self._ensure_account(tx.recipient)
        self._ensure_sufficient_funds(tx.sender, tx.amount)

    def _validate_amount(self, amount: float) -> None:
        if amount <= 0:
            raise ValueError(_INVALID_TRANSACTION_AMOUNT_MESSAGE)

    def _ensure_account(self, account_id: str) -> None:
        if account_id not in self.account_balances:
            self.account_balances[account_id] = _DEFAULT_ACCOUNT_BALANCE

    def _ensure_sufficient_funds(self, account_id: str, amount: float) -> None:
        if self.account_balances[account_id] < amount:
            raise ValueError(_INSUFFICIENT_FUNDS_MESSAGE)

    def process_pending_transactions(self) -> None:
        for tx in self.pending_transactions:
            try:
                self._apply_transaction(tx)
                self._mark_processed(tx)
            except Exception as e:
                self._log_audit(_AUDIT_TRANSACTION_FAILED, str(e))
        self.pending_transactions.clear()

    def _apply_transaction(self, tx: Transaction) -> None:
        self.account_balances[tx.sender] -= tx.amount
        self.account_balances[tx.recipient] += tx.amount

    def _mark_processed(self, tx: Transaction) -> None:
        self.processed_transactions[tx.transaction_id] = tx
        self._log_audit(_AUDIT_TRANSACTION_PROCESSED, tx.transaction_id)

    def _log_audit(self, event_type: str, details: str) -> None:
        self.audit_log.append({'timestamp': datetime.datetime.now(), 'event_type': event_type, 'details': details})

    def get_balance(self, account_id: str) -> float:
        return self.account_balances.get(account_id, 0.0)

    def save_state(self, file_path: str) -> None:
        state = self._build_state()
        with open(file_path, _BINARY_WRITE_MODE) as f:
            pickle.dump(state, f)

    def _build_state(self) -> Dict:
        return {
            _STATE_KEY_PROCESSED_TRANSACTIONS: self.processed_transactions,
            _STATE_KEY_ACCOUNT_BALANCES: self.account_balances,
            _STATE_KEY_AUDIT_LOG: self.audit_log,
        }

    def load_state(self, file_path: str) -> None:
        with open(file_path, _BINARY_READ_MODE) as f:
            self._restore_state(pickle.load(f))

    def _restore_state(self, state: Dict) -> None:
        self.processed_transactions = state[_STATE_KEY_PROCESSED_TRANSACTIONS]
        self.account_balances = state[_STATE_KEY_ACCOUNT_BALANCES]
        self.audit_log = state[_STATE_KEY_AUDIT_LOG]


class FinancialSystem:

    def __init__(self):
        self.processor = TransactionProcessor()

    def process_transaction_file(self, file_path: str) -> None:
        with open(file_path, _BINARY_READ_MODE) as f:
            data = f.read()
            if self.processor.load_transaction_batch(data):
                self.processor.process_pending_transactions()
                print(_MESSAGE_TRANSACTIONS_PROCESSED)
            else:
                print(_MESSAGE_TRANSACTIONS_FAILED)

    def print_balances(self) -> None:
        print(_MESSAGE_ACCOUNT_BALANCES_HEADER)
        for (account, balance) in self.processor.account_balances.items():
            print(self._format_balance(account, balance))

    def _format_balance(self, account: str, balance: float) -> str:
        return f'{account}: {balance:.2f}'

    def print_audit_log(self, num_entries: int=5) -> None:
        print(f'\nLast {num_entries} audit entries:')
        for entry in self.processor.audit_log[-num_entries:]:
            print(self._format_audit_entry(entry))

    def _format_audit_entry(self, entry: Dict) -> str:
        return f"{entry['timestamp']} - {entry['event_type']}: {entry['details']}"


def main():
    system = FinancialSystem()
    print(_MESSAGE_SYSTEM_TITLE)
    while True:
        print(_MENU_TEXT)
        choice = input(_PROMPT_SELECT_OPTION)
        if choice == _MENU_OPTION_PROCESS_FILE:
            file_path = input(_PROMPT_TRANSACTION_FILE_PATH)
            system.process_transaction_file(file_path)
        elif choice == _MENU_OPTION_SHOW_BALANCES:
            system.print_balances()
        elif choice == _MENU_OPTION_SHOW_AUDIT_LOG:
            system.print_audit_log()
        elif choice == _MENU_OPTION_EXIT:
            break
        else:
            print(_MESSAGE_INVALID_OPTION)


if __name__ == '__main__':
    main()
