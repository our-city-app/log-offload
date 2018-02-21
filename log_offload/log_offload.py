# -*- coding: utf-8 -*-
# Copyright 2018 GIG Technology NV
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# @@license_version:1.4@@
import json
import logging
import pprint
import time
from datetime import datetime

import cloudstorage
from google.appengine.api.logservice import logservice
from google.appengine.api.modules import get_versions
from google.appengine.ext import deferred, ndb

from consts import OFFLOAD_QUEUE, OFFLOAD_HEADER
from models import OffloadSettings, OffloadRun


class LogOffload(object):
    def __init__(self, cloudstorage_bucket, application_name, offload_header=OFFLOAD_HEADER, namespace=None):
        self.cloudstorage_bucket = cloudstorage_bucket
        self.application_name = application_name
        self.offload_header = offload_header
        self.namespace = namespace

    def export_logs(self):
        export_logs(self.cloudstorage_bucket, self.application_name, self.offload_header, self.namespace)

    def create_log(self, user, type_, request_data, response_data, function_=None, success=None):
        # type: (unicode, unicode, dict, dict, unicode, bool) -> None
        data = {
            'type': type_,
            'request_data': request_data,
            'response_data': response_data,
            'timestamp': time.time()
        }
        try:
            if user is not None:
                data['user'] = user
            if function_ is not None:
                data['function'] = function_
            if success is not None:
                data['status'] = success
            # todo: max 16K. if bigger, skip response_data
            logging.info(self.offload_header + json.dumps(data))
        except:
            logging.info(pprint.pformat(data))
            logging.exception('Failed to offload data')


def _get_folder_name(date):
    return '%04d-%02d-%02d %02d:00:00' % (date.year, date.month, date.day, date.hour)


def _get_bucket_file_handle(bucket, folder_name, application_name):
    counter = 0
    while True:
        counter += 1
        file_name = '/%s/%s/%s-%d.json' % (bucket, folder_name, application_name, counter)
        try:
            cloudstorage.stat(file_name)
        except cloudstorage.NotFoundError:
            break
    return cloudstorage.open(file_name, 'w', content_type='application/json')


def _fetch_logs(offset):
    versions = get_versions()
    logging.info('Fetching logs with offset %s for versions %s', offset, versions)
    return logservice.fetch(offset=offset, versions=versions, include_incomplete=False, include_app_logs=True,
                            batch_size=logservice.MAX_ITEMS_PER_FETCH)


def export_logs(cloudstorage_bucket, application_name, offload_header, namespace=None, offload_run_key=None):
    offset_settings = OffloadSettings.get_instance(namespace)
    if offload_run_key is None:
        offload_run = OffloadRun(until_request_id=offset_settings.until_request_id, namespace=namespace)
        offload_run.put()
        offload_run_key = offload_run.key

    deferred.defer(_export_logs, cloudstorage_bucket, application_name, offload_header, namespace, offload_run_key,
                   _queue=OFFLOAD_QUEUE)


def get_log_datetime(date_obj):
    # type: (datetime) -> datetime
    return datetime(date_obj.year, date_obj.month, date_obj.day, date_obj.hour)


def _convert_to_unicode(v):
    if v is None:
        return None
    if isinstance(v, str):
        return v.decode('utf-8')
    return v


def _export_logs(cloudstorage_bucket, application_name, offload_header, namespace, offload_run_key):
    # type: (unicode, unicode, unicode, ndb.Key) -> None
    offload_header_length = len(offload_header)
    offload_run = offload_run_key.get()
    offset = offload_run.offset
    properties = ['app_id', 'end_time', 'host', 'ip', 'latency', 'status', 'start_time', 'mcycles', 'resource',
                  'response_size', 'user_agent', 'task_queue_name', 'task_name', 'pending_time']
    _gcs_handles = {}
    start = time.time()
    done = False
    for request_log in _fetch_logs(offset):
        if offset is None:
            # This is the first request => Store the request id
            offload_settings = OffloadSettings.get_instance(namespace)
            if offload_run.until_request_id is None:
                offload_run.until_request_id = request_log.request_id
                offload_run.put()
            offload_settings.until_request_id = request_log.request_id
            offload_settings.put()
        elif request_log.request_id == offload_run.until_request_id:
            logging.info('Log offload complete')
            offload_run_key.delete()  # This job is done
            done = True
            break
        offset = request_log.offset
        request_info = {prop: getattr(request_log, prop) for prop in properties}
        if request_info['task_name'] and request_log.app_logs:
            log = request_log.app_logs[0]
            if 'X-Appengine-Taskretrycount' in log.message:
                headers = dict([tuple(header.split(':')) for header in log.message.split(', ')])
                request_info['task_retry_count'] = int(headers['X-Appengine-Taskretrycount'])
        date = get_log_datetime(datetime.fromtimestamp(request_log.start_time))
        folder_name = _get_folder_name(date)
        gcs_file_handle = _gcs_handles.get(folder_name)
        if not gcs_file_handle:
            gcs_file_handle = _get_bucket_file_handle(cloudstorage_bucket, folder_name, application_name)
            _gcs_handles[folder_name] = gcs_file_handle
        gcs_file_handle.write(json.dumps({'type': '_request', 'data': request_info}))
        gcs_file_handle.write('\n')
        for appLog in request_log.app_logs:
            if appLog.message and _convert_to_unicode(appLog.message).startswith(offload_header):
                gcs_file_handle.write(appLog.message[offload_header_length:])
                gcs_file_handle.write('\n')
        if time.time() - start > 9 * 60:
            logging.info('Task deadline approaching, continuing in new task')
            offload_run.offset = offset
            offload_run.put()
            break
    else:
        logging.info('Initial log offload complete')
        done = True
    for handle in _gcs_handles.itervalues():
        handle.close()
    if not done:
        deferred.defer(_export_logs, cloudstorage_bucket, application_name, offload_header, namespace, offload_run_key,
                       _queue=OFFLOAD_QUEUE)
