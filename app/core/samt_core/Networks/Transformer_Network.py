import torch
import torch.nn as nn
import math
from torch.autograd import Variable

class CNN_cls_head_base(nn.Module):
    def __init__(self, d_model=512, num_classes=2, nhead=4, num_layers=2,
                 dim_feedforward=512, dropout=0, activation='relu'):
        super().__init__()
        self.cnn = nn.Sequential(
            nn.Conv1d(d_model, 256, kernel_size=3, padding=1),
            nn.BatchNorm1d(256), nn.ReLU(inplace=True),
            nn.Conv1d(256, 256, kernel_size=3, padding=1),
            nn.BatchNorm1d(256), nn.ReLU(inplace=True),
            nn.AdaptiveAvgPool1d(1),
        )
        self.mlp_head = nn.Sequential(nn.Flatten(), nn.Dropout(dropout),
                                      nn.Linear(256, num_classes))

    def forward(self, x):
        x = x.permute(0, 2, 1)
        x = self.cnn(x)
        return self.mlp_head(x)
class Trans_cls_head_base(nn.Module):
    def __init__(self, d_model=512, num_classes=2, nhead=4, num_layers=2, dim_feedforward=512,
                 dropout=0, activation='relu'):
        super(Trans_cls_head_base, self).__init__()
        encoder_layer = nn.TransformerEncoderLayer(d_model=d_model, nhead=nhead, dim_feedforward=dim_feedforward,
                                                   dropout=dropout, activation=activation)
        self.transformer = nn.TransformerEncoder(encoder_layer=encoder_layer, num_layers=num_layers, norm=None)
        self.mlp_head = nn.Sequential(nn.LayerNorm(d_model), nn.Linear(d_model, num_classes))
        self.cls_token = nn.Parameter(torch.randn(1, 1, d_model))
        self.pe_sin_cos = PositionalEncoding(d_model, dropout=0, max_len=10)


    def forward(self, x):
        b, n, _ = x.shape
        cls_tokens = self.cls_token.repeat(b, 1, 1)
        x = torch.cat((cls_tokens, x), dim=1)
        x = self.pe_sin_cos(x)
        x = x.permute(1, 0, 2)
        x = self.transformer(x)
        x = x.permute(1, 0, 2)
        x = x[:, 0]

        x = self.mlp_head(x)
        return x
class PositionalEncoding(nn.Module):
    def __init__(self, d_model, dropout, max_len=5000):
        super(PositionalEncoding, self).__init__()
        self.dropout = nn.Dropout(p=dropout)
        pe = torch.zeros(max_len, d_model)
        position = torch.arange(0, max_len).unsqueeze(1)
        div_term = torch.exp(torch.arange(0, d_model, 2) * -(math.log(10000.0) / d_model))
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        pe = pe.unsqueeze(0)
        self.register_buffer('pe', pe)

    def forward(self, x):
        x = x + Variable(self.pe[:, :x.size(1)], requires_grad=False).to(x.device)
        return self.dropout(x)

    def age_encode(self, x, age):
        age_encoding = []
        for b in range(age.size(0)):
            age_encoding.append(Variable(torch.index_select(self.pe, 1, index=age[b]),
                                         requires_grad=False).to(x.device))
        age_encoding = torch.cat(age_encoding, dim=0)
        x = x + age_encoding
        return self.dropout(x)


if __name__ == '__main__':
    print('-------------------------')
