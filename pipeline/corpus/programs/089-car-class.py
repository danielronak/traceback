class Car:
    def __init__(self, make, fuel):
        self.make = make
        self.fuel = fuel

    def drive(self, miles):
        used = miles // 10
        self.fuel -= used
        return self.fuel


car = Car("Mini", 40)
print("Fuel left:", car.drive(50))
print("Fuel left:", car.drive(120))
print(f"The {car.make} has {car.fuel} litres")
