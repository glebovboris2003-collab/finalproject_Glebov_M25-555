# vaultatrade_hub/core/usecases.py

from .models import User, Wallet, Rate, Portfolio
import json
from ..decorators import log_action
import currencies
from exceptions import (
    CurrencyNotFoundError,
    InsufficientFundsError,
    ApiRequestError
)
from valutatrade_hub.infra import settings
from valutatrade_hub.parser_service.api_clients import CoinGeckoClient, ExchangeRateApiClient
from valutatrade_hub.parser_service import updater
from valutatrade_hub.cli.interface import load_json, save_json, get_rate, get_exchange_rate_static
from valutatrade_hub.core.currencies import CryptoCurrency,FiatCurrency,Currency
from exceptions import RatesCacheExpiredError
import os
from ..decorators import log_action
import logging
from datetime import datetime

cur = CryptoCurrency()
config = settings.SettingsLoader()
@log_action('LOAD_USERS')
def load_users(file_path: str) -> dict[int, User]:
    with open(file_path, 'r') as f:
        users_data = json.load(f)
    users = {}
    for user in users_data:
        users[user['id']] = User(**user)
    return users

@log_action('LOAD_WALLETS')
def load_wallets(file_path: str) -> dict[int, Wallet]:
    with open(file_path, 'r') as f:
        wallets_data = json.load(f)
    wallets = {}
    for wallet in wallets_data:
        key = (wallet['user_id'], wallet['currency'])
        wallets[key] = Wallet(**wallet)
    return wallets

@log_action('LOAD_RATES')
def load_rates(file_path: str) -> dict[str, Rate]:
    with open(file_path, 'r') as f:
        rates_data = json.load(f)
    rates = {}
    for rate in rates_data:
        key = f"{rate['currency_from']}_{rate['currency_to']}"
        rates[key] = Rate(**rate)
    return rates

@log_action('CONVERT_CURRENCY')
def convert_currency(amount: float, rate: Rate) -> float:
    return amount * rate.rate

logger = logging.getLogger(__name__)

@log_action('BUY_CURRENCY')
def buy(user_id: int, currency_code: str, amount: float):
    if amount <= 0:
        raise ValueError("Сумма должна быть больше нуля.")
    
    currency_code = cur.get_currency(currency_code)

    rates_data = load_json(settings.SettingsLoader().get('rates_path', 'data/rates.json'))
    # Получаем курс к USD
    rate_to_usd = get_exchange_rate_static(currency_code, 'USD', rates_data)
    if rate_to_usd is None:
        raise ApiRequestError(f"Не удалось получить курс для {currency_code}")

    # Обновление портфеля
    portfolios = load_json(config.get('portfolios_path', 'data/portfolios.json'))
    # Предполагаем, что портфель - список dict, по user_id
    portfolio = next((p for p in portfolios if p['user_id'] == user_id), None)
    if not portfolio:
        # Создаем новый
        portfolio = {'user_id': user_id, 'wallets': {}}
        portfolios.append(portfolio)

    wallets = portfolio['wallets']
    wallet_data = wallets.get(currency_code)
    if not wallet_data:
        # Создаем кошелек
        wallets[currency_code] = {'balance': 0.0}
        wallet_data = wallets[currency_code]

    # Пополнение кошелька
    wallet_data['balance'] += amount

    # Сохраняем
    save_json(config.get('portfolios_path', 'data/portfolios.json'), portfolios)

    # Логирование
    logger.info(f"User {user_id} купил {amount} {currency_code} по курсу {rate_to_usd}")

@log_action('SELL_CURRENCY')
def sell(user_id: int, currency_code: str, amount: float):
    if amount <= 0:
        raise ValueError("Сумма должна быть больше нуля.")
    currency_code = cur.get_currency(currency_code)

    portfolios = load_json(config.get('portfolios_path', 'data/portfolios.json'))
    portfolio = next((p for p in portfolios if p['user_id'] == user_id), None)
    if not portfolio:
        raise InsufficientFundsError("Портфель пользователя не найден.")

    wallets = portfolio['wallets']
    wallet_data = wallets.get(currency_code)
    if not wallet_data or wallet_data['balance'] < amount:
        raise InsufficientFundsError(f"Недостаточно средств для продажи {amount} {currency_code}")

    # Получаем курс к USD
    rates_data = load_json(config.get('rates_path', 'data/rates.json'))
    rate_to_usd = get_exchange_rate_static(currency_code, 'USD', rates_data)
    if rate_to_usd is None:
        raise ApiRequestError(f"Не удалось получить курс для {currency_code}")

    # Списание
    wallet_data['balance'] -= amount

    save_json(config.get('portfolios_path', 'data/portfolios.json'), portfolios)

    # Логирование
    logger.info(f"User {user_id} продал {amount} {currency_code} по курсу {rate_to_usd}")

@log_action('GET_RATE')
def get_rate(from_code: str, to_code: str):
    from_code = cur.get_currency(from_code)
    to_code = cur.get_currency(to_code)

    # Проверка TTL и обновление кеша
    rates_path = config.get('rates_path', 'data/rates.json')
    rates_data = load_json(rates_path)
    last_refresh_str = rates_data.get('metadata', {}).get('last_refresh')

    ttl_seconds = settings.SettingsLoader().get('rates_ttl_seconds', 3600)

    if not last_refresh_str or cur.needs_rate_update(last_refresh_str, ttl_seconds):
        # Попытка обновления
        try:
            updater_instance = updater.RatesUpdater(
                api_clients=[
                    CoinGeckoClient(),
                    ExchangeRateApiClient(os.getenv("EXCHANGERATE_API_KEY"))
                ],
                storage=None  # Замените на нужный, если есть
            )
            updater_instance.run_update()
            rates_data = load_json(rates_path)
        except Exception as e:
            raise RatesCacheExpiredError("Требуется обновление курсов, но оно не удалось: " + str(e))

    # Получение курса
    rate_value = None
    key = f"{from_code}_{to_code}"
    rates_dict = rates_data.get('rates', {})
    if key in rates_dict:
        rate_value = rates_dict[key]
    else:
        # Обратный курс
        reverse_key = f"{to_code}_{from_code}"
        reverse_rate = rates_dict.get(reverse_key)
        if reverse_rate:
            rate_value = 1 / reverse_rate
        else:
            raise CurrencyNotFoundError(f"Курс для {from_code}→{to_code} не найден.")

    return {'rate': rate_value, 'updated_at': rates_data.get('metadata', {}).get('last_refresh')}