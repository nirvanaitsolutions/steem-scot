## steem-scot
steem-scot is an implementation for Smart Contract Organizational Token for steem-engine.com.


### Installation

```
$ (sudo) pip install steem-scot
```

### Distributing tokens
There are two ways for distributing scot token:

### Distribute by voting
The steem-scot command distributes once a day token to authors which were upvoted by token holder.


#### Running
Once a day, token can be distributed by:

```
$ scot_by_votes /path/to/config.json
```

|        Option       | Value                                                |
|:-------------------:|------------------------------------------------------|
| scot_account | steem account name, which should distribute the token       |
| scot_token   | token symbol, which should be distributed                   |
| token_memo   | memo which is attached to each token transfer               |
| wallet_password | Contains the beempy wallet password |
| no_broadcast | When true, no transfer is made |
| yearly_inflation | yearly_inflation / 365 is the amount which is distributed daily |
| included_apps | When set to [], it is skipped. Can include a list of apps which should be included into the distribution |
| include_token_as_tag | When true, posts which have the token as one tag, are included |
| include_all_posts | When false, a upvote of a post is only included when the app is added to included_apps, the symbol is added as tag or the symbol is added as SETokensSupported field in the post json_metadata |
| downvotes | When true, downvoter which downvoted included posts will receive token |
| upvotes | When true, post authors, which were upvoted by token holder will receive token |



### Distribute by manual command through comments
Scans blocks for new comments containing the given comment_command. The the comment author has suffient
SCOT token, the SCOT account will send token to the parent author.


#### Running
Can be running all day, will only be active when a commentwith the comment_command was broadcasted.

```
$ scot_by_comment /path/to/config.json
```

|        Option       | Value                                                |
|:-------------------:|------------------------------------------------------|
| scot_account | steem account name, which should distribute the token       |
| scot_token   | token symbol, which should be distributed                   |
| token_memo   | memo which is attached to each token transfer               |
| wallet_password | Contains the beempy wallet password |
| no_broadcast | When true, no transfer is made |
| min_staked_token | Minimum amount of token a comment writer must have |
| send_token_amount | Amount of token that will be send|
| sucess_reply_body | Reply body, when token are send|
| fail_reply_body | Reply body, when no token are sent (not min_staked_token available) |
| comment_command | Command which must be included in a comment, to activate the bot |
