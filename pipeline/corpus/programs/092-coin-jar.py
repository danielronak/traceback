coins = {"1p": 1, "2p": 2, "10p": 10, "50p": 50}
jar = ["10p", "2p", "50p", "10p", "1p"]
total = 0
for coin in jar:
    total += coins[coin]
print("Coins:", len(jar))
print(f"Total pence: {total}")
print("Ten pence coins:", jar.count("10p"))
print(f"In pounds: {total / 100:.2f}")
