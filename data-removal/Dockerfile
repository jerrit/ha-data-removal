ARG BUILD_FROM
FROM ${BUILD_FROM}

# System deps for Python and Playwright/Chromium
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 \
        python3-pip \
        jq \
    && rm -rf /var/lib/apt/lists/*

# Store Playwright browsers in a predictable location inside the image
ENV PLAYWRIGHT_BROWSERS_PATH=/usr/local/playwright

WORKDIR /app

COPY requirements.txt .
RUN pip3 install --no-cache-dir --break-system-packages -r requirements.txt \
    && pip3 install --no-cache-dir --break-system-packages playwright \
    && playwright install chromium --with-deps \
    && rm -rf /tmp/* /root/.cache/pip

# Copy application source
COPY app.py db.py opt_out_db.py ./
COPY bots/ bots/
COPY templates/ templates/
COPY static/ static/

# Copy init scripts (run.sh → /usr/bin/run.sh)
COPY rootfs/ /
RUN chmod a+x /usr/bin/run.sh

ENTRYPOINT ["/usr/bin/run.sh"]
