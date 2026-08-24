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

This sounds really simple, using something like [Silverback](https://docs.apeworx.io/silverback/latest/userguides/quickstart.html) and you are all set, while it may be possible for some cases you are going to encounter two issues, one is going to be gas cost, you are going to see insane amounts of gas beign used while trying to do this and the other issue is going be that maybe the bot goes down, that leads stakers getting less than they expect.

it could work for really low counts of stakers.

## The solution
The solution would be lazy accounting,

We are going to store amount of rewards per token staked, this is going to be like a counter that is going to only increment, and this is going to count from the begining of the stkaing period until the end. Thsi in turn is going to allow us to count two other variables. one is going to be the amount of rewards the user is owed, and the other is going to be the amount of rewards the user owes. This may be confusing for some peeople, but the concept is really elegant, so let me explain.

We are storing how much rewarwds a single staked token would have rearned since the beignin of the staking period, now, not everyonone has been staking since the begining, to account for this we also have to store the "debt" the stkers has, for example, lets say Bob has started to stake in block 10, this is 10 blocks after the staking rewards have started to beign distributed, so when bob enters with a stake of 100 tokens, if we only had the rewaards_per_token_Staked variable we could be accrediting anincorret stake rewrds to Bob, how has only started staking.

Bob stake:
100 stake tokens, 5 rewards per token staked, due to Bob: 0, stmart contract would be showing due 500,

To account for this we store the "debt" Bob, meaning how much rewards tokens bob should be gettinig because of the tiem at wich he started staking. This is the model used in SushiSwaps's MasterChef staking algorithm, and is really simple to wrap your head around, we are only tracking the rewards that a single token has accroued since the beggining of time, since not all pariticapnts have been staking since the beining of time we need to account for this offset, and that is the rewardDebt.

So each time someone iteracts with the staking pool, we update the rewards per token stoored, among other things, to keep this accounting sound. For example this could be: staking, unstaking, and harvesting. This pattern makes sure that no staker misses rewards and this costs a lot less gas.

In this guide we are going to implement this solution using Vyper, inspired mainly from the Unipool and Syntheix staking rewarsd algorithm, theere are a few differences between MasterChef and Unipool, we are going to explain what those diferences are.

## Setup

For this particular project im going to be using Moccasin, that is a Vyper first smart contract development frameworks built on top of Titanoboa. im going to be using moccasing to actually write some tests, and invariants at the end of this guide so you have a better idea on how this works, and how you can apply this to your own protocols.

### Installing Moccasing
TODO: do a simple guide on how to install moccasin

### Project setup
TODO: create a project using moccasing, and create a .vy smart contract called StakingRewards.


## Staking Rewards

For this guide we are going to be wworking with vypert 0.4.3 and we are going to be using a compiler flag fetaure unique to vyper, to disable reentracy across the entire smart contract.

```vyper
# pragma version ==0.4.3
# pragma nonreentrancy off
```

Now we need to store two immutables, the tokens that we want usuers to stake, and the token we are going to distribute as rewards, in the MasterChef algorithm the rewards token is ineed the staking contract, so if you see the sourcecode wew actually mint the rewards, in Unipool isntead we just distribute rewards, this means that the contract has to have engouuht rewards to cover for the whole staking rewards period.

```vyper
# @dev We import the built-in IERC20 interface.
from ethereum.ercs import IERC20


# @dev Immutable staking token set at deploy.
staking_token: public(immutable(IERC20))


# @dev Immutable rewards token set at deploy.
rewards_token: public(immutable(IERC20))


@deploy
def __init__(_staking_token: IERC20, _rewards_token: IERC20):
  staking_token = _staking_token
  rewards_token = _rewards_token
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

Like I said before, we need to store how much each individual token generas in rewawrds, as well as the reward reate and the starting and endinig timestamps. The last ones are actually specific to the Unipool variant of the staking contract, we store how much each individual token accrues, as well as the initial reward rate, the endind time stamp and the last timestamp where the pool was udpated, remember wew only update the pool on interactions, meaining deposits, withdraws and harversts.

Unipool keeps the rewards separate, this means the user has to harvest the rewards in order to receive them, MasterChef distributes the rewards on interaction, meaning when the user stakes (if they had a previous stake) or withdraws.

These are global variables, shared accross the entire staking rewards smart contract
```vyper
# @dev TODO
period_finish: public(uint256)


# @dev TODO
reward_rate: public(uint256)


# @dev TODO
last_update_time: public(uint256)


# @dev TODO
reward_per_token stored: public(uint256)
```

Now for this spefiic rewards smart contract I only want to distribute rewards for 9 days, so im going to define a constant called DURATION and set that to 9 days in seconds:

```vyper
# @dev TODO
# 777600 = 9 days in seconds
DURATION: constant(uint256) = 777600 
```

Now that we are adding constants, lest also add a constant that is going to be used to do some calculations:

```vyper
# @dev TODO
PRECISION: constant(uint256) = 10**18 
```

And we are goinig to set the duration on the finish at timestamp in the constructor as well as the reward rate and the reward per token stored.

```vyper
@deploy
def __init__(
  _staking_token: IERC20,
  _rewards_token: IERC20,
  _reward_rate: uint256
  _reward_per_token_stored: uint256
):
  staking_token = _staking_token
  rewards_token = _rewards_token
  self.reward_rate = _reward_rate
  self.reward_per_token_stored = _reward_per_token_stored
  self.period_finish = block.timestamp + DURATION
```

So from this smart contract perspective, staking rewards are going to be distributed from the deployment until 9 days have passed.

Now we need to also store a few data fields, specific too each user, these are going to be the accumulated rewards of the staker, and the other one is going to be the userRewardPerTokenPaid, this is essentialy a record of the reward per token paid the last time the user interacted with the staking smart contract, this is going to be useful.


```vyper
# @dev TODO
reward_per_token_paid: public(HashMap[address, uint256])


# @dev TODO
rewards: public(HashMap[address, uint256])
```

Now with that in place we are also going to define a few events that are going to be useful in a produuction grade staking rewards smart contract.

```vyper
# @dev TODO
event RewardAdded:
  reward: uint256 


# @dev TODO
event Staked:
  user: indexed(address)
  amount: uint256


# @dev TODO
event Withdrawn:
  user: indexed(address)
  amount: uint256


# @dev TODO
event RewardPaid
  user: indexed(address)
  reward: uint256
```
