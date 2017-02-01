# -*- coding: utf-8 -*-
"""
MIT License

Copyright (c) 2016 Feite Brekeveld

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

"""
demo console application

Show a real-time bid-ask tick tree for configured instruments. If an instrument
has a position the result is shown and live updates of the Net-Asset-Value
is shown in the header

Code of this application is partially copied and/or inspired on code from the
urwid repos: urwid and urwidtrees.

THIS PROGRAM IS SOLELY FOR DEMONSTRATION PURPOSE
"""
import urwid
import subprocess
import logging
from collections import OrderedDict
import gevent
from urwid_geventloop import GeventLoop

# ------------------------------------
from gevent.pool import Group
from gevent.queue import Queue
from gevent import monkey

from oandapyV20 import API
from oandapyV20.exceptions import V20Error
from exampleauth import exampleAuth
from datetime import datetime

from urwidtrees.widgets import TreeBox
from urwidtrees.tree import SimpleTree
# from urwidtrees.nested import NestedTree
# from urwidtrees.decoration import ArrowTree, CollapsibleArrowTree
from urwidtrees.decoration import CollapsibleIndentedTree
from console.greenlets import GAccountDetails, GStreamingPrices
import six

monkey.patch_all()

logging.basicConfig(
    filename="./console.log",
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(name)s : %(message)s',
)

logger = logging.getLogger(__name__)


# greenlets ...
class WidgetUpdate(gevent.Greenlet):
    """Greenlet to update the widgets based on queue information."""

    def __init__(self, q_nav, q_price, widget=None):
        super(WidgetUpdate, self).__init__()
        self.q_nav = q_nav
        self.q_price = q_price
        self.widget = widget
        self.prev = {}

    def mkrecord(self, snapshot, r):
        """update the instrument row by creating all row fields.

        "positions": [
          {
            "shortUnrealizedPL": "0.0000",
            "instrument": "DE30_EUR",
            "longUnrealizedPL": "594.3000",
            "netUnrealizedPL": "594.3000"
          }
         ],
        """
        try:
            prev = self.prev[r["instrument"]]
        except KeyError:
            directionB = " "
            directionA = " "
        else:
            directionB = "^" if float(r["bids"][0]["price"]) > \
                         float(prev["bids"][0]["price"]) else "v"
            directionA = "^" if float(r["asks"][0]["price"]) > \
                         float(prev["asks"][0]["price"]) else "v"

        modeB = "red" if directionB == "v" else "green"
        modeA = "red" if directionA == "v" else "green"

        ext = []
        if snapshot:
            positions = snapshot.get('state').get('positions')
            for P in positions:
                if r["instrument"] == P["instrument"]:
                    netUnr = float(P.get('netUnrealizedPL'))
                    ext.append(('', "{:10.2f}".format(netUnr)))

        # instrument row set_text components ...
        return ["{:<11s}".format(r["instrument"]),
                (modeB, "{:10s}".format(r["bids"][0]["price"])),
                (modeA, "{:10s}".format(r["asks"][0]["price"])),
                ('', "{:s}".format(r["time"][11:22])),
                directionB] + ext

    def _run(self):

        NAV = "0.0"
        TIME = ("%s" % datetime.now())[11:22]
        snapshot = None
        n = 0
        se = None  # Saved exception
        while True:
            try:
                if not self.q_nav.empty():
                    snapshot = self.q_nav.get()
                    state = snapshot.get('state')
                    NAV = state.get('NAV')

                if not self.q_price.empty():
                    R = self.q_price.get()
                    if self.widget and R["type"] == "PRICE":
                        # update the instrument row
                        self.widget[R["instrument"]].set_text(
                            self.mkrecord(snapshot, R)
                        )
                        # save as 'previous'
                        self.prev[R["instrument"]] = R
                        TIME = R["time"]

                # update the header: NAV and time
                s = getattr(self.widget["header"], "struw")
                s = s.format(NAV=float(NAV), time=TIME[11:22])
                self.widget["header"].set_text(('bg', s))

            except V20Error as e:
                logging.error("V20Error: code: %s msg: %s loop count: %d",
                              e.code, e.msg, n)
                break

            except Exception as e:
                se = e  # save the exception to be able to re-raise it
                logging.error("??? : %s loop count: %d", e, n)
                break

            n += 1
            gevent.sleep(0)

        # raise se


class FocusableText(urwid.WidgetWrap):
    """Selectable Text used for 'leafs' in our example."""

    def __init__(self, txt):
        self.t = urwid.Text(txt)
        w = urwid.AttrMap(self.t, 'body', 'focus')
        urwid.WidgetWrap.__init__(self, w)

    def selectable(self):
        return True

    def keypress(self, size, key):
        with open("/tmp/walk.out", "a") as O:
            O.write("%s," % self.t.__class__.__name__)
            O.write("%s," % self.t)
            O.write("%s," % size)
            O.write("%s" % key)
            O.write("\n")
        return key


class FocusableNode(urwid.WidgetWrap):
    """Selectable Node used for nodes in our example."""

    MENU = None

    def __init__(self, t):
        self.t = t
        w = urwid.AttrMap(self.t, 'body', 'focus')
        urwid.WidgetWrap.__init__(self, w)

        if not self.MENU:
            self.MENU = [u'{instrument} Cmds: ',
                         ('close button', u'C'), u') close position ',
                         ('quit button', u'Q'), u') to quit.']

    def selectable(self):
        return True

    def keypress(self, size, key):

        # low: list of widgets, global variable to get rid of ...
        w = low["footer"]
        _menu = self.MENU
        try:
            instr = getattr(self.t, "instrument")
            _menu[0] = _menu[0].format(instrument=instr)
        except:
            # not in an instrument row
            _menu[0] = _menu[0].format(instrument="")
        finally:
            w.set_text(_menu)

        return key

# define a test tree in the format accepted by SimpleTree. Essentially, a
# tree is given as (nodewidget, [list, of, subtrees]). SimpleTree accepts
# lists of such trees.


def dyn_add_subtree(parent, j, selectable_nodes):
    Text = FocusableText if selectable_nodes else urwid.Text

    subtree = (Text('%s' % j), [])
    subtree[1].append((Text('xxx'), None))
    parent[1].append(subtree)


def instrument_tree(instruments, selectable_nodes=True):

    Text = FocusableText if selectable_nodes else urwid.Text

    # define root node
    tree = (Text('Instruments    Bid       Ask       Time        Result'), [])

    # add instruments as children
    for i, V in six.iteritems(instruments):
        subtree = (FocusableNode(V), [])

        # and grandchildren.. orders / pos
        if isinstance(V, urwid.Text):
            children = ["trades", "orders"]
            for j in children:
                dyn_add_subtree(subtree, j, selectable_nodes)

        tree[1].append(subtree)

    return tree


def construct_instrument_tree(selectable_nodes=True, instruments=[]):
    forrest = [instrument_tree(instruments, selectable_nodes)]
    return SimpleTree(forrest)


def mkHeader():
    _header_text = \
        u"""OANDA Console   NAV:{NAV:9.2f}                                        {time}  \n""" \
         """                                                                                  """
    initTime = ("%s" % datetime.now())[11:22]
    header_text = urwid.Text(('bg', _header_text.format(NAV=0, time=initTime)))
    # save the formatstring
    setattr(header_text, 'struw', _header_text)
    urwid.AttrMap(header_text, 'titlebar')
    return header_text


if __name__ == "__main__":

    from console.config import Config

    low = OrderedDict()

    # Queues
    Q_PRICE = Queue()   # Price queue
    Q_NAV = Queue()     # Net Asset Value queue

    accountID, access_token = exampleAuth()
    cfg = Config()

    api = API(access_token=access_token, environment="practice")

    # list of widgets
    x = 0
    loIw = OrderedDict()
    for G in cfg.instrument_groups():
        groupName, groupItems = G
        for t in groupItems:
            loIw.update({t: urwid.Text(('streak', t))})
            setattr(loIw[t], "instrument", t)

        loIw.update({"D%d" % x: urwid.Divider('-')})
        x += 1

    def exit_on_q(key):
        if key in ('q', 'Q'):
            raise urwid.ExitMainLoop()

        gevent.sleep(0)

    # Header
    low.update({"header": mkHeader()})

    # Create the menu (will display on bottom of screen)
    menu = urwid.Text([u'Press (', ('quit button', u'Q'),
                       u') to quit.'])
    low.update({"footer": menu})

    innertree = CollapsibleIndentedTree(
        construct_instrument_tree(instruments=loIw)
    )
    for P in innertree.positions():
        # print P, innertree.depth(P)
        if innertree.depth(P) == 1:
            innertree.collapse(P)

    treebox = TreeBox(innertree)
    todelete = None

    pile = urwid.Pile(loIw.values())
    fill = urwid.Filler(pile, 'top')
    layout = urwid.Frame(header=low["header"],
                         body=treebox,
                         footer=low["footer"])

    # add all the instrument widgets to the low (list of widgets)
    [low.update({k: v}) for k, v in six.iteritems(loIw)]

    # ----------------------------------------------------------------
    # manage asynchronous tasks
    gr = Group()

    # Add the greenlet to fetch streaming prices
    # and let it write the REST-call responses to Q_PRICE
    p_stream = GStreamingPrices(instruments=cfg.instruments,
                                api=api,
                                accountID=accountID,
                                queue=Q_PRICE)
    p_stream.start()
    gr.add(p_stream)

    # Add the greenlet to fetch account summary information
    # and let it write the REST-call response to Q_NAV
    acctsum = GAccountDetails(api=api,
                              accountID=accountID,
                              queue=Q_NAV,
                              sleepTime=1)
    acctsum.start()
    gr.add(acctsum)

    # Add the greenlet to update the urwid widgets based on information
    # in the queues
    gui = WidgetUpdate(q_nav=Q_NAV, q_price=Q_PRICE, widget=low)
    gui.start()
    gr.add(gui)

    # gr.join()
    loop = urwid.MainLoop(layout, cfg.palette, unhandled_input=exit_on_q,
                          event_loop=GeventLoop())
    try:
        loop.run()
    except urwid.ExitMainLoop:
        pass

    subprocess.call("clear", shell=True)
