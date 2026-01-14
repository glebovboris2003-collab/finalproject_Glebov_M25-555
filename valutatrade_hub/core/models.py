# vaultatrade_hub/core/models.py

from dataclasses import dataclass
from typing import Dict, Any
from datetime import datetime
import hashlib
import json
import os
from abc import ABC, abstractmethod
from .exceptions import InsufficientFundsError, CurrencyNotFoundError, ApiRequestError
import threading
from valutatrade_hub.infra import settings

def save_json(file_path, data):
    with open(file_path, 'w') as f:
        json.dump(data, f, indent=4)

config = settings.SettingsLoader()  # Создаст или вернет существующий экземпляр

PORTFOLIOS_FILE = config.get('path_to_json', 'data/portfolios.json')
RATES_FILE = config.get('path_to_json', 'data/rates.json')

def load_json(file_path):
    if os.path.exists(file_path):
        with open(file_path, 'r') as f:
            return json.load(f)
    return {}



@dataclass
class User:
    def __init__(self, user_id: int, username: str, hashed_password: str, salt: str, registration_date: datetime):
            self._user_id = user_id
            self._username = username
            self._hashed_password = hashed_password
            self._salt = salt
            self._registration_date = registration_date
    # Геттеры и сеттеры

    @property
    def user_id(self):
        return self._user_id

    @property
    def username(self):
        return self._username

    @username.setter
    def username(self, value):
        if not value:
            raise ValueError("Имя не может быть пустым.")
        self._username = value

    @property
    def registration_date(self):
        return self._registration_date

    # Методы класса

    def get_user_info(self):
        return {
            "user_id": self._user_id,
            "username": self._username,
            "registration_date": self._registration_date.strftime('%Y-%m-%d %H:%M:%S')
        }

    def change_password(self, new_password: str):
        if len(new_password) < 4:
            raise ValueError("Пароль должен быть не короче 4 символов.")
        # Генерируем новый соль, если нужно, или используем существующую
        # Для простоты используем существующую соль
        self._hashed_password = self._hash_password(new_password, self._salt)

    def verify_password(self, password: str) -> bool:
        hashed_input = self._hash_password(password, self._salt)
        return hashed_input == self._hashed_password

    def _hash_password(self, password: str, salt: str) -> str:
        # Простое одностороннее хеширование
        return hashlib.sha256((password + salt).encode('utf-8')).hexdigest()

@dataclass
class Wallet:
    def __init__(self, currency_code: str, balance: float = 0.0):
            self.currency_code = currency_code
            self._balance = balance if balance >= 0 else 0.0

    @property
    def balance(self):
        return self._balance

    @balance.setter
    def balance(self, value):
        if not isinstance(value, (int, float)):
            raise TypeError("Баланс должен быть числом.")
        if value < 0:
            raise ValueError("Баланс не может быть отрицательным.")
        self._balance = float(value)

    def deposit(self, amount: float):
        if not isinstance(amount, (int, float)):
            raise TypeError("Сумма пополнения должна быть числом.")
        if amount <= 0:
            raise ValueError("Сумма пополнения должна быть положительной.")
        self._balance += amount

    def withdraw(self, amount: float):
        if not isinstance(amount, (int, float)):
            raise TypeError("Сумма снятия должна быть числом.")
        if amount <= 0:
            raise ValueError("Сумма снятия должна быть положительной.")
        if amount > self._balance:
            raise ValueError("Недостаточно средств на балансе.")
        # print(self._balance)
        self._balance -= amount
        # print(self._balance)

    def get_balance_info(self):
        return {
            "currency_code": self.currency_code,
            "balance": self._balance
        }
# vaultatrade_hub/core/models.py

