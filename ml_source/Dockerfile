FROM public.ecr.aws/lambda/python:3.9

# Copy requirements
COPY requirements.txt .

# Install dependencies
RUN pip install --upgrade pip && \
    pip install --prefer-binary --no-cache-dir \
    flask \
    apig_wsgi \
    "pandas<2.0.0" \
    "numpy<1.25.0" \
    "scikit-learn==1.3.0" \
    matplotlib \
    yfinance \
    pyarrow

# Copy application code and model
# Copy application code and model
COPY app_s3.py .
COPY model.pkl .

# Fix permissions (optional but good practice)
RUN chmod 644 app_s3.py model.pkl requirements.txt

# Set the CMD to your handler (could also be done as a parameter override outside of the Dockerfile)
CMD [ "app_s3.handler" ]
