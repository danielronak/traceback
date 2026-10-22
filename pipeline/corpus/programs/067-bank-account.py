class Account:
    def __init__(self, owner, balance):
        self.owner = owner
        self.balance = balance

    def deposit(self, amount):
        self.balance += amount

    def withdraw(self, amount):
        if amount > self.balance:
            print("Not enough money")
        else:
            self.balance -= amount


account = Account("Ada", 50)
account.deposit(25)
account.withdraw(100)
account.withdraw(30)
print(f"{account.owner} has {account.balance}")
