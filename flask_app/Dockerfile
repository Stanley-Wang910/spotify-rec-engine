# Use an official Python runtime as a parent image
FROM python:3.11-slim

COPY requirements.txt /

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the current directory contents into the container at /app
COPY . /app

# Set the working directory
WORKDIR /app/src

# Make port 5000 available to the world outside this container
EXPOSE 5000


ENV PYTHONPATH=/app
ENV FLASK_APP=app.py


# Run app.py when the container launches
CMD ["gunicorn", "--config", "gunicorn.conf.py", "app:app"]