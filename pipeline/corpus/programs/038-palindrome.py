def is_palindrome(word):
    cleaned = word.lower()
    return cleaned == cleaned[::-1]


for word in ["Racecar", "Python", "Level"]:
    print(word, is_palindrome(word))
