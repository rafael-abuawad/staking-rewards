from tests.utils.constants import MAX_UINT256


def max_approve(token, spender, sender):
    token.approve(spender, MAX_UINT256, sender=sender)


def filter_logs(contract, event_name: str):
    return [log for log in contract.get_logs() if type(log).__name__ == event_name]
