# Copyright 2018 Timur Sokhin.
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
from .individ_image import IndividImage
from .individ_text import IndividText


def cradle(epochs, data_type='text', task_type='classification', parents=None, freeze=None, **kwargs):
    """Factory method for different data types

    Attributes:
        epochs (``int``): number of stage evolution
        data_type (``str``): ?
        task_type (``str``): ?
        parents (``IndividBase``): ?
        freeze (``bool``): ?
    """
    if data_type == 'text':
        return IndividText(epochs, task_type=task_type, parents=parents, freeze=freeze, **kwargs)
    elif data_type == 'image':
        return IndividImage(epochs, task_type=task_type, parents=parents, freeze=freeze, **kwargs)
    else:
        raise ValueError("Incorrect \"data_type\" argument."
                         "Available values: \"text\", \"image\"")
