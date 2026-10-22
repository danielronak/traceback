+++
id = "if-else"
title = "Making decisions with if"
+++
`if` runs some lines only when a condition is true:

```python input=15
temperature = int(input("Temperature: "))
if temperature > 25:
    print("It's hot!")
else:
    print("It's not too hot.")
```

The condition `temperature > 25` is either `True` or `False`. If it's
`True`, Python runs the indented lines under `if`. Otherwise, it runs the
lines under `else`. The `else` part is optional.

## Comparing values

| Write | Means |
| --- | --- |
| `a == b` | `a` is equal to `b` |
| `a != b` | `a` is not equal to `b` |
| `a < b`, `a > b` | less than, greater than |
| `a <= b`, `a >= b` | less than or equal to, greater than or equal to |

## More than two choices

`elif` (short for "else if") checks another condition when the ones before it
were false. Python checks from the top and runs only the first block whose
condition is true:

```python
def describe(n):
    if n > 0:
        return "positive"
    elif n < 0:
        return "negative"
    else:
        return "zero"


print(describe(5))
print(describe(0))
```

## A common mistake

One `=` stores a value; two `==` compare values. A condition needs `==`:

```python mistake=assign-in-condition
answer = 42
if answer = 42:
    print("Correct!")
```
