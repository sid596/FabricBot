from ai import understand
from search import search_fabric

message = input("You: ")

result = understand(message)
if result["intent"] == "price_lookup":
    matches = search_fabric(result["fabric"])

    if matches: 
        print(matches)
        for fabric in matches:
            print(f"Album : {fabric['album']}")
            print(f"Quality : {fabric['quality']}")
            print(f"Price  : ₹{fabric['price']}/m")
            print(f"Width  : {fabric['width']} inches")
            print(f"Category  : {fabric['category']} inches")

    else:
        print("Fabric not found.")
else: 
    print("Didn't quite understand what you are asking")
