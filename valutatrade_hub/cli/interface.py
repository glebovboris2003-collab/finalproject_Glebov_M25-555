import argparse
import json
import os
import hashlib
from datetime import datetime
from valutatrade_hub.core import models
from valutatrade_hub.core.exceptions import InsufficientFundsError,CurrencyNotFoundError,ApiRequestError,RatesCacheExpiredError
from valutatrade_hub.infra import settings
from valutatrade_hub.parser_service import updater
from valutatrade_hub.parser_service.api_clients import CoinGeckoClient, ExchangeRateApiClient
from valutatrade_hub.parser_service import storage
import logging
# from logging_config import 

# Глобальные переменные для текущей сессии
current_user = None  # словарь с данными пользователя
current_user_id = None

config = settings.SettingsLoader()  # Создаст или вернет существующий экземпляр
USERS_FILE = config.get('path_to_json', 'data/users.json')
PORTFOLIOS_FILE = config.get('path_to_json', 'data/portfolios.json')
RATES_FILE = config.get('path_to_json', 'data/rates.json')

ttl_seconds = config.get('rates_ttl_seconds', 3600)
# USERS_FILE = 'data/users.json'
# PORTFOLIOS_FILE = 'data/portfolios.json'
# RATES_FILE = 'data/rates.json'
logger = logging.getLogger(__name__)
def load_json(file_path):
    if os.path.exists(file_path):
        with open(file_path, 'r') as f:
            return json.load(f)
    return {}

def save_json(file_path, data):
    with open(file_path, 'w') as f:
        json.dump(data, f, indent=4)

def hash_password(password, salt='somesalt'):
    return hashlib.sha256((password + salt).encode()).hexdigest()

def register(args):
    users = load_json(USERS_FILE)
    portfolios = load_json(PORTFOLIOS_FILE)

    username = args.username
    password = args.password

    # Проверка уникальности username
    if any(u['username'] == username for u in users):
        print(f"Имя пользователя '{username}' уже занято")
        return

    if len(password) < 4:
        print("Пароль должен быть не короче 4 символов")
        return

    # Генерация user_id
    # print(users[0])
    user_id = (len(users)) if users else 1

    hashed_pw = hash_password(password)
    user_data = {
        'user_id': user_id,
        'username': username,
        'hashed_password': hashed_pw,
        'registration_date': str(datetime.datetime.now())
    }
    users.append(user_data)

    # Создать портфель
    portfolios.append({
        'user_id': user_id,
        'wallets': {
   "USD": {"balance": 105000.0}}
    })
    

    save_json(USERS_FILE, users)
    save_json(PORTFOLIOS_FILE, portfolios)

    print(f"Пользователь '{username}' зарегистрирован (id={user_id}). Войдите: login --username {username} --password ****")


def login(args):
    global current_user, current_user_id
    users = load_json(USERS_FILE)

    username = args.username
    password = args.password

    user_entry = None
    for u in users:
        if u['username'] == username:
            user_entry = u
            break

    if not user_entry:
        print(f"Пользователь '{username}' не найден")
        return

    hashed_input = hash_password(password)
    if hashed_input != user_entry['hashed_password']:
        print("Неверный пароль")
        return

    current_user = user_entry
    current_user_id = str(user_entry['user_id'])
    print(f"Вы вошли как '{username}'")


def show_portfolio(args):
    global current_user, current_user_id
    if not current_user:
        print("Сначала выполните login")
        return

    portfolios = load_json(PORTFOLIOS_FILE)
    user_wallet_info = next(filter(lambda w: w['user_id'] == int(current_user_id), portfolios), None)
    wallets = user_wallet_info["wallets"]
    user_portfolio = wallets
    if not user_portfolio:
        print("Портфель не найден")
        return

    wallets = user_wallet_info.get('wallets', {})
    if not wallets:
        print("У вас нет кошельков")
        return

    base = args.base or 'USD'
    rates = load_json(RATES_FILE)

    # Проверка курса
    matching_item = next((item for item in rates.keys() if item.find(base) != -1), None)
    if matching_item ==-1:
        print(f"Неизвестная базовая валюта '{base}'")
        return

    total_value = 0.0
    print(f"Портфель пользователя '{current_user['username']}' (база: {base}):")
    for code, data in wallets.items():
        balance = data['balance']
        try:
            rate = get_exchange_rate_static(code, base, rates)
        except CurrencyNotFoundError as e:
            print(f"Ошибка: {str(e)}")
            continue
        # rate = get_exchange_rate_static(code, base, rates)
        
        if rate is None:
            print(f"Ошибка: Курс для {code} не найден")
            continue

        try:
            value_in_base = balance * rate
            total_value += value_in_base
            print(f"- {code}: {balance:.4f} → {value_in_base:.4f} {base}")
        except CurrencyNotFoundError as e:
            print(f"Ошибка: {str(e)}")

    print("---------------------------------")
    print(f"ИТОГО: {total_value:.2f} {base}")

