# -*- coding: utf-8 -*-
"""Simple demo of streaming transaction data."""
from oandapyV20 import API
from oandapyV20.exceptions import V20Error, StreamTerminated
from oandapyV20.endpoints.transactions import TransactionsStream
from exampleauth import exampleAuth

accountID, access_token = exampleAuth()
api = API(access_token=access_token, environment="practice")

s = TransactionsStream(accountID=accountID)
MAXTRANS = 10

print("read from stream until {} transactions received".format(MAXTRANS))
try:
    n = 0
    for R in api.request(s):
        print(R)
        n += 1
        if n > MAXTRANS:
            s.terminate("max transactions received")

except StreamTerminated as e:
    print("{}".format(e))
except V20Error as e:
    print("Error: {}".format(e))
