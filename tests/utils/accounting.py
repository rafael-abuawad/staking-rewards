from tests.utils.constants import PRECISION


def expected_reward_per_token(
    stored: int,
    last_update: int,
    now: int,
    period_finish: int,
    rate: int,
    total_supply: int,
) -> int:
    if total_supply == 0:
        return stored
    applicable = min(now, period_finish)
    return stored + (applicable - last_update) * rate * PRECISION // total_supply


def expected_earned(
    balance: int, reward_per_token: int, paid: int, stored_rewards: int
) -> int:
    return balance * (reward_per_token - paid) // PRECISION + stored_rewards
