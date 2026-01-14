from exceptions import InsufficientFundsError, CurrencyNotFoundError, ApiRequestError
from abc import ABC, abstractmethod
from datetime import datetime, timedelta

# Реестр валют (фабрика)
currencies = {}
class Currency(ABC):
    def __init__(self, name: str, code: str):
        # Валидация name
        if not isinstance(name, str) or not name.strip():
            raise ValueError("name must be a non-empty string")
        self.name = name

        # Валидация code
        if not isinstance(code, str):
            raise ValueError("code must be a string")
        code_upper = code.upper()
        if not (2 <= len(code_upper) <= 5) or ' ' in code_upper:
            raise ValueError("code must be 2-5 characters, uppercase, no spaces")
        self.code = code_upper

    @abstractmethod
    def get_display_info(self) -> str:
        pass

    def needs_rate_update(last_refresh_str: str, ttl_seconds: int) -> bool:
        """Проверяет, нужно ли обновлять курсы по TTL."""
        try:
            last_refresh = datetime.fromisoformat(last_refresh_str)
        except Exception:
            return True
        return datetime.utcnow() - last_refresh > timedelta(seconds=ttl_seconds)

# Наследник: FiatCurrency
class FiatCurrency(Currency):
    def __init__(self, name: str, code: str, issuing_country: str):
        super().__init__(name, code)
        if not isinstance(issuing_country, str) or not issuing_country.strip():
            raise ValueError("issuing_country must be a non-empty string")
        self.issuing_country = issuing_country

    def get_display_info(self) -> str:
        return f"[FIAT] {self.code} — {self.name} (Issuing: {self.issuing_country})"

# Наследник: CryptoCurrency
class CryptoCurrency(Currency):
    def __init__(self, name: str, code: str, algorithm: str, market_cap: float):
        super().__init__(name, code)
        if not isinstance(algorithm, str) or not algorithm.strip():
            raise ValueError("algorithm must be a non-empty string")
        if not isinstance(market_cap, (int, float)) or market_cap <= 0:
            raise ValueError("market_cap must be a positive number")
        self.algorithm = algorithm
        self.market_cap = market_cap

    def get_display_info(self) -> str:
        return f"[CRYPTO] {self.code} — {self.name} (Algo: {self.algorithm}, MCAP: {self.market_cap:.2e})"



    def register_currency(currency: Currency):
        """Добавляет валюту в реестр."""
        currencies[currency.code] = currency

    def get_currency(code: str) -> Currency:
        """Возвращает валюту по коду, или выбрасывает исключение."""
        code_upper = code.upper()
        if code_upper not in currencies:
            raise CurrencyNotFoundError(f"Currency with code '{code}' not found")
        return currencies[code_upper]       

