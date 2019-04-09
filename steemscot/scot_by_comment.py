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
from steemengine.tokens import Tokens
import time
import shelve
import json
import logging
import argparse
import os
import sys
from steemscot.utils import print_block_log,check_config

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logging.basicConfig()


class Scot_by_comment:
    def __init__(self, config, steemd_instance):
        self.config = config
        self.stm = steemd_instance
        token_list = Tokens()
        if not self.config["no_broadcast"]:
            self.stm.wallet.unlock(self.config["wallet_password"])
        self.token_config = {}
        # add log stats
        self.log_data = {"start_time": 0, "last_block_num": None, "new_commands": 0, "stop_block_num": 0,
                         "stop_block_num": 0, "time_for_blocks": 0} 
        config_cnt = 0
        necessary_fields = ["scot_account", "scot_token", "min_staked_token", "comment_command",
                            "token_memo", "reply", "sucess_reply_body", "fail_reply_body", "no_token_left_body",
                            "user_can_specify_amount", "maximum_amount", "usage_upvote_percentage"]
        self.token_config = check_config(self.config["config"], necessary_fields, self.stm)

        self.blockchain = Blockchain(mode='head', steem_instance=self.stm)
        
    def run(self, start_block):
        
        stop_block = self.blockchain.get_current_block_num()

        if start_block is not None:
            last_block_num = start_block - 1
        self.log_data["start_block_num"] = start_block
        for op in self.blockchain.stream(start=start_block, stop=stop_block, opNames=["comment"],  max_batch_size=50):
            self.log_data = print_block_log(self.log_data, op, self.config["print_log_at_block"])
            last_block_num = op["block_num"]
            
            if op["type"] == "comment":
                token = None
                
                for key in self.token_config:
                    if op["body"].find(self.token_config[key]["comment_command"]) >= 0:
                        token = key
                if token is None:
                    continue
                if op["author"] == self.token_config[token]["scot_account"]:
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
                    if r["author"] == self.token_config[token]["scot_account"]:
                        already_replied = True
                if already_replied:
                    continue
                # Load scot token balance
                scot_wallet = Wallet(self.token_config[token]["scot_account"], steem_instance=self.stm)
                scot_token = scot_wallet.get_token(self.token_config[token]["scot_token"])

                # parse amount when user_can_specify_amount is true
                amount = self.token_config[token]["maximum_amount"]
                if self.token_config[token]["user_can_specify_amount"]:
                    start_index = c_comment["body"].find(self.token_config[token]["comment_command"])
                    stop_index = c_comment["body"][start_index:].find("\n")
                    if stop_index >= 0:
                        command = c_comment["body"][start_index + 1:start_index + stop_index]
                    else:
                        command = c_comment["body"][start_index + 1:]
                        
                    command_args = command.replace('  ', ' ').split(" ")[1:]          
                    
                    if len(command_args) > 0:
                        try:
                            amount = float(command_args[0])
                        except Exception as e:
                            exc_type, exc_obj, exc_tb = sys.exc_info()
                            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                            logger.warn("%s - %s - %s" % (str(exc_type), str(fname), str(exc_tb.tb_lineno)))                        
                            logger.info("Could not parse amount")
                    
                self.log_data["new_commands"] += 1
                wallet = Wallet(c_comment["author"], steem_instance=self.stm)
                token_in_wallet = wallet.get_token(self.token_config[token]["scot_token"])
                if token_in_wallet is None or float(token_in_wallet["balance"]) < self.token_config[token]["min_staked_token"]:
                    reply_body = self.token_config[token]["fail_reply_body"]
                elif c_comment["parent_author"] == c_comment["author"]:
                    reply_body = "You cannot sent token to yourself."
                elif float(scot_token["balance"]) < amount:
                    reply_body = self.token_config[token]["no_token_left_body"]
                else:
                    if "%s" in self.token_config[token]["sucess_reply_body"]:
                        reply_body = self.token_config[token]["sucess_reply_body"] % c_comment["parent_author"]
                    else:
                        reply_body = self.token_config[token]["sucess_reply_body"]
                    if "%s" in self.token_config[token]["token_memo"]:
                        token_memo = self.token_config[token]["token_memo"] % c_comment["author"]
                    else:
                        token_memo = self.token_config[token]["token_memo"]
                    sendwallet = Wallet(self.token_config[token]["scot_account"], steem_instance=self.stm)
                    try:
                        logger.info("Sending %.2f %s to %s" % (amount, self.token_config[token]["scot_token"], c_comment["parent_author"]))
                        sendwallet.transfer(c_comment["parent_author"], amount, self.token_config[token]["scot_token"], token_memo)
                    except Exception as e:
                        exc_type, exc_obj, exc_tb = sys.exc_info()
                        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                        logger.warn("%s - %s - %s" % (str(exc_type), str(fname), str(exc_tb.tb_lineno)))                     
                        logger.warn("Could not send %s token" % self.token_config[token]["scot_token"])
                        continue
                        
                reply_identifier = construct_authorperm(c_comment["parent_author"], c_comment["parent_permlink"])
                if self.config["no_broadcast"]:
                    logger.info("%s" % reply_body)
                else:
                    try:
                        self.stm.post("", reply_body, author=self.token_config[token]["scot_account"], reply_identifier=reply_identifier)
                    except Exception as e:
                        exc_type, exc_obj, exc_tb = sys.exc_info()
                        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                        logger.warn("%s - %s - %s" % (str(exc_type), str(fname), str(exc_tb.tb_lineno)))                     
                        logger.warn("Could not reply to post")
                        continue
                    if self.token_config[token]["usage_upvote_percentage"] > 0:
                        try:
                            c_comment.upvote(self.token_config[token]["usage_upvote_percentage"], voter=self.token_config[token]["scot_account"])
                        except Exception as e:
                            exc_type, exc_obj, exc_tb = sys.exc_info()
                            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                            logger.warn("%s - %s - %s" % (str(exc_type), str(fname), str(exc_tb.tb_lineno)))                        
                            logger.warn("Could not upvote comment")
                            
                time.sleep(4)
        return last_block_num


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("config", help="Config file in JSON format")
    parser.add_argument("--datadir", help="Data storage dir", default='.')
    args = parser.parse_args()
    logger.info("Loading config: %s" % str(args.config))
    config = json.loads(open(args.config).read())
    datadir = args.datadir

    nodelist = NodeList()
    nodelist.update_nodes()
    stm = Steem(node=nodelist.get_nodes(), num_retries=5, call_num_retries=3, timeout=15)

    scot = Scot_by_comment(
        config,
        stm
    )
    
    data_file = os.path.join(datadir, 'data.db')
    data_db = shelve.open(data_file)
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
    block_counter = None
    while True:
        
        last_block_num = scot.run(start_block)
        # Update nodes once a day
        if block_counter is None:
            block_counter = last_block_num
        elif last_block_num - block_counter > 20 * 60 * 24:
            nodelist.update_nodes()
            stm = Steem(node=nodelist.get_nodes(), num_retries=5, call_num_retries=3, timeout=15)
            scot.stm = stm

        start_block = last_block_num + 1
        data_db = shelve.open(data_file)
        data_db["last_block_num"] = last_block_num
        data_db.close()
        time.sleep(3)

    
if __name__ == "__main__":
    main()
