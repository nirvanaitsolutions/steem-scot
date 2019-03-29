#!/usr/bin/python
from beem import Steem
from beem.comment import Comment
from beem.account import Account
from beem.amount import Amount
from beem.blockchain import Blockchain
from beem.nodelist import NodeList
from beem.exceptions import ContentDoesNotExistsException
from beem.utils import addTzInfo, resolve_authorperm, construct_authorperm, derive_permlink, formatTimeString
from datetime import datetime, timedelta
from steemengine.wallet import Wallet
import time
import shelve
import json
import logging
import argparse

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logging.basicConfig()


class Scot_by_comment:
    def __init__(self, config, steemd_instance):
        self.config = config
        self.stm = steemd_instance
        
        if not self.config["no_broadcast"]:
            self.stm.wallet.unlock(self.config["wallet_password"])
        self.blockchain = Blockchain(mode='head', steem_instance=self.stm)
        
    def run(self, start_block):
        
        stop_block = self.blockchain.get_current_block_num()
        if stop_block % 20 == 0:
            logger.info("current block %d" % (stop_block))
        last_block_num = stop_block
        cnt = 0
        for op in self.blockchain.stream(start=start_block, stop=stop_block, opNames=["comment"],  max_batch_size=50):
            cnt += 1
            last_block_num = op["block_num"]
            
            if op["type"] == "comment":
                  
                if op["body"].find(self.config["comment_command"]) < 0:
                    continue
                if op["author"] == self.config["scot_account"]:
                    continue

                try:
                    c_comment = Comment(op, steem_instance=self.stm)
                    c_comment.refresh()
                except:
                    logger.warn("Could not read %s/%s" % (op["author"], op["permlink"]))
                    continue
                if c_comment.is_main_post():
                    continue
                if abs((c_comment["created"] - op['timestamp']).total_seconds()) > 9.0:
                    logger.warn("Skip %s, as edited" % c_comment["authorperm"])
                    continue
                already_replied = False
                for r in c_comment.get_all_replies():
                    if r["author"] == self.config["scot_account"]:
                        already_replied = True
                if already_replied:
                    continue
                
                
                
                wallet = Wallet(c_comment["author"], steem_instance=self.stm)
                token = wallet.get_token(self.config["scot_token"])
                if token is None or float(token["balance"]) < self.config["min_staked_token"]:
                    reply_body = self.config["fail_reply_body"]
                elif c_comment["parent_author"] == c_comment["author"]:
                    reply_body = "You cannot sent token to yourself."
                else:
                    if "%s" in self.config["sucess_reply_body"]:
                        reply_body = self.config["sucess_reply_body"] % c_comment["parent_author"]
                    else:
                        reply_body = self.config["sucess_reply_body"]
                    if "%s" in self.config["token_memo"]:
                        token_memo = self.config["token_memo"] % c_comment["author"]
                    else:
                        token_memo = self.config["token_memo"]
                    sendwallet = Wallet(self.config["scot_account"], steem_instance=self.stm)
                    sendwallet.transfer(c_comment["parent_author"], self.config["send_token_amount"], self.config["scot_token"], token_memo)

                reply_identifier = c_comment["authorperm"]
                if self.config["no_broadcast"]:
                    logger.info("%s" % reply_body)
                else:
                    self.stm.post("", reply_body, author=self.config["scot_account"], reply_identifier=reply_identifier)
                time.sleep(4)
        return last_block_num
        
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("config", help="Config file in JSON format")
    args = parser.parse_args()
    config = json.loads(open(args.config).read())

    nodelist = NodeList()
    nodelist.update_nodes()
    stm = Steem(node=nodelist.get_nodes(), num_retries=5, call_num_retries=3, timeout=15)

    scot = Scot_by_comment(
        config,
        stm
    )
    
    data_db = shelve.open('data.db')
    if "last_block_num" in data_db:
        last_block_num = data_db["last_block_num"]
    else:
        last_block_num = 0
    if "comment_queue" in data_db:
        comment_queue = data_db["comment_queue"]
    else:
        comment_queue = {}
  
    if "last_block_num" in data_db:
        start_block = data_db["last_block_num"] + 1
    else:
        start_block = None
    data_db.close()
    logger.info("starting token distributor..")
    
    while True:
        
        last_block_num = scot.run(start_block)
        start_block = last_block_num + 1
        data_db = shelve.open('data.db')
        data_db["last_block_num"] = last_block_num
        data_db.close()
        time.sleep(3)

    
if __name__ == "__main__":
    main()
