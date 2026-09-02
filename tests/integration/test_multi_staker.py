import boa

from tests.utils import max_approve
from tests.utils.constants import DEFAULT_STAKE_AMOUNT


def test_equal_stakes_earn_equal_rewards(
    staking_rewards, funded_staker, funded_second_staker, reward_rate
):
    """Money Flow: rewards accrue equally to two equal stakes."""
    staking_rewards.deposit(DEFAULT_STAKE_AMOUNT, sender=funded_staker)
    staking_rewards.deposit(DEFAULT_STAKE_AMOUNT, sender=funded_second_staker)

    boa.env.time_travel(seconds=200)

    first = staking_rewards.earned(funded_staker)
    second = staking_rewards.earned(funded_second_staker)
    assert first == second
    assert first == reward_rate * 200 // 2


def test_one_to_three_split_is_proportional(
    staking_rewards, staking_token, funded_staker, second_staker, reward_rate
):
    """Money Flow: 1:3 stake split earns 1:3 of the interval rewards."""
    small = DEFAULT_STAKE_AMOUNT
    large = DEFAULT_STAKE_AMOUNT * 3
    staking_token.mint(second_staker, large)
    max_approve(staking_token, staking_rewards.address, second_staker)

    staking_rewards.deposit(small, sender=funded_staker)
    staking_rewards.deposit(large, sender=second_staker)
    boa.env.time_travel(seconds=400)

    first = staking_rewards.earned(funded_staker)
    second = staking_rewards.earned(second_staker)
    assert first == reward_rate * 400 // 4
    assert second == reward_rate * 400 * 3 // 4
    assert second == first * 3


def test_earlier_staker_earns_more_than_late_joiner(
    staking_rewards, funded_staker, funded_second_staker, reward_rate
):
    """Money Flow: first staker takes the solo interval plus half of the overlap."""
    staking_rewards.deposit(DEFAULT_STAKE_AMOUNT, sender=funded_staker)
    boa.env.time_travel(seconds=100)

    staking_rewards.deposit(DEFAULT_STAKE_AMOUNT, sender=funded_second_staker)
    boa.env.time_travel(seconds=100)

    first = staking_rewards.earned(funded_staker)
    second = staking_rewards.earned(funded_second_staker)
    assert first == reward_rate * 100 + reward_rate * 100 // 2
    assert second == reward_rate * 100 // 2
    assert first > second


def test_deposit_partial_withdraw_harvest_redeposit(
    staking_rewards, staking_token, rewards_token, funded_staker, reward_rate
):
    """Money Flow: stake in, partial stake out, rewards out, stake in again."""
    staking_rewards.deposit(DEFAULT_STAKE_AMOUNT, sender=funded_staker)
    boa.env.time_travel(seconds=40)

    half = DEFAULT_STAKE_AMOUNT // 2
    staking_rewards.withdraw(half, sender=funded_staker)
    pending_after_withdraw = staking_rewards.earned(funded_staker)
    assert pending_after_withdraw == reward_rate * 40

    staking_rewards.harvest(sender=funded_staker)
    assert rewards_token.balanceOf(funded_staker) == pending_after_withdraw
    assert staking_rewards.earned(funded_staker) == 0

    staking_rewards.deposit(half, sender=funded_staker)
    boa.env.time_travel(seconds=20)
    assert staking_rewards.balanceOf(funded_staker) == DEFAULT_STAKE_AMOUNT
    assert staking_rewards.earned(funded_staker) == reward_rate * 20
    assert staking_token.balanceOf(staking_rewards.address) == DEFAULT_STAKE_AMOUNT
