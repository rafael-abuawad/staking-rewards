# pragma version ==0.4.3
# pragma nonreentrancy off

from ethereum.ercs import IERC20
implements: IERC20


event Transfer:
    sender: indexed(address)
    receiver: indexed(address)
    amount: uint256


event Approval:
    owner: indexed(address)
    spender: indexed(address)
    amount: uint256


name: public(String[32])
symbol: public(String[8])
decimals: public(uint8)
totalSupply: public(uint256)
balanceOf: public(HashMap[address, uint256])
allowance: public(HashMap[address, HashMap[address, uint256]])


@deploy
def __init__(name_: String[32], symbol_: String[8], decimals_: uint8):
    self.name = name_
    self.symbol = symbol_
    self.decimals = decimals_


@external
def mint(to: address, amount: uint256):
    self.totalSupply += amount
    self.balanceOf[to] += amount
    log Transfer(sender=empty(address), receiver=to, amount=amount)


@external
def approve(spender: address, amount: uint256) -> bool:
    self.allowance[msg.sender][spender] = amount
    log Approval(owner=msg.sender, spender=spender, amount=amount)
    return True


@external
def transfer(receiver: address, amount: uint256) -> bool:
    self.balanceOf[msg.sender] -= amount
    self.balanceOf[receiver] += amount
    log Transfer(sender=msg.sender, receiver=receiver, amount=amount)
    return True


@external
def transferFrom(owner: address, receiver: address, amount: uint256) -> bool:
    allowance: uint256 = self.allowance[owner][msg.sender]
    if allowance != max_value(uint256):
        self.allowance[owner][msg.sender] = allowance - amount
    self.balanceOf[owner] -= amount
    self.balanceOf[receiver] += amount
    log Transfer(sender=owner, receiver=receiver, amount=amount)
    return True
