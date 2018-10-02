[![Build Status](https://travis-ci.org/rogerthat-platform/log-offload.svg?branch=master)](https://travis-ci.org/rogerthat-platform/log-offload)


To save the logs to GCS, go to the Google Cloud Platform 'logging' page, and click 'exports'.

 - Create a new 'log export sink'
 - Assign the 'Storage Object Viewer' permission to the log parsing project's service account
 - Add the bucket you used for the sink to the log parsing project its config file
