mName = ""
destination = ""
cMembers = float(1)
distance = float(1.1)
speed = float(1.1)
fuel = float(1.1)
realDistance = float(1.1)


def main():
    print("MISSION CONTROL!")
    print("_______________________________________")
    getinfo()
    print("Calculating mission...")
    print("")
    print("=======================================")
    types()
    print(f"MISSION: {mName.upper()}")
    print(f"Destination: {destination.capitalize()}")
    print(f"Crew: {cMembers} astronauts")
    print("")
    getRealDistance()
    print(f"Distance: {realDistance:,} km")
    print(f"Travel time: {calculateTravelTime()} days")
    print(f"Fuel Required: {float(fuelRequirement()):,} kg")
    print("")
    print("Estimated food required:")
    print("")
    print(f"{calculateFood()} kg")
    print("")
    print("MISSION SUMMARY")
    print("Each astronaut will travel approximately")
    print(f"{eachAstro():,} km")
    print("=======================================")

def types():
    global mName,destination,cMembers,distance,speed,fuel,realDistance
    cMembers = float(cMembers)
    distance = float(distance)
    speed = float(speed)
    fuel = float(fuel)
    realDistance = float(realDistance)
def getinfo():
    global mName,destination,cMembers,distance,speed,fuel
    mName = input("Mission Name: ")
    destination = input("Destination: ")
    cMembers = input("Crew Members: ")
    distance = input("Distance to destination (million km): ")
    speed = input("Average spacecraft speed (km/h): ")
    fuel = input("Fuel Consumption (kg/hour): ")
    
def getRealDistance():
    global realDistance
    realDistance = float(distance*1000000)
def calculateTravelTime():
    return float((realDistance/speed)/24)
def fuelRequirement():
    return (fuel*calculateTravelTime()*24)
def calculateFood():
    return cMembers * float(calculateTravelTime()) * 2
def eachAstro():
    return realDistance / cMembers



main()