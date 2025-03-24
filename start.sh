#!/bin/bash

# Start the Discord bot in the background
python bot.py &

# Start the Flask webhook (or FastAPI) on port 10000
gunicorn webhook:app --workers 1 --threads 8 -b 0.0.0.0:10000
