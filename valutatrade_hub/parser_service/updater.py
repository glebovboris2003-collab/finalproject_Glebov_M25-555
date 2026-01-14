import logging
import json
from datetime import datetime, timezone
from .config import ParserConfig

# Настройка логирования
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class RatesUpdater:
    def __init__(self, api_clients, storage):
        """
        :param api_clients: список экземпляров клиентов, реализующих fetch_rates()
        :param storage: объект хранилища с методом save(data: dict)
        """
        self.api_clients = api_clients
        self.storage = storage

    def run_update(self):
        logger.info("Начало обновления курсов валют.")
        aggregated_rates = {}
        measurement_log = []  # список для журналов измерений
        for client in self.api_clients:
            client_name = client.__class__.__name__
            try:
                logger.info(f"Запрос данных у клиента: {client_name}")
                rates = client.fetch_rates()
                logger.info(f"Получено {len(rates)} курсов от {client_name}")
                # Объединяем данные
                parse_name_value = ParserConfig()
                crypto_dict = parse_name_value.CRYPTO_ID_MAP  # например, {"BTC": "bitcoin", ...}
                for key, value in rates.items():
                    matched = False
                    name_valute = key.split('_')[0]
                    for prefix, value2 in crypto_dict.items():
                        if value2.lower() == name_valute.lower():
                            new_key = f"{prefix}_USD"
                            if new_key not in aggregated_rates:
                                aggregated_rates[new_key] = value
                            matched = True
                            break
                    if not matched:
                        aggregated_rates[key] = value
            except Exception as e:
                logger.warning(f"Ошибка при получении данных от {client_name}: {e}")

        # После сбора всех курсов, формируем журнал измерений
        for code, rate in aggregated_rates.items():
            if rate is None:
                # пропускаем или логируем ошибку, тут можно добавить
                continue
            try:
                from_currency = code.split('_')[0].upper()
                to_currency = code.split('_')[1].upper()
                timestamp = datetime.now(timezone.utc).isoformat()
                record_id = f"{from_currency}_{to_currency}_{timestamp}"

                # Создаем мета-данные (можно дополнить)
                meta = {
                    "raw_id": from_currency.lower(),  # или источник
                    "request_ms": 0,
                    "status_code": 200,
                    "etag": ""
                }

                measurement_entry = {
                    "id": record_id,
                    "from_currency": from_currency,
                    "to_currency": to_currency,
                    "rate": rate,
                    "timestamp": timestamp,
                    "source": client_name,
                    "meta": meta
                }
                # добавляем запись в журнал
                measurement_log.append(measurement_entry)
            except Exception as e:
                logger.warning(f"Ошибка при формировании журнала для {code}: {e}")

        # Добавляем метаданные
        update_metadata = {
            
            "last_refresh": datetime.now(timezone.utc).isoformat() + 'Z'
        }
        result = {
            "rates": measurement_log,
            "metadata": update_metadata
        }
            # Создаем структуру для top_rates, если нужно
        sorted_rates_items = sorted(aggregated_rates.items(), key=lambda item: item[1], reverse=True)
        rates_items = list(aggregated_rates.items())
        top_6 = dict(rates_items[:6])

        # Формируем result с нужной структурой для result2
        now_iso = datetime.now(timezone.utc).isoformat()
        pairs_dict = {}
        for code, rate in aggregated_rates.items():
            from_currency, to_currency = code.split('_')
            pair_key = f"{from_currency}_{to_currency}"
            pairs_dict[pair_key] = {
                "rate": rate,
                "updated_at": now_iso,
                "source": client_name  
            }

        update_metadata = {
            "last_refresh": now_iso
        }

        result2 = {
            "pairs": pairs_dict,
            "last_refresh": now_iso
        }
        # сохраняем результаты
        try:
            logger.info("Сохраняем обновленные данные в хранилище.")
            self.storage.write_rates(result)
            self.storage.write_rates2(result2)
            # здесь можно дополнительно сохранить журнал, например, в файл или базу
            # self.storage.write_measurements(measurement_log)
            logger.info("Данные успешно сохранены.")
        except Exception as e:
            logger.error(f"Ошибка при сохранении данных: {e}")

        logger.info("Обновление завершено.")