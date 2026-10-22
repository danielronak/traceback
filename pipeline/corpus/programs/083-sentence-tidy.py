sentence = "  python is fun and python is free  "
tidy = sentence.strip()
print(tidy.replace("python", "Python"))
print("Starts with python:", tidy.startswith("python"))
print("Count of is:", tidy.count("is"))
words = tidy.split()
words.reverse()
print(" ".join(words))
