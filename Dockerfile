
# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container at /app
COPY ml_source/requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container at /app
COPY ml_source/app.py .
COPY ml_source/model.pkl .

# Make port 5000 available to the world outside this container
EXPOSE 5000

# Define environment variables
ENV S3_BUCKET_NAME=mdaie-prml-spy-bucket
ENV S3_DATA_KEY=market-data/latest.parquet
ENV AWS_REGION=ap-southeast-1
ENV FLASK_ENV=production

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=40s --retries=3 \
  CMD python -c "import requests; requests.get('http://localhost:5000/healthcheck', timeout=2)"

# Run app.py when the container launches
CMD ["python", "app.py"]
