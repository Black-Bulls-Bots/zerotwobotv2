FROM python:3.12-slim

WORKDIR /usr/src/bot
COPY . .

RUN pip3 install --no-cache-dir -r requirements.txt

RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

CMD ["python3", "-m", "zerotwo"]