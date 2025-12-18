from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional


# ===================== MODELS =====================

@dataclass
class Transaction:
    time: str
    type: str
    amount: int
    balance: int
    card: str
    note: str = ""


class Card:
    MAX_PIN_TRY = 3

    def __init__(self, number: str, pin: str, card_type: str, expiry: str):
        self._number = number
        self._pin = pin
        self.type = card_type
        self.expiry = expiry
        self.blocked = False
        self.pin_tries = 0
        self.daily_limit = 5_000_000
        self.used_today = 0

    def masked(self) -> str:
        return f"{self._number[:4]} **** **** {self._number[-4:]}"

    def verify_pin(self, pin: str) -> bool:
        if self.blocked:
            return False

        if pin == self._pin:
            self.pin_tries = 0
            return True

        self.pin_tries += 1
        if self.pin_tries >= self.MAX_PIN_TRY:
            self.blocked = True
        return False

    def change_pin(self, old: str, new: str) -> tuple:
        if not self.verify_pin(old):
            return False, "Eski PIN noto‘g‘ri"

        if not (new.isdigit() and len(new) == 4):
            return False, "PIN 4 xonali bo‘lishi kerak"

        self._pin = new
        return True, "PIN muvaffaqiyatli o‘zgartirildi"

    def can_spend(self, amount: int) -> bool:
        return self.used_today + amount <= self.daily_limit

    def spend(self, amount: int):
        self.used_today += amount


class Account:
    def __init__(self, number: str, owner: str, balance: int = 0):
        self.number = number
        self.owner = owner
        self._balance = balance
        self.cards: List[Card] = []
        self.transactions: List[Transaction] = []
        self.opened = datetime.now()

    @property
    def balance(self) -> int:
        return self._balance

    def add_card(self, card: Card):
        self.cards.append(card)

    def deposit(self, amount: int):
        self._balance += amount

    def withdraw(self, amount: int):
        self._balance -= amount

    def add_transaction(self, t: Transaction):
        self.transactions.append(t)


# ===================== SERVICES =====================

class AccountService:
    WITHDRAW_LIMIT = 2_000_000
    COMMISSION = 0.01

    def withdraw(self, acc: Account, amount: int, card: Card) -> tuple:
        if amount <= 0 or amount % 10_000 != 0:
            return False, "Summa 10 000 ga karrali bo‘lishi kerak"

        if amount > acc.balance:
            return False, "Yetarli mablag‘ yo‘q"

        if amount > self.WITHDRAW_LIMIT:
            return False, "Maksimal limit oshdi"

        if not card.can_spend(amount):
            return False, "Kunlik limit tugadi"

        acc.withdraw(amount)
        card.spend(amount)
        self._log(acc, "Pul olish", -amount, card)
        return True, f"{amount:,} so‘m yechildi"

    def deposit(self, acc: Account, amount: int):
        acc.deposit(amount)
        self._log(acc, "Pul qo‘yish", amount, None)

    def transfer(self, sender: Account, receiver: Account, amount: int, note="") -> tuple:
        fee = int(amount * self.COMMISSION)
        total = amount + fee

        if total > sender.balance:
            return False, "Komissiya bilan yetarli emas"

        sender.withdraw(total)
        receiver.deposit(amount)

        self._log(sender, f"O‘tkazma → {receiver.owner}", -total, None, note)
        self._log(receiver, "Qabul qilindi", amount, None)
        return True, "O‘tkazma bajarildi"

    def _log(self, acc: Account, ttype: str, amount: int,
             card: Optional[Card], note=""):
        acc.add_transaction(Transaction(
            time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            type=ttype,
            amount=amount,
            balance=acc.balance,
            card=card.masked() if card else "N/A",
            note=note
        ))


# ===================== ATM =====================

class ATM:
    def __init__(self, service: AccountService):
        self.service = service
        self.accounts = {}
        self.cards = {}
        self.current_account = None
        self.current_card = None

    def register(self, acc: Account):
        self.accounts[acc.number] = acc
        for c in acc.cards:
            self.cards[c._number] = (c, acc)

    def login(self, card_number: str, pin: str) -> bool:
        if card_number not in self.cards:
            return False

        card, acc = self.cards[card_number]
        if card.verify_pin(pin):
            self.current_account = acc
            self.current_card = card
            return True
        return False
