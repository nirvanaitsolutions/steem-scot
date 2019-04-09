# This Python file uses the following encoding: utf-8
# (c) holger80
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from beem import Steem
from beem.comment import Comment
from beem.nodelist import NodeList
from beem.blockchain import Blockchain
from beem.utils import addTzInfo, construct_authorperm
from steemengine.tokenobject import Token
from steemengine.wallet import Wallet
import time
import json
import shelve
import math
import argparse
import logging
from datetime import datetime, date, timedelta

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logging.basicConfig()

timeFormatZ = '%Y-%m-%dT%H:%M:%S.%fZ'


class Scot:
    def __init__(self, config, steemd_instance):
        self.config = config
        self.stm = steemd_instance
        
        self.daily_inflation = self.config["yearly_inflation"] / 365
        if not self.config["no_broadcast"]:
            self.stm.wallet.unlock(self.config["wallet_password"])
        
        self.scot_token = Token(self.config["scot_token"])
        self.token_wallet = Wallet(self.config["scot_account"], steem_instance=self.stm)        

    def get_token_holder(self):
        offset = 0
        get_holder = self.scot_token.get_holder()
        offset += 1000
        new_holder = self.scot_token.get_holder(offset=offset)
        while len(new_holder) > 0:
            get_holder.append(new_holder)
            offset += 1000
            new_holder = self.scot_token.get_holder(offset=offset)        
            
        token_per_100_vote = {}
        token_sum = 0
        for item in get_holder:
            if item["account"] == self.config["scot_account"]:
                continue
            token_sum += float(item["balance"])
        
        for item in get_holder:
            if item["account"] == self.config["scot_account"]:
                continue
            token_sum += float(item["balance"])
            if float(item["balance"]) > 0:
                token_per_100_vote[item["account"]] = (float(item["balance"]) / token_sum) * self.daily_inflation / 10
        return token_per_100_vote

    def get_token_to_sent(self, start_block, stop_block, token_per_100_vote):
        token_to_authors = {}
        b = Blockchain(steem_instance=self.stm)
        for op in b.stream(start=start_block, stop=stop_block, opNames=["vote"], max_batch_size=50):
            if op["voter"] not in token_per_100_vote:
                continue
            if not self.config["downvotes"] and op["weight"] < 0:
                continue
            if not self.config["upvotes"] and op["weight"] > 0:
                continue
            comment = Comment(op, steem_instance=self.stm)
            try:
                comment.refresh()
            except:
                print("Could not fetch %s" % comment["authorperm"])
                continue
            json_metadata = comment["json_metadata"]
            app = None
            SETokensSupported = None
            if isinstance(json_metadata, str):
                json_metadata = json.loads(json_metadata)
            if "app" in json_metadata:
                app = json_metadata["app"]
                if isinstance(app, dict) and "name" in app:
                    app = app["name"]
                elif isinstance(app, dict):
                    app = ""
            if "SETokensSupported" in json_metadata:
                SETokensSupported = json_metadata["SETokensSupported"]
            
            app_or_symbol = False
            if app is not None and len(self.config["included_apps"]) > 0 and app != "" and app in self.config["included_apps"]:
                app_or_symbol = True
            elif self.config["include_token_as_tag"] and self.scot_token["symbol"] in comment["tags"]:
                app_or_symbol = True
            elif SETokensSupported is not None and len(SETokensSupported) > 0 and self.scot_token["symbol"] in SETokensSupported:
                app_or_symbol = True
            if not app_or_symbol and not self.config["include_all_posts"]:
                continue
    
            token_amount = abs(op["weight"]) / 10000 * token_per_100_vote[op["voter"]]
            if op["weight"] < 0:
                if op["voter"] not in token_to_authors:
                    token_to_authors[op["voter"]] = token_amount
                else:
                    token_to_authors[op["voter"]] += token_amount
            else:
                if op["author"] not in token_to_authors:
                    token_to_authors[op["author"]] = token_amount
                else:
                    token_to_authors[op["author"]] += token_amount
        return token_to_authors

    def get_token_transfer_last_24_h(self):
        yesterday = date.today() - timedelta(days=1)
        yesterday_0_0_0 = datetime(yesterday.year, yesterday.month, yesterday.day)
        yesterday_23_59_59 = datetime(yesterday.year, yesterday.month, yesterday.day, 23,59, 59)        
        token_sent_last_24_h = 0
        for hist in self.token_wallet.get_history(self.scot_token["symbol"]):
            timestamp = datetime.strptime(hist["timestamp"], timeFormatZ)
            if timestamp <= yesterday_23_59_59:
                continue
            print(hist)
            if hist["from"] != self.config["scot_account"]:
                continue
            token_sent_last_24_h = float(hist["quantity"])
        return token_sent_last_24_h

    def count_token(self, token_to_authors):
        token_amount_to_sent = 0
        for author in token_to_authors:
            token_amount_to_sent += token_to_authors[author]
        return token_amount_to_sent

    def adapt_to_precision(self, token_to_authors):
        token_amount_to_sent = self.count_token(token_to_authors)
        for author in token_to_authors:
            token_to_authors[author] = token_to_authors[author] * self.daily_inflation / token_amount_to_sent
            token_to_authors[author] = math.floor(token_to_authors[author] * 10**self.scot_token["precision"]) / 10**self.scot_token["precision"]
        return token_to_authors

    def send_token(self, token_to_authors):

        
        for author in token_to_authors:
            if token_to_authors[author] < 10**(-self.scot_token["precision"]):
                continue
            if self.config["no_broadcast"]:
                logger.info("Sending %f %s to %s" % (token_to_authors[author], self.scot_token["symbol"], author))
            else:
                self.token_wallet.transfer(author, token_to_authors[author], self.scot_token["symbol"], memo=self.config["token_memo"])
                time.sleep(4)

    def run(self):
        b = Blockchain(steem_instance=self.stm)
        
        yesterday = date.today() - timedelta(days=1)
        yesterday_0_0_0 = datetime(yesterday.year, yesterday.month, yesterday.day)
        yesterday_23_59_59 = datetime(yesterday.year, yesterday.month, yesterday.day, 23,59, 59)
        start_block = b.get_estimated_block_num(addTzInfo(yesterday_0_0_0))
        stop_block = b.get_estimated_block_num(addTzInfo(yesterday_23_59_59))
        logger.info("Check token transfer from %s..." % self.config["scot_account"])
        token_sent_last_24_h = self.get_token_transfer_last_24_h()
        if token_sent_last_24_h > 0:
            logger.warning("Token were already sent today...")
            return
        logger.info("No token transfer were found, continue...")
        token_per_100_vote = self.get_token_holder()
        logger.info("%d token holder were found." % len(token_per_100_vote))
        token_to_authors = self.get_token_to_sent(start_block, stop_block, token_per_100_vote)
        token_to_authors = self.adapt_to_precision(token_to_authors)
        token_amount_to_sent = self.count_token(token_to_authors)
        logger.info("Start to send %f token to %d accounts" % (token_amount_to_sent, len(token_to_authors)))
        self.send_token(token_to_authors)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("config", help="Config file in JSON format")
    args = parser.parse_args()
    config = json.loads(open(args.config).read())

    nodelist = NodeList()
    nodelist.update_nodes()
    stm = Steem(node=nodelist.get_nodes())

    scot = Scot(
        config,
        stm
    )
    scot.run()


if __name__ == '__main__':
    main()   