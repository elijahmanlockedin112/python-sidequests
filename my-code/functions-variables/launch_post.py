# SIDEQUEST: Launch Post  (Week 0 · Functions, Variables)
#
# Ask for three things, in this order:
#   1. the product name
#   2. a one-line tagline (no period at the end)
#   3. the monthly price, as a number like 9 or 4.5
#
# Then print exactly two lines:
#   Introducing <PRODUCT NAME IN ALL CAPS>
#   <Tagline with only its first letter capitalized>. $<price, 2 decimals>/month
#
# Spaces typed around any answer should disappear.
#
# Example:
# $ python launch_post.py
# Product:   document x-ray
# Tagline: find HIDDEN prompt injections in resumes
# Price: 9
# Introducing DOCUMENT X-RAY
# Find hidden prompt injections in resumes. $9.00/month
#
# Check it on the Python Sidequests page (python quest.py).



def main():
    pName = input("What is your Product Name? ")
    tagline = input ("what is your one-line tagline --> No period ")
    price = input("What is your montly price, as a number? ")
    price = price.strip()
    price = float(price)
    print(f"Introducing {pName.upper().strip()}")
    print(f"{tagline.strip().capitalize()}. ${price:.2f}/month")
main()