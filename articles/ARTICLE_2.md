# Staking rewards are just an accumulator (in Vyper 🐍)

Staking rewards look complicated. They are not.

I went through a pile of articles on staking, and the mechanism is simpler than I expected. If you are going to ship a pool, you need to understand this model.

## The naive way

First thought: an offchain bot that pays everyone every block.

```python
@bot.on_(chain.blocks)
def distribute_rewards(block):
    for staker in stakers:
        token.transfer(staker, calculate_rewards_amount(staker))
```

[Silverback](https://docs.apeworx.io/silverback/latest/userguides/quickstart.html) can do this. It even looks clean.

You will hit two walls. Gas: looping every staker every block is expensive. Liveness: if the bot goes down, stakers earn less than they were promised.

There is a simpler way, and it lives onchain.

## Lazy accounting

Lazy accounting means you do not push rewards every second. You keep a running index of how much one staked token is owed, and you only settle a user when they touch the pool.

The index is a counter that only goes up, from the start of the period to the end. From that one number you get two others: how much the user is owed, and a checkpoint (often called debt) of the index at the moment they staked.

You are storing how much a single staked token would have earned since the beginning. Not everyone has been in since the beginning, so you also store each staker's checkpoint.

Example. Rewards started at block 0. Bob deposits 100 tokens at block 10. The index is already 5. If you only stored `reward_per_token_staked`, the contract would show Bob owed 500 for a stake he just opened. He is owed 0.

So you store `reward_per_token_stored_paid` for Bob, and you subtract it later. He does not get paid for time he was not in.

That is the MasterChef idea, and it is small once you see it: track what one token has accrued since t=0, then store an offset per user because not everyone started at t=0. That offset is the reward debt.

Every time someone interacts (stake, unstake, harvest), you update the index first. No active staker is cheated for time they were in. Time with zero stake is not paid to the next depositor, and you are not paying the whole set on every block.

In this guide we implement it in Vyper, mostly from Unipool and the Synthetix staking rewards pattern. MasterChef and Unipool are not the same contract. I will mark where they split.

## Setup

I am using Moccasin, a Vyper-first framework built on top of Titanoboa. This repo's tests and invariants live under `tests/` (unitary, integration, fuzz) — steal that pattern for your own protocol rather than inlining it here.

### Installing Moccasin

Python 3.11+ and uv. Install Moccasin as a global tool:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
uv tool install moccasin
mox --version
```

`mox` is the CLI. If it is missing, restart the terminal (or `source ~/.bashrc`) after installing uv.

### Project setup

```bash
mox init staking-rewards
cd staking-rewards
```

You get `src/`, `tests/`, `script/`, and `moccasin.toml`. Put the contract in `src/StakingRewards.vy`. This guide targets Vyper 0.4.3:

```bash
uv add moccasin
uv add "vyper==0.4.3"
```

## Staking Rewards

Vyper 0.4.3, with the compiler flag that puts a contract-wide reentrancy lock on external functions (this is also the 0.4 default).

```vyper
# pragma version ==0.4.3
# pragma nonreentrancy on
```

Two immutables: the token users stake, and the token you pay as rewards.

In MasterChef, users stake LP tokens and the contract mints a separate reward token. In Unipool you transfer a pre-funded reward token, so the contract must already hold enough for the whole period. In this Unipool-style contract the two tokens must be different, otherwise harvest can pay out other people's deposits.

```vyper
# @dev We import the built-in IERC20 interface.
from ethereum.ercs import IERC20

# @dev Immutable staking token set at deploy.
staking_token: public(immutable(IERC20))

# @dev Immutable rewards token set at deploy.
rewards_token: public(immutable(IERC20))
```

Track how much `staking_token` is in the pool, and how much each staker put in.

```vyper
# @dev The total amount of staking_token staked.
total_supply: uint256

# @dev The amount that each individual staker
# has staked.
balances: HashMap[address, uint256]
```

Then the index, the reward rate, and the timestamps. `period_finish` and `reward_rate` are Unipool-specific, and immutables here because this implementation never changes them after deploy. We store how much each staked token has accrued, tokens per second for the whole pool, when the period ends, and the last time the pool was updated. Remember: we only update on deposit, withdraw, and harvest.

Unipool keeps rewards separate. The user has to harvest to receive them. MasterChef pays on interaction: stake (if they already had a stake) or withdraw.

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

Per staker: the last index they were paid against, and rewards already owed but not harvested.

If they harvested when `reward_per_token_stored` was 3, and it is 7 now, those first 3 are done. `rewards` is the snapshot of unclaimed earnings, so a later deposit or withdraw does not drop them if they have not harvested yet.

```vyper
# @dev Personal mark that each staker is going to have, tracks what was the last
#      `reward_per_token_stored` that the user got paid
reward_per_token_stored_paid: public(HashMap[address, uint256])

# @dev Tracks how much rewards a user is owed.
rewards: public(HashMap[address, uint256])
```

This contract only pays for 9 days:

```vyper
# @dev Duration in seconds. 9 days.
DURATION: constant(uint256) = 777600
```

And a WAD scale for the accumulator. This is Q-notation precision for `reward_per_token_stored`, not the token decimals.

```vyper
# @dev Accumulator scale (1 WAD). This is Q-notation precision for
#      reward_per_token_stored, not the staking or rewards token decimals.
PRECISION: constant(uint256) = 10**18
```

Set `period_finish`, `reward_rate`, and `last_update_time` in the constructor. Assert the two tokens are different.

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

From this contract's point of view, rewards run from deploy until 9 days later.

Events you actually want in a production pool:

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

## The index

The key function is `_reward_per_token()`. It answers one question: how much has a single staked token earned?

The formula is the same shape in Unipool and MasterChef. Unipool counts seconds. MasterChef counts blocks.

```vyper
@internal
@view
def _reward_per_token() -> uint256:
  if self.total_supply == 0:
    return self.reward_per_token_stored

  return self.reward_per_token_stored + ((self._last_time_reward_applicable() - self.last_update_time) * reward_rate * PRECISION) // self.total_supply
```

If `total_supply` is 0, skip the accumulator. Nobody is there to credit, so that interval's rewards stay in the contract instead of going to whoever deposits next.

Otherwise add `(time_delta * reward_rate * PRECISION) / total_supply` to the stored index. Dilution is automatic: more stake in the pool, slower the index moves.

`_last_time_reward_applicable` is just `min(block.timestamp, period_finish)`.

```vyper
@internal
@view
def _last_time_reward_applicable() -> uint256:
  return min(block.timestamp, period_finish)
```

With those two, you can compute unclaimed rewards for any staker:

```vyper
@internal
@view
def _earned(account: address) -> uint256:
  return self.balances[account] * (self._reward_per_token() - self.reward_per_token_stored_paid[account]) // PRECISION + self.rewards[account]
```

Then the function everything else hangs on: `_update_pool`.

```vyper
@internal
def _update_pool(account: address):
  self.reward_per_token_stored = self._reward_per_token()
  self.last_update_time = self._last_time_reward_applicable()
  if account != empty(address):
    self.rewards[account] = self._earned(account)
    self.reward_per_token_stored_paid[account] = self.reward_per_token_stored
```

Call this before anything else, on every deposit, withdraw, and harvest. You settle the user against the current index before you change balances.

Line 1 moves the global index forward: how much one token has earned since the start.

Line 2 caps time at `period_finish`, so you stop accruing after the window.

If the account is not the zero address, you snapshot what they are owed into `rewards`, then move their paid checkpoint up to the current index so the next delta does not double-count.

## Pool interactions

Once `_update_pool`, `_earned`, and the index are right, that is the staking algorithm. The external functions are just the doors.

Deposit:

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

Zero amount reverts. Then update the pool, before any balance change. Then bump `total_supply` and the user's balance, transfer in (CEI), emit `Staked`.

Withdraw:

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

Same order: check, update pool, then accounting, then transfer out. Vyper reverts on underflow, so you do not need a separate "enough stake" check. Notice we do not send rewards here. That is harvest.

Harvest:

```vyper
@external
def harvest():
  self._update_pool(msg.sender)
  earned: uint256 = self._earned(msg.sender)
  if earned > 0:
    self.rewards[msg.sender] = 0
    extcall rewards_token.transfer(msg.sender, earned)
    log RewardPaid(user=msg.sender, reward=earned)
```

Update the pool first so `earned` is current. If `earned` is 0, do nothing (no event). Else zero `rewards`, then transfer (CEI).

You could add `exit()` that withdraws and harvests in one call. If you want to write it, go for it.

## Extra views

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

## Final notes

A few things you should not skip:

1. Be honest about funding. The pool has to hold enough `rewards_token` for the whole period. If it does not, `harvest` reverts, and that is a broken product, not a gas trick.
2. This is Unipool, by k06a, not MasterChef. Read the original if you want the smallest version of the idea.
3. Do the math once on paper. The [RareSkills staking algorithm post](https://rareskills.io/post/staking-algorithm) is the cleanest path to this formula. Useful if you care about algorithmic thinking, not just copying the contract.

Don't only ship the pool. Understand the index.

[StakingRewards source and tests](https://github.com/rafael-abuawad/staking-rewards)
