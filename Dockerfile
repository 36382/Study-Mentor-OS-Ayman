FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY . /app
RUN pip install --no-cache-dir --no-deps .

ENV PYTHONUNBUFFERED=1
ENV TZ=Asia/Riyadh

CMD ["python", "-m", "ayman_os_agent.telegram_bot"]
