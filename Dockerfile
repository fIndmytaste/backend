FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && apt-get clean

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the project files
COPY . .

# Expose the port the app runs on
EXPOSE 8000

# Command to run the application with Daphne for ASGI/WebSocket support
CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "findmytaste.asgi:application"]