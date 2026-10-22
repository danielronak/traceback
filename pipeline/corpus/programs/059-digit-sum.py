# inputs: 4096
number = input("A number: ")
total = 0
for digit in number:
    total += int(digit)
print("The digits add up to", total)