def get_exchange_rate_static(from_code, to_code, rates):
    # Временная функция для получения курса из кеша rates.json
    # с учетом возможных обратных курсов.
    if from_code == to_code:
        return 1.0
    else:
        try:
            pairs = rates.get('pairs')
            if not pairs:
                raise CurrencyNotFoundError(f"Пары не найдены в данных: {rates}")
            pair_key = f"{from_code}_{to_code}"
            pair_data = pairs.get(pair_key)
            if not pair_data:
                raise CurrencyNotFoundError(f"Курс для пары {pair_key} не найден")
            rate = pair_data.get('rate')
            if rate is None:
                raise CurrencyNotFoundError(f"Курс для пары {pair_key} отсутствует")
            return rate
        except AttributeError:
            # Если rates.get('pairs') возвращает None, либо не словарь
            raise CurrencyNotFoundError(f"Некорректные данные для курса: {rates}")



def buy(args):
    global current_user, current_user_id
    if not current_user:
        print("Сначала выполните login")
        return
    currency = args.currency.upper()
    amount = args.amount

    if amount <= 0:
        print("'amount' должен быть положительным числом")
        return

    try:
        portfolios = load_json(PORTFOLIOS_FILE)
        portfolio = models.Portfolio(current_user_id, current_user, portfolios)
        portfolio.buy_currency(currency, amount)

        rate = get_exchange_rate_static(currency, 'USD', load_json(RATES_FILE))
        if rate is None:
            print(f"Не удалось получить курс для {currency}")
            return

        print(f"Покупка выполнена: {amount:.4f} {currency} по курсу {rate:.2f} USD/{currency}")
        print(f"Изменения в портфеле: +{amount:.4f} {currency}")
    except CurrencyNotFoundError as e:
        print(f"Ошибка: {str(e)}")
    except ApiRequestError as e:
        print(f"Ошибка API: {str(e)}")
    except Exception as e:
        print(f"Произошла ошибка при покупке: {str(e)}")
        logger.error(f"Ошибка при покупке для пользователя {current_user['username']}: {str(e)}")

def sell(args):
    global current_user, current_user_id
    if not current_user:
        print("Сначала выполните login")
        return
    currency = args.currency.upper()
    amount = args.amount

    if amount <= 0:
        print("'amount' должен быть положительным числом")
        return

    try:
        portfolios = load_json(PORTFOLIOS_FILE)
        portfolio = models.Portfolio(current_user_id, current_user, portfolios)
        portfolio.sell_currency(currency, amount)

        rate = get_exchange_rate_static(currency, 'USD', load_json(RATES_FILE))
        if rate is None:
            print(f"Не удалось получить курс для {currency}")
            return

        print(f"Продажа выполнена: {amount:.4f} {currency} по курсу {rate:.2f} USD/{currency}")
        print(f"Оценочная выручка: {amount * rate:.2f} USD")
    except InsufficientFundsError as e:
        print(f"Недостаточно средств: {str(e)}")
    except CurrencyNotFoundError as e:
        print(f"Ошибка: {str(e)}")
    except ApiRequestError as e:
        print(f"Ошибка API: {str(e)}")
    except Exception as e:
        print(f"Произошла ошибка при продаже: {str(e)}")
        logger.error(f"Ошибка при продаже для пользователя {current_user['username']}: {str(e)}")

def get_rate(args):
    try:
        from_code = args.from_.upper()
        to_code = args.to.upper()
        rates = load_json(RATES_FILE)
        rate = get_exchange_rate_static(from_code, to_code, rates)
        if rate is None:
            print(f"Курс {from_code}→{to_code} недоступен. Повторите попытку позже.")
            return
        # Обратный курс
        reverse_rate = 1 / rate if rate != 0 and rate is not None else None
        print(f"Курс {from_code}→{to_code}: {rate:.6f} (обновлено: {rates.get('last_refresh', 'неизвестно')})")
        if reverse_rate:
            print(f"Обратный курс {to_code}→{from_code}: {reverse_rate:.9f}")
    except CurrencyNotFoundError as e:
        print(f"Ошибка: {str(e)}")
    except RatesCacheExpiredError as e:
        print(f"Ошибка: {str(e)}")
    except ApiRequestError as e:
        print(f"Ошибка API: {str(e)}")
    except Exception as e:
        print(f"Произошла ошибка при получении курса: {str(e)}")
        logger.error(f"Ошибка при получении курса {args.from_}→{args.to}: {str(e)}")
    

def command_update_rates(args):
    print("INFO: Starting rates update...")
    try:
        # Инициализация клиентов
        clients = []
        if args.source is None or args.source.lower() == 'coingecko':
            clients.append(CoinGeckoClient())
        if args.source is None or args.source.lower() == 'exchangerate':
            EXCHANGERATE_API_KEY: str = os.getenv("EXCHANGERATE_API_KEY")
            API_KEY = EXCHANGERATE_API_KEY
            clients.append(ExchangeRateApiClient(API_KEY))

        updater_instance = updater.RatesUpdater(api_clients=clients, storage=storage)
        updater_instance.run_update()
        print(f"Update successful. Total rates updated: {len(clients)}")
        print(f"Last refresh: {datetime.utcnow().isoformat()}")
    except Exception as e:
        print(f"ERROR: {str(e)}")
        print("Update completed with errors. Check logs/parser.log for details.")

