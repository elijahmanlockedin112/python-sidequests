"""Python Sidequests, the CS50P companion.

    python quest.py               learning mode: opens the page at http://localhost:8950
    python quest.py maintenance   maintenance mode, in the terminal (not learning; nothing counts)
"""
import sys

if sys.version_info < (3, 11):
    sys.exit("Python Sidequests needs Python 3.11 or newer.")

from app.main import main

main(sys.argv[1:])
