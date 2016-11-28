oandapyV20 - examples
=====================

This repo contains a number of examples to demonstrate how to
use OANDA's REST-V20 API with the oandapyV20_ Python API-wrapper.

.. _oandapyV20: https://github.com/hootnot/oanda-api-v20

Setup
-----

Token
~~~~~

Access to the OANDA REST-API requires a token. If you do not have a token
you can obtain one. Check developer.oanda.com_ for details.
Edit the file *token.txt*  and put the token in it.

.. _developer.oanda.com: http://developer.oanda.com

AccountID
~~~~~~~~~

If you have a token, you have an account. Edit the file *account.txt* and
put the **accountID** in it.

.. warning::

   Make sure you have made the setup based on a **practice** account !
   Leveraged trading is high risk. Losses can exceed investment.


Examples
--------


=============================  =============
Source                         Description
=============================  =============
**Streams**
`src/streaming_prices`         Simple streaming prices
`src/streaming_trans.py`       Simple streaming transactions
`src/concurrent_streaming.py`  Demonstrate concurrent streaming of prices and events along with the polling of account changes based on gevent greenlets
=============================  =============