def command_show_rates(args):
    rates_path = RATES_FILE
    if not os.path.exists(rates_path):
        print("Локальный кеш курсов пуст. Выполните 'update-rates', чтобы загрузить данные.")
        return

    rates_data = load_json(rates_path)
    if not rates_data:
        print("Кеш пуст или не содержит данных.")
        return

    # Обработка фильтров
    base = args.base or 'USD'
    currency_filter = args.currency
    top_n = args.top

    # Поиск курса относительно базовой валюты
    relevant_rates = {}
    for key, value in rates_data.get('pairs', {}).items():
        # Предполагается, что ключи в формате CODE_CODE, например BTC_USD
        if base in key:
            relevant_rates[key] = value.get('rate')

    if not relevant_rates:
        print(f"Нет данных для базы '{base}'. Обновите курсы командой 'update-rates'.")
        return

    # Фильтр по валюте
    if currency_filter:
        filtered = {k: v for k, v in relevant_rates.items() if k.endswith(currency_filter) or k.startswith(currency_filter)}
        if not filtered:
            print(f"Курс для '{currency_filter}' не найден в кеше.")
            return
        relevant_rates = filtered

    # Сортировка
    # print(relevant_rates)
    # print(relevant_rates.items())
    sorted_rates = sorted(relevant_rates.items(), key=lambda item: item[1], reverse=(args.top is not None))

    print(f"Rates from cache (updated at {rates_data.get('last_refresh', {})}):")
    count = 0
    for key, data in sorted_rates:
        if args.top and count >= args.top:
            break
        print(f"- {key}: {data:.2f}")
        count += 1
# Настройка argparse
def main():
# Создаем парсер один раз
    parser = argparse.ArgumentParser(description='Crypto Portfolio CLI')
    subparsers = parser.add_subparsers(dest='command')

    # register
    parser_register = subparsers.add_parser('register', help='Зарегистрироваться')
    parser_register.add_argument('--username', required=True)
    parser_register.add_argument('--password', required=True)

    # login
    parser_login = subparsers.add_parser('login', help='Войти в систему')
    parser_login.add_argument('--username', required=True)
    parser_login.add_argument('--password', required=True)

    # show-portfolio
    parser_show = subparsers.add_parser('show-portfolio', help='Показать портфель')
    parser_show.add_argument('--base', default='USD')

    # buy
    parser_buy = subparsers.add_parser('buy', help='Купить валюту')
    parser_buy.add_argument('--currency', required=True)
    parser_buy.add_argument('--amount', type=float, required=True)

    # sell
    parser_sell = subparsers.add_parser('sell', help='Продать валюту')
    parser_sell.add_argument('--currency', required=True)
    parser_sell.add_argument('--amount', type=float, required=True)

    # get-rate
    parser_rate = subparsers.add_parser('get-rate', help='Получить курс валюты')
    parser_rate.add_argument('--from', dest='from_', required=True)
    parser_rate.add_argument('--to', required=True)
    
    # add update-rates
    parser_update = subparsers.add_parser('update-rates', help='Обновить курсы валют')
    parser_update.add_argument('--source', choices=['coingecko', 'exchangerate'], help='Источник данных')

    # add show-rates
    parser_show_rates = subparsers.add_parser('show-rates', help='Показать текущие курсы')
    parser_show_rates.add_argument('--currency', type=str, help='Фильтр по валюте (например BTC)')
    parser_show_rates.add_argument('--top', type=int, help='Показать N самых дорогих')
    parser_show_rates.add_argument('--base', type=str, default='USD', help='Базовая валюта (по умолчанию USD)')
    # exit
    parser_exit = subparsers.add_parser('exit', help='Выйти из программы')
    parser_exit.add_argument('--quit', action='store_true', help='Выйти из программы')

    while True:
        try:
            user_input = input("Введите команду (или 'exit' для выхода): ")  # читаем строку
            args = parser.parse_args(user_input.split())

            if args.command == 'exit':
                print("Выход из программы.")
                break

            if not args.command:
                print("Некорректная команда. Попробуйте снова.")
                continue

            # Вызов функций
            if args.command == 'register':
                register(args)
            elif args.command == 'login':
                login(args)
            elif args.command == 'show-portfolio':
                show_portfolio(args)
            elif args.command == 'buy':
                buy(args)
            elif args.command == 'sell':
                sell(args)
            elif args.command == 'get-rate':
                get_rate(args)
            elif args.command == 'update-rates':
                command_update_rates(args)
            elif args.command == 'show-rates':
                command_show_rates(args)

        except SystemExit:
            # Это чтобы parser не завершал программу при неправильном вводе
            print("Некорректная команда. Попробуйте снова.")
            continue
if __name__ == '__main__':
    main()