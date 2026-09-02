from datetime import timedelta

import boa
import pytest
from hypothesis import Phase, settings

from script.deploy import deploy
from tests.utils import max_approve
from tests.utils.constants import DEFAULT_STAKE_AMOUNT

boa.env.enable_fast_mode()

no_shrink = settings.register_profile(
    "no-shrink",
    phases=list(Phase)[:4],
    deadline=timedelta(seconds=1000),
)
settings.load_profile("no-shrink")


@pytest.fixture
def staker():
    return boa.env.generate_address("staker")


@pytest.fixture
def second_staker():
    return boa.env.generate_address("second_staker")


@pytest.fixture
def deployment():
    return deploy()


@pytest.fixture
def staking_token(deployment):
    return deployment.staking_token


@pytest.fixture
def rewards_token(deployment):
    return deployment.rewards_token


@pytest.fixture
def staking_rewards(deployment):
    return deployment.pool


@pytest.fixture
def reward_rate(deployment):
    return deployment.reward_rate


@pytest.fixture
def funded_staker(staking_token, staking_rewards, staker):
    staking_token.mint(staker, DEFAULT_STAKE_AMOUNT)
    max_approve(staking_token, staking_rewards.address, staker)
    return staker


@pytest.fixture
def funded_second_staker(staking_token, staking_rewards, second_staker):
    staking_token.mint(second_staker, DEFAULT_STAKE_AMOUNT)
    max_approve(staking_token, staking_rewards.address, second_staker)
    return second_staker
