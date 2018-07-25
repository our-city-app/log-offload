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

from google.appengine.ext import ndb


class OffloadSettings(ndb.Model):
    until_request_id = ndb.StringProperty(indexed=False)

    @staticmethod
    def get_instance(namespace):
        return OffloadSettings.get_or_insert('settings', namespace=namespace)


class OffloadRun(ndb.Model):
    offset = ndb.StringProperty(indexed=False)
    until_request_id = ndb.StringProperty(indexed=False)
    creation_time = ndb.DateTimeProperty(auto_now_add=True, indexed=False)