class Portfolio:
    # Фиктивные курсы валют для конвертации
    rates = load_json(RATES_FILE)

    def __init__(self, user_id: int, user, wallets=None):
        self._user_id = user_id
        self._user = user  # объект пользователя
        self._wallets = wallets if wallets is not None else {}

    @property
    def user(self):
        return self._user

    @property
    def wallets(self):
        # возвращает копию словаря
        return self._wallets.copy()

    def add_currency(self, currency_code: str):
        if currency_code in self._wallets:
            raise ValueError(f"Кошелек для {currency_code} уже существует.")
        self._wallets[currency_code] = Wallet(currency_code)


    def get_wallet(self, user_id: int, currency_code: str):
        wallets_list = self._wallets
        user_wallet_info = next(filter(lambda w: w['user_id'] == int(self._user_id), wallets_list), None)
        if user_wallet_info is None:
            raise CurrencyNotFoundError("Пользовательский кошелек не найден.")
        wallets = user_wallet_info['wallets']
        # print(currency_code)
        wallet_data = wallets.get(currency_code)
        # print(wallet_data)
        if wallet_data is None:
            raise CurrencyNotFoundError(f"Кошелек для валюты {currency_code} не найден.")
        # создать объект Wallet из данных
        return Wallet(currency_code, wallet_data['balance'])

    def get_total_value(self, base_currency='USD'):
        if base_currency not in self.rates:
            raise ValueError(f"Курс для {base_currency} не определен.")
        total = 0.0
        for wallet in self._wallets.values():
            rate = self.rates.get(wallet.currency_code)
            if rate is None:
                continue  # пропускаем валюты без курса
            # Конвертируем баланс в базовую валюту
            total += wallet.balance * rate / self.rates[wallet.currency_code]
        # В данном случае, поскольку rate уже в курсе относительно USD,
        # можно просто умножить баланс на курс
        return total
    def buy_currency(self, currency_code: str, amount: float):
        # Получаем объект кошелька USD
        usd_wallet = self.get_wallet(self._user_id, 'USD')
        if usd_wallet is None:
            raise ValueError("Отсутствует кошелек USD.")
        if amount <= 0:
            raise ValueError("Сумма покупки должна быть положительной.")

        rate_info = self.rates.get("pairs").get(f"{currency_code}_USD")
        if rate_info is None:
            raise CurrencyNotFoundError(f"Курс для {currency_code} не найден.")
        rate = rate_info.get('rate')
        if rate is None:
            raise CurrencyNotFoundError(f"Некорректный курс для {currency_code}.")

        cost_in_usd = amount * rate

        if usd_wallet.balance < cost_in_usd:
            raise InsufficientFundsError("Недостаточно средств на USD кошельке.")

        # списываем USD
        # print(f"Баланс USD до списания: {usd_wallet.balance}") #105000.0
        usd_wallet.withdraw(cost_in_usd)
        # print(f"Баланс USD после списания: {usd_wallet.balance}") #104821.98837
        # print(self._wallets) #[{'user_id': 1, 'wallets': {'USD': {'balance': 105000.0}, 'BTC': {'balance': 8.06202}, 'EUR': {'balance': 20.0}}}]
        for user_wallet in self._wallets:
            if user_wallet['user_id'] == int(self._user_id):
                user_wallet['wallets']['USD']['balance'] = usd_wallet.balance
                break

        save_json(PORTFOLIOS_FILE, self._wallets)  # сохраняем после списания

        # добавляем валюту в кошелек пользователя
        wallets_list = self._wallets
        user_wallet_info = next(filter(lambda w: w['user_id'] == int(self._user_id), wallets_list), None)        
        if user_wallet_info is None:
            raise ValueError("Пользователь не найден.")

        wallets = user_wallet_info['wallets']
        # Обновляем баланс в структуре
        if currency_code in wallets:
            wallet_obj = Wallet(currency_code, wallets[currency_code]['balance'])
            wallet_obj.deposit(amount)
            wallets[currency_code]['balance'] = wallet_obj.balance
        else:
            new_wallet = Wallet(currency_code, 0)
            new_wallet.deposit(amount)
            wallets[currency_code] = {'balance': new_wallet.balance}        # Сохраняем изменения в файл
        save_json(PORTFOLIOS_FILE, self._wallets)

    def sell_currency(self, currency_code: str, amount: float):
        """
        Продажа валюты: списание из кошелька валюты, зачисление в USD.
        """
        wallet = self.get_wallet(self._user_id, currency_code)
        if wallet is None:
            raise ValueError(f"Кошелек для {currency_code} не найден.")
        if amount <= 0:
            raise ValueError("Сумма продажи должна быть положительной.")
        if wallet.balance < amount:
            raise InsufficientFundsError("Недостаточно средств в кошельке валюты.")

        # Получаем курс для обмена
        rate_info = self.rates.get("pairs").get(f"{currency_code}_USD")
        if rate_info is None:
            raise CurrencyNotFoundError(f"Курс для {currency_code} не найден.")
        rate = rate_info.get('rate')
        if rate is None:
            raise CurrencyNotFoundError(f"Некорректный курс для {currency_code}.")

        # Рассчитываем сумму в USD
        amount_in_usd = amount * rate

        # Списываем валюту из кошелька
        wallet.withdraw(amount)

        # Обновляем баланс этой валюты в self._wallets
        for user_wallet in self._wallets:
            if user_wallet['user_id'] == int(self._user_id):
                user_wallet['wallets'][currency_code]['balance'] = wallet.balance
                break

        # Обновляем баланс USD
        usd_wallet = self.get_wallet(self._user_id, 'USD')
        if usd_wallet is None:
            self.add_currency('USD')
            usd_wallet = self.get_wallet(self._user_id, 'USD')

        usd_wallet.deposit(amount_in_usd)

        # Обновляем баланс USD в self._wallets
        for user_wallet in self._wallets:
            if user_wallet['user_id'] == int(self._user_id):
                user_wallet['wallets']['USD']['balance'] = usd_wallet.balance
                break

        # Сохраняем изменения
        save_json(PORTFOLIOS_FILE, self._wallets)


# # Исключение для неизвестных валют
# class CurrencyNotFoundError(Exception):
#     pass

# Абстрактный базовый класс Currency
@dataclass
class Rate:
    currency_from: str
    currency_to: str
    rate: float