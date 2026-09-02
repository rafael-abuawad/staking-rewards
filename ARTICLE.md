# Exploring an essential DeFi model: Staking Rewards! Using Vyper 🐍

During this investigation, I came across a lot of articles and content about staking, and staking rewards, the reality on how this mechanism works is much simpler than anything I ever imagined, and I think is really important to understand this model.

## Staking rewards the naive way

The first thought you may have in mind is to have an offchain system, a bot or a simple script that distributes said rewards per second or per block, this is simple and straight forward, right?

```python
@bot.on_(chain.blocks)
def distribute_rewards(block):
    for staker in stakers:
      token.transfer(staker, calculate_rewards_amount(staker))
```

This sounds really simple, using something like [Silverback](https://docs.apeworx.io/silverback/latest/userguides/quickstart.html) and you are all set, while it may be possible for some cases you are going to encounter two issues, one is going to be gas cost, you are going to see insane amounts of gas beign used while trying to do this and the other issue is going be that maybe the bot goes down, if that happens, that leads stakers getting less than they expect.

There is a simpler, more efficient way to do this.

## The solution
The solution would be lazy accounting, meaning, a simple algorithm that counts how much a token stored is owed in staking rewards.

We are going to store amount of rewards per token staked, this is going to be like a counter that is going to only increment, and this is going to count from the begining of the stkaing period until the end. This in turn is going to allow us to count two other variables: one is going to be the amount of rewards the user is owed, and the other is a checkpoint (often called "debt") of the accumulator at the moment they staked. This may be confusing for some peeople, but the concept is really elegant, so let me explain.

We are storing how much rewards a single staked token would have earned since the beignin of the staking period, now, not everyonone has been staking since the begining, to account for this we also have to store a checkpoint of the accumulator for each staker, for example, lets say Bob has started to stake in block 10, this is 10 blocks after the staking rewards have started to beign distributed, so when bob enters with a stake of 100 tokens, if we only had the rewaards_per_token_Staked variable we could be accrediting anincorret stake rewrds to Bob, how has only started staking.

Bob stake:
100 stake tokens, 5 rewards per token staked, due to Bob: 0, stmart contract would be showing due 500,

To account for this we store `reward_per_token_stored_paid` for Bob, a checkpoint we subtract later so he does not get rewards from before he deposited. This is the model used in SushiSwaps's MasterChef staking algorithm, and is really simple to wrap your head around, we are only tracking the rewards that a single token has accroued since the beggining of time, since not all pariticapnts have been staking since the beining of time we need to account for this offset, and that is the rewardDebt.

So each time someone iteracts with the staking pool, we update the rewards per token stoored, among other things, to keep this accounting sound. For example this could be: staking, unstaking, and harvesting. This pattern makes sure that no staker misses rewards and this costs a lot less gas. This is important, because we only update the pool in interactions (deposit, withdraw, harvest)

In this guide we are going to implement this solution using Vyper, inspired mainly from the Unipool and Syntheix staking rewarsd algorithm, theere are a few differences between MasterChef and Unipool, we are going to explain what those diferences are.

## Setup

For this particular project im going to be using Moccasin, that is a Vyper first smart contract development frameworks built on top of Titanoboa. im going to be using moccasing to actually write some tests, and invariants at the end of this guide so you have a better idea on how this works, and how you can apply this to your own protocols.

### Installing Moccasin
You need Python 3.11+ and [uv](https://docs.astral.sh/uv/). Then install Moccasin as a global tool:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
uv tool install moccasin
mox --version
```

`mox` is the Moccasin CLI. If the command is not found, restart your terminal (or `source ~/.bashrc`) after installing uv.

### Project setup
Scaffold a new project and drop in the staking contract:

```bash
mox init staking-rewards
cd staking-rewards
```

That gives you `src/`, `tests/`, `script/`, and `moccasin.toml`. Rename or replace the sample contract with `src/StakingRewards.vy` — that is the file we are going to write next. This guide targets Vyper 0.4.3, so pin it in the project if you are using a local venv:

```bash
uv add moccasin
uv add "vyper==0.4.3"
```


## Staking Rewards

For this guide we are going to be wworking with vypert 0.4.3 and we are going to be using a compiler flag unique to vyper that enables a contract-wide reentrancy lock on external functions (this is also the Vyper 0.4 default).

```vyper
# pragma version ==0.4.3
# pragma nonreentrancy on
```

Now we need to store two immutables, the tokens that we want usuers to stake, and the token we are going to distribute as rewards, in the MasterChef algorithm the rewards token is ineed the staking contract, so if you see the sourcecode wew actually mint the rewards, in Unipool isntead we just distribute rewards, this means that the contract has to have engouuht rewards to cover for the whole staking rewards period. In this Unipool-style contract the staking token and the rewards token must be different, otherwise harvest could pay out other people's deposits.

```vyper
# @dev We import the built-in IERC20 interface.
from ethereum.ercs import IERC20


# @dev Immutable staking token set at deploy.
staking_token: public(immutable(IERC20))


# @dev Immutable rewards token set at deploy.
rewards_token: public(immutable(IERC20))
```

Now that we have those immutables in place, we are going to define the storage variables that we are going to use to distribute the staking rewards. Wew need to track how much of staking_token has been staked, and how much each staker has staked.

```vyper
...

# @dev The total amount of staking_token staked.
total_supply: uint256


# @dev The amount that each individual staker
# has staked.
balances: HashMap[address, uint256]

...
```

Like I said before, we need to store how much each individual token generas in rewawrds, as well as the reward reate and the starting and endinig timestamps. The last ones are actually specific to the Unipool variant of the staking contract, we store how much each individual token accrues, as well as the pool-wide reward rate (tokens per second), the endind time stamp and the last timestamp where the pool was udpated, remember wew only update the pool on interactions, meaining deposits, withdraws and harversts.

Unipool keeps the rewards separate, this means the user has to harvest the rewards in order to receive them, MasterChef distributes the rewards on interaction, meaning when the user stakes (if they had a previous stake) or withdraws.

These are global variables, shared accross the entire staking rewards smart contract. `period_finish` and `reward_rate` are immutables because this implementation never updates them after deploy.
```vyper
# @dev We store when is the staking rewards period going to end.
#      Since there is no way to update this in this implementation we
#      are going to store this as an immutable.
period_finish: public(immutable(uint256))


# @dev Reward tokens distributed per second across the whole pool.
#      Since there is no way to update this in this implementation we
#      are going to store this as an immutable.
reward_rate: public(immutable(uint256))


# @dev We store the last time someone interacted with the pool.
last_update_time: public(uint256)


# @dev We store how much each individual staked token has earned in rewards
reward_per_token_stored: public(uint256)
```

And these are staker-bound variables, so we stored them as mappings, we store how much any given staker has already being paid in rewards_per_token, meaning, not in rewards (for example, lets say user did a harverst wen reward_per_token_stored was 3, and now reward_per_token_stored is 7, we should not be taking into account those initial 3 anymore) and rewards, rewards is going to be a mapping that stores the last rewards count the user has accumulated, useful is the user is doing a new deposit or withdraw and hasnt harvest yet.
```vyper
# @dev Personal mark that each staker is going to have, tracks what was the last
#      `reward_per_token_stored` that the user got paid
reward_per_token_stored_paid: public(HashMap[address, uint256])


# @dev Tracks how much rewards a user is owed.
rewards: public(HashMap[address, uint256])
```


Now for this spefiic rewards smart contract I only want to distribute rewards for 9 days, so im going to define a constant called DURATION and set that to 9 days in seconds:

```vyper
# @dev Duration in seconds. 9 days in seconds.
DURATION: constant(uint256) = 777600 
```

Now that we are adding constants, lest also add a constant that is going to be used as accumulator scale (1e18 Q-notation), not as the token decimals:

```vyper
# @dev Accumulator scale (1 WAD). This is Q-notation precision for
#      reward_per_token_stored, not the staking or rewards token decimals.
PRECISION: constant(uint256) = 10**18 
```

And we are goinig to set `period_finish`, `reward_rate`, and `last_update_time` in the constructor. We also assert that the staking token and the rewards token are different.

```vyper
@deploy
def __init__(
  _staking_token: IERC20,
  _rewards_token: IERC20,
  _reward_rate: uint256
):
  assert _staking_token != _rewards_token  # dev: staking and rewards tokens must differ
  staking_token = _staking_token
  rewards_token = _rewards_token
  period_finish = block.timestamp + DURATION
  reward_rate = _reward_rate
  self.last_update_time = block.timestamp
```

So from this smart contract perspective, staking rewards are going to be distributed from the deployment until 9 days have passed.

Now with that in place we are also going to define a few events that are going to be useful in a produuction grade staking rewards smart contract.

```vyper
# @dev Emitted when a user stakes tokens.
event Staked:
  user: indexed(address)
  amount: uint256


# @dev Emitted when a user withdraws staked tokens.
event Withdrawn:
  user: indexed(address)
  amount: uint256


# @dev Emitted when a user harvests staking rewards.
event RewardPaid:
  user: indexed(address)
  reward: uint256
```

The first and most imporatnt, an a key component, is going to be the _reward_per_token() function. This function is going to tell us how much rewards a SINGLE staked token has earned. The formula is similar, for both Unipool and MasterChef, the only difference is that Unipool counts seconds and MasterChef counts blocks.

```vyper
@internal
@view
def _reward_per_token() -> uint256:
  if self.total_supply == 0:
    return self.reward_per_token_stored

  return self.reward_per_token_stored + ((self._last_time_reward_applicable() - self.last_update_time) * reward_rate * PRECISION) // self.total_supply
```

Like I said, this part of the algorithm is essential, if we analize it line by line we are going to find a few things. First is that if the total_supply of tokens staked is 0, we skip the accumulator: there is nobody to credit, so rewards for that interval are left in the contract instead of being given to later stakers. Else, we do a calculation, we add to reward_per_token_stored the increment `(time_delta * reward_rate * PRECISION) / total_supply`, where time_delta is `_last_time_reward_applicable() - last_update_time`. The dilution is automatic, is going to happen.

_last_time_reward_applicable is just the minimum number between block.timestamp and the finish timestamp.
```vyper
@internal
@view
def _last_time_reward_applicable() -> uint256:
  return min(block.timestamp, period_finish)
```

With these two functions in place we can calculate how much any given staker has earned, how many rewards the user has not yet claimed.
```vyper
@internal
@view
def _earned(account: address) -> uint256:
  return self.balances[account] * (self._reward_per_token() - self.reward_per_token_stored_paid[account]) // PRECISION + self.rewards[account]
```

Now, with all these internal view functions we can do the most essential part of the staking smart contract, the _update_pool smatr contract.
```vyper
@internal
def _update_pool(account: address):
  self.reward_per_token_stored = self._reward_per_token()
  self.last_update_time = self._last_time_reward_applicable()
  if account != empty(address):
    self.rewards[account] = self._earned(account)
    self.reward_per_token_stored_paid[account] = self.reward_per_token_stored
```
Now, lets go over this function, this function gets called before anything else, and is called on every pool interaction (withdraw, deposit, harvest), this is because we need to update our stakers first, before any pool update, to avoid issues.

The first line is going to update or move forward the reward_per_token_stored, this is to have the accumulator up to date, because if we look at how that function works is the algorithm that tells the staking pool how much a single staked token has earned in rewards, since the start. The second line is we check if the pool is still active, meaning, if we keep updating the time or the current timestamp is out of bounds for the distribution and the third line is a conditional, if the address that we passed to the function is not the zero address we update the rewasrds so the user can claim them later, and we update their `reward_per_token_stored_paid` checkpoint so the algorithm is not paying the user staking rewards from before this interaction.


## Pool interactions
NOow with all of those functions in place we are almost done, see, the most important thing of a staking algorithm is going to be the _update_pool, how much a user has earned, what is the current reward rate per token stored, that IS staking, ONce that is done we can build the functions that the stakers are goinog to be calling to interact with the stakingn pool.

The first function is going to be deposit, and is self descriptive.
```vyper
@external
def deposit(amount: uint256):
  assert amount > 0 # dev: invalid deposit amount
  self._update_pool(msg.sender)
  self.total_supply += amount
  self.balances[msg.sender] += amount
  extcall staking_token.transferFrom(msg.sender, self, amount)
  log Staked(user=msg.sender, amount=amount)
```
If we go over this function line by line we are going to see a few things, first, we check that the user is not sending in amount zero. Then we update the pool! this is important because the pool update NEEDs to happen before any user balance update or any pool update, then we update the total supply of tokens staked and the amount that each user has staked, then (following CEI) we transfer the staking tokens from the caller to the pool and we emit an event indicating that the user has staked.

The next function is going to be withdraw.
```vyper
@external
def withdraw(amount: uint256):
  assert amount > 0 # dev: invalid withdraw amount
  self._update_pool(msg.sender)
  self.total_supply -= amount
  self.balances[msg.sender] -= amount
  extcall staking_token.transfer(msg.sender, amount)
  log Withdrawn(user=msg.sender, amount=amount)
```
If we go ove this function line by line, we first see the check, then we update the pool! again this extremly important, the pool update has to happen before any of the internal accounting variables gets updated, the we reduce the total amount of staked tokens and the amount of staked tokens by that caller, since we are using vyper, we do not need to check if the user has engouht the vyper compiler is good enught to revert if the subtractioon results in an underflow, after that (following CEI) we transfer the staked tokens back to the caller and we emit an event. If yoou notice something here, we are not transfering rewards, thats were the next function comes in.

The next function is going to be harvest, and here is where we are going to transfer the staking rewards. 
```vyper
@external
def harvest():
  self._update_pool(msg.sender)
  
  earned: uint256 = self._earned(msg.sender)
  assert earned > 0 # dev: no staking rewards earned
  self.rewards[msg.sender] = 0
  extcall rewards_token.transfer(msg.sender, earned)
  log RewardPaid(user=msg.sender, reward=earned)
```
If we go over line by line in this functiono we are going to see a few things, First (you see where this is going) upadte the pooool!!!!! The order is important here, we want to make sure the rewards earned by our staker are up to date before doing the harvest, we take the amount of tokens earned, if there aren't any we just revert, else, we reset the rewards to 0, and (following CEI) transfer the reward tokens

We could also add an exit function, a function that withdraws and harvest at the same time. If you want to give it a try, go for it!

## Extra view functions
We should add the folliwng view fucntions for better functinality:

```vyper
@external
@view
def balanceOf(account: address) -> uint256:
    return self.balances[account]


@external
@view
def totalSupply() -> uint256:
    return self.total_supply



@external
@view
def last_time_reward_applicable() -> uint256:
    return self._last_time_reward_applicable()


@external
@view
def reward_per_token() -> uint256:
    return self._reward_per_token()


@external
@view
def earned(account: address) -> uint256:
    return self._earned(account)
```


## Conclusion

A few things you may have noticed, the staking pool contract has to have enought of the reward token to distrubute, else, calling harvest is goinog to revert, and we don't want that. Second, this is based on the UNipool staking algothim by k06a. If you go over to the original implementation you are going to sees that is extremly simple, I would recommend going over the [RereSkills Staking Algothim post first](https://rareskills.io/post/staking-algorithm), there is some interesting math here, and you can defently see how to get to this exact formula using only math, useful for algothimic thingking. i hope you like this article.

Github repo.
