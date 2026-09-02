import boa

from tests.utils.accounting import expected_earned, expected_reward_per_token
from tests.utils.constants import DEFAULT_STAKE_AMOUNT, DURATION, PRECISION


def test_last_time_reward_applicable_is_timestamp_before_finish(staking_rewards):
    assert staking_rewards.last_time_reward_applicable() == boa.env.evm.patch.timestamp
    boa.env.time_travel(seconds=1_000)
    assert staking_rewards.last_time_reward_applicable() == boa.env.evm.patch.timestamp
    assert (
        staking_rewards.last_time_reward_applicable() < staking_rewards.period_finish()
    )


def test_last_time_reward_applicable_caps_at_period_finish(staking_rewards):
    period_finish = staking_rewards.period_finish()
    boa.env.time_travel(seconds=DURATION + 5_000)
    assert boa.env.evm.patch.timestamp > period_finish
    assert staking_rewards.last_time_reward_applicable() == period_finish


def test_reward_per_token_stays_zero_while_empty(staking_rewards):
    """Empty pool does not accrue the accumulator — later stakers are not paid idle time."""
    assert staking_rewards.totalSupply() == 0
    boa.env.time_travel(seconds=10_000)
    assert staking_rewards.reward_per_token() == 0
    assert staking_rewards.reward_per_token_stored() == 0


def test_earned_is_zero_immediately_after_deposit(staking_rewards, funded_staker):
    staking_rewards.deposit(DEFAULT_STAKE_AMOUNT, sender=funded_staker)
    assert staking_rewards.earned(funded_staker) == 0


def test_earned_grows_linearly_for_sole_staker(
    staking_rewards, funded_staker, reward_rate
):
    staking_rewards.deposit(DEFAULT_STAKE_AMOUNT, sender=funded_staker)
    elapsed = 250
    boa.env.time_travel(seconds=elapsed)

    expected = reward_rate * elapsed
    assert staking_rewards.earned(funded_staker) == expected
    assert (
        staking_rewards.reward_per_token()
        == expected * PRECISION // DEFAULT_STAKE_AMOUNT
    )


def test_late_staker_is_not_paid_for_time_before_deposit(
    staking_rewards, funded_staker, funded_second_staker, reward_rate
):
    """Late staker checkpoints reward_per_token_stored_paid so pre-deposit rewards are excluded."""
    staking_rewards.deposit(DEFAULT_STAKE_AMOUNT, sender=funded_staker)
    boa.env.time_travel(seconds=100)

    staking_rewards.deposit(DEFAULT_STAKE_AMOUNT, sender=funded_second_staker)
    assert staking_rewards.earned(funded_second_staker) == 0
    assert (
        staking_rewards.reward_per_token_stored_paid(funded_second_staker)
        == staking_rewards.reward_per_token_stored()
    )

    boa.env.time_travel(seconds=100)
    first_earned = staking_rewards.earned(funded_staker)
    second_earned = staking_rewards.earned(funded_second_staker)
    assert first_earned == reward_rate * 100 + reward_rate * 100 // 2
    assert second_earned == reward_rate * 100 // 2
    assert first_earned > second_earned


def test_empty_pool_gap_is_not_credited_to_next_staker(
    staking_rewards, funded_staker, reward_rate
):
    """Money Flow: rewards during totalSupply == 0 stay in the pool."""
    staking_rewards.deposit(DEFAULT_STAKE_AMOUNT, sender=funded_staker)
    boa.env.time_travel(seconds=10)
    staking_rewards.exit(sender=funded_staker)

    stranded_before_gap = staking_rewards.reward_per_token()
    boa.env.time_travel(seconds=1_000)
    assert staking_rewards.reward_per_token() == stranded_before_gap

    staking_rewards.deposit(DEFAULT_STAKE_AMOUNT, sender=funded_staker)
    boa.env.time_travel(seconds=10)
    assert staking_rewards.earned(funded_staker) == reward_rate * 10


def test_view_helpers_match_python_formula(staking_rewards, funded_staker, reward_rate):
    staking_rewards.deposit(DEFAULT_STAKE_AMOUNT, sender=funded_staker)
    last_update = staking_rewards.last_update_time()
    stored = staking_rewards.reward_per_token_stored()
    period_finish = staking_rewards.period_finish()
    boa.env.time_travel(seconds=77)

    rpt = expected_reward_per_token(
        stored,
        last_update,
        boa.env.evm.patch.timestamp,
        period_finish,
        reward_rate,
        DEFAULT_STAKE_AMOUNT,
    )
    earned = expected_earned(DEFAULT_STAKE_AMOUNT, rpt, stored, 0)
    assert staking_rewards.reward_per_token() == rpt
    assert staking_rewards.earned(funded_staker) == earned
