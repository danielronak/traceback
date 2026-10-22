class Counter:
    def __init__(self):
        self.count = 0

    def add(self, amount):
        self.count += amount


clicks = Counter()
for _ in range(3):
    clicks.add(2)
print("Clicks:", clicks.count)
