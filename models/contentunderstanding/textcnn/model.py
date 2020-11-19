#   Copyright (c) 2020 PaddlePaddle Authors. All Rights Reserved.
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

from paddlerec.core.utils import envs
from paddlerec.core.model import ModelBase
import paddle


class Model(ModelBase):
    def __init__(self, config):
        ModelBase.__init__(self, config)
        self.dict_dim = envs.get_global_env("hyper_parameters.dict_dim")
        self.max_len = envs.get_global_env("hyper_parameters.max_len")
        self.cnn_dim = envs.get_global_env("hyper_parameters.cnn_dim")
        self.cnn_filter_size1 = envs.get_global_env(
            "hyper_parameters.cnn_filter_size1")
        self.cnn_filter_size2 = envs.get_global_env(
            "hyper_parameters.cnn_filter_size2")
        self.cnn_filter_size3 = envs.get_global_env(
            "hyper_parameters.cnn_filter_size3")
        self.emb_dim = envs.get_global_env("hyper_parameters.emb_dim")
        self.hid_dim = envs.get_global_env("hyper_parameters.hid_dim")
        self.class_dim = envs.get_global_env("hyper_parameters.class_dim")
        self.is_sparse = envs.get_global_env("hyper_parameters.is_sparse")

    def input_data(self, is_infer=False, **kwargs):
        data = paddle.static.data(
            name="input", shape=[None, self.max_len], dtype='int64')
        seq_len = paddle.static.data(
            name="seq_len", shape=[None], dtype='int64')
        label = paddle.static.data(
            name="label", shape=[None, 1], dtype='int64')
        return [data, seq_len, label]

    def net(self, input, is_infer=False):
        """ network definition """
        data = input[0]
        seq_len = input[1]
        label = input[2]

        # embedding layer
        emb = paddle.static.nn.embedding(
            input=data,
            size=[self.dict_dim, self.emb_dim],
            is_sparse=self.is_sparse)
        emb = paddle.fluid.layers.sequence_unpad(emb, length=seq_len)
        # convolution layer
        conv1 = paddle.fluid.nets.sequence_conv_pool(
            input=emb,
            num_filters=self.cnn_dim,
            filter_size=self.cnn_filter_size1,
            act="tanh",
            pool_type="max")

        conv2 = paddle.fluid.nets.sequence_conv_pool(
            input=emb,
            num_filters=self.cnn_dim,
            filter_size=self.cnn_filter_size2,
            act="tanh",
            pool_type="max")

        conv3 = paddle.fluid.nets.sequence_conv_pool(
            input=emb,
            num_filters=self.cnn_dim,
            filter_size=self.cnn_filter_size3,
            act="tanh",
            pool_type="max")

        convs_out = paddle.concat(x=[conv1, conv2, conv3], axis=1)

        # full connect layer
        fc_1 = paddle.static.nn.fc(x=convs_out,
                                   size=self.hid_dim,
                                   activation="tanh")
        # softmax layer
        prediction = paddle.static.nn.fc(x=[fc_1], size=self.class_dim)
        #activation="softmax")
        #1.8 api cost = paddle.fluid.layers.cross_entropy(input=prediction, label=label)
        cost = paddle.nn.functional.loss.cross_entropy(
            input=prediction, label=label)
        avg_cost = paddle.mean(x=cost)
        acc = paddle.metric.accuracy(input=prediction, label=label)

        self._cost = avg_cost
        if is_infer:
            self._infer_results["acc"] = acc
            self._infer_results["loss"] = avg_cost
        else:
            self._metrics["acc"] = acc
            self._metrics["loss"] = avg_cost
