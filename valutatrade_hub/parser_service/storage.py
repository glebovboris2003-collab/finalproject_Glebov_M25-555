import os
import json
from valutatrade_hub.infra import settings

# Получение пути к файлу из настроек
config = settings.SettingsLoader()
RATES_FILE_PATH = config.get('path_to_json', "data/exchange_rates.json")
SIMPLE_6_FILE_PATH = config.get('path_to_json', "data/rates.json")
def load_json(file_path):
    if os.path.exists(file_path):
        with open(file_path, 'r') as f:
            return json.load(f)
    return {}

def save_json(file_path, data):
    with open(file_path, 'w') as f:
        json.dump(data, f, indent=4)
def read_rates():
    """Читает данные из файла exchange_rates.json с помощью функции из interface.py."""
    return load_json(RATES_FILE_PATH)

def write_rates(data):
    """Записывает данные в файл exchange_rates.json с помощью функции из interface.py."""
    os.makedirs(os.path.dirname(RATES_FILE_PATH), exist_ok=True)
    save_json(RATES_FILE_PATH, data)

def write_rates2(data):
    """Записывает данные в файл rates.json с помощью функции из interface.py."""
    os.makedirs(os.path.dirname(SIMPLE_6_FILE_PATH), exist_ok=True)
    save_json(SIMPLE_6_FILE_PATH, data)
