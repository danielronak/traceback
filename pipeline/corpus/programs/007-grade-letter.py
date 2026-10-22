def letter(score):
    if score >= 90:
        return "A"
    elif score >= 80:
        return "B"
    elif score >= 70:
        return "C"
    return "F"


for score in [95, 82, 71, 40]:
    print(score, letter(score))
