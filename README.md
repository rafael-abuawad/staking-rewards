# Staking Rewards

Unipool-style staking pool in Vyper 0.4.3. Users stake one ERC20 and earn another over 9 days (`DURATION = 777600`). Rewards use a lazy `reward_per_token_stored` index, settled on deposit, withdraw, and harvest.

Contract: [`src/StakingRewards.vy`](src/StakingRewards.vy). Writeup: [`articles/ARTICLE_2.md`](articles/ARTICLE_2.md) (original draft: [`articles/ARTICLE.md`](articles/ARTICLE.md)).

## Setup

Python 3.11+, [uv](https://docs.astral.sh/uv/), and [Moccasin](https://cyfrin.github.io/moccasin):

```bash
uv tool install moccasin
mox --version
```

## Commands

```bash
mox test
mox run deploy
```

`mox run deploy` runs [`script/deploy.py`](script/deploy.py) on local pyevm: two `MockERC20`s, `StakingRewards`, then mints `reward_rate * DURATION` of the rewards token to the pool. That is not a production deploy.

## Layout

- `src/StakingRewards.vy` — pool
- `tests/unitary/`, `tests/integration/`, `tests/fuzz/` — Titanoboa / Hypothesis
- `script/deploy.py` — local deploy helper
- `articles/` — writeups

## License

[GPL-3.0](LICENSE)
