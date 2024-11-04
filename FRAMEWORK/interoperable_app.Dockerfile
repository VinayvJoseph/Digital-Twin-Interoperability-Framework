FROM python:3.8
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY dtsrs-39010-firebase-adminsdk-1jlzc-61844505e2.json /usr/src/app
COPY interoperable_app.py .
ENV PYTHONUNBUFFERED=1
CMD ["python", "interoperable_app.py"]