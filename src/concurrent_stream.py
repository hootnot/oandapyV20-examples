# -*- coding: utf-8 -*-
"""Concurrent streams and account polling using gevent.

demonstrates usage of oandapyV20:
- streaming prices
- streaming events
- account polling
- restart of a greenlet in case of an exception

For gevent details check: http://sdiehl.github.io/gevent-tutorial/
For REST-API V20 check: http://developer.oanda.com

Example:

  concurrent_stream.py --nice --pollcount 10 --instr EUR_USD --instr EUR_JPY
"""
import sys
import os
import argparse
import json
import gevent
from gevent.pool import Group
from gevent import monkey
import time
import logging

from oandapyV20 import API
from oandapyV20.exceptions import V20Error, StreamTerminated
from oandapyV20.endpoints.pricing import PricingStream
from oandapyV20.endpoints.transactions import TransactionsStream
from oandapyV20.endpoints.accounts import AccountChanges, AccountSummary
from exampleauth import exampleAuth
from requests.exceptions import ConnectionError
from datetime import datetime

monkey.patch_all()

# create the top-level parser
parser = argparse.ArgumentParser(prog='concurrent_stream')
parser.add_argument('--nice', action='store_true', help='json indented')
parser.add_argument('--timeout', default=0, type=float,
                    help='timeout in secs., default no timeout')
parser.add_argument('--tickcount', default=0, type=int,
                    help='max # of records to receive, default = unlimited.')
parser.add_argument('--pollcount', default=0, type=int,
                    help='max # poll requests, default = unlimited.')
parser.add_argument('--instruments', type=str, nargs='?',
                    action='append', help='instruments')


accountID, access_token = exampleAuth()

clargs = parser.parse_args()
if not clargs.instruments:
    parser.parse_args(["--help"])


request_params = {}
if clargs.timeout:
    request_params = {"timeout": clargs.timeout}

api = API(access_token=access_token,
          environment="practice",
          request_params=request_params)

logging.basicConfig(
    filename="./concurrent.log",
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(name)s : %(message)s',
)

logger = logging.getLogger(__name__)


# The greenlets ...
class StreamingPrices(gevent.Greenlet):
    """Greenlet to handle streaming prices."""

    def __init__(self, instruments, maxrec=0, nice=False):
        super(StreamingPrices, self).__init__()
        self.nice = nice
        self.instruments = instruments
        self.maxrec = maxrec

    def _run(self):
        tickMsg = "write tick record ...{}\n"
        while True:
            r = PricingStream(
                    accountID=accountID,
                    params={"instruments": ",".join(self.instruments)})

            se = None   # to save the exception if it occurs
            with open("prices.txt", "a") as O:
                n = 0
                try:
                    for R in api.request(r):
                        now = datetime.now()
                        sys.stderr.write(tickMsg.format(now))

                        if self.nice:
                            O.write(json.dumps(R, indent=2)+"\n")
                        else:
                            O.write(json.dumps(R)+"\n")
                        O.flush()
                        gevent.sleep(0)
                        n += 1
                        if self.maxrec and n >= self.maxrec:
                            r.terminate("maxrecs received: {}".format(n))

                except V20Error as e:
                    # catch API related errors that may occur
                    se = e   # save for reraise
                    logger.error("V20Error: %s %d", e, n)
                    break

                except ConnectionError as e:
                    logger.error("ConnectionError: %s %d", e, n)
                    time.sleep(3)

                except StreamTerminated as e:
                    se = e   # save for reraise
                    logger.error("StreamTerminated: %s %d", e, n)
                    break

                except Exception as e:
                    se = e   # save for reraise
                    logger.error("Some exception: %s %d", e, n)
                    break

        # raise se


class StreamingEvents(gevent.Greenlet):
    """Greenlet to handle streaming events."""

    def __init__(self, m=0):
        super(StreamingEvents, self).__init__()
        self.m = m

    def _run(self):
        r = TransactionsStream(accountID=accountID)
        while True:
            with open("events.txt", "a") as O:
                try:
                    n = 0
                    for R in api.request(r):
                        now = datetime.now()
                        sys.stderr.write("write event ...{}\n".format(now))
                        O.write(json.dumps(R)+"\n")
                        O.flush()
                        gevent.sleep(0)
                        n += 1
                        if n > self.m:
                            r.terminate("maxrecs received: {}".format(self.m))

                except StreamTerminated as e:
                    logger.error("StreamTerminated: %s %d", e, n)
                    # re-raise
                    raise e

                except Exception as e:
                    logger.error("Some exception: %s %d", e, n)


class ChangePoller(gevent.Greenlet):
    """Greenlet to poll for account changes."""

    def __init__(self, sinceTransactionID, maxpoll=0):
        super(ChangePoller, self).__init__()
        self.sinceTransactionID = sinceTransactionID
        self.maxpoll = maxpoll

    def _run(self):
        r = AccountChanges(
                accountID=accountID,
                params={"sinceTransactionID": self.sinceTransactionID})

        n = 0
        while True:
            try:
                R = api.request(r)

            except Exception as e:
                logger.error("Some exception: %s %d", e, n)

            else:
                fName = "changes.{}.txt".format(self.sinceTransactionID)
                now = datetime.now()
                sys.stderr.write("write change ...{}\n".format(now))
                with open(fName, "a") as O:
                    O.write("------------\n" + json.dumps(R, indent=2)+"\n")
                    O.flush()
                    n += 1
                    if self.maxpoll and n > self.maxpoll:
                        sys.stderr.write("max changes polled\n")
                        break

                    lastTransactionID = R["lastTransactionID"]
                    if lastTransactionID != self.sinceTransactionID:
                        self.sinceTransactionID = lastTransactionID
                        params = {"sinceTransactionID":
                                  self.sinceTransactionID}
                        r = AccountChanges(accountID=accountID, params=params)

                    gevent.sleep(15)


# manage asynchronous tasks
gr = Group()


def events_exceptionhandler(g):
    """create a new greenlet."""
    logger.info("restart greenlet %s", g.__class__.__name__)
    print("Restart {}".format(g.__class__.__name__))
    x = g.__class__(m=5)
    gr.discard(g)
    x.link_exception(events_exceptionhandler)
    x.start()
    gr.add(x)
    gr.join()


p_stream = StreamingPrices(instruments=clargs.instruments,
                           nice=clargs.nice,
                           maxrec=clargs.tickcount)
p_stream.start()

# figure out the ID to poll from
r = AccountSummary(accountID=accountID)
try:
    rv = api.request(r)
except V20Error as e:
    logger.error("V20Error %s %s", e.code, e.msg)
    print("V20Error : {} {}".format(e.code, e.msg))
    exit(2)
except Exception as e:
    exc_type, exc_obj, exc_tb = sys.exc_info()
    fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
    logger.error("Generic exception %s %s %s",
                 exc_type, fname, exc_tb.tb_lineno)
    exit(2)
else:
    since = rv["lastTransactionID"]

ch_poller = ChangePoller(sinceTransactionID=since, maxpoll=clargs.pollcount)
ch_poller.start()

e_stream = StreamingEvents(5)
e_stream.link_exception(events_exceptionhandler)
e_stream.start()

gr.add(p_stream)
gr.add(ch_poller)
gr.add(e_stream)
gr.join()
