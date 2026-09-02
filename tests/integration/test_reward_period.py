import boa

from tests.utils.constants import DEFAULT_STAKE_AMOUNT, DURATION


def test_full_period_sole_staker_harvests_rate_times_duration(
    staking_rewards, rewards_token, funded_staker, reward_rate
):
    """Money Flow: entire reward budget → sole staker over DURATION."""
    staking_rewards.deposit(DEFAULT_STAKE_AMOUNT, sender=funded_staker)
    boa.env.time_travel(seconds=DURATION)

    earned = staking_rewards.earned(funded_staker)
    assert earned == reward_rate * DURATION

    staking_rewards.harvest(sender=funded_staker)
    assert rewards_token.balanceOf(funded_staker) == earned
    assert staking_rewards.earned(funded_staker) == 0


def test_no_further_accrual_after_period_finish(
    staking_rewards, funded_staker, reward_rate
):
    staking_rewards.deposit(DEFAULT_STAKE_AMOUNT, sender=funded_staker)
    boa.env.time_travel(seconds=DURATION)
    earned_at_finish = staking_rewards.earned(funded_staker)

    boa.env.time_travel(seconds=50_000)
    assert staking_rewards.earned(funded_staker) == earned_at_finish
    assert earned_at_finish == reward_rate * DURATION
    assert (
        staking_rewards.last_time_reward_applicable() == staking_rewards.period_finish()
    )


def test_sequence_crossing_period_finish(
    staking_rewards, staking_token, rewards_token, funded_staker, reward_rate
):
    """Money Flow: deposit, harvest mid-period, stay staked past finish, exit."""
    staking_rewards.deposit(DEFAULT_STAKE_AMOUNT, sender=funded_staker)
    boa.env.time_travel(seconds=DURATION // 2)

    mid = staking_rewards.earned(funded_staker)
    staking_rewards.harvest(sender=funded_staker)
    assert rewards_token.balanceOf(funded_staker) == mid

    boa.env.time_travel(seconds=DURATION)
    remaining = staking_rewards.earned(funded_staker)
    assert remaining == reward_rate * (DURATION - DURATION // 2)

    staking_rewards.exit(sender=funded_staker)
    assert staking_rewards.totalSupply() == 0
    assert staking_token.balanceOf(funded_staker) == DEFAULT_STAKE_AMOUNT
    assert rewards_token.balanceOf(funded_staker) == reward_rate * DURATION


def test_idle_gap_reduces_distributed_rewards(
    staking_rewards, rewards_token, funded_staker, reward_rate
):
    """Rewards during totalSupply == 0 stay in the pool instead of going to later stakers."""
    staking_rewards.deposit(DEFAULT_STAKE_AMOUNT, sender=funded_staker)
    boa.env.time_travel(seconds=100)
    staking_rewards.exit(sender=funded_staker)
    paid_first = rewards_token.balanceOf(funded_staker)
    assert paid_first == reward_rate * 100

    boa.env.time_travel(seconds=1_000)

    staking_rewards.deposit(DEFAULT_STAKE_AMOUNT, sender=funded_staker)
    boa.env.time_travel(seconds=100)
    staking_rewards.harvest(sender=funded_staker)

    total_paid = rewards_token.balanceOf(funded_staker)
    assert total_paid == reward_rate * 200
    leftover = rewards_token.balanceOf(staking_rewards.address)
    assert leftover == reward_rate * DURATION - total_paid
    assert leftover >= reward_rate * 1_000
