from __future__ import print_function
import torch
import torch.nn as nn
import torch.nn.functional as F


class RankNet(nn.Module):
    def __init__(self, config):
        super().__init__()
        self.config = config
        # S: sentence, L: list, LL: list of list
        self.input_type = 'S'

    def forward(self, q_data, d_data, q_len, d_len):
        return q_data, d_data, q_len, d_len

    def pair_loss(self, x, y):
        x = x.view(-1)
        pos = x[::2]
        neg = x[1::2]
        loss = torch.mean(torch.clamp(1.0 + neg - pos, min=0.))
        return loss
