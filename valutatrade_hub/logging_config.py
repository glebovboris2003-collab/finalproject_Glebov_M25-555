import logging
from logging.handlers import RotatingFileHandler

logger = logging.getLogger('actions')
logger.setLevel(logging.INFO)

handler = RotatingFileHandler('logs/actions.log', maxBytes=10**6, backupCount=5)
formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
handler.setFormatter(formatter)

logger.addHandler(handler)