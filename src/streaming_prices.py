# -*- coding: utf-8 -*-
"""Streaming price data.

demonstrate the PricingStream request and convenient handling of data using Pydantic.

Usage:
    streaming_prices.py --instrument <instrument> [--instrument <instrument>] [--nice] [--timeout <timeout>] [--count <count>]

Options:
    --nice                 json indented formatting
    --timeout=<timeout>    timeout in seconds
    --count=<count>        # of records to receive [default: 0] unlimited
"""
import json
from oandapyV20 import API
from oandapyV20.exceptions import V20Error, StreamTerminated
from oandapyV20.endpoints.pricing import PricingStream
from exampleauth import exampleAuth
from requests.exceptions import ConnectionError
import logging
from typing import List
from pydantic import BaseModel
from datetime import datetime


logging.basicConfig(
    filename="pricingstream.log",
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s : %(message)s',
)

logger = logging.getLogger(__name__)


class HeartBeat(BaseModel):
    type: str
    time: datetime


class Price(BaseModel):
    price: float
    liquidity: int


class PriceRecord(BaseModel):
    instrument: str
    type: str
    time: datetime
    closeoutBid: float
    closeoutAsk: float
    status: str
    tradeable: bool
    bids: List[Price]
    asks: List[Price]


def main(clargs):
    accountID, access_token = exampleAuth()

    request_params = {}
    if clargs['--timeout']:
        request_params = {"timeout": clargs['--timeout']}

    # fetch MAXREC stream records
    MAXREC = int(clargs['--count'])

    api = API(access_token=access_token,
              environment="practice",
              request_params=request_params)

    # setup the stream request
    r = PricingStream(accountID=accountID,
                      params={"instruments": ",".join(clargs['<instrument>'])})

    n = 0
    _m = {"PRICE": PriceRecord,
          "HEARTBEAT": HeartBeat}

    while True:
        try:
            for rv in api.request(r):
                # create a Pydantic record based on the type
                rec = _m[rv['type']](**rv)

                n += 1
                if MAXREC and n >= MAXREC:
                    r.terminate("maxrecs received: {}".format(MAXREC))

                print(rec.json() if clargs['--nice'] else rec)

        except V20Error as e:
            # catch API related errors that may occur
            logger.error("V20Error: %s", e)
            break

        except ConnectionError as e:
            logger.error("%s", e)

        except StreamTerminated as e:
            logger.error("Stopping: %s", e)
            break

        except Exception as e:
            logger.error("%s", e)
            break


if __name__ == '__main__':
    from docopt import docopt

    # commandline args ...
    clargs = docopt(__doc__)
    main(clargs)
