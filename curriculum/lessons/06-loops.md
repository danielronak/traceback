+++
id = "loops"
title = "Repeating things with loops"
teaches = ["int-not-iterable", "loop-condition-unchanged", "infinite-loop", "off-by-one"]
+++

A `for` loop repeats its indented lines once for each item in a sequence. To
repeat something a number of times, loop over `range()`:

```python
for n in range(5):
    print(n)
```

`range(5)` counts 0, 1, 2, 3, 4: it starts at 0 and stops just *before* 5. You
can choose the start, and a step too:

```python
for n in range(1, 4):
    print(n, "squared is", n * n)

for n in range(10, 0, -3):
    print(n)
```

A loop can build up an answer. Start a variable before the loop, and update it
inside:

```python
total = 0
for n in [4, 8, 15]:
    total += n
print(total)
```

`total += n` is short for `total = total + n`.

## while loops

A `while` loop repeats as long as its condition is true. Something inside it
must change, or it never stops:

```python
count = 3
while count > 0:
    print(count)
    count -= 1
print("Lift off!")
```

## Common mistakes

Looping over a number instead of a `range`:

```python broken=int-not-iterable
for i in 3:
    print(i)
```

A `while` loop whose condition never changes runs forever. PyMentor stops it
after a few seconds and explains:

```python broken=loop-condition-unchanged
count = 0
while count < 3:
    print(count)
```
