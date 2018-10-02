# -*- coding: utf-8 -*-
# Copyright 2018 Mobicage NV
# NOTICE: THIS FILE HAS BEEN MODIFIED BY MOBICAGE NV IN ACCORDANCE WITH THE APACHE LICENSE VERSION 2.0
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
# @@license_version:1.5@@

import json
import logging
import pprint
import time

from consts import OFFLOAD_HEADER


class LogOffload(object):
    def __init__(self, offload_header=OFFLOAD_HEADER):
        self.offload_header = offload_header

    def create_log(self, user, type_, request_data, response_data, function_=None, success=None, timestamp=None):
        # type: (unicode, unicode, dict, dict, unicode, bool, float) -> None
        data = {
            'type': type_,
            'request_data': request_data,
            'response_data': response_data,
            'timestamp': timestamp or time.time()
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

