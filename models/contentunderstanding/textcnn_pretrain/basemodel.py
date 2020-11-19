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
from paddlerec.core.metrics import RecallK
import paddle


class Model(ModelBase):
    def __init__(self, config):
        ModelBase.__init__(self, config)
        self.dict_size = 2000000 + 1
        self.max_seq_len = 1024
        self.emb_dim = 128
        self.cnn_hid_dim = 128
        self.cnn_win_size = 3
        self.cnn_win_size2 = 5
        self.hid_dim1 = 96
        self.class_dim = 30
        self.is_sparse = True

    def input_data(self, is_infer=False, **kwargs):

        text = paddle.static.data(
            name="text", shape=[None, self.max_seq_len, 1], dtype='int64')
        label = paddle.static.data(
            name="category", shape=[None, 1], dtype='int64')
        seq_len = paddle.static.data(
            name="seq_len", shape=[None], dtype='int64')
        return [text, label, seq_len]

    def net(self, inputs, is_infer=False):
        """ network definition """
        #text label
        self.data = inputs[0]
        self.label = inputs[1]
        self.seq_len = inputs[2]
        emb = embedding(self.data, self.dict_size, self.emb_dim,
                        self.is_sparse)
        concat = multi_convs(emb, self.seq_len, self.cnn_hid_dim,
                             self.cnn_win_size, self.cnn_win_size2)
        self.fc_1 = full_connect(concat, self.hid_dim1)
        self.metrics(is_infer)

    def metrics(self, is_infer=False):
        """ classification and metrics """
        # softmax layer
        prediction = paddle.static.nn.fc(
            x=[self.fc_1],
            size=self.class_dim,
            #  activation="softmax",
            name="pretrain_fc_1")
        cost = paddle.nn.functional.loss.cross_entropy(
            input=prediction, label=self.label)
        # 1.8 api: cost = paddle.fluid.layers.cross_entropy(input=prediction, label=self.label)
        avg_cost = paddle.mean(x=cost)
        acc = paddle.metric.accuracy(input=prediction, label=self.label)
        #acc = RecallK(input=prediction, label=label, k=1)

        self._cost = avg_cost
        if is_infer:
            self._infer_results["acc"] = acc
        else:
            self._metrics["acc"] = acc


def embedding(inputs, dict_size, emb_dim, is_sparse):
    """ embeding definition """
    emb = paddle.static.nn.embedding(
        input=inputs,
        size=[dict_size, emb_dim],
        is_sparse=is_sparse,
        param_attr=paddle.ParamAttr(
            name='pretrain_word_embedding',
            initializer=paddle.fluid.initializer.Xavier()))
    return emb


def multi_convs(input_layer, seq_len, cnn_hid_dim, cnn_win_size,
                cnn_win_size2):
    """conv and concat"""
    emb = paddle.fluid.layers.sequence_unpad(
        input_layer, length=seq_len, name="pretrain_unpad")
    conv = paddle.fluid.nets.sequence_conv_pool(
        param_attr=paddle.ParamAttr(name="pretrain_conv0_w"),
        bias_attr=paddle.ParamAttr(name="pretrain_conv0_b"),
        input=emb,
        num_filters=cnn_hid_dim,
        filter_size=cnn_win_size,
        act="tanh",
        pool_type="max")
    conv2 = paddle.fluid.nets.sequence_conv_pool(
        param_attr=paddle.ParamAttr(name="pretrain_conv1_w"),
        bias_attr=paddle.ParamAttr(name="pretrain_conv1_b"),
        input=emb,
        num_filters=cnn_hid_dim,
        filter_size=cnn_win_size2,
        act="tanh",
        pool_type="max")
    concat = paddle.concat(x=[conv, conv2], axis=1, name="pretrain_concat")
    return concat


def full_connect(input_layer, hid_dim1):
    """full connect layer"""
    fc_1 = paddle.static.nn.fc(name="pretrain_fc_0",
                               x=input_layer,
                               size=hid_dim1,
                               activation="tanh")
    return fc_1
