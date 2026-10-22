# inputs: Paris | 4 | blue
answers = {"capital": "paris", "sum": "4", "sky": "blue"}
score = 0
reply = input("Capital of France? ")
if reply.strip().lower() == answers["capital"]:
    score += 1
reply = input("What is 2 + 2? ")
if reply.strip() == answers["sum"]:
    score += 1
reply = input("Colour of the sky? ")
if reply.strip().lower() == answers["sky"]:
    score += 1
print("Score:", score)
print(f"You got {score} out of 3")
