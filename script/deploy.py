from dataclasses import dataclass

from moccasin.boa_tools import VyperContract

from src import StakingRewards
from tests.mocks import MockERC20
from tests.utils.constants import DEFAULT_REWARD_RATE, DURATION


@dataclass
class StakingDeployment:
    staking_token: VyperContract
    rewards_token: VyperContract
    pool: VyperContract
    reward_rate: int


def deploy(reward_rate: int = DEFAULT_REWARD_RATE) -> StakingDeployment:
    staking_token: VyperContract = MockERC20.deploy("Stake", "STK", 18)
    rewards_token: VyperContract = MockERC20.deploy("Reward", "RWD", 18)
    pool: VyperContract = StakingRewards.deploy(
        staking_token.address, rewards_token.address, reward_rate
    )
    rewards_token.mint(pool.address, reward_rate * DURATION)
    return StakingDeployment(
        staking_token=staking_token,
        rewards_token=rewards_token,
        pool=pool,
        reward_rate=reward_rate,
    )


def moccasin_main() -> VyperContract:
    deployment = deploy()
    print("StakingRewards:", deployment.pool.address)
    print("staking_token:", deployment.staking_token.address)
    print("rewards_token:", deployment.rewards_token.address)
    print("reward_rate:", deployment.reward_rate)
    print("period_finish:", deployment.pool.period_finish())
    return deployment.pool
