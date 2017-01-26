# -*- coding: utf-8 -*-
import gevent
import time

from oandapyV20.endpoints.pricing import PricingStream
from oandapyV20.exceptions import V20Error, StreamTerminated
from requests.exceptions import ConnectionError


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
                with open("LOG", "a") as LOG:
                    LOG.write("V20Error: {} {}\n".format(e, n))
                break

            except ConnectionError as e:
                with open("LOG", "a") as LOG:
                    LOG.write("Error: {} {}\n".format(e, n))
                    time.sleep(3)

            except StreamTerminated as e:
                with open("LOG", "a") as LOG:
                    LOG.write("Stopping: {} {}\n".format(e, n))
                break

            except Exception as e:
                with open("LOG", "a") as LOG:
                    LOG.write("??? : {} {}\n".format(e, n))
                break

        raise e
