import sys
from .standalone import Main

if __name__ == "__main__":
    if len(sys.argv) > 1:
        Main(sys.argv[1]).run()
    else:
        print("Usage: python -m dshow MEDIA_FILE", file=sys.stderr)
