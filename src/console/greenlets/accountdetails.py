# -*- coding: utf-8 -*-
import gevent

from oandapyV20.endpoints.accounts import AccountDetails, AccountChanges


class GAccountDetails(gevent.Greenlet):
    """Greenlet to handle account details/changes.

    Initially get the AccountDetails and then keep polling
    for account changes.
    In case of changes put those on the NAV-Queue
    """
    def __init__(self, api, accountID, queue, sleepTime=4):
        super(GAccountDetails, self).__init__()
        self.api = api
        self.accountID = accountID
        self.queue = queue
        self.sleepTime = sleepTime

    def _run(self):
        # setup the summary request
        r = AccountDetails(accountID=self.accountID)
        rv = self.api.request(r)

        lastTransactionID = rv.get("lastTransactionID")
        lastLastTransactionID = lastTransactionID

        r = None
        while True:
            if not r or lastLastTransactionID != lastTransactionID:
                params = {"sinceTransactionID":
                          int(rv.get("lastTransactionID"))}
                r = AccountChanges(accountID=self.accountID, params=params)
                lastLastTransactionID = lastTransactionID

            rv = self.api.request(r)
            lastTransactionID = rv.get('lastTransactionID')
            self.queue.put_nowait(rv)
            gevent.sleep(self.sleepTime)
