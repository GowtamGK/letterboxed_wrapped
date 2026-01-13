FROM python:3.11-slim

# Install Chrome and ChromeDriver
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    unzip \
    curl \
    jq \
    && wget -q -O /tmp/google-chrome.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb \
    && apt-get install -y /tmp/google-chrome.deb \
    && rm /tmp/google-chrome.deb \
    # Get Chrome major version and download matching ChromeDriver from Chrome for Testing
    && CHROME_VERSION=$(google-chrome --version | awk '{print $3}' | cut -d'.' -f1) \
    && CHROMEDRIVER_URL=$(curl -s "https://googlechromelabs.github.io/chrome-for-testing/last-known-good-versions-with-downloads.json" | jq -r ".channels.Stable.downloads.chromedriver[] | select(.platform==\"linux64\") | .url") \
    && wget -q -O /tmp/chromedriver.zip "$CHROMEDRIVER_URL" \
    && unzip -j /tmp/chromedriver.zip -d /usr/local/bin/ \
    && chmod +x /usr/local/bin/chromedriver \
    && rm /tmp/chromedriver.zip \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set environment variables
ENV CHROMEDRIVER_PATH=/usr/local/bin/chromedriver
ENV CHROME_BIN=/usr/bin/google-chrome

# Set working directory
WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app files
COPY . .

# Expose port
EXPOSE 10000

# Start command
CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:10000", "--timeout", "120"]
