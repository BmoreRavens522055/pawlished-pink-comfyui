#!/usr/bin/env python3
# Compatibility entrypoint for a previously saved monitor command.
import sys
from ppctl import main

sys.argv = [sys.argv[0], "monitor"] + sys.argv[1:]
main()
