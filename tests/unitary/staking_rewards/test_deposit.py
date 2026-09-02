import boa

from tests.utils import filter_logs, max_approve
from tests.utils.constants import DEFAULT_STAKE_AMOUNT


def test_deposit_increases_balance_and_total_supply(
    staking_rewards, staking_token, funded_staker
):
    """Money Flow: staking_token (staker) → pool."""
    amount = DEFAULT_STAKE_AMOUNT

    # ================= Capture initial state =================
    assert staking_rewards.balanceOf(funded_staker) == 0
    assert staking_rewards.totalSupply() == 0
    staker_before = staking_token.balanceOf(funded_staker)
    pool_before = staking_token.balanceOf(staking_rewards.address)

    # ================= Execute =================
    staking_rewards.deposit(amount, sender=funded_staker)

    # ================= Verify state and money flows =================
    assert staking_rewards.balanceOf(funded_staker) == amount
    assert staking_rewards.totalSupply() == amount
    assert staking_token.balanceOf(funded_staker) == staker_before - amount
    assert staking_token.balanceOf(staking_rewards.address) == pool_before + amount


def test_deposit_emits_staked(staking_rewards, funded_staker):
    amount = DEFAULT_STAKE_AMOUNT

    staking_rewards.deposit(amount, sender=funded_staker)

    logs = filter_logs(staking_rewards, "Staked")
    assert len(logs) == 1
    assert logs[0].user == funded_staker
    assert logs[0].amount == amount


def test_deposit_zero_reverts(staking_rewards, funded_staker):
    with boa.reverts(dev="invalid amount to deposit"):
        staking_rewards.deposit(0, sender=funded_staker)


def test_deposit_without_approval_reverts(staking_rewards, staking_token, staker):
    amount = DEFAULT_STAKE_AMOUNT
    staking_token.mint(staker, amount)

    with boa.reverts():
        staking_rewards.deposit(amount, sender=staker)


def test_deposit_insufficient_balance_reverts(staking_rewards, staking_token, staker):
    amount = DEFAULT_STAKE_AMOUNT
    staking_token.mint(staker, amount // 2)
    max_approve(staking_token, staking_rewards.address, staker)

    with boa.reverts():
        staking_rewards.deposit(amount, sender=staker)


def test_second_deposit_checkpoints_pending_rewards(staking_rewards, funded_staker):
    """Money Flow: staking_token (staker) → pool; rewards stay in pool."""
    first = DEFAULT_STAKE_AMOUNT // 2
    second = DEFAULT_STAKE_AMOUNT // 2
    elapsed = 100

    # ================= Setup =================
    staking_rewards.deposit(first, sender=funded_staker)
    boa.env.time_travel(seconds=elapsed)
    expected = staking_rewards.earned(funded_staker)
    assert expected > 0

    # ================= Execute =================
    staking_rewards.deposit(second, sender=funded_staker)

    # ================= Verify checkpoint =================
    assert staking_rewards.balanceOf(funded_staker) == first + second
    assert staking_rewards.totalSupply() == first + second
    assert staking_rewards.rewards(funded_staker) == expected
    assert (
        staking_rewards.reward_per_token_stored_paid(funded_staker)
        == staking_rewards.reward_per_token_stored()
    )
    assert staking_rewards.earned(funded_staker) == expected
