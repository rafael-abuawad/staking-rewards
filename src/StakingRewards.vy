# pragma version ==0.4.3
# pragma nonreentrancy off

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
