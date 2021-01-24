# -*- coding: utf-8 -*-
"""Streaming price data.

demonstrate the PricingStream request.

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


logging.basicConfig(
    filename="pricingstream.log",
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s : %(message)s',
)

logger = logging.getLogger(__name__)


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
    while True:
        try:
            for R in api.request(r):
                if clargs['--nice']:
                    R = json.dumps(R, indent=2)
                print(R)
                n += 1
                if MAXREC and n >= MAXREC:
                    r.terminate("maxrecs received: {}".format(MAXREC))

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
