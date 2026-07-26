FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set working directory
WORKDIR /app

# Install Python dependencies
# Note: psycopg2-binary ships prebuilt wheels, so no gcc/libpq-dev needed.
COPY requirements.txt .
RUN pip install --no-cache-dir --timeout=120 -r requirements.txt

# Copy the project files
COPY . .

# Expose the port the app runs on
EXPOSE 8000

# Run migrations, then start Celery (worker + embedded beat) and Daphne.
# The Celery beat scheduler here is what fires the weekly rider payout.
CMD ["sh", "start.sh"]
