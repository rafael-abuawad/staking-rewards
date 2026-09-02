import boa
from src import StakingRewards

from tests.mocks import MockERC20
from tests.utils import filter_logs
from tests.utils.constants import DEFAULT_REWARD_RATE, DEFAULT_STAKE_AMOUNT, DURATION


def test_harvest_pays_earned_and_zeros_rewards(
    staking_rewards, rewards_token, funded_staker
):
    """Money Flow: rewards_token (pool) → staker."""
    staking_rewards.deposit(DEFAULT_STAKE_AMOUNT, sender=funded_staker)
    boa.env.time_travel(seconds=100)
    earned = staking_rewards.earned(funded_staker)
    assert earned > 0

    # ================= Capture initial state =================
    staker_before = rewards_token.balanceOf(funded_staker)
    pool_before = rewards_token.balanceOf(staking_rewards.address)

    # ================= Execute =================
    staking_rewards.harvest(sender=funded_staker)

    # ================= Verify money flows =================
    assert staking_rewards.rewards(funded_staker) == 0
    assert staking_rewards.earned(funded_staker) == 0
    assert rewards_token.balanceOf(funded_staker) == staker_before + earned
    assert rewards_token.balanceOf(staking_rewards.address) == pool_before - earned


def test_harvest_emits_reward_paid(staking_rewards, funded_staker):
    staking_rewards.deposit(DEFAULT_STAKE_AMOUNT, sender=funded_staker)
    boa.env.time_travel(seconds=100)
    earned = staking_rewards.earned(funded_staker)

    staking_rewards.harvest(sender=funded_staker)

    logs = filter_logs(staking_rewards, "RewardPaid")
    assert len(logs) == 1
    assert logs[0].user == funded_staker
    assert logs[0].reward == earned


def test_harvest_zero_earned_is_noop(staking_rewards, rewards_token, funded_staker):
    """Money Flow: none — harvest with zero earned does not transfer or emit."""
    staking_rewards.deposit(DEFAULT_STAKE_AMOUNT, sender=funded_staker)
    staker_before = rewards_token.balanceOf(funded_staker)

    staking_rewards.harvest(sender=funded_staker)

    logs = filter_logs(staking_rewards, "RewardPaid")
    assert logs == []
    assert rewards_token.balanceOf(funded_staker) == staker_before
    assert staking_rewards.earned(funded_staker) == 0


def test_harvest_after_period_finish_pays_accrued(
    staking_rewards, rewards_token, funded_staker
):
    """Money Flow: rewards_token (pool) → staker for time up to period_finish."""
    staking_rewards.deposit(DEFAULT_STAKE_AMOUNT, sender=funded_staker)
    boa.env.time_travel(seconds=DURATION + 1_000)
    earned = staking_rewards.earned(funded_staker)
    assert earned == DEFAULT_REWARD_RATE * DURATION

    staking_rewards.harvest(sender=funded_staker)

    assert rewards_token.balanceOf(funded_staker) == earned
    assert staking_rewards.earned(funded_staker) == 0


def test_harvest_reverts_when_pool_has_no_rewards_tokens(funded_staker):
    staking_token = MockERC20.deploy("Stake", "STK", 18)
    rewards_token = MockERC20.deploy("Reward", "RWD", 18)
    pool = StakingRewards.deploy(
        staking_token.address, rewards_token.address, DEFAULT_REWARD_RATE
    )
    staking_token.mint(funded_staker, DEFAULT_STAKE_AMOUNT)
    staking_token.approve(pool.address, DEFAULT_STAKE_AMOUNT, sender=funded_staker)

    pool.deposit(DEFAULT_STAKE_AMOUNT, sender=funded_staker)
    boa.env.time_travel(seconds=10)

    with boa.reverts():
        pool.harvest(sender=funded_staker)
