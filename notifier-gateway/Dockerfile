FROM python:3.12-slim
WORKDIR /app
RUN pip install flask requests gunicorn
COPY app.py .
ENV PYTHONUNBUFFERED=1
CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:8787", "app:app"]

