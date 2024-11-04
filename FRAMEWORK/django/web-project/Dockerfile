# Use a slim Python image as the base
FROM python:3.11-slim-buster

# Set working directory
WORKDIR /usr/src/app

# Copy requirements.txt (if you have any dependencies)
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy project code
COPY . .

# Expose the port Django typically uses (default 8000)
EXPOSE 8000

# Specify the command to run when the container starts
CMD [ "python", "manage.py", "runserver", "0.0.0.0:8000" ]
