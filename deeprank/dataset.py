"""This is the Data Utils for Letor source code.

This module is used to read data from letor dataset.
"""

__version__ = '0.2'
__author__ = 'Liang Pang'

import json
import random
import sys

import numpy as np
import torch

from deeprank import utils


class DataLoader():

    def __init__(self, config_file):
        self.config_file = config_file
        self.config = json.loads( open(config_file).read() )

        self.Letor07Path = self.config['data_dir'] #'/home/pangliang/matching/data/letor/r5w/'

        self.word_dict, self.iword_dict = utils.read_word_dict(
            filename=self.Letor07Path + '/word_dict.txt')
        self.query_data = utils.read_data(
            filename=self.Letor07Path + '/qid_query.txt')
        self.doc_data = utils.read_data(
            filename=self.Letor07Path + '/docid_doc.txt')
        self.embed_dict = utils.read_embedding(
            filename=self.Letor07Path + '/embed_wiki-pdc_d50_norm')
        self.idf_dict = utils.read_embedding(
            filename=self.Letor07Path + '/embed.idf')

        self.feat_size = self.config['feat_size']

        self._PAD_ = len(self.word_dict)
        self.word_dict[self._PAD_] = '[PAD]'
        self.iword_dict['[PAD]'] = self._PAD_

        self.embed_dict[self._PAD_] = np.zeros((50, ), dtype=np.float32)
        self.W_init_embed = np.float32(
            np.random.uniform(-0.02, 0.02, [len(self.word_dict), 50]))
        self.embedding = utils.convert_embed_2_numpy(
            self.embed_dict, embed = self.W_init_embed)

        self.W_init_idf = np.float32(
            np.zeros([len(self.word_dict), 1]))
        self.idf_embedding = utils.convert_embed_2_numpy(
            self.idf_dict, embed = self.W_init_idf)

class PairGenerator():
    def __init__(self, rel_file, config):
        rel = utils.read_relation(filename=rel_file)
        self.pair_list = self.make_pair(rel)
        self.config = config

    def make_pair(self, rel):
        rel_set = {}
        pair_list = []
        for label, d1, d2 in rel:
            if d1 not in rel_set:
                rel_set[d1] = {}
            if label not in rel_set[d1]:
                rel_set[d1][label] = []
            rel_set[d1][label].append(d2)
        for d1 in rel_set:
            label_list = sorted(rel_set[d1].keys(), reverse = True)
            for hidx, high_label in enumerate(label_list[:-1]):
                for low_label in label_list[hidx+1:]:
                    for high_d2 in rel_set[d1][high_label]:
                        for low_d2 in rel_set[d1][low_label]:
                            pair_list.append( (d1, high_d2, low_d2) )
        print('Pair Instance Count:', len(pair_list))
        return pair_list

    def get_batch(self, data1, data2):
        config = self.config
        X1 = np.zeros(
            (config['batch_size']*2, config['data1_maxlen']), dtype=np.int64)
        X1_len = np.zeros((config['batch_size']*2,), dtype=np.int64)
        X1_id = [''] * (config['batch_size']*2)
        X2 = np.zeros(
            (config['batch_size']*2, config['data2_maxlen']), dtype=np.int64)
        X2_len = np.zeros((config['batch_size']*2,), dtype=np.int64)
        X2_id = [''] * (config['batch_size']*2)
        Y = np.zeros((config['batch_size']*2,), dtype=np.int64)
        F = np.zeros(
            (config['batch_size']*2, config['feat_size']), dtype=np.float32)

        Y[::2] = 1
        X1[:] = config['fill_word']
        X2[:] = config['fill_word']
        for i in range(config['batch_size']):
            d1, d2p, d2n = random.choice(self.pair_list)

            d1_len = min(config['data1_maxlen'], len(data1[d1]))
            d2p_len = min(config['data2_maxlen'], len(data2[d2p]))
            d2n_len = min(config['data2_maxlen'], len(data2[d2n]))

            X1[i*2,   :d1_len],  X1_len[i*2]   = data1[d1][:d1_len],   d1_len
            X2[i*2,   :d2p_len], X2_len[i*2]   = data2[d2p][:d2p_len], d2p_len
            X1[i*2+1, :d1_len],  X1_len[i*2+1] = data1[d1][:d1_len],   d1_len
            X2[i*2+1, :d2n_len], X2_len[i*2+1] = data2[d2n][:d2n_len], d2n_len

            X1_id[i * 2], X2_id[i * 2] = d1, d2p
            X1_id[i * 2 + 1], X2_id[i * 2 + 1] = d1, d2n
            #F[i*2] = features[(d1, d2p)]
            #F[i*2+1] = features[(d1, d2n)]

        return X1, X1_len, X1_id, X2, X2_len, X2_id, Y, F


class ListGenerator():
    def __init__(self, rel_file, config):
        rel = utils.read_relation(filename=rel_file)
        self.list_list = self.make_list(rel)
        self.config = config

    def make_list(self, rel):
        list_list = {}
        for label, d1, d2 in rel:
            if d1 not in list_list:
                list_list[d1] = []
            list_list[d1].append( (label, d2) )
        for d1 in list_list:
            list_list[d1] = sorted(list_list[d1], reverse = True)
        print('List Instance Count:', len(list_list))
        return list_list.items()

    def get_batch(self, data1, data2):
        config = self.config
        for i, (d1, d2_list) in enumerate(self.list_list):
            X1 = np.zeros(
                (len(d2_list), config['data1_maxlen']), dtype=np.int64)
            X1_len = np.zeros((len(d2_list),), dtype=np.int64)
            X1_id = [''] * len(d2_list)
            X2 = np.zeros(
                (len(d2_list), config['data2_maxlen']), dtype=np.int64)
            X2_len = np.zeros((len(d2_list),), dtype=np.int64)
            X2_id = [''] * len(d2_list)
            Y = np.zeros((len(d2_list),), dtype= np.int64)
            F = np.zeros((len(d2_list), config['feat_size']), dtype=np.float32)
            X1[:] = config['fill_word']
            X2[:] = config['fill_word']
            d1_len = min(config['data1_maxlen'], len(data1[d1]))
            for j, (l, d2) in enumerate(d2_list):
                d2_len = min(config['data2_maxlen'], len(data2[d2]))
                X1[j, :d1_len], X1_len[j] = data1[d1][:d1_len], d1_len
                X2[j, :d2_len], X2_len[j] = data2[d2][:d2_len], d2_len
                Y[j] = l
                X1_id[j], X2_id[j] = d1, d2
                #F[j] = features[(d1, d2)]
            yield X1, X1_len, X1_id, X2, X2_len, X2_id, Y, F


if __name__ == '__main__':
    loader = DataLoader('./config/letor07_mp_fold1.model')
