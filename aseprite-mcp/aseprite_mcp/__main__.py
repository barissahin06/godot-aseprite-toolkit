from . import mcp
from .tools import *

def main():
    mcp.run(transport='stdio')

if __name__ == "__main__":
    main()
