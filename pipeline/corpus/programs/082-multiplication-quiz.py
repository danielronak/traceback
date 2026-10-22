# inputs: 12 | 20 | 31
questions = [3, 4, 5]
score = 0
for i in range(3):
    answer = int(input(f"What is {questions[i]} x 4? "))
    if answer == questions[i] * 4:
        score += 1
        print("Correct")
    else:
        print("Not quite, it is", questions[i] * 4)
print(f"Score: {score}/3")
