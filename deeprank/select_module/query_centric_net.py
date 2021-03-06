from collections import defaultdict
from itertools import chain

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

from deeprank import select_module


class QueryCentricNet(select_module.SelectNet):
    def __init__(self, config, out_device=None):
        super().__init__(config)
        self.output_type = 'LL'

        self.pad_value = self.config['pad_value']

        self.max_match = self.config['max_match']
        self.win_size = self.config['win_size']

        self.q_size = self.config['q_limit']
        self.d_size = self.max_match

        # key (doc_id, q_item)
        self.cache = {}
        self.out_device = out_device

    def get_win(self, d, p):
        start = p - self.win_size
        stop = p + self.win_size + 1
        return d[start: stop]

    def process_item(self, q_item, d_item, q_item_len, d_item_len):

        d_pad = F.pad(
            d_item, (self.win_size, self.win_size), value=self.pad_value)

        snippet = [[] for _ in range(q_item_len)]
        position = [[] for _ in range(q_item_len)]
        snippet_len = [0] * q_item_len
        for d_p in range(d_item_len):
            d_pad_p = d_p + self.win_size
            dw = d_pad[d_pad_p]
            win = None
            for q_p in range(q_item_len):
                if snippet_len[q_p] >= self.max_match:
                    continue
                qw = q_item[q_p]
                if dw.item() == qw.item():
                    win =  win if win is not None else self.get_win(
                        d_pad, d_pad_p)
                    snippet_len[q_p] += 1
                    snippet[q_p].append(win.unsqueeze(dim=0))
                    position[q_p].append(d_p)

        snippet = list(chain.from_iterable(snippet))
        position = list(chain.from_iterable(position))

        snippet = torch.cat(
            snippet, dim=0) if len(snippet) > 0 else torch.zeros(
                0, self.win_size*2+1, dtype=torch.int64).to(q_item.device)
        position = torch.FloatTensor(position)

        return snippet, snippet_len, position

    def forward_cache(self, q_data, d_data, q_len, d_len, qid_list, did_list):

        n_item = q_data.shape[0]
        snippets = []
        snippets_len = []
        positions = []

        for i in range(n_item):

            key = (qid_list[i], did_list[i])
            if key not in self.cache:
                self.cache[key] = self.process_item(
                    q_data[i], d_data[i], q_len[i].item(), d_len[i].item())
            snippet, snippet_len, position = self.cache[key]

            snippets.append(snippet)
            snippets_len.append(snippet_len)
            positions.append(position)

        return q_data, snippets, q_len, snippets_len, positions

    def forward_normal(self, q_data, d_data, q_len, d_len):

        n_item = q_data.shape[0]
        snippets = []
        snippets_len = []

        for i in range(n_item):

            snippet, snippet_len, position = self.process_item(
                q_data[i], d_data[i], q_len[i].item(), d_len[i].item())

            snippets.append(snippet)
            snippets_len.append(snippet_len)
            positions.append(position)

        return q_data, snippets, q_len, snippets_len, positions

    def forward(
            self, q_data, d_data, q_len, d_len, qid_list=None, did_list=None):
        if qid_list is not None and did_list is not None:
            q_data, snippets, q_len, snippets_len, positions = \
                self.forward_cache(
                    q_data, d_data, q_len, d_len, qid_list, did_list)
        else:
            q_data, snippets, q_len, snippets_len, positions = \
                self.forward_normal(
                    q_data, d_data, q_len, d_len)

        if self.out_device:
            q_data = q_data.to(self.out_device)
            snippets = [snippet.to(self.out_device) for snippet in snippets]
            positions = [
                position.to(self.out_device) for position in positions]

        return q_data, snippets, q_len, snippets_len, positions
