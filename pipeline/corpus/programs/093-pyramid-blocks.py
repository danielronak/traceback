# inputs: 4
rows = int(input("Rows: "))
level = 1
blocks = 0
while level <= rows:
    print("#" * level)
    blocks += level
    level += 1
print("Blocks used:", blocks)
