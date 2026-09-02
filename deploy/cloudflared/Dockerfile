FROM python:3.13-slim

COPY cloudflared /usr/local/bin/cloudflared
COPY entrypoint.py /entrypoint.py
RUN chmod +x /usr/local/bin/cloudflared /entrypoint.py

ENTRYPOINT ["python3", "/entrypoint.py"]
