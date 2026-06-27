# 1. Use an official, lightweight Python runtime base image
FROM python:3.12-slim

# 2. Set production-grade system environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

# 3. Create and set the internal directory structure
WORKDIR /app

# 4. Install system dependencies required for compilation (if any)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 5. Copy and install application requirements
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade -r requirements.txt

# 6. Copy the rest of your local source code into the container
COPY . .

# 7. Expose the networking port to the outside world
EXPOSE 8000

# 8. Run the application using Uvicorn web server bound to all interfaces
CMD ["uvicorn", "src.app:app", "--host", "0.0.0.0", "--port", "8000"]