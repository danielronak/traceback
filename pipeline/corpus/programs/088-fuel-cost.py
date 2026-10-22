def trip_cost(miles, mpg, price):
    gallons = miles / mpg
    result = gallons * price
    return result


print(f"School run: {trip_cost(10, 40, 6.5):.2f}")
print(f"Seaside: {trip_cost(120, 45, 6.5):.2f}")
print(f"Gran's house: {trip_cost(60, 40, 6.8):.2f}")
