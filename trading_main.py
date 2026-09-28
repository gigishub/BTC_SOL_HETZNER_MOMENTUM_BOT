import logging
import datetime
import time
from trade_BTC_SOL import trade_SOL, trade_BTC

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s.%(msecs)03d - %(levelname)s - %(message)s', datefmt='%H:%M:%S')
ch.setFormatter(formatter)
logger.addHandler(ch)
logger.propagate = False

def main(runtime=5, testing=False):
    start_time = datetime.datetime.now()
    while start_time + datetime.timedelta(minutes=runtime) > datetime.datetime.now():
        trade_SOL(testing)
        trade_BTC(testing)
        logger.info('Trade check completed for today\n')
        time.sleep(60)
    logger.info('testing runtime completed')

if __name__ == '__main__':
    main(runtime=5, testing=False)
