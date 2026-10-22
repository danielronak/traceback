+++
id = "input"
title = "Asking the user"
+++
`input` shows a prompt, waits for the user to type something and press
Enter, and gives back what they typed:

```python input=Ada
name = input("What's your name? ")
print("Hello, " + name)
```

When you run this, type a name into the console below the editor. The `+`
joins two strings into one.

## `input` always gives back text

Whatever the user types, `input` gives back a string, even if they type
digits. The text `"12"` isn't the number `12`, and Python won't guess which
one you meant. To turn the text into a whole number, use `int`:

```python input=12
age = int(input("How old are you? "))
print(age + 1)
```

## A common mistake

Without `int`, the program tries to add the number `1` to a string, and
Python stops:

```python mistake=input-is-string input=12
age = input("How old are you? ")
print(age + 1)
```
