ages = {"Ada": 36, "Sam": 12, "Bo": 17}
print("Ada is", ages["Ada"])
ages["Sam"] += 1
print("Sam is now", ages["Sam"])
adults = 0
for person in ages:
    if ages[person] >= 18:
        adults += 1
print(f"Adults: {adults}")
print(f"Total age: {ages['Ada'] + ages['Sam'] + ages['Bo']}")
