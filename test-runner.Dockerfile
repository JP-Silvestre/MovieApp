FROM python:3.10-slim

WORKDIR /tests

COPY backend/requirements.txt /tmp/backend-requirements.txt
COPY mongo/requirements.txt /tmp/mongo-requirements.txt
RUN pip install --no-cache-dir -r /tmp/backend-requirements.txt \
    && pip install --no-cache-dir -r /tmp/mongo-requirements.txt

COPY backend/ ./backend/
COPY mongo/ ./mongo/
COPY tests/ ./tests/

ENV PYTHONPATH=/tests/backend

CMD ["pytest", "-v", "--junitxml=test-results.xml", "tests/test_app.py", "mongo/test_db.py"]
