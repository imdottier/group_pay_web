# Use an official lightweight Python image.
# https://hub.docker.com/_/python
FROM python:3.12-slim

# Set environment variables to make Python run better in a container
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set the working directory in the container
WORKDIR /app

# Copy and install dependencies first to leverage Docker layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your application code
COPY ./backend /app/backend
COPY ./alembic /app/alembic
COPY alembic.ini .
COPY test_db_connection.py .

# Expose the port Cloud Run will use
EXPOSE 8080

# Define the command to run your application
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8080"] 