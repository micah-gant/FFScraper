# Base image with headless Chromium
FROM zenika/alpine-chrome:with-node

USER root
# Install Python 3 and pip
RUN apk add --no-cache python3 py3-pip

# Set working directory inside container
WORKDIR /app

# Copy your script and dependencies
COPY requirements.txt ./
RUN python3 -m venv /venv && \
    /venv/bin/pip install --upgrade pip && \
    /venv/bin/pip install --no-cache-dir -r requirements.txt

ENV PATH="/venv/bin:$PATH"
# Optional: Copy everything (if needed)
# COPY . .

# Default command for running manually
CMD ["python", "finder.py"]
