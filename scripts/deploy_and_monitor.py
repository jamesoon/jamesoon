import boto3
import sagemaker
import os
import time
from sagemaker.sklearn.model import SKLearnModel
from sagemaker.model_monitor import DataCaptureConfig, DefaultModelMonitor, DatasetFormat, CronExpressionGenerator

# Configuration
ROLE = os.environ.get("SAGEMAKER_ROLE_ARN") # User must set this or we try to get it
BUCKET = sagemaker.Session().default_bucket()
PREFIX = "sutd-mlops-project"
MODEL_PATH = "ml_source/model.pkl"
ENTRY_POINT = "ml_source/sagemaker_inference.py"
ENDPOINT_NAME = f"spy-prediction-endpoint-{int(time.time())}"

def get_role():
    try:
        return sagemaker.get_execution_role()
    except ValueError:
        if ROLE:
            return ROLE
        else:
            print("Error: SAGEMAKER_ROLE_ARN environment variable not set and not running on SageMaker.")
            exit(1)

def deploy_model():
    role = get_role()
    print(f"Using role: {role}")
    print(f"Using bucket: {BUCKET}")

    # Upload model to S3 (SageMaker expects a tar.gz usually, but SKLearnModel handles repacking if we point to source dir or we can just tar it ourselves)
    # Actually SKLearnModel with model_data pointing to a local file will upload it.
    # But usually it expects model.tar.gz. Let's tar it first to be safe or let SDK handle it.
    # The SDK 'model_data' arg usually expects an S3 URI or local path to .tar.gz.
    # If we pass source_dir, it packs that.
    
    # Let's create a model.tar.gz from model.pkl
    os.system(f"tar -czf model.tar.gz -C ml_source model.pkl")
    model_data_path = f"model.tar.gz"

    # Data Capture Configuration
    data_capture_config = DataCaptureConfig(
        enable_capture=True,
        sampling_percentage=100,
        destination_s3_uri=f"s3://{BUCKET}/{PREFIX}/data-capture",
        capture_options=["REQUEST", "RESPONSE"],
        csv_content_types=["text/csv"],
        json_content_types=["application/json"]
    )

    # Define Model
    sklearn_model = SKLearnModel(
        model_data=model_data_path,
        role=role,
        entry_point=ENTRY_POINT,
        framework_version="1.0-1", # Adjust based on needed scikit-learn version
        py_version="py3",
        sagemaker_session=sagemaker.Session()
    )

    # Deploy Endpoint
    print(f"Deploying endpoint: {ENDPOINT_NAME}...")
    predictor = sklearn_model.deploy(
        initial_instance_count=1,
        instance_type="ml.m5.large",
        endpoint_name=ENDPOINT_NAME,
        data_capture_config=data_capture_config
    )
    
    print(f"Endpoint deployed: {ENDPOINT_NAME}")
    return predictor

def setup_monitoring(predictor):
    role = get_role()
    session = sagemaker.Session()
    
    # Define the Monitor
    my_monitor = DefaultModelMonitor(
        role=role,
        instance_count=1,
        instance_type='ml.m5.large',
        volume_size_in_gb=20,
        max_runtime_in_seconds=3600,
        sagemaker_session=session
    )

    # Upload baseline data
    baseline_local_path = "ml_source/baseline_data/baseline.csv"
    if not os.path.exists(baseline_local_path):
        print(f"Error: Baseline data not found at {baseline_local_path}")
        return

    baseline_prefix = f"{PREFIX}/baseline"
    baseline_data_uri = f"s3://{BUCKET}/{baseline_prefix}/baseline.csv"
    print(f"Uploading baseline data to {baseline_data_uri}...")
    session.upload_data(baseline_local_path, bucket=BUCKET, key_prefix=baseline_prefix)

    # Suggest Baseline
    print("Starting baseline processing job (this may take a few minutes)...")
    my_monitor.suggest_baseline(
        baseline_dataset=baseline_data_uri,
        dataset_format=DatasetFormat.csv(header=False),
        output_s3_uri=f"s3://{BUCKET}/{PREFIX}/baseline-results",
        wait=True
    )
    print("Baseline job complete.")

    # Create Monitoring Schedule
    print("Creating monitoring schedule...")
    my_monitor.create_monitoring_schedule(
        monitor_schedule_name=f"spy-monitor-{int(time.time())}",
        endpoint_input=predictor.endpoint_name,
        output_s3_uri=f"s3://{BUCKET}/{PREFIX}/monitoring-reports",
        statistics=my_monitor.baseline_statistics(),
        constraints=my_monitor.suggested_constraints(),
        schedule_cron_expression=CronExpressionGenerator.hourly(),
        enable_cloudwatch_metrics=True
    )
    print(f"Monitoring schedule created for endpoint {predictor.endpoint_name}")

if __name__ == "__main__":
    if not os.path.exists("model.tar.gz"):
        print("Creating model.tar.gz...")
        # Check if model.pkl exists
        if not os.path.exists("ml_source/model.pkl"):
            print("Error: ml_source/model.pkl not found. Run training first.")
            exit(1)
        os.system("tar -czf model.tar.gz -C ml_source model.pkl")

    predictor = deploy_model()
    setup_monitoring(predictor)
