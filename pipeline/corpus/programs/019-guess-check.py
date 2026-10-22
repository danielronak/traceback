# inputs: 3 | 7 | 5
secret = 5
guess = 0
tries = 0
while guess != secret:
    guess = int(input("Guess: "))
    tries += 1
    if guess < secret:
        print("Too low")
    elif guess > secret:
        print("Too high")
print("Got it in", tries, "tries")
