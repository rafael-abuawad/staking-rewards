import boa

from tests.utils import filter_logs
from tests.utils.constants import DEFAULT_STAKE_AMOUNT


def _deposit(staking_rewards, funded_staker, amount=DEFAULT_STAKE_AMOUNT):
    staking_rewards.deposit(amount, sender=funded_staker)
    return amount


def test_withdraw_decreases_balance_and_returns_tokens(
    staking_rewards, staking_token, funded_staker, rewards_token
):
    """Money Flow: staking_token (pool) → staker; rewards stay in pool."""
    amount = _deposit(staking_rewards, funded_staker)

    # ================= Capture initial state =================
    staker_stake_before = staking_token.balanceOf(funded_staker)
    pool_stake_before = staking_token.balanceOf(staking_rewards.address)
    staker_rewards_before = rewards_token.balanceOf(funded_staker)

    # ================= Execute =================
    staking_rewards.withdraw(amount, sender=funded_staker)

    # ================= Verify state and money flows =================
    assert staking_rewards.balanceOf(funded_staker) == 0
    assert staking_rewards.totalSupply() == 0
    assert staking_token.balanceOf(funded_staker) == staker_stake_before + amount
    assert (
        staking_token.balanceOf(staking_rewards.address) == pool_stake_before - amount
    )
    assert rewards_token.balanceOf(funded_staker) == staker_rewards_before


def test_withdraw_emits_withdrawn(staking_rewards, funded_staker):
    amount = _deposit(staking_rewards, funded_staker)

    staking_rewards.withdraw(amount, sender=funded_staker)

    logs = filter_logs(staking_rewards, "Withdrawn")
    assert len(logs) == 1
    assert logs[0].user == funded_staker
    assert logs[0].amount == amount


def test_withdraw_zero_reverts(staking_rewards, funded_staker):
    _deposit(staking_rewards, funded_staker)

    with boa.reverts(dev="invalid amount to withdraw"):
        staking_rewards.withdraw(0, sender=funded_staker)


def test_withdraw_more_than_balance_reverts(staking_rewards, funded_staker):
    amount = _deposit(staking_rewards, funded_staker)

    with boa.reverts():
        staking_rewards.withdraw(amount + 1, sender=funded_staker)


def test_partial_withdraw_leaves_remainder_and_checkpoints(
    staking_rewards, funded_staker
):
    """Money Flow: staking_token (pool) → staker for the withdrawn slice."""
    amount = _deposit(staking_rewards, funded_staker)
    withdraw_amount = amount // 4
    elapsed = 50

    # ================= Setup =================
    boa.env.time_travel(seconds=elapsed)
    expected = staking_rewards.earned(funded_staker)
    assert expected > 0

    # ================= Execute =================
    staking_rewards.withdraw(withdraw_amount, sender=funded_staker)

    # ================= Verify =================
    assert staking_rewards.balanceOf(funded_staker) == amount - withdraw_amount
    assert staking_rewards.totalSupply() == amount - withdraw_amount
    assert staking_rewards.rewards(funded_staker) == expected
    assert (
        staking_rewards.reward_per_token_stored_paid(funded_staker)
        == staking_rewards.reward_per_token_stored()
    )
    assert staking_rewards.earned(funded_staker) == expected
