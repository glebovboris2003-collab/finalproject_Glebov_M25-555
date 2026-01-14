import requests
from abc import ABC, abstractmethod
from .config import ParserConfig

config = ParserConfig()
# Исключение для ошибок API-запросов
class ApiRequestError(Exception):
    pass

# Маппинг криптовалютных ID для CoinGecko
crypto_ids = config.CRYPTO_ID_MAP
# Базовый абстрактный класс
class BaseApiClient(ABC):
    @abstractmethod
    def fetch_rates(self) -> dict:
        pass

# Реализация CoinGeckoClient
class CoinGeckoClient(BaseApiClient):
    BASE_URL = config.COINGECKO_URL

    print(BASE_URL)
    print(crypto_ids.values())
    def __init__(self, crypto_ids=None, vs_currencies=None):
        # Например, по умолчанию
        # Маппинг криптовалютных ID для CoinGecko
        crypto_ids = config.CRYPTO_ID_MAP
        self.crypto_ids = list(crypto_ids.values())
        self.vs_currencies = vs_currencies or ['usd']
    
    def fetch_rates(self) -> dict:
        params = {
            'ids': ','.join(self.crypto_ids),
            'vs_currencies': ','.join(self.vs_currencies),
        }
        try:
            response = requests.get(self.BASE_URL, params=params, timeout=10)
            print(response)
            if response.status_code != 200:
                raise ApiRequestError(f'CoinGecko API error: status code {response.status_code}')
            data = response.json()
            # преобразуем в стандартный формат: {"BTC_USD": value, ...}
            rates = {}
            for crypto in self.crypto_ids:
                for currency in self.vs_currencies:
                    key = f"{crypto.upper()}_{currency.upper()}"
                    value = data.get(crypto, {}).get(currency)
                    if value is None:
                        raise ApiRequestError(f'Missing data for {key}')
                    rates[key] = value
            return rates
        except requests.exceptions.RequestException as e:
            raise ApiRequestError(f'Request failed: {e}')

# Реализация ExchangeRateApiClient
class ExchangeRateApiClient(BaseApiClient):
    BASE_URL = config.EXCHANGERATE_API_URL
    print(BASE_URL)
    def __init__(self, api_key: str, base_currency: str = 'USD'):
        self.api_key = api_key
        self.base_currency = base_currency.upper()

    def fetch_rates(self) -> dict:
        url = self.BASE_URL.format(self.base_currency)
        print('ExchangeRateApiClient')
        print(url)
        headers = {
            'Authorization': f'Bearer {self.api_key}'
        }
        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code != 200:
                raise ApiRequestError(f'ExchangeRate API error: status code {response.status_code}')
            data = response.json()
            # print(data)
            rates_data = data.get('conversion_rates')
            if rates_data is None:
                raise ApiRequestError('Missing rates data in response')
            # Приводим к стандартному формату
            rates = {}
            for currency, rate in rates_data.items():
                key = f"{self.base_currency}_{currency}"
                rates[key] = rate
            return rates
        except requests.exceptions.RequestException as e:
            raise ApiRequestError(f'Request failed: {e}')