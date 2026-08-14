from django.core.validators import URLValidator


# Django's URLField only accepts http/https/ftp/ftps, so every rtsp:// camera
# address was rejected with "Enter a valid URL." URLValidator takes a schemes
# argument; note that this has to be attached to a CharField rather than a
# URLField, because URLField's own http-only validator would still run
# alongside anything passed via validators=.
STREAM_URL_SCHEMES = ["rtsp", "rtsps", "http", "https"]

validate_stream_url = URLValidator(
    schemes=STREAM_URL_SCHEMES,
    message="Enter a valid stream URL, e.g. rtsp://192.168.1.50:554/stream1",
)
