import os
import boto3
from dotenv import load_dotenv
from botocore.exceptions import ClientError

load_dotenv()

AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION = os.getenv("AWS_REGION")
BUCKET_NAME = os.getenv("S3_BUCKET_NAME")

s3 = boto3.client(
    "s3",
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    region_name=AWS_REGION,
)


def upload_file_to_s3(file_obj, object_key):
    s3.upload_fileobj(file_obj, BUCKET_NAME, object_key)

    return object_key


def download_file_from_s3(object_key, local_path):

    s3.download_file(
        BUCKET_NAME,
        object_key,
        local_path
    )

    return local_path


def delete_file_from_s3(object_key):
    s3.delete_object(
        Bucket=BUCKET_NAME,
        Key=object_key
    )


def generate_presigned_url(object_key, expires=3600):
    try:
        url = s3.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": BUCKET_NAME,
                "Key": object_key
            },
            ExpiresIn=expires
        )

        return url

    except ClientError:
        return None