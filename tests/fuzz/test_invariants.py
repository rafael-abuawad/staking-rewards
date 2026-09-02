import boa
from hypothesis import settings
from hypothesis import strategies as st
from hypothesis.stateful import (
    RuleBasedStateMachine,
    invariant,
    rule,
)

from script.deploy import deploy
from tests.utils import max_approve
from tests.utils.constants import DURATION

STAKE_CEILING = 10**24
WALLET_BUDGET = 10**32


class StakingRewardsMachine(RuleBasedStateMachine):
    def __init__(self):
        super().__init__()
        self._anchor = boa.env.anchor()
        self._anchor.__enter__()

        deployment = deploy()
        self.staking_token = deployment.staking_token
        self.rewards_token = deployment.rewards_token
        self.pool = deployment.pool
        self.period_finish = self.pool.period_finish()
        self.stakers = [
            boa.env.generate_address("fuzz_staker_0"),
            boa.env.generate_address("fuzz_staker_1"),
        ]
        self.balances = {staker: 0 for staker in self.stakers}
        self.last_rpt = 0
        self.capped_earned = {}

        for staker in self.stakers:
            self.staking_token.mint(staker, WALLET_BUDGET)
            max_approve(self.staking_token, self.pool.address, staker)

    def teardown(self):
        self._anchor.__exit__(None, None, None)

    @rule(
        staker_idx=st.integers(min_value=0, max_value=1),
        amount=st.integers(min_value=1, max_value=STAKE_CEILING),
    )
    def deposit(self, staker_idx, amount):
        staker = self.stakers[staker_idx]
        if amount > self.staking_token.balanceOf(staker):
            return
        self.pool.deposit(amount, sender=staker)
        self.balances[staker] += amount

    @rule(
        staker_idx=st.integers(min_value=0, max_value=1),
        amount=st.integers(min_value=1, max_value=STAKE_CEILING),
    )
    def withdraw(self, staker_idx, amount):
        staker = self.stakers[staker_idx]
        staked = self.balances[staker]
        if staked == 0:
            return
        amount = min(amount, staked)
        self.pool.withdraw(amount, sender=staker)
        self.balances[staker] -= amount

    @rule(staker_idx=st.integers(min_value=0, max_value=1))
    def harvest(self, staker_idx):
        staker = self.stakers[staker_idx]
        earned_before = self.pool.earned(staker)
        rewards_before = self.rewards_token.balanceOf(staker)

        self.pool.harvest(sender=staker)

        received = self.rewards_token.balanceOf(staker) - rewards_before
        assert received <= earned_before
        if earned_before > 0:
            assert received == earned_before

    @rule(seconds=st.integers(min_value=1, max_value=DURATION))
    def advance_time(self, seconds):
        boa.env.time_travel(seconds=seconds)

    @rule(staker_idx=st.integers(min_value=0, max_value=1))
    def withdraw_more_than_balance_reverts(self, staker_idx):
        staker = self.stakers[staker_idx]
        staked = self.pool.balanceOf(staker)
        with boa.reverts():
            self.pool.withdraw(staked + 1, sender=staker)

    @invariant()
    def supply_matches_stakes_and_token_balance(self):
        tracked = sum(self.balances.values())
        assert tracked == self.pool.totalSupply()
        assert tracked == self.staking_token.balanceOf(self.pool.address)
        for staker in self.stakers:
            assert self.pool.balanceOf(staker) == self.balances[staker]

    @invariant()
    def reward_per_token_is_non_decreasing(self):
        rpt = self.pool.reward_per_token()
        assert rpt >= self.last_rpt
        self.last_rpt = rpt

    @invariant()
    def earned_does_not_increase_after_period_finish(self):
        if boa.env.evm.patch.timestamp < self.period_finish:
            return
        for staker in self.stakers:
            current = self.pool.earned(staker)
            if staker in self.capped_earned:
                assert current <= self.capped_earned[staker]
            self.capped_earned[staker] = current


StakingRewardsMachine.TestCase.settings = settings(
    max_examples=40,
    stateful_step_count=25,
    deadline=None,
)
TestStakingRewardsInvariants = StakingRewardsMachine.TestCase
