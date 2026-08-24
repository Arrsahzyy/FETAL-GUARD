import torch
import torch.nn as nn


class CTGCNNLSTM(nn.Module):
    def __init__(self, n_features=3, cnn_ch=64, lstm_hidden=64):
        super().__init__()
        self.cnn = nn.Sequential(
            nn.Conv1d(n_features, 32, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.Conv1d(32, cnn_ch, kernel_size=3, padding=1),
            nn.ReLU(),
        )
        self.lstm = nn.LSTM(cnn_ch, lstm_hidden, batch_first=True)

        self.fhr_head = nn.Linear(lstm_hidden, 3)
        self.mhr_head = nn.Linear(lstm_hidden, 3)
        self.uc_head = nn.Linear(lstm_hidden, 3)
        self.overall_head = nn.Linear(lstm_hidden, 2)

    def forward(self, x):
        # x: (batch, seq_len, 3) -> conv butuh (batch, channels, seq_len)
        x = x.permute(0, 2, 1)
        feat = self.cnn(x).permute(0, 2, 1)  # (batch, seq_len, cnn_ch)
        _, (h_n, _) = self.lstm(feat)
        h = h_n[-1]  # (batch, lstm_hidden)

        return {
            "fhr": self.fhr_head(h),
            "mhr": self.mhr_head(h),
            "uc": self.uc_head(h),
            "overall": self.overall_head(h),
        }
