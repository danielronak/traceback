+++
id = "functions"
title = "Writing your own functions"
+++
A **function** is a named set of instructions that you can use again and
again. You have already used functions that come with Python, such as `print`
and `input`. You can also write your own with `def`:

```python
def triple(n):
    return n * 3


print(triple(4))
print(triple(10))
```

Here is what each part means:

- `def triple(n):` starts the function. `triple` is its name, and `n` is a
  **parameter**: a name for the value the function is given.
- The lines indented underneath are the function's **body**. They run only
  when the function is called.
- `return` hands a value back to whoever called the function.
- `triple(4)` **calls** the function, with `n` set to `4`, and the call is
  replaced by whatever it returns: `12`.

## More than one parameter

Separate the parameters with commas, and give the values in the same order
when you call the function:

```python
def add(a, b):
    return a + b


print(add(2, 3))
```

## `return` is not `print`

`print` shows a value on the screen, but the program can't use it after
that. `return` hands the value back, so the program can store it, use it in a
sum or print it. Exercises check what your functions *return*, so use
`return` when a task says "returns".

## A common mistake

The `def` line must end with a colon `:`. The colon tells Python an indented
block comes next:

```python mistake=missing-colon
def triple(n)
    return n * 3
```
