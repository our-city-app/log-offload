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
import threading
import time
from Queue import Queue
from datetime import datetime

import cloudstorage
from google.appengine.api.logservice import logservice
from google.appengine.ext import deferred, ndb

from consts import OFFLOAD_QUEUE, OFFLOAD_HEADER, MAX_BUF_SIZE
from models import OffloadSettings, OffloadRun

try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO


class LogOffload(object):
    def __init__(self, cloudstorage_bucket, application_name, offload_header=OFFLOAD_HEADER, namespace=None):
        self.cloudstorage_bucket = cloudstorage_bucket
        self.application_name = application_name
        self.offload_header = offload_header
        self.namespace = namespace

    def export_logs(self):
        ndb.delete_multi(OffloadSettings.query(namespace=self.namespace).fetch(None, keys_only=True))
        ndb.delete_multi(OffloadRun.query(namespace=self.namespace).fetch(None, keys_only=True))
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
            logging.info(self.offload_header + json.dumps(data))
        except:
            logging.info(pprint.pformat(data))
            logging.exception('Failed to offload data')


def _get_bucket_file_handle(date, bucket, application_name):
    counter = 0
    while True:
        counter += 1
        file_name = '/%s/%04d-%02d-%02d %02d:00:00/%s-%d.json' % (bucket, date.year, date.month, date.day, date.hour,
                                                                  application_name, counter)
        try:
            cloudstorage.stat(file_name)
        except cloudstorage.NotFoundError:
            break
    return cloudstorage.open(file_name, 'w', content_type='application/json')


def _fetch_logs(offset):
    return logservice.fetch(offset=offset, minimum_log_level=logservice.LOG_LEVEL_INFO, include_incomplete=False,
                            include_app_logs=True, batch_size=logservice.MAX_ITEMS_PER_FETCH)


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


def _export_logs(cloudstorage_bucket, application_name, offload_header, namespace, offload_run_key):
    # type: (unicode, unicode, unicode, ndb.Key) -> None
    offload_header_length = len(offload_header)
    to_be_saved = []
    to_be_deleted = []
    write_queue = Queue()

    # Look into https://cloud.google.com/storage/docs/composite-objects for possibly better perf
    def writer():
        current_date = None
        gcs_file_handler = None
        while True:
            packet = write_queue.get()
            if packet is None:
                if gcs_file_handler:
                    gcs_file_handler.close()
                return  # Exit thread
            date, buf, offset, to_be_saved = packet
            if current_date is None or current_date != date:
                if gcs_file_handler:
                    gcs_file_handler.close()
                current_date = date
                gcs_file_handler = _get_bucket_file_handle(date, cloudstorage_bucket, application_name)
            gcs_file_handler.write(buf.getvalue())
            if offset is not None:
                offload_run = offload_run_key.get()
                offload_run.offset = offset
                to_be_saved.append(offload_run)
            if to_be_saved:
                ndb.put_multi(to_be_saved)

    done = False
    offload_run = offload_run_key.get()
    offset = offload_run.offset
    thread = threading.Thread(target=writer)
    thread.daemon = True
    thread.start()
    properties = ['app_id', 'end_time', 'host', 'ip', 'latency', 'status', 'start_time', 'mcycles', 'resource',
                  'response_size', 'user_agent', 'task_queue_name', 'task_name', 'pending_time']
    try:
        buf_date = None
        buf = StringIO()
        start = time.time()
        for request_log in _fetch_logs(offset):
            if offset is None:
                # This is the first request => Store the request id
                offset_settings = OffloadSettings.get_instance(namespace)
                offset_settings.until_request_id = request_log.request_id
                to_be_saved.append(offset_settings)
            elif request_log.request_id == offload_run.until_request_id:
                if buf_date:
                    write_queue.put((buf_date, buf, None, to_be_saved))
                    to_be_deleted.append(offload_run_key)  # This job is done
                done = True
                break
            offset = request_log.offset
            date = get_log_datetime(datetime.fromtimestamp(request_log.start_time))
            if not buf_date:
                buf_date = date
            elif date != buf_date:
                if buf.tell() > 0:
                    write_queue.put((buf_date, buf, offset, to_be_saved))
                    to_be_saved = []
                    buf = StringIO()
                buf_date = date
            elif buf.tell() > MAX_BUF_SIZE:
                write_queue.put((buf_date, buf, offset, to_be_saved))
                to_be_saved = []
                buf = StringIO()
            elif time.time() - start > 9 * 60:  # Deferred deadline = 10 minutes
                write_queue.put((buf_date, buf, offset, to_be_saved))
                break

            request_info = {prop: getattr(request_log, prop) for prop in properties}
            if request_info['task_name'] and request_log.app_logs:
                log = request_log.app_logs[0]
                if 'X-Appengine-Taskretrycount' in log.message:
                    headers = dict([tuple(header.split(':')) for header in log.message.split(', ')])
                    request_info['task_retry_count'] = int(headers['X-Appengine-Taskretrycount'])
            buf.write(json.dumps({'type': '_request', 'data': request_info}))
            buf.write('\n')
            for appLog in request_log.app_logs:
                if appLog.message and appLog.message.startswith(offload_header):
                    buf.write(appLog.message[offload_header_length:])
                    buf.write('\n')
        else:
            if buf.tell() > 0:
                write_queue.put((buf_date, buf, None, to_be_saved))
            done = True
    finally:
        write_queue.put(None)  # Exit writer thread
        thread.join()

    if to_be_deleted:
        ndb.delete_multi(to_be_deleted)

    if not done:
        export_logs(cloudstorage_bucket, application_name, offload_header, namespace, offload_run_key)
