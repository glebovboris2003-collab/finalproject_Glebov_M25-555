class InsufficientFundsError(Exception):
    def __init__(self, available: float, code: str, required: float):
        self.available = available
        self.code = code
        self.required = required
        super().__init__(f"Недостаточно средств: доступно {available} {code}, требуется {required} {code}")

class CurrencyNotFoundError(Exception):
    def __init__(self, code: str):
        self.code = code
        super().__init__(f"Неизвестная валюта '{code}'")

class ApiRequestError(Exception):
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(f"Ошибка при обращении к внешнему API: {reason}")

class RatesCacheExpiredError(Exception):
    def __init__(self, message: str):
        super().__init__(f"Кэш курсов устарел или отсутствует: {message}")