FROM python:3.10-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade -r requirements.txt
COPY app .
EXPOSE 3100
CMD ["fastapi", "run", "app.py", "--port", "3100"]