class Pet:
    def __init__(self, name, food):
        self.name = name
        self.food = food
        self.meals = 0

    def feed(self):
        self.meals += 1
        return self.name + " eats " + self.food


rex = Pet("Rex", "biscuits")
print(rex.feed())
print(rex.feed())
print("Meals so far:", rex.meals)
