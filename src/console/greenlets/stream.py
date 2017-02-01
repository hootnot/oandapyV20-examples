# -*- coding: utf-8 -*-
import gevent
import time

from oandapyV20.endpoints.pricing import PricingStream
from oandapyV20.exceptions import V20Error, StreamTerminated
from requests.exceptions import ConnectionError
import logging

logger = logging.getLogger(__name__)


class GStreamingPrices(gevent.Greenlet):
    """Greenlet to handle streaming prices."""

    def __init__(self, instruments, api, accountID, queue, sleepTime=0):
        super(GStreamingPrices, self).__init__()
        self.instruments = instruments
        self.api = api
        self.accountID = accountID
        self.queue = queue
        self.sleepTime = sleepTime
        self.prev = {}

    def _run(self):

        se = None  # save exception for reraise
        while True:
            # setup the stream-request
            r = PricingStream(
                    accountID=self.accountID,
                    params={"instruments": ",".join(self.instruments)})

            n = 0
            try:
                for R in self.api.request(r):
                    # now = datetime.now()
                    self.queue.put_nowait(R)
                    gevent.sleep(0)
                    n += 1

            except V20Error as e:
                # catch API related errors that may occur
                se = e
                logger.error("V20Error: %s %s %d", e.code, e.msg, n)
                break

            except ConnectionError as e:
                logger.error("ConnectionError: %s %d", e, n)
                time.sleep(3)

            except StreamTerminated as e:
                se = e
                logger.error("StreamTerminated: %s %d", e, n)
                break

            except Exception as e:
                se = e
                logger.error("Exception: %s %d", e, n)
                break

        raise se
