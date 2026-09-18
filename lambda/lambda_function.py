import json
import base64
import uuid
import os
import hashlib
import hmac
import urllib.request
import urllib.parse
from datetime import datetime, timezone


BUCKET_NAME = "upload-images-2026-neha"
REGION = "ap-south-1"


def response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json"
        },
        "body": json.dumps(body)
    }


def sign(key, message):
    return hmac.new(
        key,
        message.encode("utf-8"),
        hashlib.sha256
    ).digest()


def get_signature_key(secret_key, date_stamp, region, service):

    k_date = sign(
        ("AWS4" + secret_key).encode("utf-8"),
        date_stamp
    )

    k_region = hmac.new(
        k_date,
        region.encode("utf-8"),
        hashlib.sha256
    ).digest()

    k_service = hmac.new(
        k_region,
        service.encode("utf-8"),
        hashlib.sha256
    ).digest()

    k_signing = hmac.new(
        k_service,
        b"aws4_request",
        hashlib.sha256
    ).digest()

    return k_signing


def upload_to_s3(file_bytes, object_key, content_type):

    print("========== S3 UPLOAD START ==========")

    # Lambda temporary execution-role credentials
    access_key = os.environ["AWS_ACCESS_KEY_ID"]
    secret_key = os.environ["AWS_SECRET_ACCESS_KEY"]
    session_token = os.environ["AWS_SESSION_TOKEN"]

    service = "s3"

    host = (
        f"{BUCKET_NAME}.s3."
        f"{REGION}.amazonaws.com"
    )

    # Encode only the object key portion
    encoded_key = urllib.parse.quote(
        object_key,
        safe="/"
    )

    endpoint = f"https://{host}/{encoded_key}"

    print("S3 Host:", host)
    print("S3 Key:", object_key)
    print("S3 Endpoint:", endpoint)

    now = datetime.now(timezone.utc)

    amz_date = now.strftime(
        "%Y%m%dT%H%M%SZ"
    )

    date_stamp = now.strftime(
        "%Y%m%d"
    )

    payload_hash = hashlib.sha256(
        file_bytes
    ).hexdigest()

    canonical_uri = "/" + encoded_key

    canonical_querystring = ""

    canonical_headers = (
        f"host:{host}\n"
        f"x-amz-content-sha256:{payload_hash}\n"
        f"x-amz-date:{amz_date}\n"
        f"x-amz-security-token:{session_token}\n"
    )

    signed_headers = (
        "host;"
        "x-amz-content-sha256;"
        "x-amz-date;"
        "x-amz-security-token"
    )

    canonical_request = (
        "PUT\n"
        + canonical_uri
        + "\n"
        + canonical_querystring
        + "\n"
        + canonical_headers
        + "\n"
        + signed_headers
        + "\n"
        + payload_hash
    )

    algorithm = "AWS4-HMAC-SHA256"

    credential_scope = (
        f"{date_stamp}/"
        f"{REGION}/"
        f"{service}/"
        f"aws4_request"
    )

    canonical_request_hash = hashlib.sha256(
        canonical_request.encode("utf-8")
    ).hexdigest()

    string_to_sign = (
        algorithm
        + "\n"
        + amz_date
        + "\n"
        + credential_scope
        + "\n"
        + canonical_request_hash
    )

    signing_key = get_signature_key(
        secret_key,
        date_stamp,
        REGION,
        service
    )

    signature = hmac.new(
        signing_key,
        string_to_sign.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()

    authorization = (
        f"{algorithm} "
        f"Credential={access_key}/"
        f"{credential_scope}, "
        f"SignedHeaders={signed_headers}, "
        f"Signature={signature}"
    )

    request = urllib.request.Request(
        endpoint,
        data=file_bytes,
        method="PUT"
    )

    request.add_header(
        "Host",
        host
    )

    request.add_header(
        "x-amz-date",
        amz_date
    )

    request.add_header(
        "x-amz-content-sha256",
        payload_hash
    )

    request.add_header(
        "x-amz-security-token",
        session_token
    )

    request.add_header(
        "Authorization",
        authorization
    )

    request.add_header(
        "Content-Type",
        content_type
    )

    try:

        with urllib.request.urlopen(
            request,
            timeout=30
        ) as result:

            print(
                "S3 HTTP STATUS:",
                result.status
            )

            return result.status

    except urllib.error.HTTPError as e:

        error_body = e.read().decode(
            "utf-8",
            errors="replace"
        )

        print(
            "========== S3 ERROR =========="
        )

        print(
            "HTTP STATUS:",
            e.code
        )

        print(
            "ERROR BODY:",
            error_body
        )

        raise Exception(
            f"S3 HTTP {e.code}: {error_body}"
        )


def lambda_handler(event, context):

    print(
        "========== LAMBDA START =========="
    )

    try:

        print(
            "Event:",
            json.dumps(
                event,
                default=str
            )
        )

        request_context = event.get(
            "requestContext",
            {}
        )

        http_info = request_context.get(
            "http",
            {}
        )

        method = http_info.get(
            "method",
            ""
        )

        print(
            "HTTP Method:",
            method
        )

        # --------------------------------
        # OPTIONS
        # --------------------------------

        if method == "OPTIONS":

            return {
                "statusCode": 200,
                "headers": {
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Headers": "content-type",
                    "Access-Control-Allow-Methods": "POST,OPTIONS"
                },
                "body": ""
            }

        # --------------------------------
        # GET
        # --------------------------------

        if method == "GET":

            return response(
                200,
                {
                    "message":
                    "UploadImageLambda is working",
                    "python":
                    "3.14"
                }
            )

        # --------------------------------
        # POST
        # --------------------------------

        if method != "POST":

            return response(
                405,
                {
                    "message":
                    "Only POST is allowed"
                }
            )

        # --------------------------------
        # GET REQUEST BODY
        # --------------------------------

        body = event.get(
            "body"
        )

        if not body:

            return response(
                400,
                {
                    "message":
                    "Image data is missing"
                }
            )

        print(
            "Body received"
        )

        # --------------------------------
        # BASE64 DECODE
        # --------------------------------

        try:

            file_bytes = base64.b64decode(
                body,
                validate=True
            )

        except Exception as e:

            print(
                "Base64 error:",
                str(e)
            )

            return response(
                400,
                {
                    "message":
                    "Invalid Base64 image",
                    "error":
                    str(e)
                }
            )

        print(
            "Image size:",
            len(file_bytes),
            "bytes"
        )

        # --------------------------------
        # CREATE S3 KEY
        # --------------------------------

        image_id = str(
            uuid.uuid4()
        )

        object_key = (
            f"images/{image_id}.jpg"
        )

        print(
            "Object key:",
            object_key
        )

        # --------------------------------
        # UPLOAD
        # --------------------------------

        s3_status = upload_to_s3(
            file_bytes,
            object_key,
            "image/jpeg"
        )

        print(
            "Upload successful"
        )

        # --------------------------------
        # RESPONSE
        # --------------------------------

        return response(
            200,
            {
                "message":
                "Image uploaded successfully",

                "bucket":
                BUCKET_NAME,

                "key":
                object_key,

                "s3Status":
                s3_status
            }
        )

    except Exception as e:

        print(
            "========== LAMBDA ERROR =========="
        )

        print(
            "Error type:",
            type(e).__name__
        )

        print(
            "Error:",
            str(e)
        )

        return response(
            500,
            {
                "message":
                "Upload failed",

                "error":
                str(e),

                "errorType":
                type(e).__name__
            }
        )