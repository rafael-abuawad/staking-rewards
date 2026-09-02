import boa
from src import StakingRewards

from tests.mocks import MockERC20
from tests.utils.constants import DEFAULT_REWARD_RATE, DURATION


def test_constructor_sets_immutables(
    staking_rewards, staking_token, rewards_token, reward_rate
):
    """Money Flow: none — constructor only stores immutables."""
    assert staking_rewards.staking_token() == staking_token.address
    assert staking_rewards.rewards_token() == rewards_token.address
    assert staking_rewards.reward_rate() == reward_rate


def test_constructor_sets_period_and_last_update(staking_rewards):
    """Money Flow: none — period_finish is deploy timestamp + DURATION."""
    last_update = staking_rewards.last_update_time()
    assert staking_rewards.period_finish() == last_update + DURATION
    assert last_update == boa.env.evm.patch.timestamp


def test_constructor_starts_with_empty_pool(staking_rewards):
    """Money Flow: none — no stake and no accumulator at deploy."""
    assert staking_rewards.totalSupply() == 0
    assert staking_rewards.reward_per_token() == 0
    assert staking_rewards.reward_per_token_stored() == 0


def test_constructor_reverts_when_tokens_are_the_same():
    token = MockERC20.deploy("Stake", "STK", 18)

    with boa.reverts(dev="staking and rewards tokens must differ"):
        StakingRewards.deploy(token.address, token.address, DEFAULT_REWARD_RATE)
