FROM python:3.8
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY dtsrs_client.py .
ENV PYTHONUNBUFFERED=1
CMD ["python", "dtsrs_client.py"]