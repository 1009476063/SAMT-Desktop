import pretrainedmodels
import torch.nn as nn
import torch

class Resnet18_backbone(nn.Module):
    def __init__(self, in_channels=2):
        super(Resnet18_backbone, self).__init__()
        net = pretrainedmodels.resnet18(num_classes=1000, pretrained=None)
        net.conv1 = nn.Conv2d(in_channels, 64, kernel_size=(7, 7), stride=(2, 2), padding=(3, 3), bias=False)
        self.resnet_layer = nn.Sequential(*list(net.children())[:-2])
        self.amp = nn.AdaptiveAvgPool2d(output_size=1)
        self.dim_reduction = nn.Conv2d(512, 256, kernel_size=1, bias=False)

    def forward(self, x):
        x = self.resnet_layer(x)
        x = self.dim_reduction(x)
        x = self.amp(x)
        x = x.view(x.size(0), -1)
        return x

if __name__ == '__main__':
    # net = Resnet18_backbone(in_channels=2)
    print(pretrainedmodels.model_names)
    print(pretrainedmodels.pretrained_settings['resnet18'])
