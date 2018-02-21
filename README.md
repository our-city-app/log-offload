[![Build Status](https://travis-ci.org/rogerthat-platform/log-offload.svg?branch=master)](https://travis-ci.org/rogerthat-platform/log-offload)

# Offload logs to GCS

When updating your application (uploading a new version), do not delete that version before the logs of it are processed, else the logs for the last hour will not be processed.