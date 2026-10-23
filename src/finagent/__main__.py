"""`python -m finagent <command>`: the same entry point as the `finagent` console script."""
import sys

from finagent.cli import main

sys.exit(main())
