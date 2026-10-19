import sys
import os

api_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.abspath(os.path.join(api_dir, '..'))

if api_dir not in sys.path:
    sys.path.insert(0, api_dir)
if root_dir not in sys.path:
    sys.path.insert(1, root_dir)

from app import app
