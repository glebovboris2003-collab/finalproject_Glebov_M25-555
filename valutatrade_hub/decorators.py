import functools
import logging
from datetime import datetime

logger = logging.getLogger('actions')

def log_action(action_type, verbose=False):
    """
    Декоратор для логирования действия.
    :param action_type: 'BUY', 'SELL', 'REGISTER', 'LOGIN'
    :param verbose: bool, добавлять дополнительный контекст
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start_time = datetime.utcnow()
            try:
                result = func(*args, **kwargs)
                status = 'OK'
                error_message = ''
            except Exception as e:
                result = 'ERROR'
                status = 'ERROR'
                error_message = str(e)
                # Логировать ошибку и пробросить дальше
                log_message = build_log_message(
                    start_time, action_type, args, kwargs, result, error_message, verbose
                )
                logger.info(log_message)
                raise
            # Лог успешного выполнения
            log_message = build_log_message(
                start_time, action_type, args, kwargs, result, '', verbose
            )
            logger.info(log_message)
            return result
        return wrapper
    return decorator

def build_log_message(start_time, action, args, kwargs, result, error_message, verbose):
    timestamp = start_time.isoformat()
    username = extract_username(args, kwargs)
    currency_code = extract_currency_code(args, kwargs)
    amount = extract_amount(args, kwargs)
    rate = extract_rate(args, kwargs)
    base = extract_base(args, kwargs)
    
    msg = f"{timestamp} {action} user='{username}' currency='{currency_code}' amount={amount} rate={rate} base='{base}' result={result}"
    if error_message:
        msg += f" error_message='{error_message}'"
    if verbose:
        # Добавить дополнительный контекст, например, состояние кошелька
        wallet_state = get_wallet_state(args, kwargs)
        msg += f" wallet_state={wallet_state}"
    return msg

# Вспомогательные функции для извлечения данных
def extract_username(args, kwargs):
    # Предполагается, что username передается как именованный аргумент или в args
    return kwargs.get('username') or (args[0] if args else 'unknown')

def extract_currency_code(args, kwargs):
    return kwargs.get('currency_code') or (args[1] if len(args) > 1 else 'UNKNOWN')

def extract_amount(args, kwargs):
    return kwargs.get('amount') or (args[2] if len(args) > 2 else '0')

def extract_rate(args, kwargs):
    return kwargs.get('rate') or 'N/A'

def extract_base(args, kwargs):
    return kwargs.get('base') or 'N/A'

def get_wallet_state(args, kwargs):
    # Заглушка, предполагается, что есть такой объект
    # Можно передать состояние как часть args или kwargs
    return kwargs.get('wallet_state', 'unknown')