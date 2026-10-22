+++
id = "functions"
title = "Functions: naming a set of steps"
teaches = ["missing-argument", "printed-not-returned", "missing-return", "function-never-called", "indent-expected", "naming-function"]
+++

A **function** is a set of steps with a name, so you can use them again and
again. You create one with `def`, give it a name and its **parameters** (the
values it needs), and indent the steps underneath:

```python
def greet(name):
    print("Hello,", name)


greet("Ada")
greet("Sam")
```

`def` only creates the function. Nothing happens until you **call** it, by
writing its name with round brackets.

## Giving back an answer

Many functions work something out and hand it back with `return`. The code
that called the function can then store or use the answer:

```python
def double(n):
    return n * 2


answer = double(21)
print(answer)
```

`print()` and `return` are easy to mix up. `print()` only shows a value on the
screen. `return` hands it back to the code that called the function. A
function without `return` gives back `None`, Python's "nothing" value:

```python
def shout(word):
    print(word.upper())


result = shout("hi")
print(result)
```

Exercises check what your function *returns*, so use `return` for the answer.

## Common mistakes

Calling a function without the values it needs:

```python broken=missing-argument
def greet(name):
    print("Hello,", name)


greet()
```
