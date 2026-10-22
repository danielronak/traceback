+++
id = "variables-and-input"
title = "Remembering things: variables and input"
teaches = ["name-typo", "used-before-assignment", "name-undefined", "input-exhausted"]
+++

A **variable** is a name for a value, so your program can remember it. You
create one with `=`, which means "store this value under this name":

```python
name = "Ada"
print("Hello,", name)
```

`=` doesn't mean "equals" as in maths. It's an instruction: work out the
right-hand side, then store it under the name on the left. That's why this
works:

```python
score = 10
score = score + 5
print(score)
```

## Asking the user

`input()` shows a question, waits for the user to type an answer and press
Enter, and gives back what they typed. Store it in a variable to use it:

```python inputs=Sam
name = input("What's your name? ")
print("Nice to meet you,", name)
```

Variable names are lowercase words joined by underscores, such as
`first_name`. That's the Python style, called *snake_case*.

## Common mistakes

Python only knows names exactly as you wrote them. A typo is a brand-new name:

```python broken=name-typo
message = "Good morning"
print(mesage)
```

Python runs from top to bottom, so a variable must be created before it's used:

```python broken=used-before-assignment
print(score)
score = 10
```
