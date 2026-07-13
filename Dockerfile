# Use official Python slim image
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    poppler-utils \
    wget \
    curl \
    ca-certificates \
    --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Install Tectonic LaTeX compiler
RUN curl --proto '=https' --tlsv1.2 -fsSL \
    https://drop.rust-lang.org/tectonic-installer.sh | sh && \
    mv ~/.tectonic/bin/tectonic /usr/local/bin/tectonic || \
    (wget -qO /usr/local/bin/tectonic \
      "https://github.com/tectonic-typesetting/tectonic/releases/download/tectonic@0.15.0/tectonic-x86_64-unknown-linux-musl.tar.gz" \
      && chmod +x /usr/local/bin/tectonic)

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create required directories
RUN mkdir -p uploads outputs

# Expose port
EXPOSE 5000

# Environment defaults (override via Code Engine secrets)
ENV FLASK_ENV=production
ENV FLASK_DEBUG=0
ENV FLASK_PORT=5000
ENV LATEX_COMPILER=tectonic

# Run with Gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "120", "wsgi:app"]
