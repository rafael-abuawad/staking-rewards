import boa

from tests.utils import filter_logs
from tests.utils.constants import DEFAULT_STAKE_AMOUNT, DURATION


def test_exit_withdraws_and_harvests(
    staking_rewards, staking_token, rewards_token, funded_staker
):
    """Money Flow: staking_token and rewards_token (pool) → staker."""
    staking_rewards.deposit(DEFAULT_STAKE_AMOUNT, sender=funded_staker)
    boa.env.time_travel(seconds=100)
    earned = staking_rewards.earned(funded_staker)
    assert earned > 0

    # ================= Capture initial state =================
    staker_stake_before = staking_token.balanceOf(funded_staker)
    staker_rewards_before = rewards_token.balanceOf(funded_staker)

    # ================= Execute =================
    staking_rewards.exit(sender=funded_staker)

    # ================= Verify money flows =================
    assert staking_rewards.balanceOf(funded_staker) == 0
    assert staking_rewards.totalSupply() == 0
    assert (
        staking_token.balanceOf(funded_staker)
        == staker_stake_before + DEFAULT_STAKE_AMOUNT
    )
    assert rewards_token.balanceOf(funded_staker) == staker_rewards_before + earned
    assert staking_rewards.earned(funded_staker) == 0


def test_exit_emits_withdrawn_and_reward_paid(staking_rewards, funded_staker):
    staking_rewards.deposit(DEFAULT_STAKE_AMOUNT, sender=funded_staker)
    boa.env.time_travel(seconds=100)
    earned = staking_rewards.earned(funded_staker)

    staking_rewards.exit(sender=funded_staker)

    withdrawn = filter_logs(staking_rewards, "Withdrawn")
    paid = filter_logs(staking_rewards, "RewardPaid")
    assert len(withdrawn) == 1
    assert withdrawn[0].user == funded_staker
    assert withdrawn[0].amount == DEFAULT_STAKE_AMOUNT
    assert len(paid) == 1
    assert paid[0].user == funded_staker
    assert paid[0].reward == earned


def test_exit_with_zero_balance_reverts(staking_rewards, staker):
    with boa.reverts(dev="invalid amount to withdraw"):
        staking_rewards.exit(sender=staker)


def test_exit_after_period_finish(
    staking_rewards, staking_token, rewards_token, funded_staker
):
    staking_rewards.deposit(DEFAULT_STAKE_AMOUNT, sender=funded_staker)
    boa.env.time_travel(seconds=DURATION + 1)
    earned = staking_rewards.earned(funded_staker)

    staking_rewards.exit(sender=funded_staker)

    assert staking_token.balanceOf(funded_staker) == DEFAULT_STAKE_AMOUNT
    assert rewards_token.balanceOf(funded_staker) == earned
    assert staking_rewards.totalSupply() == 0
