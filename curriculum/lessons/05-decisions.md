+++
id = "decisions"
title = "Making decisions with if"
teaches = ["missing-colon", "indent-expected", "assign-in-condition", "compare-bool", "unexpected-indent", "unindent-mismatch"]
+++

`if` lets a program choose what to do. Python checks the **condition**, and runs
the indented lines underneath only when it's true. `else` covers every other
case:

```python
temperature = 25
if temperature > 20:
    print("It's warm")
else:
    print("It's cool")
```

Two things make this work: the **colon** at the end of the `if` and `else`
lines, and the **indentation** (4 spaces) of the lines that belong to them.

To check several cases in turn, use `elif` ("else if"). Python stops at the
first condition that's true:

```python
score = 75
if score >= 90:
    print("A")
elif score >= 70:
    print("B or C")
else:
    print("Keep practising")
```

Conditions compare values: `==` (equal), `!=` (not equal), `<`, `>`, `<=` and
`>=`. The remainder operator `%` is handy too: `n % 2` is 0 when `n` is even.

```python
print(7 % 2)
print(8 % 2)
```

## Common mistakes

Forgetting the colon:

```python broken=missing-colon
age = 20
if age >= 18
    print("adult")
```

Using `=` (store) when you mean `==` (compare):

```python broken=assign-in-condition
answer = "yes"
if answer = "yes":
    print("Great!")
```

Forgetting to indent the lines inside the `if`:

```python broken=indent-expected
if True:
print("inside")
```
