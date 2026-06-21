import logging
from config import PATHS

PATHS["logs"].mkdir(exist_ok=True)

logger = logging.getLogger("subtilearn")
handler = logging.FileHandler(PATHS["logs"] / "subtilearn.log")
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.DEBUG)