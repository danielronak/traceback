def average(first, second, third):
    result = (first + second + third) / 3
    return result


def letter(score):
    if score >= 70:
        return "A"
    elif score >= 50:
        return "B"
    else:
        return "C"


ada = average(80, 75, 90)
sam = average(55, 40, 62)
bo = average(30, 45, 50)
print(f"Ada: {ada:.1f} {letter(ada)}")
print(f"Sam: {sam:.1f} {letter(sam)}")
print(f"Bo: {bo:.1f} {letter(bo)}")
