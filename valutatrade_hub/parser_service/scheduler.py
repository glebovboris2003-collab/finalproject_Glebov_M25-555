import threading
import time
from .updater import RatesUpdater  
from .api_clients import CoinGeckoClient, ExchangeRateApiClient  
from .storage import write_rates 

# Настройка клиентов
coin_gecko_client = CoinGeckoClient()
exchange_rate_client = ExchangeRateApiClient()  

# Создаем объект хранилища
class StorageWrapper:
    def save(self, data):
        write_rates(data)

storage = StorageWrapper()

# Создаем экземпляр обновления данных котировок
rates_updater = RatesUpdater(
    api_clients=[coin_gecko_client, exchange_rate_client],
    storage=storage
)

def update_exchange_rates():
    try:
        rates_updater.run_update()
        print("Курсы обновлены успешно.")
    except Exception as e:
        print(f"Ошибка при обновлении курсов: {e}")

def periodic_update(interval_hours=1):
    """Функция для периодического вызова обновления"""
    while True:
        update_exchange_rates()
        # Ждем указанное количество часов
        time.sleep(interval_hours * 3600)

if __name__ == "__main__":
    # Запускаем поток, который будет обновлять курсы каждые 1 час
    updater_thread = threading.Thread(target=periodic_update, args=(1,), daemon=True)
    updater_thread.start()

    # Можно оставить основной поток для выполнения других задач или просто ждать
    # Например, чтобы программа не завершилась:
    while True:
        time.sleep(3600)