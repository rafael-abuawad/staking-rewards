# pragma version ==0.4.3
# pragma nonreentrancy off

# @dev We import the built-in IERC20 interface.
from ethereum.ercs import IERC20


# @dev Immutable staking token set at deploy.
staking_token: public(immutable(IERC20))


# @dev Immutable rewards token set at deploy.
rewards_token: public(immutable(IERC20))


# @dev We store the amount of staked tokens
total_supply: uint256


# @dev We store how much each staker has currently staked
balances: HashMap[address, uint256]


# @dev We store when is the staking rewards period going to end.
#      Since there is no way to update this in this implementation we
#      are going to store this as an immutable.
period_finish: public(immutable(uint256))


# @dev The initial reward rate per token stored.
#      Since there is no way to update this in this implementation we
#      are going to store this as an immutable.
reward_rate: public(immutable(uint256))


# @dev We store the last time some interacted with the pool.
last_update_time: public(uint256)


# @dev We store how much each individual staked token has earned in rewards
reward_per_token_stored: public(uint256)


# @dev Personal mark that each staker is going to have, tracks what was the last
#      `reward_per_token_stored` that the user got paid
reward_per_token_stored_paid: public(HashMap[address, uint256])


# @dev Tracks how much rewards a user is owed.
rewards: public(HashMap[address, uint256])


# @dev Duration in seconds. 9 days in seconds.
DURATION: constant(uint256) = 777600


# @dev Used for calculations, since we are working with Q-notation
#      We are goinig to store 1 WAD. This number is going to be different
#      if you are woirking with tokens with different decimals, for example
#      USDT or USDC.
PRECISION: constant(uint256) = 1 * 10**18


# @dev TODO
event Staked:
    user: indexed(address)
    amount: uint256


# @dev TODO
event Withdrawn:
    user: indexed(address)
    amount: uint256


# @dev TODO
event RewardPaid:
    user: indexed(address)
    reward: uint256


@deploy
def __init__(
    _staking_token: IERC20, _rewards_token: IERC20, _reward_rate: uint256
):
    staking_token = _staking_token
    rewards_token = _rewards_token
    period_finish = block.timestamp + DURATION
    reward_rate = _reward_rate


@internal
@view
def _last_time_reward_applicable() -> uint256:
    return min(block.timestamp, period_finish)


@internal
@view
def _reward_per_token() -> uint256:
    if self.total_supply == 0:
        return self.reward_per_token_stored

    return (
        self.reward_per_token_stored
        + (
            (self._last_time_reward_applicable() - block.timestamp)
            * reward_rate
            * PRECISION
        ) // self.total_supply
    )


@internal
@view
def _earned(account: address) -> uint256:
    return (
        self.balances[account]
        * (
            self._reward_per_token()
            - self.reward_per_token_stored_paid[account]
        ) // PRECISION
        + self.rewards[account]
    )


@internal
def _update_pool(account: address):
    latest_reward_per_token_stored: uint256 = self._reward_per_token()
    self.reward_per_token_stored = latest_reward_per_token_stored
    self.last_update_time = self._last_time_reward_applicable()
    if account != empty(address):
        self.rewards[account] = self._earned(account)
        self.reward_per_token_stored_paid[
            account
        ] = latest_reward_per_token_stored


@internal
def _deposit(account: address, amount: uint256):
    assert amount > 0  # dev: invalid amount to deposit
    self._update_pool(account)
    self.balances[account] += amount
    self.total_supply += amount
    extcall staking_token.transferFrom(account, self, amount)
    log Staked(user=account, amount=amount)


@internal
def _withdraw(account: address, amount: uint256):
    assert amount > 0  # dev: invalid amount to withdraw
    self._update_pool(account)
    self.balances[account] -= amount
    self.total_supply -= amount
    extcall staking_token.transfer(account, amount)
    log Withdrawn(user=account, amount=amount)


@internal
def _harvest(account: address):
    self._update_pool(account)
    earned: uint256 = self._earned(account)
    if earned > 0:
        self.rewards[account] = 0
        extcall rewards_token.transfer(account, earned)
        log RewardPaid(user=account, reward=earned)


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


@internal
@view
def earned(account: address) -> uint256:
    return self._earned(account)


@external
def deposit(amount: uint256):
    self._deposit(msg.sender, amount)


@external
def withdraw(amount: uint256):
    self._withdraw(msg.sender, amount)


@external
def harvest():
    self._harvest(msg.sender)


@external
def exit():
    amount: uint256 = self.balances[msg.sender]
    self._withdraw(msg.sender, amount)
    self._harvest(msg.sender)
